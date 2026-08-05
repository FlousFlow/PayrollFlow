# -*- coding: utf-8 -*-
from odoo import api, fields, models


class HrSalaryRuleCategory(models.Model):
    """Grouping for salary rules (Basic, Allowance, Deduction, ...)."""
    _description = "Salary Rule Category"
    _name = 'hr.salary.rule.category'
    _order = 'sequence, id'

    name = fields.Char(string="Name", required=True, translate=True)
    code = fields.Char(string="Code", required=True,
                       help="Stable code used by the salary rules (e.g. BASIC, DEDUCTION).")
    sequence = fields.Integer(string="Sequence", default=10)
    company_id = fields.Many2one(
        'res.company', string="Company", required=True,
        default=lambda self: self.env.company, ondelete='restrict')
    parent_id = fields.Many2one(
        'hr.salary.rule.category', string="Parent", ondelete='cascade',
        check_company=True)
    child_ids = fields.One2many(
        'hr.salary.rule.category', 'parent_id', string="Children")

    @api.constrains('parent_id')
    def _check_no_recursion(self):
        for category in self:
            if category.parent_id and category.id in category.parent_id._get_parents().ids:
                raise models.ValidationError(
                    "A salary rule category cannot have itself as an ancestor.")

    def _get_parents(self):
        """Self plus all ancestors."""
        self.ensure_one()
        categories = self
        parent = self.parent_id
        while parent:
            categories |= parent
            parent = parent.parent_id
        return categories
