# -*- coding: utf-8 -*-
from odoo import fields, models


class AccountMove(models.Model):
    """Link payslip accrual journal entries to their payslip."""
    _inherit = 'account.move'

    hr_payslip_id = fields.Many2one(
        'hr.payslip', string="Payslip", index=True, ondelete='restrict',
        help="The payslip that created this journal entry, when applicable.")
