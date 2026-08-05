# -*- coding: utf-8 -*-
from odoo import api, fields, models


class HrPayrollStructure(models.Model):
    """Salary structure grouping salary rules, with parent hierarchy.

    Mirrors Odoo Enterprise ``hr.payroll.structure``: a structure holds the
    salary rules applied to a contract / payslip and can inherit rules from
    its parent structure (``get_structure_with_parents`` / ``get_all_rules``).
    """
    _description = "Salary Structure"
    _name = 'hr.payroll.structure'
    _order = 'sequence, id'

    name = fields.Char(string="Name", required=True, translate=True)
    code = fields.Char(string="Code", required=True)
    sequence = fields.Integer(string="Sequence", default=10)
    company_id = fields.Many2one(
        'res.company', string="Company", required=True,
        default=lambda self: self.env.company, ondelete='restrict')
    parent_id = fields.Many2one(
        'hr.payroll.structure', string="Parent", ondelete='cascade',
        check_company=True)
    child_ids = fields.One2many(
        'hr.payroll.structure', 'parent_id', string="Children")
    rule_ids = fields.Many2many(
        'hr.salary.rule', 'hr_payroll_structure_rule_rel',
        'structure_id', 'rule_id', string="Salary Rules")
    note = fields.Text(string="Note")

    def get_structure_with_parents(self):
        """Self plus all ancestors (inheritance chain)."""
        self.ensure_one()
        structures = self
        parent = self.parent_id
        while parent:
            structures |= parent
            parent = parent.parent_id
        return structures

    def get_all_rules(self):
        """All salary rules of this structure and its parents, by sequence.

        Rules are collected from the whole parent chain (children inherit the
        parent structure's rules), then sorted by sequence like Odoo core.
        """
        rules = self.env['hr.salary.rule']
        for structure in self.get_structure_with_parents():
            rules |= structure.rule_ids
        return rules.sorted(key=lambda r: (r.sequence, r.id))

    @api.constrains('parent_id')
    def _check_no_recursion(self):
        for structure in self:
            if structure.parent_id and structure.id in structure.parent_id.get_structure_with_parents().ids:
                raise models.ValidationError(
                    "A salary structure cannot have itself as an ancestor.")
