# -*- coding: utf-8 -*-
from odoo import api, fields, models


class HrPayslipLine(models.Model):
    """One computed line of a payslip (from a salary rule)."""
    _description = "Payslip Line"
    _name = 'hr.payslip.line'

    name = fields.Char(string="Description", required=True)
    payslip_id = fields.Many2one(
        'hr.payslip', string="Payslip", required=True,
        ondelete='cascade', index=True)
    employee_id = fields.Many2one(
        'hr.employee', string="Employee",
        related='payslip_id.employee_id', store=True, index=True)
    salary_rule_id = fields.Many2one(
        'hr.salary.rule', string="Rule", ondelete='restrict')
    category_id = fields.Many2one(
        'hr.salary.rule.category', string="Category")
    code = fields.Char(string="Code")

    amount = fields.Float(string="Amount", digits=(16, 2), default=0.0,
                          help="Computed amount (negative = deduction).")
    quantity = fields.Float(string="Quantity", digits=(16, 2), default=1.0)
    rate = fields.Float(string="Rate (%)", digits=(16, 2), default=100.0)
    total = fields.Float(
        string="Total", digits=(16, 2), compute='_compute_total', store=True,
        help="amount x quantity x rate / 100")

    account_debit = fields.Many2one(
        'account.account', string="Debit Account",
        related='salary_rule_id.account_debit')
    account_credit = fields.Many2one(
        'account.account', string="Credit Account",
        related='salary_rule_id.account_credit')

    @api.depends('amount', 'quantity', 'rate')
    def _compute_total(self):
        for line in self:
            line.total = line.amount * line.quantity * line.rate / 100.0
