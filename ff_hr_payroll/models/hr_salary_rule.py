# -*- coding: utf-8 -*-
import re

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools.safe_eval import safe_eval


class HrSalaryRule(models.Model):
    """Flexible salary rule.

    Each rule computes a payslip line amount through a condition (Python) and
    an amount (fixed / percentage / Python). This allows unlimited deduction
    rules: a rule that deducts one day per absent day, another per hour,
    another a fixed penalty, etc.
    """
    _description = "Salary Rule"
    _name = 'hr.salary.rule'
    _order = 'sequence, id'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _check_company_auto = True

    name = fields.Char(string="Name", required=True, translate=True, tracking=True)
    code = fields.Char(string="Code", required=True, tracking=True,
                       help="Stable code used to reference the rule (e.g. BASIC, ABSENT_DAY, PENALTY).")
    sequence = fields.Integer(string="Sequence", default=10, tracking=True,
                              help="Lower sequences are computed first.")
    category_id = fields.Many2one(
        'hr.salary.rule.category', string="Category", required=True, tracking=True,
        ondelete='restrict', check_company=True,
        help="Groups the line on the payslip (Basic / Allowance / Deduction / ...).")
    company_id = fields.Many2one(
        'res.company', string="Company", required=True,
        default=lambda self: self.env.company, ondelete='restrict', tracking=True)
    active = fields.Boolean(string="Active", default=True)

    # --- Structure / hierarchy (like Enterprise) ---
    structure_ids = fields.Many2many(
        'hr.payroll.structure', 'hr_payroll_structure_rule_rel',
        'rule_id', 'structure_id', string="Salary Structures",
        help="Structures this rule belongs to. A rule is applied when the "
             "payslip structure (or one of its parents) includes it.")
    parent_rule_id = fields.Many2one(
        'hr.salary.rule', string="Parent Rule", index=True, ondelete='cascade',
        help="If set, this rule is a child of the parent rule and its result "
             "is aggregated into the parent rule's payslip line.")
    child_ids = fields.One2many(
        'hr.salary.rule', 'parent_rule_id', string="Child Rules")

    structure_type_ids = fields.Many2many(
        'hr.payroll.structure.type', string="Salary Structure Types",
        help="Legacy structure types this rule applies to. Empty = applies to all.")

    # --- Condition ---
    condition_select = fields.Selection([
        ('always', 'Always True'),
        ('none', 'Always False'),
        ('range', 'Range'),
        ('python', 'Python Expression'),
    ], string="Condition Based On", default='always', required=True, tracking=True)
    condition_python = fields.Text(
        string="Python Condition", tracking=True,
        help="""Python expression evaluated in a context with:
- employee, contract, payslip, result (dict of previously computed line totals)
- worked_days (dict of worked day lines by code)
- inputs (dict of manual inputs by code)
Example: result.get('ABSENT_DAY', 0.0) and contract.wage""")
    condition_range_min = fields.Float(
        string="Min. Wage", digits=(16, 2), tracking=True,
        help="Only applies if the employee's wage is greater than or equal to this amount.")
    condition_range_max = fields.Float(
        string="Max. Wage", digits=(16, 2), tracking=True,
        help="Only applies if the employee's wage is lower than or equal to this amount.")

    # --- Amount ---
    amount_select = fields.Selection([
        ('fixed', 'Fixed Amount'),
        ('percentage', 'Percentage (%)'),
        ('python', 'Python Code'),
    ], string="Amount Type", default='fixed', required=True, tracking=True)
    amount_fixed = fields.Float(string="Fixed Amount", digits=(16, 2), tracking=True,
                                help="Used when Amount Type = Fixed Amount. Negative = deduction.")
    amount_percentage = fields.Float(string="Percentage (%)", digits=(16, 2), tracking=True,
                                     help="Percentage of the Base Amount.")
    amount_percentage_base = fields.Char(
        string="Percentage Based On", tracking=True,
        help="Code of a previous rule/line used as the percentage base. "
             "Empty = the 'BASIC' rule (or the first computed rule).")
    amount_python = fields.Text(
        string="Python Code", tracking=True,
        help="""Python expression returning the line amount.
Available: employee, contract, payslip, result, worked_days, inputs, categories
Example: -1 * contract.wage / 30  (deduct one day of wage per absent day)""")

    # --- Accounting (configurable) ---
    account_debit = fields.Many2one(
        'account.account', string="Debit Account", check_company=True,
        help="Account debited by this rule when it increases the wage (e.g. salary expense).")
    account_credit = fields.Many2one(
        'account.account', string="Credit Account", check_company=True,
        help="Account credited by this rule (e.g. salary payable, tax payable, loan).")

    # --- Registration ---
    appears_on_payslip = fields.Boolean(string="Appears on Payslip", default=True)
    register_id = fields.Many2one(
        'hr.contribution.register', string="Contribution Register",
        help="Third-party contribution register (taxes, insurance, ...).")

    # --- KPI bonus (goals-based, flexible) ---
    is_kpi_bonus = fields.Boolean(
        string="KPI Bonus Rule", default=False,
        help="If enabled, this rule automatically computes the employee's bonus "
             "from his/her KPI goals (target_bonus x completeness). Set amount_select = Fixed "
             "to use it; the amount is ignored and replaced by the KPI bonus total.")
    kpi_bonus_rate = fields.Float(
        string="KPI Bonus Rate (%)", digits=(16, 2), default=100.0,
        help="Percentage of the employee's total KPI bonus paid by this rule "
             "(e.g. 100% = full bonus, 50% = half).")

    # --- Absence rule helper (build a deduction rule from the UI, no Python needed) ---
    is_absence_rule = fields.Boolean(
        string="Absence Rule",
        help="Build an absence deduction rule without writing Python. "
             "Choose the absence type and multiplier; the condition and amount "
             "are generated automatically on save.")
    absence_code = fields.Selection([
        ('ABSENT', 'Absence (No Leave)'),
        ('LEAVE90', 'Unpaid Leave (Approved)'),
    ], string="Absence Type", default='ABSENT')
    absence_multiplier = fields.Float(
        string="Days Multiplier", digits=(16, 2), default=1.0,
        help="How many days to deduct per absent day (1 = one day, 2 = two days, ...).")
    absence_daily_wage = fields.Boolean(
        string="Based on Daily Wage", default=True,
        help="Base = contract.wage / 30. Uncheck to use a fixed amount per day.")
    absence_fixed_amount = fields.Float(
        string="Fixed Amount per Day", digits=(16, 2),
        help="Used when 'Based on Daily Wage' is unchecked.")

    # --- Sales KPI / commission helper (from confirmed sales of the linked user) ---
    is_sales_bonus = fields.Boolean(
        string="Sales Bonus Rule",
        help="Build a sales bonus/commission rule automatically from the "
             "employee's confirmed sales (sale.order state='sale'), monthly "
             "target and commission rate. No Python needed.")
    sales_mode = fields.Selection([
        ('target', 'Target Bonus'),
        ('commission', 'Sales Commission'),
    ], string="Sales Bonus Type", default='target',
        help="Target Bonus: pays wage x target_percent scaled by how much of the "
             "target was reached (full when the target is met).\n"
             "Sales Commission: pays commission_rate% of the confirmed sales "
             "above the target.")

    def _get_sales_vals(self, vals):
        """Return condition/amount vals built from the sales helper fields.

        Pure function (no write) so it can be merged into create/write once.
        """
        mode = vals.get('sales_mode') or 'target'
        # amount_python = exec-style code setting 'result' (result_rate/qty default)
        # Confirmed sales = sum of sale.order (state='sale') of the linked user
        # in the payslip period. Monthly target = wage x sales_target_percent/100.
        if mode == 'commission':
            amount_python = (
                "result = max(0.0, employee.get_confirmed_sales("
                "payslip.date_from, payslip.date_to) - "
                "(contract.wage or 0.0) * (employee.sales_target_percent or 0.0) / 100.0) * "
                "(employee.sales_commission_rate or 0.0) / 100.0"
            )
        else:  # target bonus
            amount_python = (
                "result = min(1.0, employee.get_confirmed_sales("
                "payslip.date_from, payslip.date_to) / "
                "max(1.0, (contract.wage or 0.0) * (employee.sales_target_percent or 0.0) / 100.0)) * "
                "(contract.wage or 0.0) * (employee.sales_target_percent or 0.0) / 100.0"
            )
        return {
            'condition_select': 'always',
            'condition_python': "",
            'amount_select': 'python',
            'amount_python': amount_python,
        }

    def _get_absence_vals(self, vals):
        """Return condition/amount vals built from the absence helper fields.

        Pure function (no write) so it can be merged into create/write once.
        """
        code = vals.get('absence_code') or 'ABSENT'
        mult = vals.get('absence_multiplier') or 1.0
        res = {
            'condition_select': 'python',
            'condition_python': "bool(worked_days.get('%s', 0.0))" % code,
            'amount_select': 'python',
        }
        if vals.get('absence_daily_wage', True):
            res['amount_python'] = "-%s * (contract.wage / 30.0) * worked_days.get('%s', 0.0)" % (mult, code)
        else:
            amount = vals.get('absence_fixed_amount') or 0.0
            res['amount_python'] = "-%s * %s * worked_days.get('%s', 0.0)" % (amount, mult, code)
        return res

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('is_absence_rule'):
                vals.update(self._get_absence_vals(vals))
            if vals.get('is_sales_bonus'):
                vals.update(self._get_sales_vals(vals))
        return super().create(vals_list)

    def write(self, vals):
        # Merge the absence helper values (current + new) and rebuild the
        # condition/amount Python so no separate write is triggered (no recursion).
        if any(f in vals for f in (
                'is_absence_rule', 'absence_code', 'absence_multiplier',
                'absence_daily_wage', 'absence_fixed_amount')):
            for rec in self:
                merged = {f: getattr(rec, f) for f in (
                    'is_absence_rule', 'absence_code', 'absence_multiplier',
                    'absence_daily_wage', 'absence_fixed_amount')}
                merged.update({k: v for k, v in vals.items() if k in merged})
                if merged['is_absence_rule']:
                    vals.update(rec._get_absence_vals(merged))
        # Same merge logic for the sales helper fields.
        if any(f in vals for f in ('is_sales_bonus', 'sales_mode')):
            for rec in self:
                merged = {f: getattr(rec, f) for f in ('is_sales_bonus', 'sales_mode')}
                merged.update({k: v for k, v in vals.items() if k in merged})
                if merged['is_sales_bonus']:
                    vals.update(rec._get_sales_vals(merged))
        return super().write(vals)

    # ------------------------------------------------------------------
    # Constraints
    # ------------------------------------------------------------------
    @api.constrains('code')
    def _check_code(self):
        for rule in self:
            if not rule.code:
                raise ValidationError(_("The salary rule code is required."))
            duplicate = self.search([
                ('code', '=', rule.code),
                ('company_id', '=', rule.company_id.id),
                ('id', '!=', rule.id),
            ])
            if duplicate:
                raise ValidationError(_("A salary rule with code '%s' already exists for this company.", rule.code))

    @api.constrains('condition_select', 'condition_python')
    def _check_condition(self):
        for rule in self:
            if rule.condition_select == 'python' and not rule.condition_python:
                raise ValidationError(_("Please provide the Python condition for this rule."))

    @api.constrains('amount_select')
    def _check_amount(self):
        for rule in self:
            if rule.amount_select == 'fixed' and not rule.amount_fixed:
                pass  # zero is a valid fixed amount (e.g. placeholder)
            if rule.amount_select == 'python' and not rule.amount_python:
                raise ValidationError(_("Please provide the Python code for this rule."))

    # ------------------------------------------------------------------
    # Evaluation
    # ------------------------------------------------------------------
    def _eval_condition(self, context):
        """Whether the rule applies in the given evaluation context."""
        self.ensure_one()
        if self.condition_select == 'always':
            return True
        if self.condition_select == 'none':
            return False
        if self.condition_select == 'range':
            wage = context.get('contract') and context['contract'].wage or 0.0
            if self.condition_range_min and wage < self.condition_range_min:
                return False
            if self.condition_range_max and wage > self.condition_range_max:
                return False
            return True
        # python expression (evaluated with eval mode)
        try:
            return bool(safe_eval(self.condition_python, context, mode='eval'))
        except Exception:
            return False

    def _compute_amount(self, context):
        """Compute the line amount for the rule (may be negative for deductions)."""
        self.ensure_one()
        # KPI bonus rule: compute from the employee's goals automatically.
        if self.is_kpi_bonus:
            employee = context.get('employee')
            if not employee:
                return 0.0
            total_bonus = employee.kpi_bonus_total or 0.0
            rate = self.kpi_bonus_rate or 100.0
            return total_bonus * rate / 100.0
        if self.amount_select == 'fixed':
            return self.amount_fixed
        if self.amount_select == 'percentage':
            base_code = self.amount_percentage_base or 'BASIC'
            base = context['result'].get(base_code, 0.0)
            return base * self.amount_percentage / 100.0
        # python expression (evaluated with eval mode)
        try:
            value = safe_eval(self.amount_python, context, mode='eval')
            return float(value or 0.0)
        except Exception:
            return 0.0

    # ------------------------------------------------------------------
    # _compute_rule — Enterprise-style result / result_rate / result_qty
    # ------------------------------------------------------------------
    def _compute_rule(self, context):
        """Compute the rule and return a dict with 'amount', 'rate', 'quantity'.

        Supports two writing styles in the Python code of the rule:
        * eval style (default, backward compatible): the code is an expression
          that returns the amount directly, e.g. ``contract.wage`` or
          ``inputs.ADVANCE * -1``.
        * exec style (Enterprise-like): the code is a small program that sets
          the ``result`` variable and optionally ``result_rate`` and
          ``result_qty``, e.g.::

              result = max(0, result.get('CONFIRMED_SALES', 0.0) - 10000)
              result_rate = 100.0
              result_qty = 1.0

        The payslip line total is then ``amount * quantity * rate / 100``.
        """
        self.ensure_one()
        result = {'amount': 0.0, 'rate': 100.0, 'quantity': 1.0}
        # KPI bonus rule: computed from the employee's goals automatically.
        if self.is_kpi_bonus:
            employee = context.get('employee')
            total_bonus = employee.kpi_bonus_total if employee else 0.0
            rate = self.kpi_bonus_rate or 100.0
            result['amount'] = total_bonus * rate / 100.0
            return result
        if self.amount_select == 'fixed':
            result['amount'] = self.amount_fixed
            return result
        if self.amount_select == 'percentage':
            base_code = self.amount_percentage_base or 'BASIC'
            base = context['result'].get(base_code, 0.0)
            result['amount'] = base * self.amount_percentage / 100.0
            return result
        if not self.amount_python:
            return result
        # Detect exec style: the code assigns to result / result_rate / result_qty.
        exec_style = bool(re.search(r'\bresult(?:_rate|_qty)?\s*=', self.amount_python))
        if exec_style:
            localdict = dict(context)
            localdict.update({
                'result': 0.0,
                'result_rate': 100.0,
                'result_qty': 1.0,
                # accumulated codes so far (for tax / contribution rules)
                'result_codes': context['result'],
                'company': context.get('payslip') and context['payslip'].company_id,
            })
            try:
                safe_eval(self.amount_python, localdict, mode='exec')
            except Exception:
                # exec failed -> fall back to the amount already accumulated
                localdict['result'] = localdict.get('result', 0.0) or 0.0
            result['amount'] = float(localdict.get('result') or 0.0)
            result['rate'] = float(localdict.get('result_rate') or 100.0)
            result['quantity'] = float(localdict.get('result_qty') or 1.0)
            return result
        # eval style: the code is an expression returning the amount.
        try:
            value = safe_eval(self.amount_python, context, mode='eval')
            result['amount'] = float(value or 0.0)
        except Exception:
            result['amount'] = 0.0
        return result
