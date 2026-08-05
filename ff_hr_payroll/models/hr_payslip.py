# -*- coding: utf-8 -*-
from datetime import datetime, timedelta

from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools.safe_eval import safe_eval


class HrPayslip(models.Model):
    """Payroll payslip.

    Generated per employee and period, computed through the salary rules,
    and posted as an automatic accrual journal entry (Dr expense / Cr payable)
    when confirmed.
    """
    _description = "Payslip"
    _name = 'hr.payslip'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_from desc, id desc'
    _check_company_auto = True

    name = fields.Char(
        string="Reference", required=True, tracking=True,
        default=lambda self: _('New'))
    number = fields.Char(string="Number", copy=False, readonly=True)
    employee_id = fields.Many2one(
        'hr.employee', string="Employee", required=True, tracking=True,
        ondelete='restrict', check_company=True)
    contract_id = fields.Many2one(
        'hr.contract', string="Contract", tracking=True, check_company=True,
        ondelete='restrict')
    company_id = fields.Many2one(
        'res.company', string="Company", required=True,
        default=lambda self: self.env.company, tracking=True)
    currency_id = fields.Many2one(
        'res.currency', string="Currency",
        related='company_id.currency_id', readonly=True)

    date_from = fields.Date(string="From", required=True, tracking=True)
    date_to = fields.Date(string="To", required=True, tracking=True)
    date_payment = fields.Date(string="Payment Date", tracking=True)

    struct_id = fields.Many2one(
        'hr.payroll.structure', string="Structure", tracking=True,
        help="Salary structure whose rules are applied to this payslip. "
             "Parent structures' rules are inherited.")
    payslip_run_id = fields.Many2one(
        'hr.payslip.run', string="Payslip Batch", tracking=True, copy=False,
        ondelete='set null')
    structure_type_id = fields.Many2one(
        'hr.payroll.structure.type', string="Salary Structure Type",
        tracking=True)

    state = fields.Selection([
        ('draft', 'Draft'),
        ('verify', 'Waiting'),
        ('done', 'Done'),
        ('cancel', 'Rejected'),
    ], string="Status", default='draft', required=True, tracking=True)

    line_ids = fields.One2many(
        'hr.payslip.line', 'payslip_id', string="Payslip Lines",
        copy=True)
    input_ids = fields.One2many(
        'hr.payslip.input', 'payslip_id', string="Inputs",
        copy=True)
    input_type_ids = fields.Many2many(
        'hr.payslip.input.type', string="Input Types",
        compute='_compute_input_type_ids',
        help="All input types available for this company (advance, loan, fine, ...).")
    worked_days_ids = fields.One2many(
        'hr.payslip.worked.days', 'payslip_id', string="Worked Days",
        copy=True)

    # --- Totals ---
    gross_wage = fields.Float(
        string="Gross Wage", compute='_compute_totals', store=True, digits=(16, 2))
    total_deductions = fields.Float(
        string="Total Deductions", compute='_compute_totals', store=True, digits=(16, 2))
    net_wage = fields.Float(
        string="Net Wage", compute='_compute_totals', store=True, digits=(16, 2),
        help="Net pay = sum of all payslip lines (earnings - deductions).")

    # --- Accounting ---
    move_id = fields.Many2one(
        'account.move', string="Accounting Entry", readonly=True, copy=False,
        ondelete='restrict', index=True)
    move_state = fields.Selection(related='move_id.state', string="Entry Status", readonly=True)

    # ------------------------------------------------------------------
    # Defaults / helpers
    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('hr.payslip') or _('New')
            if not vals.get('contract_id') and vals.get('employee_id'):
                contract = self.env['hr.contract'].search([
                    ('employee_id', '=', vals['employee_id']),
                    ('state', '=', 'open'),
                ], order='date_start desc', limit=1)
                if contract:
                    vals['contract_id'] = contract.id
                    if not vals.get('struct_id'):
                        vals['struct_id'] = contract.struct_id.id
                    if not vals.get('structure_type_id'):
                        vals['structure_type_id'] = contract.structure_type_id.id
            employee = self.env['hr.employee'].browse(vals.get('employee_id'))
            if employee and not vals.get('company_id'):
                vals['company_id'] = employee.company_id.id or self.env.company.id
        return super().create(vals_list)

    @api.onchange('employee_id', 'date_from', 'date_to')
    def _onchange_employee_period(self):
        if self.employee_id and self.date_from and self.date_to and not self.contract_id:
            contract = self.env['hr.contract'].search([
                ('employee_id', '=', self.employee_id.id),
                ('state', '=', 'open'),
                ('date_start', '<=', self.date_to),
            ], order='date_start desc', limit=1)
            if contract:
                self.contract_id = contract.id
                self.struct_id = contract.struct_id.id
                self.structure_type_id = contract.structure_type_id.id

    # ------------------------------------------------------------------
    # Worked days generation (from Attendance + Time Off)
    # ------------------------------------------------------------------
    def _get_work_entry_type(self, code):
        """Find (or create) an hr.work.entry.type by code."""
        wet = self.env['hr.work.entry.type'].search([('code', '=', code)], limit=1)
        if not wet:
            name = {'WORK100': 'Worked Days', 'LEAVE100': 'Paid Leave',
                    'LEAVE90': 'Unpaid Leave', 'ABSENT': 'Absence (No Leave)'}.get(code, code)
            wet = self.env['hr.work.entry.type'].create({
                'name': name, 'code': code, 'is_leave': code.startswith('LEAVE')})
        return wet

    def _get_expected_work_days(self, employee, d_from, d_to):
        """Number of working days in the period according to the employee calendar."""
        calendar = employee.resource_calendar_id
        if not calendar:
            # fall back to a 5-day working week
            days = 0
            day = d_from
            while day <= d_to:
                if day.weekday() < 5:
                    days += 1
                day += timedelta(days=1)
            return days
        attendance_days = {a.dayofweek for a in calendar.attendance_ids}
        days = 0
        day = d_from
        while day <= d_to:
            if str(day.weekday()) in attendance_days:
                days += 1
            day += timedelta(days=1)
        return days

    def action_generate_worked_days(self):
        """Aggregate Attendance and validated Time Off into worked days lines.

        - WORK100: days actually attended (from hr.attendance)
        - LEAVE100: validated paid leave (from hr.leave)
        - LEAVE90:  validated UNPAID leave (approved leave with no balance ->
          deducted one day for one day)
        - ABSENT:    absence WITHOUT an approved leave (unapproved absence) ->
          a separate code so you can build a flexible rule that deducts the
          day as 2 days or more (e.g. -2 * wage/30 * ABSENT).
        """
        for payslip in self:
            vals = []
            if not (payslip.employee_id and payslip.date_from and payslip.date_to):
                payslip.worked_days_ids = [(5, 0, 0)]
                continue
            employee = payslip.employee_id
            d_from = payslip.date_from
            d_to = payslip.date_to

            # --- 1) Attendance days -> WORK100 ---
            start_dt = datetime.combine(d_from, datetime.min.time())
            end_dt = datetime.combine(d_to, datetime.max.time())
            attendances = self.env['hr.attendance'].search([
                ('employee_id', '=', employee.id),
                ('check_in', '>=', start_dt),
                ('check_in', '<=', end_dt),
            ])
            work_days = len({a.check_in.date() for a in attendances})
            work_hours = sum(
                (a.check_out - a.check_in).total_seconds() / 3600.0
                for a in attendances if a.check_out)

            # --- 2) Validated leaves -> LEAVE100 (paid) / LEAVE90 (unpaid) ---
            paid_days = 0.0
            unpaid_days = 0.0
            leaves = self.env['hr.leave'].search([
                ('employee_id', '=', employee.id),
                ('state', 'in', ['validate', 'validate1']),
                ('date_from', '<=', end_dt),
                ('date_to', '>=', start_dt),
            ])
            for leave in leaves:
                # paid/unpaid determined by the leave TYPE (hr.leave.type.unpaid)
                days = leave.number_of_days or 0.0
                if leave.holiday_status_id.unpaid:
                    unpaid_days += days
                else:
                    paid_days += days

            # --- 3) Unapproved absence: expected - attended - paid - unpaid leave ---
            #      -> ABSENT (separate code, NOT LEAVE90) so a flexible rule can
            #         deduct it at 2x, 3x, ... per day.
            expected = self._get_expected_work_days(employee, d_from, d_to)
            absence = max(0, expected - work_days - paid_days - unpaid_days)

            wet_work = self._get_work_entry_type('WORK100')
            wet_leave100 = self._get_work_entry_type('LEAVE100')
            wet_leave90 = self._get_work_entry_type('LEAVE90')
            wet_absent = self._get_work_entry_type('ABSENT')

            if work_days:
                vals.append((0, 0, {
                    'work_entry_type_id': wet_work.id, 'code': 'WORK100',
                    'name': 'Worked Days', 'number_of_days': work_days,
                    'number_of_hours': work_hours,
                }))
            if paid_days:
                vals.append((0, 0, {
                    'work_entry_type_id': wet_leave100.id, 'code': 'LEAVE100',
                    'name': 'Paid Leave', 'number_of_days': paid_days,
                    'number_of_hours': paid_days * 8.0,
                }))
            if unpaid_days:
                vals.append((0, 0, {
                    'work_entry_type_id': wet_leave90.id, 'code': 'LEAVE90',
                    'name': 'Unpaid Leave', 'number_of_days': unpaid_days,
                    'number_of_hours': unpaid_days * 8.0,
                }))
            if absence:
                vals.append((0, 0, {
                    'work_entry_type_id': wet_absent.id, 'code': 'ABSENT',
                    'name': 'Absence (No Leave)', 'number_of_days': absence,
                    'number_of_hours': absence * 8.0,
                }))

            payslip.worked_days_ids = [(5, 0, 0)] + vals
        return True

    @api.depends('company_id')
    def _compute_input_type_ids(self):
        for payslip in self:
            payslip.input_type_ids = self.env['hr.payslip.input.type'].search(
                [('company_id', '=', payslip.company_id.id)])

    @api.depends('line_ids.total')
    def _compute_totals(self):
        for payslip in self:
            gross = 0.0
            deductions = 0.0
            for line in payslip.line_ids:
                # employer (company) contributions are a company cost and do
                # NOT enter the employee's gross / deductions / net.
                if line.category_id and line.category_id.code == 'COMPANY_CONTRIBUTION':
                    continue
                if line.total >= 0:
                    gross += line.total
                else:
                    deductions += line.total
            payslip.gross_wage = gross
            payslip.total_deductions = deductions
            payslip.net_wage = gross + deductions

    # ------------------------------------------------------------------
    # Computation (applies the salary rules)
    # ------------------------------------------------------------------
    def _get_evaluation_context(self):
        """Build the safe_eval context shared by all rules."""
        self.ensure_one()
        result = {}
        # worked_days: code -> number of days (like Odoo core)
        worked_days = {wd.code: wd.number_of_days for wd in self.worked_days_ids}
        # inputs: code -> amount (negative = deduction)
        inputs = {inp.code: inp.amount for inp in self.input_ids}
        categories = {c.code: 0.0 for c in self.env['hr.salary.rule.category'].search([('company_id', '=', self.company_id.id)])}
        return {
            'employee': self.employee_id,
            'contract': self.contract_id,
            'payslip': self,
            'result': result,
            'worked_days': worked_days,
            'inputs': inputs,
            'categories': categories,
            'env': self.env,
        }

    def compute_sheet(self):
        """Apply every applicable salary rule and rebuild the payslip lines.

        Rules come from the payslip structure (with inherited parent rules) or,
        as a fallback, from all company rules. Hierarchical rules (parent with
        children) are aggregated: the parent line shows the sum of its children.
        """
        self.ensure_one()
        if self.state not in ('draft', 'verify'):
            raise UserError(_("Only draft or waiting payslips can be computed."))

        # 1) Select the applicable rules.
        if self.struct_id:
            rules = self.struct_id.get_all_rules()
            # Keep only active company rules.
            rules = rules.filtered(lambda r: r.active and r.company_id.id == self.company_id.id)
        else:
            rules = self.env['hr.salary.rule'].search([
                ('company_id', '=', self.company_id.id),
                ('active', '=', True),
            ], order='sequence, id')
            if self.structure_type_id:
                rules = rules.filtered(
                    lambda r: not r.structure_type_ids or self.structure_type_id in r.structure_type_ids)

        context = self._get_evaluation_context()
        line_vals = []

        def _is_company_contribution(rule):
            return bool(rule.category_id and rule.category_id.code == 'COMPANY_CONTRIBUTION')

        def _acc(rule, amount):
            # employer (company) contributions are a company cost and are NOT
            # part of the employee's taxable / reference result.
            if not _is_company_contribution(rule):
                context['result'][rule.code] = context['result'].get(rule.code, 0.0) + amount

        # 2) Compute the leaf rules (children are aggregated into their parent).
        children_ids = set(rules.child_ids.ids)
        for rule in rules:
            if rule.parent_rule_id:
                # child -> computed by its parent aggregation, but still
                # accumulated into 'result' so other rules can reference it
                if rule._eval_condition(context):
                    amount = rule._compute_rule(context)['amount']
                    _acc(rule, amount)
                continue
            if not rule._eval_condition(context):
                continue
            rule_vals = rule._compute_rule(context)
            amount = rule_vals['amount']
            # aggregate children into this parent rule's amount
            if rule.child_ids:
                for child in rule.child_ids:
                    if child._eval_condition(context):
                        amount += child._compute_rule(context)['amount']
            if not rule.appears_on_payslip:
                _acc(rule, amount)
                continue
            line_vals.append((0, 0, {
                'name': rule.name,
                'salary_rule_id': rule.id,
                'category_id': rule.category_id.id,
                'code': rule.code,
                'amount': amount,
                'quantity': rule_vals['quantity'],
                'rate': rule_vals['rate'],
                'total': amount * rule_vals['quantity'] * rule_vals['rate'] / 100.0,
            }))
            _acc(rule, amount)

        # 3) Add confirmed HR fines (state = done) whose period overlaps the
        #    payslip period as a single deduction line (code FINES).
        fines_total = 0.0
        if self.employee_id:
            fines = self.env['hr.payslip.fine'].search([
                ('employee_id', '=', self.employee_id.id),
                ('company_id', '=', self.company_id.id),
                ('state', '=', 'done'),
            ])
            for fine in fines:
                f_from = fine.date_from or self.date_from
                f_to = fine.date_to or self.date_to
                if f_to >= self.date_from and f_from <= self.date_to:
                    fines_total += fine.amount
        if fines_total:
            deduction_cat = self.env['hr.salary.rule.category'].search([
                ('company_id', '=', self.company_id.id),
                ('code', '=', 'DEDUCTION'),
            ], limit=1)
            line_vals.append((0, 0, {
                'name': _('Fines'),
                'category_id': deduction_cat.id if deduction_cat else False,
                'code': 'FINES',
                'amount': -fines_total,
                'quantity': 1.0,
                'rate': 100.0,
                'total': -fines_total,
            }))
            context['result']['FINES'] = -fines_total

        self.line_ids = [(5, 0, 0)] + line_vals
        return True

    def action_send_email(self):
        """Open the email composer pre-filled with the payslip template and the
        payslip PDF attached (company document layout applies)."""
        self.ensure_one()
        template = self.env.ref('ff_hr_payroll.email_template_hr_payslip')
        return {
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'mail.compose.message',
            'view_id': self.env.ref('mail.email_compose_message_wizard_form').id,
            'target': 'new',
            'context': {
                'default_model': 'hr.payslip',
                'default_res_id': self.id,
                'default_use_template': True,
                'default_template_id': template.id,
                'default_composition_mode': 'comment',
                'force_email': True,
            },
        }

    # ------------------------------------------------------------------
    # State flow
    # ------------------------------------------------------------------
    def action_payslip_done(self):
        """Confirm: compute if needed, then post the accrual journal entry."""
        for payslip in self:
            if not payslip.line_ids:
                payslip.compute_sheet()
            payslip._create_account_move()
            payslip.write({'state': 'done'})

    def action_payslip_cancel(self):
        for payslip in self:
            if payslip.move_id:
                payslip.move_id.button_cancel()
            payslip.write({'state': 'cancel'})

    def action_payslip_draft(self):
        self.write({'state': 'draft'})

    def action_open_move(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Accounting Entry'),
            'res_model': 'account.move',
            'res_id': self.move_id.id,
            'view_mode': 'form',
            'view_id': self.env.ref('account.view_move_form').id,
        }

    # ------------------------------------------------------------------
    # Accounting (automatic accrual posting)
    # ------------------------------------------------------------------
    def _create_account_move(self):
        """Create and post the accrual journal entry (Dr expense / Cr payable).

        Accounting logic (always balanced):
          - Every positive payslip line (earnings) is debited to the salary
            expense account (from the rule's account_debit, or the company
            default).
          - Every negative line (deduction) is credited to its own account
            (the rule's account_credit, or the company payable default).
          - The net difference is credited to the salary payable account
            (the balance owed to the employee).
        """
        self.ensure_one()
        if self.move_id:
            return self.move_id
        company = self.company_id
        journal = company.ff_hr_payroll_journal_id or self.env['account.journal'].search(
            [('company_id', '=', company.id), ('type', '=', 'general')], limit=1)
        if not journal:
            raise UserError(_("No accrual journal configured for company '%s'.", company.name))

        default_debit = company.ff_hr_payroll_expense_account_id
        default_credit = company.ff_hr_payroll_payable_account_id

        def _is_company_contribution(line):
            return bool(line.category_id and line.category_id.code == 'COMPANY_CONTRIBUTION')

        # 1. Total earnings (positive lines, excluding employer contributions)
        #    -> salary expense debit
        earnings = 0.0
        expense_account = False
        for line in self.line_ids:
            if line.total > 0 and not _is_company_contribution(line):
                earnings += line.total
                if not expense_account:
                    expense_account = line.account_debit or default_debit
        if not expense_account:
            raise UserError(_(
                "No salary expense account configured. Set it on the salary rule or in the payroll settings."))
        if earnings == 0.0 and not any(l.total < 0 for l in self.line_ids) \
                and not any(l.total > 0 and _is_company_contribution(l) for l in self.line_ids):
            raise UserError(_("The payslip has no computable amount to post."))

        # 1b. Employer (company) contributions -> Dr expense / Cr its liability
        contribution_pairs = []  # (debit_account_id, credit_account_id, amount)
        for line in self.line_ids:
            if line.total > 0 and _is_company_contribution(line):
                dr_acct = line.account_debit or company.ff_hr_payroll_si_expense_account_id or default_debit
                cr_acct = line.account_credit or default_credit
                if not dr_acct or not cr_acct:
                    raise UserError(_(
                        "Missing debit/credit account for company contribution '%s'. "
                        "Configure it on the rule or in the payroll settings.", line.name))
                contribution_pairs.append((dr_acct.id, cr_acct.id, line.total))

        # 2. Deductions (negative lines) -> credited to their own account
        deduction_lines = []  # (account_id, amount_abs)
        for line in self.line_ids:
            if line.total < 0:
                account = line.account_credit or default_credit
                if not account:
                    raise UserError(_(
                        "No credit account for salary rule '%s'. Configure it on the rule or company.", line.name))
                deduction_lines.append((account.id, abs(line.total)))

        # 3. Net = earnings - deductions -> salary payable
        total_deductions = sum(amt for _, amt in deduction_lines)
        net = earnings - total_deductions
        payable_account = default_credit
        if not payable_account:
            raise UserError(_(
                "No salary payable account configured. Set it in the payroll settings."))

        ref = _('Payslip %s - %s', self.number or self.name, self.employee_id.name)
        partner = self.employee_id.work_contact_id.id or False
        line_vals = [(0, 0, {
            'name': ref, 'account_id': expense_account.id,
            'partner_id': partner, 'debit': earnings, 'credit': 0.0,
        })]
        for account_id, amt in deduction_lines:
            line_vals.append((0, 0, {
                'name': ref, 'account_id': account_id,
                'partner_id': partner, 'debit': 0.0, 'credit': amt,
            }))
        for dr_id, cr_id, amt in contribution_pairs:
            line_vals.append((0, 0, {
                'name': ref, 'account_id': dr_id,
                'partner_id': partner, 'debit': amt, 'credit': 0.0,
            }))
            line_vals.append((0, 0, {
                'name': ref, 'account_id': cr_id,
                'partner_id': partner, 'debit': 0.0, 'credit': amt,
            }))
        if abs(net) > 0.01:
            line_vals.append((0, 0, {
                'name': ref, 'account_id': payable_account.id,
                'partner_id': partner,
                'debit': -net if net < 0 else 0.0,
                'credit': net if net > 0 else 0.0,
            }))

        move = self.env['account.move'].with_company(company.id).create({
            'journal_id': journal.id,
            'date': self.date_to,
            'ref': ref,
            'hr_payslip_id': self.id,
            'line_ids': line_vals,
        })
        # Respect fiscal lock dates: keep draft if locked, else post.
        if company.ff_hr_payroll_auto_post:
            try:
                move.action_post()
            except Exception:
                # locked period: keep as draft, user posts later
                pass
        self.move_id = move.id
        return move
