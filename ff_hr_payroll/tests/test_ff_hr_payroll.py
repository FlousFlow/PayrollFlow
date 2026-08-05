# -*- coding: utf-8 -*-
import uuid
from datetime import date, datetime

from odoo.exceptions import UserError, ValidationError
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestFFHrPayroll(TransactionCase):
    """Business rules of the Flous Flow payroll engine."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company

        cls.expense_acct = cls.env['account.account'].create({
            'name': 'Payroll Test Expense', 'code': '9PYREXP',
            'account_type': 'expense',
        })
        cls.payable_acct = cls.env['account.account'].create({
            'name': 'Payroll Test Payable', 'code': '9PYRPAY',
            'account_type': 'liability_current', 'reconcile': True,
        })
        cls.advance_acct = cls.env['account.account'].create({
            'name': 'Payroll Test Advance', 'code': '9PYRADV',
            'account_type': 'asset_current', 'reconcile': True,
        })
        cls.journal = cls.env['account.journal'].create({
            'name': 'Payroll Test Journal', 'code': 'PYR', 'type': 'general',
        })
        cls.company.ff_hr_payroll_journal_id = cls.journal.id
        cls.company.ff_hr_payroll_expense_account_id = cls.expense_acct.id
        cls.company.ff_hr_payroll_payable_account_id = cls.payable_acct.id
        cls.company.ff_hr_payroll_auto_post = True

        cls.employee = cls.env['hr.employee'].create({
            'name': 'Test Employee', 'company_id': cls.company.id, 'wage': 300.0,
        })
        cls.structure = cls.env['hr.payroll.structure.type'].create({'name': 'Worker'})
        cls.contract = cls.env['hr.contract'].create({
            'name': 'CTR-TEST', 'employee_id': cls.employee.id,
            'company_id': cls.company.id, 'wage': 300.0,
            'schedule_pay': 'monthly', 'structure_type_id': cls.structure.id,
            'date_start': date(2026, 1, 1),
        })
        cls.contract.action_open()

        cls.cat_basic = cls.env['hr.salary.rule.category'].create({
            'name': 'Basic', 'code': 'BASIC', 'company_id': cls.company.id})
        cls.cat_ded = cls.env['hr.salary.rule.category'].create({
            'name': 'Deduction', 'code': 'DEDUCTION', 'company_id': cls.company.id})

        cls.env['hr.salary.rule'].create({
            'name': 'Basic Wage', 'code': 'BASIC', 'sequence': 10,
            'category_id': cls.cat_basic.id, 'company_id': cls.company.id,
            'condition_select': 'always', 'amount_select': 'fixed',
            'amount_fixed': 300.0, 'account_debit': cls.expense_acct.id,
            'account_credit': cls.payable_acct.id,
        })
        cls.rule_absent = cls.env['hr.salary.rule'].create({
            'name': 'Absent Day', 'code': 'ABSENT_DAY', 'sequence': 20,
            'category_id': cls.cat_ded.id, 'company_id': cls.company.id,
            'condition_select': 'python',
            'condition_python': "bool(worked_days.get('LEAVE90', 0.0))",
            'amount_select': 'python',
            'amount_python': "-1 * (contract.wage / 30.0) * worked_days.get('LEAVE90', 0.0)",
            'account_credit': cls.payable_acct.id,
        })
        cls.rule_advance = cls.env['hr.salary.rule'].create({
            'name': 'Advance', 'code': 'ADVANCE', 'sequence': 30,
            'category_id': cls.cat_ded.id, 'company_id': cls.company.id,
            'condition_select': 'python',
            'condition_python': "bool(inputs.get('INPUT.ADVANCE', 0.0))",
            'amount_select': 'python',
            'amount_python': "inputs.get('INPUT.ADVANCE', 0.0)",
            'account_credit': cls.advance_acct.id,
        })

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _create_payslip(self):
        return self.env['hr.payslip'].create({
            'employee_id': self.employee.id,
            'contract_id': self.contract.id,
            'company_id': self.company.id,
            'structure_type_id': self.structure.id,
            'date_from': date(2026, 1, 1),
            'date_to': date(2026, 1, 31),
        })

    def _add_absence(self, payslip, days=2.0):
        leave90 = self.env['hr.work.entry.type'].search([('code', '=', 'LEAVE90')], limit=1)
        if not leave90:
            leave90 = self.env['hr.work.entry.type'].create({'name': 'Unpaid', 'code': 'LEAVE90'})
        self.env['hr.payslip.worked.days'].create({
            'payslip_id': payslip.id, 'work_entry_type_id': leave90.id,
            'name': 'Unpaid Absence', 'number_of_days': days, 'number_of_hours': days * 8.0,
        })

    def _add_advance(self, payslip, amount=-100.0):
        input_type = self.env['hr.payslip.input.type'].search([('code', '=', 'INPUT.ADVANCE')], limit=1)
        if not input_type:
            input_type = self.env['hr.payslip.input.type'].create({
                'name': 'Advance', 'code': 'INPUT.ADVANCE', 'company_id': self.company.id})
        self.env['hr.payslip.input'].create({
            'payslip_id': payslip.id, 'input_type_id': input_type.id,
            'name': 'Advance', 'amount': amount,
        })

    # ------------------------------------------------------------------
    # Contract tests
    # ------------------------------------------------------------------
    def test_contract_flow(self):
        self.assertEqual(self.contract.state, 'open')
        self.assertEqual(self.contract.wage, 300.0)

    def test_contract_no_overlap(self):
        with self.assertRaises(ValidationError):
            self.env['hr.contract'].create({
                'name': 'CTR-OVERLAP', 'employee_id': self.employee.id,
                'company_id': self.company.id, 'wage': 400.0,
                'schedule_pay': 'monthly', 'structure_type_id': self.structure.id,
                'date_start': date(2026, 1, 15), 'date_end': date(2026, 3, 15),
            })

    def test_contract_negative_wage(self):
        with self.assertRaises(ValidationError):
            self.env['hr.contract'].create({
                'name': 'CTR-NEG', 'employee_id': self.employee.id,
                'company_id': self.company.id, 'wage': -5.0,
                'schedule_pay': 'monthly', 'structure_type_id': self.structure.id,
                'date_start': date(2026, 1, 1),
            })

    # ------------------------------------------------------------------
    # Salary rule tests
    # ------------------------------------------------------------------
    def test_rule_duplicate_code_blocked(self):
        with self.assertRaises(ValidationError):
            self.env['hr.salary.rule'].create({
                'name': 'Dup', 'code': 'BASIC', 'category_id': self.cat_basic.id,
                'company_id': self.company.id,
            })

    def test_rule_python_requires_code(self):
        with self.assertRaises(ValidationError):
            self.env['hr.salary.rule'].create({
                'name': 'No Py', 'code': 'NOPY', 'category_id': self.cat_basic.id,
                'company_id': self.company.id, 'condition_select': 'python',
            })

    # ------------------------------------------------------------------
    # Payslip computation tests
    # ------------------------------------------------------------------
    def test_payslip_basic_only(self):
        payslip = self._create_payslip()
        payslip.compute_sheet()
        self.assertEqual(payslip.net_wage, 300.0)
        self.assertEqual(payslip.gross_wage, 300.0)
        self.assertEqual(payslip.total_deductions, 0.0)

    def test_payslip_with_absence_and_advance(self):
        payslip = self._create_payslip()
        self._add_absence(payslip, 2.0)
        self._add_advance(payslip, -100.0)
        payslip.compute_sheet()
        self.assertEqual(payslip.gross_wage, 300.0)
        self.assertEqual(payslip.total_deductions, -120.0)
        self.assertEqual(payslip.net_wage, 180.0)
        codes = payslip.line_ids.mapped('code')
        self.assertIn('ABSENT_DAY', codes)
        self.assertIn('ADVANCE', codes)

    # ------------------------------------------------------------------
    # KPI bonus tests (goals-based, flexible)
    # ------------------------------------------------------------------
    def _create_kpi_goal(self, employee, target_bonus=200.0, current=50.0, target=100.0):
        """Create a gamification goal linked to the employee's user and mark it as KPI."""
        user = employee.user_id
        if not user:
            # make a real internal user so goals can be attached
            user = self.env['res.users'].create({
                'name': 'KPI User', 'login': 'kpi_user_test_%s' % self.id,
                'group_ids': [(6, 0, [self.env.ref('base.group_user').id])],
            })
            employee.user_id = user.id
        definition = self.env['gamification.goal.definition'].create({
            'name': 'KPI Goal Test', 'computation_mode': 'manually',
            'display_mode': 'progress', 'domain': '[]', 'condition': 'higher',
        })
        goal = self.env['gamification.goal'].create({
            'definition_id': definition.id,
            'user_id': user.id,
            'target_goal': target,
            'current': current,
            'is_kpi': True,
            'kpi_weight': 100.0,
            'target_bonus': target_bonus,
        })
        return goal

    def test_kpi_bonus_computed_from_goal(self):
        """A KPI bonus rule pays the employee's weighted goal bonus."""
        goal = self._create_kpi_goal(self.employee)
        # completeness = current/target = 50/100 = 50% -> bonus = 200 * 50% = 100
        self.assertAlmostEqual(goal.completeness, 50.0, places=2)
        self.assertAlmostEqual(goal.kpi_bonus, 100.0, places=2)
        self.assertAlmostEqual(self.employee.kpi_bonus_total, 100.0, places=2)

        rule = self.env['hr.salary.rule'].create({
            'name': 'KPI Bonus', 'code': 'KPI_BONUS', 'sequence': 40,
            'category_id': self.cat_basic.id, 'company_id': self.company.id,
            'condition_select': 'always', 'amount_select': 'fixed',
            'amount_fixed': 0.0, 'is_kpi_bonus': True, 'kpi_bonus_rate': 100.0,
            'account_debit': self.expense_acct.id,
            'account_credit': self.payable_acct.id,
        })
        payslip = self._create_payslip()
        payslip.compute_sheet()
        kpi_line = payslip.line_ids.filtered(lambda l: l.code == 'KPI_BONUS')
        self.assertTrue(kpi_line)
        self.assertAlmostEqual(kpi_line.total, 100.0, places=2)
        self.assertAlmostEqual(payslip.net_wage, 400.0, places=2)

    def test_kpi_bonus_rate_50(self):
        """kpi_bonus_rate=50% pays half of the weighted bonus."""
        self._create_kpi_goal(self.employee)
        rule = self.env['hr.salary.rule'].create({
            'name': 'KPI Half', 'code': 'KPI_HALF', 'sequence': 40,
            'category_id': self.cat_basic.id, 'company_id': self.company.id,
            'condition_select': 'always', 'amount_select': 'fixed',
            'amount_fixed': 0.0, 'is_kpi_bonus': True, 'kpi_bonus_rate': 50.0,
            'account_debit': self.expense_acct.id,
            'account_credit': self.payable_acct.id,
        })
        payslip = self._create_payslip()
        payslip.compute_sheet()
        kpi_line = payslip.line_ids.filtered(lambda l: l.code == 'KPI_HALF')
        self.assertTrue(kpi_line)
        self.assertAlmostEqual(kpi_line.total, 50.0, places=2)
        self.assertAlmostEqual(payslip.net_wage, 350.0, places=2)

    def test_kpi_no_goal_pays_zero(self):
        """Without any KPI goal the bonus rule contributes nothing."""
        rule = self.env['hr.salary.rule'].create({
            'name': 'KPI None', 'code': 'KPI_NONE', 'sequence': 40,
            'category_id': self.cat_basic.id, 'company_id': self.company.id,
            'condition_select': 'always', 'amount_select': 'fixed',
            'amount_fixed': 0.0, 'is_kpi_bonus': True, 'kpi_bonus_rate': 100.0,
            'account_debit': self.expense_acct.id,
            'account_credit': self.payable_acct.id,
        })
        payslip = self._create_payslip()
        payslip.compute_sheet()
        kpi_line = payslip.line_ids.filtered(lambda l: l.code == 'KPI_NONE')
        self.assertTrue(kpi_line)
        self.assertAlmostEqual(kpi_line.total, 0.0, places=2)
        self.assertAlmostEqual(payslip.net_wage, 300.0, places=2)

    # ------------------------------------------------------------------
    # Structure / hierarchy / batch tests
    # ------------------------------------------------------------------
    def test_structure_inherits_rules(self):
        """A child structure inherits the rules of its parent."""
        parent = self.env['hr.payroll.structure'].create({
            'name': 'Base', 'code': 'BASE', 'company_id': self.company.id})
        child = self.env['hr.payroll.structure'].create({
            'name': 'Child', 'code': 'CHILD', 'company_id': self.company.id,
            'parent_id': parent.id})
        rule = self.env['hr.salary.rule'].create({
            'name': 'Struct Bonus', 'code': 'STRUCT_BONUS', 'sequence': 50,
            'category_id': self.cat_basic.id, 'company_id': self.company.id,
            'condition_select': 'always', 'amount_select': 'fixed',
            'amount_fixed': 50.0,
            'structure_ids': [(6, 0, [parent.id])],
            'account_debit': self.expense_acct.id,
            'account_credit': self.payable_acct.id,
        })
        self.assertIn(rule, parent.get_all_rules())
        self.assertIn(rule, child.get_all_rules())  # inherited from parent
        payslip = self._create_payslip()
        payslip.struct_id = child.id
        payslip.compute_sheet()
        line = payslip.line_ids.filtered(lambda l: l.code == 'STRUCT_BONUS')
        self.assertTrue(line)
        self.assertAlmostEqual(line.total, 50.0, places=2)

    def test_hierarchical_rule_aggregation(self):
        """A parent rule aggregates its child rules' amounts."""
        parent = self.env['hr.salary.rule'].create({
            'name': 'Allowances', 'code': 'ALLOW', 'sequence': 15,
            'category_id': self.cat_basic.id, 'company_id': self.company.id,
            'condition_select': 'always', 'amount_select': 'fixed',
            'amount_fixed': 0.0, 'account_debit': self.expense_acct.id,
            'account_credit': self.payable_acct.id,
        })
        self.env['hr.salary.rule'].create({
            'name': 'Transport', 'code': 'ALLOW_TRANS', 'sequence': 16,
            'category_id': self.cat_basic.id, 'company_id': self.company.id,
            'condition_select': 'always', 'amount_select': 'fixed',
            'amount_fixed': 100.0, 'parent_rule_id': parent.id,
        })
        self.env['hr.salary.rule'].create({
            'name': 'Food', 'code': 'ALLOW_FOOD', 'sequence': 17,
            'category_id': self.cat_basic.id, 'company_id': self.company.id,
            'condition_select': 'always', 'amount_select': 'fixed',
            'amount_fixed': 50.0, 'parent_rule_id': parent.id,
        })
        payslip = self._create_payslip()
        payslip.compute_sheet()
        # parent line aggregates 100 (transport) + 50 (food) = 150
        parent_line = payslip.line_ids.filtered(lambda l: l.code == 'ALLOW')
        self.assertTrue(parent_line)
        self.assertAlmostEqual(parent_line.total, 150.0, places=2)
        self.assertAlmostEqual(payslip.net_wage, 450.0, places=2)

    def test_range_condition(self):
        """A rule with a wage range condition only applies within the range."""
        self.env['hr.salary.rule'].create({
            'name': 'High Wage Bonus', 'code': 'HIGH_BONUS', 'sequence': 60,
            'category_id': self.cat_basic.id, 'company_id': self.company.id,
            'condition_select': 'range', 'condition_range_min': 400.0,
            'amount_select': 'fixed', 'amount_fixed': 100.0,
            'account_debit': self.expense_acct.id,
            'account_credit': self.payable_acct.id,
        })
        # contract wage is 300 -> below range, rule does not apply
        payslip = self._create_payslip()
        payslip.compute_sheet()
        self.assertFalse(payslip.line_ids.filtered(lambda l: l.code == 'HIGH_BONUS'))
        # raise wage -> applies
        self.contract.wage = 500.0
        payslip2 = self._create_payslip()
        payslip2.compute_sheet()
        line = payslip2.line_ids.filtered(lambda l: l.code == 'HIGH_BONUS')
        self.assertTrue(line)
        self.assertAlmostEqual(line.total, 100.0, places=2)

    def test_payslip_run_generates_payslips(self):
        """A payslip batch generates one payslip per employee with an open contract."""
        batch = self.env['hr.payslip.run'].create({
            'name': 'Batch Test',
            'date_start': date(2026, 1, 1),
            'date_end': date(2026, 1, 31),
            'company_id': self.company.id,
            'employee_ids': [(6, 0, [self.employee.id])],
        })
        batch.action_generate_payslips()
        self.assertEqual(len(batch.payslip_ids), 1)
        self.assertEqual(batch.payslip_ids.employee_id, self.employee)
        self.assertEqual(batch.payslip_ids.date_from, date(2026, 1, 1))
        self.assertEqual(batch.payslip_ids.date_to, date(2026, 1, 31))

    def test_generate_worked_days_from_attendance_and_leave(self):
        """action_generate_worked_days reads Attendance + validated Time Off."""
        payslip = self.env['hr.payslip'].create({
            'employee_id': self.employee.id,
            'contract_id': self.contract.id,
            'company_id': self.company.id,
            'structure_type_id': self.structure.id,
            'date_from': date(2026, 8, 1),
            'date_to': date(2026, 8, 31),
        })
        # 2 attendance days
        for d in (1, 2):
            self.env['hr.attendance'].create({
                'employee_id': self.employee.id,
                'check_in': datetime(2026, 8, d, 9, 0, 0),
                'check_out': datetime(2026, 8, d, 17, 0, 0),
            })
        # 1 unpaid leave day
        leave_type = self.env['hr.leave.type'].create({
            'name': 'Unpaid Test', 'request_unit': 'day',
            'leave_validation_type': 'no_validation',
            'requires_allocation': False,
            'unpaid': True,
        })
        # work_entry_type_id lives on the leave TYPE; no_validation -> auto validate
        self.env['hr.leave'].sudo().create({
            'employee_id': self.employee.id,
            'holiday_status_id': leave_type.id,
            'date_from': datetime(2026, 8, 3, 8, 0, 0),
            'date_to': datetime(2026, 8, 3, 17, 0, 0),
            'number_of_days': 1.0,
        })
        payslip.action_generate_worked_days()
        wd = {w.code: w.number_of_days for w in payslip.worked_days_ids}
        # attendance read correctly
        self.assertAlmostEqual(wd.get('WORK100', 0.0), 2.0, places=1)
        # approved unpaid leave -> LEAVE90 (deducted one day for one day)
        self.assertAlmostEqual(wd.get('LEAVE90', 0.0), 1.0, places=1)
        # unapproved absence -> separate ABSENT code (for a flexible 2x/3x rule)
        self.assertGreater(wd.get('ABSENT', 0.0), 0.0)

    def test_unapproved_absence_is_separate_from_unpaid_leave(self):
        """ABSENT (no leave) must be a distinct code from LEAVE90 (approved unpaid leave)."""
        payslip = self.env['hr.payslip'].create({
            'employee_id': self.employee.id,
            'contract_id': self.contract.id,
            'company_id': self.company.id,
            'structure_type_id': self.structure.id,
            'date_from': date(2026, 8, 1),
            'date_to': date(2026, 8, 31),
        })
        # one attendance day only -> lots of unapproved absence
        self.env['hr.attendance'].create({
            'employee_id': self.employee.id,
            'check_in': datetime(2026, 8, 1, 9, 0, 0),
            'check_out': datetime(2026, 8, 1, 17, 0, 0),
        })
        payslip.action_generate_worked_days()
        codes = {w.code for w in payslip.worked_days_ids}
        self.assertIn('WORK100', codes)
        self.assertIn('ABSENT', codes)
        # no approved unpaid leave -> LEAVE90 absent
        self.assertNotIn('LEAVE90', codes)

    def test_absence_rule_auto_build(self):
        """is_absence_rule generates condition + amount Python from the UI fields."""
        rule = self.env['hr.salary.rule'].create({
            'name': 'Absence Penalty', 'code': 'ABSENT_PEN',
            'category_id': self.cat_ded.id, 'company_id': self.company.id,
            'is_absence_rule': True, 'absence_code': 'ABSENT',
            'absence_multiplier': 2.0, 'absence_daily_wage': True,
            'account_debit': self.expense_acct.id,
            'account_credit': self.payable_acct.id,
        })
        self.assertEqual(rule.condition_select, 'python')
        self.assertIn("'ABSENT'", rule.condition_python)
        self.assertIn('-2.0 * (contract.wage / 30.0)', rule.amount_python)
        # switching to a fixed amount regenerates the amount
        rule.write({'absence_daily_wage': False, 'absence_fixed_amount': 50.0})
        self.assertIn('-50.0 * 2.0', rule.amount_python)

    # ------------------------------------------------------------------
    # Accounting posting tests
    # ------------------------------------------------------------------
    def test_confirm_posts_balanced_accrual(self):
        payslip = self._create_payslip()
        self._add_absence(payslip, 2.0)
        self._add_advance(payslip, -100.0)
        payslip.compute_sheet()
        payslip.action_payslip_done()
        self.assertEqual(payslip.state, 'done')
        self.assertTrue(payslip.move_id)
        self.assertEqual(payslip.move_id.state, 'posted')
        # balanced
        total_dr = sum(l.debit for l in payslip.move_id.line_ids)
        total_cr = sum(l.credit for l in payslip.move_id.line_ids)
        self.assertAlmostEqual(total_dr, total_cr, places=2)
        # expected: Dr expense 300, Cr absence 20, Cr advance 100, Cr net 180
        self.assertAlmostEqual(total_dr, 300.0, places=2)
        self.assertAlmostEqual(total_cr, 300.0, places=2)

    def test_no_post_without_lines(self):
        """A payslip with no rules and no lines cannot post an empty entry."""
        # Remove all salary rules for this company -> nothing computable
        self.env['hr.salary.rule'].search([('company_id', '=', self.company.id)]).unlink()
        payslip = self._create_payslip()
        payslip.compute_sheet()
        self.assertEqual(len(payslip.line_ids), 0)
        with self.assertRaises(UserError):
            payslip.action_payslip_done()

    # ------------------------------------------------------------------
    # Payslip PDF report test
    # ------------------------------------------------------------------
    def test_payslip_report_renders(self):
        """The QWeb PDF report template renders for a real payslip."""
        payslip = self._create_payslip()
        self._add_absence(payslip, 2.0)
        self._add_advance(payslip, -100.0)
        payslip.compute_sheet()
        report = self.env.ref('ff_hr_payroll.action_report_hr_payslip')
        self.assertTrue(report)
        html = self.env['ir.actions.report']._render_qweb_html(
            'ff_hr_payroll.report_hr_payslip', payslip.id, data=None)
        self.assertTrue(html)
        rendered = html[0].decode('utf-8') if isinstance(html[0], bytes) else html[0]
        self.assertIn('Payslip', rendered)
        self.assertIn('Net Wage', rendered)
        self.assertIn(str(int(payslip.net_wage)), rendered)

    # ------------------------------------------------------------------
    # result_rate / result_qty (exec-style rules)
    # ------------------------------------------------------------------
    def test_compute_rule_exec_rate_qty(self):
        """A rule using exec-style result / result_rate / result_qty is honoured."""
        rule = self.env['hr.salary.rule'].create({
            'name': 'Overtime', 'code': 'OVERTIME', 'sequence': 25,
            'category_id': self.cat_basic.id, 'company_id': self.company.id,
            'condition_select': 'always', 'amount_select': 'python',
            'amount_python': (
                "result = (contract.wage / 30.0) * 2.0\n"
                "result_rate = 100.0\n"
                "result_qty = 2.0\n"
            ),
            'account_debit': self.expense_acct.id,
            'account_credit': self.payable_acct.id,
        })
        payslip = self._create_payslip()
        payslip.compute_sheet()
        line = payslip.line_ids.filtered(lambda l: l.code == 'OVERTIME')
        self.assertTrue(line)
        # amount = (300/30)*2 = 20 ; total = 20 * qty(2) * rate(100)/100 = 40
        self.assertAlmostEqual(line.amount, 20.0, places=2)
        self.assertAlmostEqual(line.quantity, 2.0, places=2)
        self.assertAlmostEqual(line.rate, 100.0, places=2)
        self.assertAlmostEqual(line.total, 40.0, places=2)

    def test_eval_style_still_works(self):
        """Existing eval-style rules (expression returning a value) still work."""
        payslip = self._create_payslip()
        payslip.compute_sheet()
        basic = payslip.line_ids.filtered(lambda l: l.code == 'BASIC')
        self.assertTrue(basic)
        self.assertAlmostEqual(basic.total, 300.0, places=2)

    # ------------------------------------------------------------------
    # Sales KPI / commission
    # ------------------------------------------------------------------
    def _make_sales_user_and_order(self, amount):
        """Create a res.users linked to the test employee + one confirmed order."""
        user = self.env['res.users'].create({
            'name': 'Sales Test',
            'login': 'sales_test_%s' % uuid.uuid4().hex[:8],
        })
        self.employee.user_id = user.id
        order = self.env['sale.order'].create({
            'partner_id': user.partner_id.id,
            'user_id': user.id,
            'date_order': '2026-01-15 10:00:00',
            'state': 'sale',
        })
        order.amount_total = amount  # stored compute, writable from ORM
        return user

    def test_sales_rule_auto_build(self):
        """is_sales_bonus generates an exec-style amount referencing the sales fields."""
        rule = self.env['hr.salary.rule'].create({
            'name': 'Sales Commission', 'code': 'SALES_COMM',
            'category_id': self.cat_basic.id, 'company_id': self.company.id,
            'is_sales_bonus': True, 'sales_mode': 'commission',
            'account_debit': self.expense_acct.id,
            'account_credit': self.payable_acct.id,
        })
        self.assertEqual(rule.amount_select, 'python')
        self.assertIn('result =', rule.amount_python)
        self.assertIn('get_confirmed_sales', rule.amount_python)
        self.assertIn('sales_commission_rate', rule.amount_python)

    def test_sales_target_bonus_full_when_met(self):
        """Reaching the monthly target pays the full wage-linked bonus."""
        if not self.env.get('sale.order'):
            self.skipTest('sale module not installed')
        self.employee.write({
            'sales_target_percent': 100.0,  # target = wage = 300
            'sales_commission_rate': 10.0,
        })
        self._make_sales_user_and_order(300.0)  # confirmed sales = 300 = target
        rule = self.env['hr.salary.rule'].create({
            'name': 'Sales Target', 'code': 'SALES_TARGET', 'sequence': 15,
            'category_id': self.cat_basic.id, 'company_id': self.company.id,
            'is_sales_bonus': True, 'sales_mode': 'target',
            'account_debit': self.expense_acct.id,
            'account_credit': self.payable_acct.id,
        })
        payslip = self._create_payslip()
        payslip.compute_sheet()
        line = payslip.line_ids.filtered(lambda l: l.code == 'SALES_TARGET')
        self.assertTrue(line)
        self.assertAlmostEqual(line.total, 300.0, places=2)

    def test_sales_commission_above_target(self):
        """Sales above the target pay commission on the excess only."""
        if not self.env.get('sale.order'):
            self.skipTest('sale module not installed')
        self.employee.write({
            'sales_target_percent': 100.0,  # target = wage = 300
            'sales_commission_rate': 10.0,
        })
        self._make_sales_user_and_order(500.0)  # excess = 500 - 300 = 200
        rule = self.env['hr.salary.rule'].create({
            'name': 'Sales Commission', 'code': 'SALES_COMM', 'sequence': 15,
            'category_id': self.cat_basic.id, 'company_id': self.company.id,
            'is_sales_bonus': True, 'sales_mode': 'commission',
            'account_debit': self.expense_acct.id,
            'account_credit': self.payable_acct.id,
        })
        payslip = self._create_payslip()
        payslip.compute_sheet()
        line = payslip.line_ids.filtered(lambda l: l.code == 'SALES_COMM')
        self.assertTrue(line)
        # commission = 200 * 10/100 = 20
        self.assertAlmostEqual(line.total, 20.0, places=2)

    def test_sales_separate_target_and_commission_rules(self):
        """Two separate rules (target bonus + commission) coexist on one payslip."""
        if not self.env.get('sale.order'):
            self.skipTest('sale module not installed')
        # wage = 300 -> target = 300 ; sales = 500 (target met + excess 200)
        self.employee.write({
            'sales_target_percent': 100.0,
            'sales_commission_rate': 10.0,
        })
        self._make_sales_user_and_order(500.0)
        # Rule 1: target bonus (full wage-linked amount once target is met)
        self.env['hr.salary.rule'].create({
            'name': 'Sales Target', 'code': 'SALES_TARGET', 'sequence': 14,
            'category_id': self.cat_basic.id, 'company_id': self.company.id,
            'is_sales_bonus': True, 'sales_mode': 'target',
            'account_debit': self.expense_acct.id,
            'account_credit': self.payable_acct.id,
        })
        # Rule 2: commission on the excess only
        self.env['hr.salary.rule'].create({
            'name': 'Sales Commission', 'code': 'SALES_COMM', 'sequence': 15,
            'category_id': self.cat_basic.id, 'company_id': self.company.id,
            'is_sales_bonus': True, 'sales_mode': 'commission',
            'account_debit': self.expense_acct.id,
            'account_credit': self.payable_acct.id,
        })
        payslip = self._create_payslip()
        payslip.compute_sheet()
        target_line = payslip.line_ids.filtered(lambda l: l.code == 'SALES_TARGET')
        comm_line = payslip.line_ids.filtered(lambda l: l.code == 'SALES_COMM')
        # both independent lines appear on the SAME payslip
        self.assertTrue(target_line)
        self.assertTrue(comm_line)
        self.assertAlmostEqual(target_line.total, 300.0, places=2)  # full target
        self.assertAlmostEqual(comm_line.total, 20.0, places=2)     # 200 * 10%
        # BASIC 300 + target 300 + commission 20 = 620
        self.assertAlmostEqual(payslip.net_wage, 620.0, places=2)

    # ------------------------------------------------------------------
    # HR fines
    # ------------------------------------------------------------------
    def test_fines_deducted_from_payslip(self):
        """A confirmed fine inside the payslip period is deducted."""
        fine = self.env['hr.payslip.fine'].create({
            'employee_id': self.employee.id,
            'company_id': self.company.id,
            'amount': 50.0,
            'date': date(2026, 1, 10),
            'date_from': date(2026, 1, 1),
            'date_to': date(2026, 1, 31),
            'reason': 'Late attendance',
        })
        fine.action_done()
        payslip = self._create_payslip()
        payslip.compute_sheet()
        line = payslip.line_ids.filtered(lambda l: l.code == 'FINES')
        self.assertTrue(line)
        self.assertAlmostEqual(line.total, -50.0, places=2)
        self.assertAlmostEqual(payslip.net_wage, 250.0, places=2)

    def test_fines_outside_period_not_deducted(self):
        """A confirmed fine whose period does not overlap is NOT deducted."""
        self.env['hr.payslip.fine'].create({
            'employee_id': self.employee.id,
            'company_id': self.company.id,
            'amount': 50.0,
            'date': date(2026, 3, 10),
            'date_from': date(2026, 3, 1),
            'date_to': date(2026, 3, 31),
        }).action_done()
        payslip = self._create_payslip()  # January
        payslip.compute_sheet()
        self.assertFalse(payslip.line_ids.filtered(lambda l: l.code == 'FINES'))
        self.assertAlmostEqual(payslip.net_wage, 300.0, places=2)

    def test_fine_draft_not_deducted(self):
        """A draft (unconfirmed) fine is not deducted."""
        self.env['hr.payslip.fine'].create({
            'employee_id': self.employee.id,
            'company_id': self.company.id,
            'amount': 50.0,
            'date': date(2026, 1, 10),
            'date_from': date(2026, 1, 1),
            'date_to': date(2026, 1, 31),
        })
        payslip = self._create_payslip()
        payslip.compute_sheet()
        self.assertFalse(payslip.line_ids.filtered(lambda l: l.code == 'FINES'))

    # ------------------------------------------------------------------
    # Egyptian payroll taxes (social insurance + income tax)
    # ------------------------------------------------------------------
    def _enable_taxes(self):
        """Turn on payroll taxes on the test company with known rates."""
        si_pay = self.env['account.account'].create({
            'name': 'SI Payable', 'code': '9TSI', 'account_type': 'liability_payable', 'reconcile': True})
        si_exp = self.env['account.account'].create({
            'name': 'SI Expense', 'code': '9TSEE', 'account_type': 'expense'})
        tax_pay = self.env['account.account'].create({
            'name': 'Tax Payable', 'code': '9TTX', 'account_type': 'liability_payable', 'reconcile': True})
        self.company.write({
            'ff_hr_payroll_apply_taxes': True,
            'ff_hr_payroll_si_enabled': True,
            'ff_hr_payroll_si_employee_rate': 11.0,
            'ff_hr_payroll_si_employer_rate': 18.75,
            'ff_hr_payroll_si_max_insurable': 0.0,
            'ff_hr_payroll_si_payable_account_id': si_pay.id,
            'ff_hr_payroll_si_expense_account_id': si_exp.id,
            'ff_hr_payroll_income_tax_enabled': True,
            'ff_hr_payroll_income_tax_exemption': 15000.0,
            'ff_hr_payroll_income_tax_payable_account_id': tax_pay.id,
        })
        # simple brackets (annual, progressive)
        self.env['hr.payslip.tax.bracket'].create([
            {'company_id': self.company.id, 'sequence': 1, 'amount_from': 0.0, 'amount_to': 15000.0, 'rate': 0.0},
            {'company_id': self.company.id, 'sequence': 2, 'amount_from': 15000.0, 'amount_to': 30000.0, 'rate': 10.0},
            {'company_id': self.company.id, 'sequence': 3, 'amount_from': 30000.0, 'amount_to': 100000.0, 'rate': 20.0},
        ])

    def test_tax_rules_auto_created(self):
        """Enabling taxes creates the SI + income tax deduction rules."""
        self._enable_taxes()
        for code in ('SI_EMP', 'SI_COMP', 'INCOME_TAX'):
            rule = self.env['hr.salary.rule'].search(
                [('company_id', '=', self.company.id), ('code', '=', code)], limit=1)
            self.assertTrue(rule, 'rule %s not created' % code)
        si = self.env['hr.salary.rule'].search(
            [('company_id', '=', self.company.id), ('code', '=', 'SI_EMP')], limit=1)
        self.assertEqual(si.sequence, 90)  # runs after earnings

    def test_social_insurance_and_income_tax(self):
        """SI (employee + employer) and income tax are computed correctly and
        the employer share is excluded from the employee net."""
        self._enable_taxes()
        payslip = self._create_payslip()
        payslip.compute_sheet()
        si = payslip.line_ids.filtered(lambda l: l.code == 'SI_EMP')
        comp = payslip.line_ids.filtered(lambda l: l.code == 'SI_COMP')
        it = payslip.line_ids.filtered(lambda l: l.code == 'INCOME_TAX')
        self.assertTrue(si)
        self.assertTrue(comp)
        self.assertTrue(it)
        # wage = 300 (BASIC) -> SI employee 11% = -33 ; employer 18.75% = +56.25
        self.assertAlmostEqual(si.total, -33.0, places=2)
        self.assertAlmostEqual(comp.total, 56.25, places=2)
        # income tax: monthly = 300 - 33 = 267 ; annual = 267*12 - 15000 = -11796 -> 0
        self.assertAlmostEqual(it.total, 0.0, places=2)
        # employer share excluded from net: net = 300 - 33 - 0 = 267
        self.assertAlmostEqual(payslip.net_wage, 267.0, places=2)

    def test_tax_toggle_off_removes_deductions(self):
        """Turning the taxes master switch OFF removes all tax lines."""
        self._enable_taxes()
        self.company.write({'ff_hr_payroll_apply_taxes': False})
        payslip = self._create_payslip()
        payslip.compute_sheet()
        codes = [l.code for l in payslip.line_ids]
        self.assertFalse(any(c in ('SI_EMP', 'SI_COMP', 'INCOME_TAX') for c in codes))
        self.assertAlmostEqual(payslip.net_wage, 300.0, places=2)

    def test_employer_contribution_posts_balanced(self):
        """Posting a payslip with an employer SI contribution stays balanced and
        posts the employer share as Dr expense / Cr SI payable."""
        self._enable_taxes()
        # BASIC is a fixed 300 in the test setup -> add a fixed allowance to
        # raise the insurance base (gross = 300 + 5000 = 5300).
        self.env['hr.salary.rule'].create({
            'name': 'Bonus', 'code': 'BONUS', 'sequence': 15,
            'category_id': self.cat_basic.id, 'company_id': self.company.id,
            'condition_select': 'always', 'amount_select': 'fixed',
            'amount_fixed': 5000.0,
            'account_debit': self.expense_acct.id,
            'account_credit': self.payable_acct.id,
        })
        payslip = self._create_payslip()
        payslip.compute_sheet()
        payslip.action_payslip_done()
        self.assertTrue(payslip.move_id)
        self.assertEqual(payslip.move_id.state, 'posted')
        dr = sum(l.debit for l in payslip.move_id.line_ids)
        cr = sum(l.credit for l in payslip.move_id.line_ids)
        self.assertAlmostEqual(dr, cr, places=2)
        # gross = 5300 -> SI employee 11% = 583 ; employer 18.75% = 993.75
        si = payslip.line_ids.filtered(lambda l: l.code == 'SI_EMP')
        comp = payslip.line_ids.filtered(lambda l: l.code == 'SI_COMP')
        self.assertAlmostEqual(si.total, -583.0, places=2)
        self.assertAlmostEqual(comp.total, 993.75, places=2)
        # SI payable credited with employee + employer shares
        si_lines = payslip.move_id.line_ids.filtered(
            lambda l: l.account_id.code == '9TSI')
        self.assertAlmostEqual(sum(l.credit for l in si_lines), 583.0 + 993.75, places=2)

    # ------------------------------------------------------------------
    # Payslip register (aggregate report)
    # ------------------------------------------------------------------
    def test_register_wizard_collects_and_renders(self):
        """The register wizard collects the done payslips and the PDF renders."""
        p1 = self._create_payslip()
        p1.compute_sheet()
        p1.action_payslip_done()
        wiz = self.env['hr.payslip.register.wizard'].create({
            'company_id': self.company.id,
            'date_from': date(2026, 1, 1), 'date_to': date(2026, 1, 31),
            'state': 'done'})
        found = wiz._get_payslips()
        self.assertIn(p1, found)
        # Excel URL is generated
        self.assertIn('/ff_hr_payroll/payslip_register_xlsx', wiz.action_download_xlsx()['url'])
        # PDF renders
        pdf = self.env['ir.actions.report']._render_qweb_pdf(
            'ff_hr_payroll.report_hr_payslip_register', found.ids, data=None)
        self.assertTrue(pdf and pdf[0])


