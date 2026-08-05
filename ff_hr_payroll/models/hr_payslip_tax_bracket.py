# -*- coding: utf-8 -*-
from odoo import api, fields, models


class HrPayslipTaxBracket(models.Model):
    """Income tax bracket (annual amounts) used by the payroll income tax rule.

    Brackets are configured per company and fully editable from the company /
    settings screen because tax legislation changes over time.
    """
    _name = 'hr.payslip.tax.bracket'
    _description = "Income Tax Bracket (annual)"
    _order = 'sequence, amount_from'

    company_id = fields.Many2one(
        'res.company', string="Company", required=True, ondelete='cascade')
    sequence = fields.Integer(string="Sequence", default=10)
    amount_from = fields.Monetary(
        string="From (annual)", currency_field='currency_id', required=True,
        help="Lower bound of the annual taxable amount for this bracket.")
    amount_to = fields.Monetary(
        string="To (annual)", currency_field='currency_id',
        help="Upper bound of the annual taxable amount. Leave empty for the "
             "last (unlimited) bracket.")
    rate = fields.Float(
        string="Rate (%)", required=True,
        help="Tax rate applied to the part of the annual income inside this "
             "bracket (progressive).")
    currency_id = fields.Many2one(
        'res.currency', string="Currency",
        related='company_id.currency_id', readonly=True)

    _rate_positive = models.Constraint(
        'check (rate >= 0)',
        'The tax rate must be positive.',
    )
