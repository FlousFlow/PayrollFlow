# -*- coding: utf-8 -*-
from odoo import api, fields, models


class HrEmployee(models.Model):
    """Extend employee with payroll helper fields."""
    _inherit = 'hr.employee'

    contract_ids = fields.One2many(
        'hr.contract', 'employee_id', string="Contracts")
    current_contract_id = fields.Many2one(
        'hr.contract', string="Current Contract",
        compute='_compute_current_contract_id', store=True)
    payslip_count = fields.Integer(
        string="Payslip Count", compute='_compute_payslip_count')

    # ---- Sales KPI / commission (confirmed sales of the linked user) ----
    sales_target_percent = fields.Float(
        string="Sales Target (% of wage)", default=100.0,
        help="Monthly sales target expressed as a percentage of the employee "
             "wage. Reaching it unlocks the full wage-linked KPI amount.")
    sales_commission_rate = fields.Float(
        string="Sales Commission (%)",
        help="Commission paid on confirmed sales above the target, as a "
             "percentage of the sales value.")
    sales_currency_id = fields.Many2one(
        'res.currency', string="Sales Currency",
        default=lambda self: self.env.company.currency_id)
    fine_ids = fields.One2many(
        'hr.payslip.fine', 'employee_id', string="Fines")

    @api.depends('contract_ids.state', 'contract_ids.date_start')
    def _compute_current_contract_id(self):
        for employee in self:
            contract = self.env['hr.contract'].search([
                ('employee_id', '=', employee.id),
                ('state', '=', 'open'),
            ], order='date_start desc', limit=1)
            employee.current_contract_id = contract.id

    def _compute_payslip_count(self):
        for employee in self:
            employee.payslip_count = self.env['hr.payslip'].search_count(
                [('employee_id', '=', employee.id)])

    def get_confirmed_sales(self, date_from, date_to):
        """Sum of confirmed sales (``sale.order`` with state ``sale``) linked to
        this employee through its linked user (salesperson) within the period.

        Returns 0.0 when the ``sale`` module is not installed or the employee
        has no linked user — the feature is optional and never blocks payslips.
        """
        self.ensure_one()
        user = self.user_id
        sale_order = self.env.get('sale.order')
        if not user or not sale_order:
            return 0.0
        orders = sale_order.search([
            ('user_id', '=', user.id),
            ('company_id', '=', self.company_id.id or self.env.company.id),
            ('state', '=', 'sale'),
            ('date_order', '>=', date_from),
            ('date_order', '<=', date_to),
        ])
        total = sum(order.amount_total for order in orders)
        return self.currency_id.round(total) if self.currency_id else total

    def action_create_contract(self):
        """Open a new payroll contract form for this employee."""
        self.ensure_one()
        contract = self.env['hr.contract'].create({
            'employee_id': self.id,
            'company_id': self.company_id.id or self.env.company.id,
            'date_start': fields.Date.today(),
            'name': _('New'),
        })
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'hr.contract',
            'res_id': contract.id,
            'view_mode': 'form',
            'target': 'current',
        }
