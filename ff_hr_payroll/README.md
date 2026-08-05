# Flous Flow HR Payroll

A full payroll engine for **Odoo 19 Community** (the native `hr_payroll` app is
Enterprise-only). It mirrors the standard Odoo payroll architecture so the data
model, workflow and accounting behaviour feel familiar, without requiring the
paid app.

Built by **Flous Flow** for Egyptian construction / trading / services
companies, with the Egyptian payroll taxes (social insurance + income tax) and
company document layout built in.

---

## ✨ Features

### Payroll core
- **Employee Contracts** (`hr.contract`) — wage, schedule (monthly / weekly /
  daily / hourly), start/end dates, salary structure, state workflow.
- **Salary Rule Categories** — Basic / Allowances / Deductions / Company
  Contributions.
- **Salary Rules** (`hr.salary.rule`) — the flexible calculation engine:
  - condition (always / none / range / Python) + amount (fixed / percentage /
    Python code).
  - **Unlimited deduction rules** built from the UI: per absent day, per hour,
    fixed penalties, ...
  - **Enterprise-style compute**: Python rules may set `result`,
    `result_rate` and `result_qty` (exec mode) or return a value (eval mode).
  - **Hierarchical rules**: a parent rule aggregates its children.
- **Salary Structures** (`hr.payroll.structure`) with parent inheritance.
- **Payslips** (`hr.payslip`) with computed lines, manual inputs (advances,
  loans, fines), worked days, KPI bonuses, sales commissions.
- **Payslip Batches** (`hr.payslip.run`) — generate one payslip per employee
  with an open contract.
- **Automatic accrual posting** — confirming a payslip posts a balanced journal
  entry (Dr salary expense / Cr salary payable) using configurable accounts and
  respecting fiscal lock dates.
- **Multi-company** — everything is scoped per company.

### Attendance / Time Off integration
- **Worked days** are pulled automatically from Attendance + validated Time Off:
  - `WORK100` — days actually attended.
  - `LEAVE100` — approved paid leave (has balance) → **no deduction**.
  - `LEAVE90` — approved unpaid leave (no balance) → **deducts one day**.
  - `ABSENT` — absence without any request → a **separate code** so you can
    deduct it at 2x / 3x … per day (build the rule from the UI).

### KPI & Performance
- **Flexible KPI bonuses** through the native Gamification app: a dedicated
  salary rule pays `target_bonus × completeness%` from the employee's goals.
- **Sales KPI / Commission**: monthly target as a % of wage + commission on
  confirmed sales above the target — read automatically from the linked user's
  confirmed `sale.order`s inside the payslip period.

### HR Fines
- Record a fine / penalty against an employee (`hr.payslip.fine`) from a
  dedicated screen or the employee form; confirmed fines inside the payslip
  period are deducted automatically.

### Egyptian Payroll Taxes (country-dependent, toggleable)
- Master **Apply Payroll Taxes** switch (enabled by default for Egypt, can be
  turned OFF for countries without salary taxes).
- **Social insurance**: employee share (deduction) + employer share (company
  expense), with configurable rates, min/max insurable base and accounts.
- **Income tax** on salaries: annual exemption + **editable progressive
  annual brackets** (because the law changes every year).
- The tax deduction rules are generated automatically from the company settings
  and only apply while the toggles are ON.

### Payslip Register (aggregate report)
- Generate a **Payslip Register** for a period (optionally filtered by
  structure/status): **PDF** (company layout) and **Excel** export.

### Documents & Emails
- **Payslip PDF** report using the company document layout (`web.external_layout`).
- **Send by Email** — one click opens the composer with the payslip PDF attached.
- **Arabic translations** (`ar_001`) + English.

---

## ⚙️ Configuration

1. Install the module.
2. **Settings → Payroll** (`Payroll` app appears in the settings):
   - Journal, salary expense account, salary payable account, auto-post.
   - **Payroll Taxes**: enable the master switch, social insurance and income
     tax; set rates, exemption and the progressive brackets, and the payable /
     expense accounts.
3. **Employees**: add a linked user (for KPI goals) and set Sales Target /
   Commission in the *Sales & Fines* tab.
4. **Payroll**: create salary rules (use the *Absence Rule*, *KPI Bonus* and
   *Sales Bonus* tabs to build them without Python), attach them to a
   structure, and generate payslips.

---

## 📄 Reports

- **Payslip** (PDF) — per employee, company layout, Arabic labels.
- **Payslip Register** (PDF + Excel) — aggregate per period.

---

## 🧪 Tests

```
34 tests, all passing:
- contracts, salary rules (eval + exec `result_rate/result_qty`), structures,
  hierarchical rules, range conditions, KPI (goal & no-goal), attendance +
  leaves (LEAVE100/LEAVE90/ABSENT), UI absence rules, fines (deducted / outside
  period / draft), sales target + commission (separate rules), Egyptian taxes
  (SI employee + employer, income tax, toggle off, balanced posting), payslip
  register (wizard + PDF), accrual posting, PDF rendering.
```

Run them on a test database:

```bash
odoo-bin --addons-path=addons,ff_hr_payroll -u ff_hr_payroll -d <test_db> \
  --test-enable --stop-after-init --log-level=test
```

---

## 📌 Notes & limitations

- Income tax uses a simplified monthly × 12 annualization (not YTD
  cumulative).
- The social insurance base is the total gross (all positive lines).
- No bank mass-payment integration yet; payslips post an accrual (payable) and
  are settled manually.
- Salary tax rates/brackets are **editable defaults** — verify them against the
  current regulations before going live.

---

## 🏗️ Architecture

```
models/
  hr_contract.py            Employee contracts
  hr_payroll_structure.py   Salary structures (+ inheritance)
  hr_salary_rule_category.py
  hr_salary_rule.py         Rules (condition/amount, KPI, absence, sales, taxes)
  hr_payslip.py             Payslips + worked days + accounting
  hr_payslip_line.py        Payslip lines
  hr_payslip_input.py       Manual inputs (advances/loans/fines)
  hr_payslip_worked_days.py
  hr_payslip_run.py         Payslip batches
  hr_payslip_fine.py        HR fines
  hr_employee.py            Employee payroll helper fields
  hr_employee_kpi.py        KPI goals (gamification)
  hr_payslip_tax_bracket.py Income tax brackets
  hr_payslip_register_wizard.py  Payslip register wizard
  res_company.py            Company payroll + tax settings
  res_config_settings.py    Settings exposure
controllers/
  main.py                   Payslip register Excel export
views/  reports/  security/  data/  i18n/  tests/
```

---

## 📦 Dependencies

`hr`, `hr_work_entry`, `hr_attendance`, `hr_holidays`, `hr_gamification`,
`account`, `mail`. (Sales KPI needs the `sale` module installed to read
confirmed orders — optional.)

## 📄 License

LGPL-3 — Flous Flow / Mohamed Gamal.
