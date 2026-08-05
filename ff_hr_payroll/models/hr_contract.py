# -*- coding: utf-8 -*-
from datetime import date

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class HrContract(models.Model):
    """Employee contract with payroll settings.

    Mirrors the Enterprise ``hr.contract`` used by the payroll engine.
    """
    _description = "Employee Contract"
    _name = 'hr.contract'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _check_company_auto = True
    _order = 'date_start desc, id desc'

    name = fields.Char(
        string="Contract Reference", required=True, tracking=True,
        default=lambda self: _('New'))
    employee_id = fields.Many2one(
        'hr.employee', string="Employee", required=True, tracking=True,
        ondelete='cascade', check_company=True)
    company_id = fields.Many2one(
        'res.company', string="Company", required=True,
        default=lambda self: self.env.company, tracking=True)
    currency_id = fields.Many2one(
        'res.currency', string="Currency",
        related='company_id.currency_id', readonly=True)
    department_id = fields.Many2one(
        'hr.department', string="Department",
        related='employee_id.department_id', readonly=True)
    job_id = fields.Many2one(
        'hr.job', string="Job Position",
        related='employee_id.job_id', readonly=True)

    # --- Payroll settings ---
    wage = fields.Monetary(
        string="Wage", currency_field='currency_id', tracking=True,
        help="The employee's base wage for the schedule period (e.g. monthly wage).")
    schedule_pay = fields.Selection([
        ('monthly', 'Monthly'),
        ('weekly', 'Weekly'),
        ('biweekly', 'Bi-weekly'),
        ('daily', 'Daily'),
        ('hourly', 'Hourly'),
    ], string="Schedule Pay", default='monthly', required=True, tracking=True,
        help="How often the wage is paid. Determines how the payslip period is prorated.")
    structure_type_id = fields.Many2one(
        'hr.payroll.structure.type', string="Salary Structure Type",
        tracking=True,
        help="Salary structure type (e.g. Employee / Worker) used to select the salary rules.")
    struct_id = fields.Many2one(
        'hr.payroll.structure', string="Salary Structure", tracking=True,
        help="Payroll structure that groups the salary rules applied to this "
             "contract. Its parent structures' rules are inherited.")
    resource_calendar_id = fields.Many2one(
        'resource.calendar', string="Working Schedule",
        check_company=True, tracking=True,
        help="Working hours of the employee. Used to compute worked days / hours.")

    # --- Validity ---
    date_start = fields.Date(
        string="Start Date", required=True, tracking=True,
        default=lambda self: fields.Date.today())
    date_end = fields.Date(
        string="End Date", tracking=True,
        help="Optional end date. Empty = open-ended contract.")

    state = fields.Selection([
        ('draft', 'Draft'),
        ('open', 'Running'),
        ('close', 'Expired'),
        ('cancel', 'Cancelled'),
    ], string="Status", default='draft', required=True, tracking=True)

    # --- History ---
    previous_contract_id = fields.Many2one(
        'hr.contract', string="Previous Contract",
        help="The contract that was active before this one, if any.")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('hr.contract') or _('New')
        return super().create(vals_list)

    @api.constrains('wage')
    def _check_wage(self):
        for contract in self:
            if contract.wage and contract.wage < 0:
                raise ValidationError(_("The wage cannot be negative."))

    @api.constrains('date_start', 'date_end')
    def _check_dates(self):
        for contract in self:
            if contract.date_end and contract.date_end < contract.date_start:
                raise ValidationError(_("The End Date must be on or after the Start Date."))

    @api.constrains('employee_id', 'date_start', 'date_end', 'state')
    def _check_no_overlap(self):
        """One active contract per employee at a time.

        The new contract must not overlap any OTHER running contract of the
        same employee (checked regardless of the new record's own state, so
        it also blocks creating a draft that collides with a running one).
        """
        for contract in self:
            if not contract.date_start:
                continue
            other = self.search([
                ('employee_id', '=', contract.employee_id.id),
                ('id', '!=', contract.id),
                ('state', '=', 'open'),
            ])
            for existing in other:
                existing_start = existing.date_start or date.min
                existing_end = existing.date_end or date.max
                new_start = contract.date_start
                new_end = contract.date_end or date.max
                if new_start <= existing_end and existing_start <= new_end:
                    raise ValidationError(_(
                        "This employee already has a running contract overlapping these dates."))

    # ------------------------------------------------------------------
    # State transitions
    # ------------------------------------------------------------------
    def action_open(self):
        if not self.wage:
            raise UserError(_("Please set the contract wage before opening it."))
        self.write({'state': 'open'})

    def action_view_payslips(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Payslips'),
            'res_model': 'hr.payslip',
            'view_mode': 'list,form',
            'domain': [('contract_id', '=', self.id)],
            'context': {'default_employee_id': self.employee_id.id,
                        'default_contract_id': self.id,
                        'default_company_id': self.company_id.id},
        }

    def action_close(self):
        self.write({'state': 'close'})

    def action_cancel(self):
        self.write({'state': 'cancel'})

    def action_draft(self):
        self.write({'state': 'draft'})

    # ------------------------------------------------------------------
    # Overrides
    # ------------------------------------------------------------------
    def write(self, vals):
        if 'state' in vals and vals['state'] != 'draft' and self.filtered(lambda c: c.state == 'draft'):
            pass
        return super().write(vals)

    def unlink(self):
        for contract in self:
            if contract.state == 'open':
                raise UserError(_("You cannot delete a running contract. Cancel it first."))
        return super().unlink()
