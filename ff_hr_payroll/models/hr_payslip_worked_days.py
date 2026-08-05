# -*- coding: utf-8 -*-
from odoo import fields, models


class HrPayslipWorkedDays(models.Model):
    """Worked days / absences of a payslip, aggregated from hr.work.entry."""
    _description = "Payslip Worked Days"
    _name = 'hr.payslip.worked.days'

    payslip_id = fields.Many2one(
        'hr.payslip', string="Payslip", required=True,
        ondelete='cascade', index=True)
    work_entry_type_id = fields.Many2one(
        'hr.work.entry.type', string="Work Entry Type", required=True, ondelete='restrict')
    code = fields.Char(string="Code", related='work_entry_type_id.code', store=True)
    name = fields.Char(string="Description", required=True)
    number_of_days = fields.Float(string="Number of Days", digits=(16, 2), default=0.0)
    number_of_hours = fields.Float(string="Number of Hours", digits=(16, 2), default=0.0)
    amount = fields.Float(string="Amount", digits=(16, 2), default=0.0,
                          help="Computed amount for these days (used by rules via worked_days).")
    rate = fields.Float(string="Rate (%)", digits=(16, 2), default=100.0)
    contract_id = fields.Many2one(
        'hr.contract', string="Contract",
        related='payslip_id.contract_id', store=True)
