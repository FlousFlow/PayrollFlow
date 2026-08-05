# -*- coding: utf-8 -*-
from odoo import _, api, fields, models


class ResCompany(models.Model):
    """Configurable payroll defaults per company."""
    _inherit = 'res.company'

    ff_hr_payroll_journal_id = fields.Many2one(
        'account.journal', string="Payroll Journal", check_company=True,
        domain="[('type', '=', 'general'), ('company_id', '=', id)]",
        help="Journal used to post the payslip accrual entries.")
    ff_hr_payroll_expense_account_id = fields.Many2one(
        'account.account', string="Salary Expense Account", check_company=True,
        domain="[('account_type', 'in', ('expense', 'expense_other', 'expense_direct_cost')), ('company_ids', 'in', company_ids)]",
        help="Default debit account for the salary expense (fallback when a rule has no debit account).")
    ff_hr_payroll_payable_account_id = fields.Many2one(
        'account.account', string="Salary Payable Account", check_company=True,
        domain="[('account_type', 'in', ('liability_payable', 'liability_current')), ('company_ids', 'in', company_ids)]",
        help="Default credit account for the salary payable (fallback when a rule has no credit account).")
    ff_hr_payroll_auto_post = fields.Boolean(
        string="Auto Post Payroll Entries", default=True,
        help="Post the payslip journal entries automatically. Uncheck to keep them in draft for review.")

    # ------------------------------------------------------------------
    # Payroll taxes (Egyptian: social insurance + income tax)
    # Gated by a master toggle + country; fully configurable per company.
    # ------------------------------------------------------------------
    ff_hr_payroll_apply_taxes = fields.Boolean(
        string="Apply Payroll Taxes", default=False, tracking=True,
        help="Master switch for payroll tax deductions (social insurance and "
             "income tax). Enabled by default when the company country has "
             "payroll taxes (e.g. Egypt); can be turned off at any time.")
    ff_hr_payroll_si_enabled = fields.Boolean(
        string="Social Insurance", default=False,
        help="Deduct the employee social insurance share (and post the "
             "employer share as a company expense).")
    ff_hr_payroll_si_employee_rate = fields.Float(
        string="Employee SI Rate (%)", default=11.0,
        help="Employee share of the social insurance, as a percentage of the "
             "insurable base.")
    ff_hr_payroll_si_employer_rate = fields.Float(
        string="Employer SI Rate (%)", default=18.75,
        help="Employer share of the social insurance (company expense), as a "
             "percentage of the insurable base.")
    ff_hr_payroll_si_max_insurable = fields.Monetary(
        string="Max Insurable Salary", currency_field='currency_id',
        help="Upper cap of the monthly insurable base. Leave empty for no cap.")
    ff_hr_payroll_si_min_insurable = fields.Monetary(
        string="Min Insurable Salary", currency_field='currency_id',
        help="Lower bound of the monthly insurable base. Leave empty for no floor.")
    ff_hr_payroll_si_payable_account_id = fields.Many2one(
        'account.account', string="Social Insurance Payable Account",
        check_company=True,
        domain="[('account_type', 'in', ('liability_payable', 'liability_current')), ('company_ids', 'in', company_ids)]",
        help="Account credited with the social insurance amounts (employee + "
             "employer shares) until paid to the authority.")
    ff_hr_payroll_si_expense_account_id = fields.Many2one(
        'account.account', string="Social Insurance Expense Account",
        check_company=True,
        domain="[('account_type', 'in', ('expense', 'expense_other', 'expense_direct_cost')), ('company_ids', 'in', company_ids)]",
        help="Account debited with the employer social insurance share.")
    ff_hr_payroll_income_tax_enabled = fields.Boolean(
        string="Income Tax (Salary Tax)", default=False,
        help="Deduct the employee income tax on salaries using the configured "
             "annual brackets.")
    ff_hr_payroll_income_tax_exemption = fields.Monetary(
        string="Annual Tax Exemption", currency_field='currency_id', default=15000.0,
        help="Annual amount exempt from income tax (first bracket threshold).")
    ff_hr_payroll_income_tax_payable_account_id = fields.Many2one(
        'account.account', string="Income Tax Payable Account",
        check_company=True,
        domain="[('account_type', 'in', ('liability_payable', 'liability_current')), ('company_ids', 'in', company_ids)]",
        help="Account credited with the deducted income tax until remitted to "
             "the tax authority.")
    ff_hr_payroll_income_tax_bracket_ids = fields.One2many(
        'hr.payslip.tax.bracket', 'company_id',
        string="Income Tax Brackets (annual)",
        help="Progressive income tax brackets on the ANNUAL taxable amount.")

    @api.model_create_multi
    def create(self, vals_list):
        companies = super().create(vals_list)
        for company in companies:
            if company.partner_id.country_id and company.partner_id.country_id.code == 'EG':
                company.write({'ff_hr_payroll_apply_taxes': True})
            company._sync_ff_hr_payroll_tax_rules()
        return companies

    def write(self, vals):
        res = super().write(vals)
        tax_fields = {
            'ff_hr_payroll_apply_taxes', 'ff_hr_payroll_si_enabled',
            'ff_hr_payroll_income_tax_enabled',
            'ff_hr_payroll_si_employee_rate', 'ff_hr_payroll_si_employer_rate',
            'ff_hr_payroll_si_max_insurable', 'ff_hr_payroll_si_min_insurable',
            'ff_hr_payroll_income_tax_exemption',
            'ff_hr_payroll_si_payable_account_id',
            'ff_hr_payroll_si_expense_account_id',
            'ff_hr_payroll_income_tax_payable_account_id',
        }
        if tax_fields & set(vals):
            for company in self:
                company._sync_ff_hr_payroll_tax_rules()
        return res

    def _ensure_default_eg_brackets(self):
        """Load editable default Egyptian income tax brackets when the company
        is Egyptian and has no brackets yet."""
        self.ensure_one()
        if self.ff_hr_payroll_income_tax_bracket_ids:
            return
        country = self.partner_id.country_id
        if not country or country.code != 'EG':
            return
        defaults = [
            (0.0, 15000.0, 0.0),
            (15000.0, 30000.0, 10.0),
            (30000.0, 45000.0, 15.0),
            (45000.0, 60000.0, 20.0),
            (60000.0, 200000.0, 22.5),
            (200000.0, 400000.0, 25.0),
            (400000.0, 600000.0, 27.5),
            (600000.0, 0.0, 30.0),
        ]
        for seq, (frm, to, rate) in enumerate(defaults, 1):
            self.env['hr.payslip.tax.bracket'].create({
                'company_id': self.id, 'sequence': seq,
                'amount_from': frm, 'amount_to': to or False, 'rate': rate,
            })

    def _sync_ff_hr_payroll_tax_rules(self):
        """Create/refresh the payroll tax deduction rules from the company
        configuration. The rules stay in place but only apply while the
        corresponding toggles are enabled (checked in their condition)."""
        self.ensure_one()
        env = self.env
        structure = env['hr.payroll.structure'].search(
            [('company_id', '=', self.id)])
        struct_ids = [(6, 0, structure.ids)] if structure else []
        cat_ded = env['hr.salary.rule.category'].search([
            ('company_id', '=', self.id), ('code', '=', 'DEDUCTION')], limit=1)
        cat_contrib = env['hr.salary.rule.category'].search([
            ('company_id', '=', self.id), ('code', '=', 'COMPANY_CONTRIBUTION')], limit=1)
        if not cat_ded:
            cat_ded = env['hr.salary.rule.category'].create({
                'name': 'Deduction', 'code': 'DEDUCTION', 'company_id': self.id})
        if not cat_contrib:
            cat_contrib = env['hr.salary.rule.category'].create({
                'name': 'Company Contribution', 'code': 'COMPANY_CONTRIBUTION',
                'company_id': self.id})

        if self.ff_hr_payroll_income_tax_enabled:
            self._ensure_default_eg_brackets()

        def _upsert(code, name, cat, condition, amount, appears, acct_dr, acct_cr, sequence=100):
            rule = env['hr.salary.rule'].search([
                ('company_id', '=', self.id), ('code', '=', code)], limit=1)
            vals = {
                'name': name, 'code': code, 'category_id': cat.id,
                'company_id': self.id, 'sequence': sequence,
                'condition_select': 'python', 'condition_python': condition,
                'amount_select': 'python', 'amount_python': amount,
                'appears_on_payslip': appears,
                'account_debit': acct_dr, 'account_credit': acct_cr,
                'structure_ids': struct_ids,
            }
            if rule:
                rule.write(vals)
            else:
                env['hr.salary.rule'].create(vals)

        ins_base_code = (
            "gross = sum(v for v in result_codes.values() if v and v > 0)\n"
            "cap = company.ff_hr_payroll_si_max_insurable or 0.0\n"
            "base = min(gross, cap) if cap else gross\n"
        )
        # 1) Social insurance - employee share (deduction)
        _upsert(
            'SI_EMP', 'Social Insurance (Employee)',
            cat_ded,
            "bool(payslip.company_id.ff_hr_payroll_apply_taxes and "
            "payslip.company_id.ff_hr_payroll_si_enabled)",
            ins_base_code + "result = -(base * (company.ff_hr_payroll_si_employee_rate or 0.0) / 100.0)",
            True, False, self.ff_hr_payroll_si_payable_account_id.id, 90)
        # 2) Social insurance - employer share (company contribution)
        _upsert(
            'SI_COMP', 'Social Insurance (Employer)',
            cat_contrib,
            "bool(payslip.company_id.ff_hr_payroll_apply_taxes and "
            "payslip.company_id.ff_hr_payroll_si_enabled)",
            ins_base_code + "result = base * (company.ff_hr_payroll_si_employer_rate or 0.0) / 100.0",
            True,
            self.ff_hr_payroll_si_expense_account_id.id,
            self.ff_hr_payroll_si_payable_account_id.id, 91)
        # 3) Income tax (salary tax) - deduction
        tax_code = (
            "gross = sum(v for v in result_codes.values() if v and v > 0)\n"
            "si_emp = abs(result_codes.get('SI_EMP', 0.0) or 0.0)\n"
            "monthly = max(0.0, gross - si_emp)\n"
            "annual = max(0.0, monthly * 12.0 - (company.ff_hr_payroll_income_tax_exemption or 0.0))\n"
            "tax = 0.0\n"
            "for b in company.ff_hr_payroll_income_tax_bracket_ids:\n"
            "    upper = b.amount_to if b.amount_to else 10**15\n"
            "    if annual > (b.amount_from or 0.0):\n"
            "        seg = min(annual, upper) - (b.amount_from or 0.0)\n"
            "        if seg > 0:\n"
            "            tax += seg * (b.rate or 0.0) / 100.0\n"
            "result = -(tax / 12.0)\n"
        )
        _upsert(
            'INCOME_TAX', 'Income Tax (Salary Tax)',
            cat_ded,
            "bool(payslip.company_id.ff_hr_payroll_apply_taxes and "
            "payslip.company_id.ff_hr_payroll_income_tax_enabled)",
            tax_code,
            True, False, self.ff_hr_payroll_income_tax_payable_account_id.id, 100)

