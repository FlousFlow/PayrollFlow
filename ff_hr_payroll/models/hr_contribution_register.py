# -*- coding: utf-8 -*-
from odoo import _, fields, models


class HrContributionRegister(models.Model):
    """Register of third-party contributions (taxes, insurance, ...).

    Mirrors Odoo Enterprise ``hr.contribution.register``: salary rules can be
    linked to a register so that the amounts owed to third parties (social
    insurance, taxes, unions) are tracked separately.
    """
    _description = "Contribution Register"
    _name = 'hr.contribution.register'
    _order = 'name, id'

    name = fields.Char(string="Name", required=True, translate=True)
    partner_id = fields.Many2one('res.partner', string="Partner")
    company_id = fields.Many2one(
        'res.company', string="Company", required=True,
        default=lambda self: self.env.company)
    note = fields.Text(string="Note")
