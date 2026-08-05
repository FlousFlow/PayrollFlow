# PayrollFlow

PayrollFlow is an Odoo 19 **Community** payroll module (the native `hr_payroll` app is Enterprise-only). It mirrors the standard Odoo payroll architecture so the data model, workflow and accounting behaviour feel familiar, without requiring the paid module. Built for Egyptian companies, with the Egyptian payroll taxes and the company document layout included.

The module lives in the [`ff_hr_payroll/`](ff_hr_payroll/) directory — drop it in your addons path and install it from the Apps menu.

## Features

- Employee contracts, flexible salary rules (fixed / percentage / Python) and unlimited UI-built deduction rules
- Salary structures with parent inheritance, payslips and payslip batches
- Automatic accrual posting (Dr salary expense / Cr salary payable), fiscal-lock aware
- Attendance / Time Off integration (paid / unpaid leave, absence)
- KPI bonuses (Gamification) and Sales KPI / commission
- HR fines with automatic deduction
- Egyptian payroll taxes: social insurance (employee + employer) and income tax with editable brackets (master toggle)
- Payslip register (PDF + Excel) and one-click payslip emailing
- Multi-company, configurable accounts, audit trail, Arabic + English translations

## Requirements

Odoo 19 Community. Depends on `hr`, `hr_work_entry`, `hr_attendance`, `hr_holidays`, `hr_gamification`, `account` and `mail`. The sales KPI feature optionally reads `sale.order` if the `sale` module is installed.

## License

LGPL-3 — Flous Flow / Mohamed Gamal.
