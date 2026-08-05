# -*- coding: utf-8 -*-
from odoo import fields, models


class HrPayslipInputType(models.Model):
    """Type of manual payslip input (Advance, Loan, Fine, ...)."""
    _description = "Payslip Input Type"
    _name = 'hr.payslip.input.type'
    _order = 'sequence, id'

    name = fields.Char(string="Name", required=True, translate=True)
    code = fields.Char(string="Code", required=True,
                       help="Stable code referenced by salary rules (e.g. INPUT.ADVANCE).")
    sequence = fields.Integer(string="Sequence", default=10)
    company_id = fields.Many2one(
        'res.company', string="Company", required=True,
        default=lambda self: self.env.company, ondelete='restrict')


class HrPayslipInput(models.Model):
    """Manual input entered per payslip (advance, loan, fine, ...).

    Amounts are usually negative (deductions) and are referenced by salary
    rules through their input type code.
    """
    _description = "Payslip Input"
    _name = 'hr.payslip.input'

    payslip_id = fields.Many2one(
        'hr.payslip', string="Payslip", required=True,
        ondelete='cascade', index=True)
    input_type_id = fields.Many2one(
        'hr.payslip.input.type', string="Input Type", required=True, ondelete='restrict')
    name = fields.Char(string="Description", required=True)
    code = fields.Char(string="Code", related='input_type_id.code', store=True)
    amount = fields.Float(string="Amount", digits=(16, 2), default=0.0,
                          help="Negative = deduction (e.g. -100 for an advance repayment).")
