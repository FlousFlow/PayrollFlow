# -*- coding: utf-8 -*-
from datetime import date

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class HrContract(models.Model):
    """Employee contract with payroll settings.

    Payroll fields on Odoo 20's native employee version record.
    """
    _inherit = 'hr.version'

    # --- Payroll settings ---
    schedule_pay = fields.Selection([
        ('monthly', 'Monthly'),
        ('weekly', 'Weekly'),
        ('biweekly', 'Bi-weekly'),
        ('daily', 'Daily'),
        ('hourly', 'Hourly'),
    ], string="Schedule Pay", default='monthly', required=True, tracking=True,
        help="How often the wage is paid. Determines how the payslip period is prorated.")
    struct_id = fields.Many2one(
        'hr.payroll.structure', string="Salary Structure", tracking=True,
        help="Payroll structure that groups the salary rules applied to this "
             "contract. Its parent structures' rules are inherited.")
    # Odoo 20 stores employee contract dates on hr.version.
    state = fields.Selection([
        ('draft', 'Draft'),
        ('open', 'Running'),
        ('close', 'Expired'),
        ('cancel', 'Cancelled'),
    ], string="Status", default='draft', required=True, tracking=True)

    # --- History ---
    previous_contract_id = fields.Many2one(
        'hr.version', string="Previous Contract",
        help="The contract that was active before this one, if any.")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name') in (False, _('New')):
                vals['name'] = self.env['ir.sequence'].next_by_code('hr.contract') or _('New')
        return super().create(vals_list)

    @api.constrains('wage')
    def _check_wage(self):
        for contract in self:
            if contract.wage and contract.wage < 0:
                raise ValidationError(_("The wage cannot be negative."))

    @api.constrains('contract_date_start', 'contract_date_end')
    def _check_payroll_dates(self):
        for contract in self:
            if contract.contract_date_end and contract.contract_date_end < contract.contract_date_start:
                raise ValidationError(_("The End Date must be on or after the Start Date."))

    @api.constrains('employee_id', 'contract_date_start', 'contract_date_end', 'state')
    def _check_payroll_no_overlap(self):
        """One active contract per employee at a time.

        The new contract must not overlap any OTHER running contract of the
        same employee (checked regardless of the new record's own state, so
        it also blocks creating a draft that collides with a running one).
        """
        for contract in self:
            if not contract.contract_date_start:
                continue
            other = self.search([
                ('employee_id', '=', contract.employee_id.id),
                ('id', '!=', contract.id),
                ('state', '=', 'open'),
            ])
            for existing in other:
                existing_start = existing.contract_date_start or date.min
                existing_end = existing.contract_date_end or date.max
                new_start = contract.contract_date_start
                new_end = contract.contract_date_end or date.max
                if new_start <= existing_end and existing_start <= new_end:
                    raise ValidationError(_(
                        "This employee already has a running contract overlapping these dates."))

    # ------------------------------------------------------------------
    # State transitions
    # ------------------------------------------------------------------
    def action_open(self):
        if not self.wage:
            raise UserError(_("Please set the contract wage before opening it."))
        for contract in self:
            vals = {'state': 'open'}
            if not contract.contract_date_start:
                vals['contract_date_start'] = fields.Date.today()
            contract.write(vals)

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
        self.write({'state': 'close', 'contract_date_end': fields.Date.today()})

    def action_cancel(self):
        self.write({
            'state': 'cancel',
            'contract_date_start': False,
            'contract_date_end': False,
        })

    def action_draft(self):
        self.write({'state': 'draft', 'contract_date_start': False, 'contract_date_end': False})
