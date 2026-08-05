# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class HrPayslipFine(models.Model):
    """HR fine / penalty recorded against an employee and deducted from payslips.

    A fine is linked to the payslip period (date_from / date_to) so that only
    the fines whose period overlaps the computed payslip are deducted. Fines in
    state 'done' are automatically added as a deduction line (code FINES) when
    the payslip is computed.
    """
    _name = 'hr.payslip.fine'
    _description = "HR Fine / Penalty"
    _order = 'date desc, id desc'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _check_company_auto = True

    name = fields.Char(string="Reference", required=True, tracking=True,
                       default=lambda self: _('New'))
    employee_id = fields.Many2one(
        'hr.employee', string="Employee", required=True,
        ondelete='restrict', tracking=True, index=True)
    company_id = fields.Many2one(
        'res.company', string="Company", required=True,
        default=lambda self: self.env.company)
    currency_id = fields.Many2one(
        'res.currency', string="Currency",
        related='company_id.currency_id', readonly=True)
    date = fields.Date(string="Date", required=True,
                       default=fields.Date.context_today, tracking=True)
    date_from = fields.Date(
        string="Period From", tracking=True,
        help="Start of the payslip period this fine belongs to. Used to match "
             "the fine to a payslip.")
    date_to = fields.Date(
        string="Period To", tracking=True,
        help="End of the payslip period this fine belongs to.")
    amount = fields.Monetary(
        string="Amount", required=True, tracking=True,
        currency_field='currency_id',
        help="Amount deducted from the payslip. Enter a positive number; it is "
             "deducted automatically.")
    reason = fields.Text(string="Reason", tracking=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('done', 'Done'),
        ('cancelled', 'Cancelled'),
    ], string="Status", default='draft', tracking=True, required=True)

    _name_uniq = models.Constraint(
        'unique (name, company_id)',
        'A fine with the same reference already exists for this company.',
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'hr.payslip.fine') or _('New')
        return super().create(vals_list)

    def action_done(self):
        for rec in self:
            if rec.state != 'draft':
                raise UserError(_("Only draft fines can be confirmed."))
            if rec.amount <= 0:
                raise UserError(_("The fine amount must be greater than zero."))
        self.write({'state': 'done'})

    def action_draft(self):
        self.write({'state': 'draft'})

    def action_cancel(self):
        self.write({'state': 'cancelled'})
