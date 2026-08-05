.. image:: static/description/icon.png
   :alt: Flous Flow HR Payroll
   :width: 128px

Flous Flow HR Payroll
=====================

A full payroll engine for **Odoo 19 Community** (the native ``hr_payroll`` app
is Enterprise-only). It mirrors the standard Odoo payroll architecture so the
data model, workflow and accounting behaviour feel familiar, without requiring
the paid module. Built for Egyptian companies, with the Egyptian payroll taxes
(social insurance + income tax) and the company document layout included.

Features
--------

* **Employee Contracts** (``hr.contract``) — wage, schedule type (monthly /
  weekly / daily / hourly), start/end dates, salary structure, state workflow.
* **Salary Rules** (``hr.salary.rule``) — the flexible calculation engine:
  every rule has a condition (always / range / Python) and an amount (fixed /
  percentage / Python). Create **unlimited deduction rules** from the UI
  (e.g. one day per absent day, two days for unapproved absence, fixed
  penalties, ...). Supports Enterprise-style Python code with ``result``,
  ``result_rate`` and ``result_qty``, plus **hierarchical rules** (a parent
  aggregates its children).
* **Salary Structures** (``hr.payroll.structure``) with parent inheritance.
* **Payslips** (``hr.payslip``) with computed lines, manual inputs (advances,
  loans, fines), worked days, and configurable accrual posting
  (Dr salary expense / Cr salary payable) that respects fiscal lock dates.
* **Payslip Batches** (``hr.payslip.run``) — generate one payslip per employee
  with an open contract.
* **Attendance / Time Off integration** — worked days are pulled automatically
  from Attendance and validated Time Off. ``LEAVE100`` (approved paid leave
  with balance) → **no deduction**; ``LEAVE90`` (approved unpaid leave without
  balance) → **deducts one day**; ``ABSENT`` (no request) → a **separate code**
  you can deduct at 2x / 3x … per day (build the rule from the UI).
* **Flexible KPI bonuses** through the native Gamification app (a dedicated
  rule pays ``target_bonus x completeness%``) and a **Sales KPI / commission**
  read from the linked user's confirmed sale orders.
* **HR Fines** — record penalties from a dedicated screen or the employee form;
  confirmed fines are deducted automatically from the payslip.
* **Egyptian payroll taxes (country-dependent)** — a master toggle applies
  social insurance (employee + employer shares) and income tax on salaries with
  an **editable progressive annual bracket** table. The deduction rules are
  generated automatically from the company settings and only apply while
  enabled.
* **Payslip Register** — aggregate report (PDF + Excel) for a period.
* **Printing & emails** — payslip PDF with the company document layout and a
  one-click **Send by Email** (PDF attached).
* **Multi-company**, configurable accounts, audit trail (chatter) and
  **Arabic + English** translations.

Configuration
-------------

1. Install the module.
2. **Settings → Payroll** — set the journal, the salary expense and salary
   payable accounts and auto-post. Under **Payroll Taxes**, enable the master
   switch, social insurance and income tax; set the rates, exemption and the
   progressive brackets, plus the payable / expense accounts.
3. **Employees**: add a linked user (for KPI goals) and set the Sales Target /
   Commission in the *Sales & Fines* tab.
4. **Payroll**: create salary rules (use the *Absence Rule*, *KPI Bonus* and
   *Sales Bonus* tabs to build them without Python), attach them to a structure
   and generate payslips.

Reports
-------

* **Payslip** (PDF) — per employee, company layout, Arabic labels.
* **Payslip Register** (PDF + Excel) — aggregate per period.

Requirements
------------

Odoo 19 Community. Depends on ``hr``, ``hr_work_entry``, ``hr_attendance``,
``hr_holidays``, ``hr_gamification``, ``account`` and ``mail``.
The sales KPI feature optionally reads ``sale.order`` if the ``sale`` module is
installed.

Tests
-----

34 automated tests cover contracts, salary rules (eval + exec ``result_rate`` /
``result_qty``), structures, hierarchical rules, range conditions, KPI,
attendance + leaves (LEAVE100 / LEAVE90 / ABSENT), UI absence rules, fines,
sales target + commission, Egyptian taxes (social insurance employee + employer,
income tax, toggle off, balanced posting), payslip register (wizard + PDF),
accrual posting and PDF rendering.

Notes & limitations
-------------------

* Income tax uses a simplified monthly × 12 annualization (not YTD cumulative).
* The social insurance base is the total gross (all positive lines).
* No bank mass-payment integration yet; payslips post an accrual (payable) and
  are settled manually.
* Salary tax rates / brackets are **editable defaults** — verify them against
  the current regulations before going live.

License
-------

LGPL-3 — Flous Flow / Mohamed Gamal.
