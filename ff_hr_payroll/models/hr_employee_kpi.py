# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class GamificationGoal(models.Model):
    """Extend the native Odoo goal with payroll KPI settings.

    The native ``gamification.goal`` already computes ``completeness``
    (0-100%). We add an optional bonus amount so payroll can reward goal
    achievement: bonus = target_bonus * completeness / 100.
    """
    _inherit = 'gamification.goal'

    target_bonus = fields.Monetary(
        string="Target Bonus", currency_field='company_currency_id',
        help="Bonus amount paid when the goal reaches 100%. Paid proportionally to completeness.")
    company_currency_id = fields.Many2one(
        'res.currency', string="Company Currency",
        related='user_id.company_id.currency_id', readonly=True)
    is_kpi = fields.Boolean(
        string="Is KPI", default=False,
        help="Mark goals that participate in the payroll KPI bonus.")
    kpi_weight = fields.Float(
        string="KPI Weight (%)", default=100.0,
        help="Weight of this goal in the overall KPI bonus (defaults to 100%).")

    @api.depends('target_bonus', 'completeness', 'kpi_weight')
    def _compute_kpi_bonus(self):
        for goal in self:
            goal.kpi_bonus = (goal.target_bonus or 0.0) * (goal.completeness or 0.0) / 100.0

    kpi_bonus = fields.Monetary(
        string="KPI Bonus", currency_field='company_currency_id',
        compute='_compute_kpi_bonus', store=True,
        help="Bonus earned = target bonus x completeness %.")


class HrEmployee(models.Model):
    """Expose the employee's KPI goals for the payroll bonus."""
    _inherit = 'hr.employee'

    company_currency_id = fields.Many2one(
        'res.currency', string="Company Currency",
        related='company_id.currency_id', readonly=True)
    kpi_goal_ids = fields.Many2many(
        'gamification.goal', string="KPI Goals",
        compute='_compute_kpi_goal_ids',
        help="The employee's goals that participate in the payroll KPI bonus.")
    kpi_bonus_total = fields.Monetary(
        string="Total KPI Bonus", currency_field='company_currency_id',
        compute='_compute_kpi_bonus_total',
        help="Sum of the bonuses of all KPI goals, weighted.")

    @api.depends('user_id')
    def _compute_kpi_goal_ids(self):
        for employee in self:
            goals = self.env['gamification.goal'].search([
                ('user_id', '=', employee.user_id.id),
                ('is_kpi', '=', True),
            ])
            employee.kpi_goal_ids = goals

    @api.depends('user_id')
    def _compute_kpi_bonus_total(self):
        for employee in self:
            goals = self.env['gamification.goal'].search([
                ('user_id', '=', employee.user_id.id),
                ('is_kpi', '=', True),
            ])
            total = 0.0
            for goal in goals:
                weight = goal.kpi_weight or 100.0
                total += (goal.kpi_bonus or 0.0) * weight / 100.0
            employee.kpi_bonus_total = total

    def action_create_kpi_goal(self):
        """Create a new KPI goal for this employee and open it for editing.

        Lets the user add a goals-based bonus right from the employee form,
        without leaving the Payroll app.
        """
        self.ensure_one()
        if not self.user_id:
            raise UserError(
                _("This employee has no linked user. Set a user on the employee "
                  "to create KPI goals (goals are stored per user)."))
        definition = self.env['gamification.goal.definition'].search([
            ('name', '=', 'KPI Goal'),
            ('computation_mode', '=', 'manually'),
        ], limit=1)
        if not definition:
            definition = self.env['gamification.goal.definition'].create({
                'name': 'KPI Goal', 'computation_mode': 'manually',
                'display_mode': 'progress', 'domain': '[]', 'condition': 'higher',
            })
        goal = self.env['gamification.goal'].create({
            'definition_id': definition.id,
            'user_id': self.user_id.id,
            'target_goal': 100.0,
            'current': 0.0,
            'is_kpi': True,
            'kpi_weight': 100.0,
            'target_bonus': 0.0,
        })
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'gamification.goal',
            'res_id': goal.id,
            'view_mode': 'form',
            'target': 'current',
        }
