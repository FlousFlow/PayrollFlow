# -*- coding: utf-8 -*-
from odoo import _, api, fields, models


class HrPayslipRun(models.Model):
    """Payslip batch: generate payslips for many employees at once.

    Mirrors Odoo Enterprise ``hr.payslip.run``: define a period and a set of
    employees, then generate one draft payslip per employee with an open
    contract in the period.
    """
    _description = "Payslip Batches"
    _name = 'hr.payslip.run'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_start desc, id desc'
    _check_company_auto = True

    name = fields.Char(
        string="Reference", required=True, tracking=True,
        default=lambda self: _('New'))
    date_start = fields.Date(string="Date From", required=True, tracking=True)
    date_end = fields.Date(string="Date To", required=True, tracking=True)
    struct_id = fields.Many2one(
        'hr.payroll.structure', string="Structure", tracking=True)
    company_id = fields.Many2one(
        'res.company', string="Company", required=True,
        default=lambda self: self.env.company, tracking=True)
    employee_ids = fields.Many2many(
        'hr.employee', string="Employees", tracking=True)
    payslip_ids = fields.One2many(
        'hr.payslip', 'payslip_run_id', string="Payslips", readonly=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('done', 'Done'),
    ], string="Status", default='draft', required=True, tracking=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('hr.payslip.run') or _('New')
        return super().create(vals_list)

    def action_generate_payslips(self):
        """Generate one draft payslip per selected employee with an open contract."""
        for run in self:
            payslips = self.env['hr.payslip']
            for employee in run.employee_ids:
                contract = self.env['hr.contract'].search([
                    ('employee_id', '=', employee.id),
                    ('state', '=', 'open'),
                    ('date_start', '<=', run.date_end),
                ], order='date_start desc', limit=1)
                if not contract:
                    continue
                payslips |= self.env['hr.payslip'].create({
                    'employee_id': employee.id,
                    'contract_id': contract.id,
                    'company_id': run.company_id.id,
                    'date_from': run.date_start,
                    'date_to': run.date_end,
                    'struct_id': run.struct_id.id or contract.struct_id.id,
                    'payslip_run_id': run.id,
                })
            run.payslip_ids = payslips
        return True

    def action_draft(self):
        self.write({'state': 'draft'})

    def action_done(self):
        self.write({'state': 'done'})
