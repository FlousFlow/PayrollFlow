# -*- coding: utf-8 -*-
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    """Expose payroll company settings in the HR/Accounting settings."""
    _inherit = 'res.config.settings'

    ff_hr_payroll_journal_id = fields.Many2one(
        'account.journal', string="Payroll Journal",
        related='company_id.ff_hr_payroll_journal_id', readonly=False,
        domain="[('type', '=', 'general'), ('company_id', '=', company_id)]")
    ff_hr_payroll_expense_account_id = fields.Many2one(
        'account.account', string="Salary Expense Account",
        related='company_id.ff_hr_payroll_expense_account_id', readonly=False)
    ff_hr_payroll_payable_account_id = fields.Many2one(
        'account.account', string="Salary Payable Account",
        related='company_id.ff_hr_payroll_payable_account_id', readonly=False)
    ff_hr_payroll_auto_post = fields.Boolean(
        string="Auto Post Payroll Entries",
        related='company_id.ff_hr_payroll_auto_post', readonly=False)

    # --- Payroll taxes (Egyptian) ---
    ff_hr_payroll_apply_taxes = fields.Boolean(
        string="Apply Payroll Taxes",
        related='company_id.ff_hr_payroll_apply_taxes', readonly=False)
    ff_hr_payroll_si_enabled = fields.Boolean(
        string="Social Insurance",
        related='company_id.ff_hr_payroll_si_enabled', readonly=False)
    ff_hr_payroll_si_employee_rate = fields.Float(
        string="Employee SI Rate (%)",
        related='company_id.ff_hr_payroll_si_employee_rate', readonly=False)
    ff_hr_payroll_si_employer_rate = fields.Float(
        string="Employer SI Rate (%)",
        related='company_id.ff_hr_payroll_si_employer_rate', readonly=False)
    ff_hr_payroll_si_max_insurable = fields.Monetary(
        string="Max Insurable Salary",
        related='company_id.ff_hr_payroll_si_max_insurable', readonly=False)
    ff_hr_payroll_si_min_insurable = fields.Monetary(
        string="Min Insurable Salary",
        related='company_id.ff_hr_payroll_si_min_insurable', readonly=False)
    ff_hr_payroll_si_payable_account_id = fields.Many2one(
        'account.account', string="Social Insurance Payable Account",
        related='company_id.ff_hr_payroll_si_payable_account_id', readonly=False)
    ff_hr_payroll_si_expense_account_id = fields.Many2one(
        'account.account', string="Social Insurance Expense Account",
        related='company_id.ff_hr_payroll_si_expense_account_id', readonly=False)
    ff_hr_payroll_income_tax_enabled = fields.Boolean(
        string="Income Tax (Salary Tax)",
        related='company_id.ff_hr_payroll_income_tax_enabled', readonly=False)
    ff_hr_payroll_income_tax_exemption = fields.Monetary(
        string="Annual Tax Exemption",
        related='company_id.ff_hr_payroll_income_tax_exemption', readonly=False)
    ff_hr_payroll_income_tax_payable_account_id = fields.Many2one(
        'account.account', string="Income Tax Payable Account",
        related='company_id.ff_hr_payroll_income_tax_payable_account_id', readonly=False)
    ff_hr_payroll_income_tax_bracket_ids = fields.One2many(
        'hr.payslip.tax.bracket', 'company_id',
        related='company_id.ff_hr_payroll_income_tax_bracket_ids', readonly=False)
