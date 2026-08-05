# -*- coding: utf-8 -*-
{
    'name': 'Flous Flow HR Payroll',
    'version': '19.0.1.0.0',
    'category': 'Human Resources/Payroll',
    'summary': 'Flexible payroll engine for Odoo 19 Community: contracts, salary rules, payslips, configurable deductions and automatic accrual posting',
    'description': """
Flous Flow HR Payroll
=====================

A full payroll engine for **Odoo 19 Community** (``hr_payroll`` is
Enterprise-only). It mirrors the standard Odoo payroll architecture so the data
model, workflow and accounting behaviour match what you already know from the
Enterprise app, without requiring the paid module. Built for Egyptian
companies, with the Egyptian payroll taxes (social insurance + income tax) and
the company document layout included.

Main features
-------------

* Employee Contracts (``hr.contract``) with wage, schedule, dates and salary structure.
* Flexible Salary Rules (``hr.salary.rule``): condition + amount (fixed / percentage / Python).
* Unlimited deduction rules built from the UI (absence, penalties, ...).
* Enterprise-style Python rules with ``result`` / ``result_rate`` / ``result_qty``.
* Hierarchical salary rules (a parent aggregates its children).
* Salary Structures (``hr.payroll.structure``) with parent inheritance.
* Payslips with computed lines, manual inputs (advances, loans, fines) and worked days.
* Payslip Batches (``hr.payslip.run``): one payslip per employee with an open contract.
* Automatic accrual posting (Dr salary expense / Cr salary payable), fiscal-lock aware.
* Attendance / Time Off integration: paid leave (no deduction), unpaid leave (one day), absence (separate code, deduct 2x / 3x ...).
* Flexible KPI bonuses through the native Gamification app.
* Sales KPI / commission read from the linked user's confirmed sale orders.
* HR Fines: record penalties and deduct them automatically.
* Egyptian payroll taxes (country-dependent, toggleable): social insurance (employee + employer) and income tax with editable annual brackets.
* Payslip Register: aggregate report (PDF + Excel) for a period.
* Payslip PDF with the company document layout + one-click Send by Email.
* Multi-company, configurable accounts, audit trail (chatter), Arabic + English translations.

Requirements
------------

Odoo 19 Community. Depends on ``hr``, ``hr_work_entry``, ``hr_attendance``,
``hr_holidays``, ``hr_gamification``, ``account`` and ``mail``. The sales KPI
feature optionally reads ``sale.order`` if the ``sale`` module is installed.
""",
    'author': 'Flous Flow / Mohamed Gamal',
    'website': 'https://flousflow.com',
    'license': 'LGPL-3',
    'depends': [
        'hr',
        'hr_work_entry',
        'hr_attendance',
        'hr_holidays',
        'hr_gamification',
        'account',
        'mail',
    ],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'data/salary_rule_categories.xml',
        'data/hr_payslip_fine_data.xml',
        'views/hr_contract_views.xml',
        'views/hr_payroll_structure_views.xml',
        'views/hr_salary_rule_category_views.xml',
        'views/hr_salary_rule_views.xml',
        'views/hr_payslip_views.xml',
        'views/hr_payslip_run_views.xml',
        'views/hr_payslip_fine_views.xml',
        'views/hr_payslip_register_wizard_views.xml',
        'views/hr_employee_views.xml',
        'views/res_config_settings_views.xml',
        'views/menus.xml',
        'reports/hr_payslip_reports.xml',
        'reports/hr_payslip_register_reports.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}
