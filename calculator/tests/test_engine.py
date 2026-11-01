from decimal import Decimal as D

from django.test import SimpleTestCase

from calculator.engine import (
    Course, EngineError, GradeRule, InvalidCreditError, Policy, UnknownGradeError,
    calculate_cgpa, calculate_gpa, max_grade_point, required_gpa,
)
from calculator.policies import LEGACY_10_POINT as P


def c(name, credits, grade, key='', term=0):
    return Course(name, credits, grade, key, term)


class GpaTests(SimpleTestCase):
    def test_basic_weighted_average(self):
        r = calculate_gpa([c('a', 3, 'A'), c('b', 4, 'B')], P)
        self.assertEqual(r.quality_points, D(59))
        self.assertEqual(r.counted_credits, D(7))
        self.assertEqual(r.rounded, D('8.43'))

    def test_matches_legacy_example(self):
        # 3 credits S, 3 credits A, 2 credits B => (30+27+16)/8 = 9.125
        r = calculate_gpa([c('a', 3, 'S'), c('b', 3, 'A'), c('c', 2, 'B')], P)
        self.assertEqual(r.gpa, D('9.125'))

    def test_zero_credits_returns_zero(self):
        self.assertEqual(calculate_gpa([], P).gpa, D(0))
        self.assertEqual(calculate_gpa([c('a', 0, 'A')], P).gpa, D(0))

    def test_failed_course_counts_in_denominator_but_not_earned(self):
        r = calculate_gpa([c('a', 3, 'A'), c('b', 3, 'F')], P)
        self.assertEqual(r.gpa, D('4.5'))
        self.assertEqual(r.counted_credits, D(6))
        self.assertEqual(r.earned_credits, D(3))

    def test_missing_grade_is_excluded(self):
        r = calculate_gpa([c('a', 3, 'A'), c('b', 3, None)], P)
        self.assertEqual(r.gpa, D(9))
        self.assertEqual(r.counted_credits, D(3))

    def test_unknown_grade_raises(self):
        with self.assertRaises(UnknownGradeError):
            calculate_gpa([c('a', 3, 'Z')], P)

    def test_negative_credits_rejected(self):
        with self.assertRaises(InvalidCreditError):
            c('a', -1, 'A')

    def test_floats_rejected(self):
        with self.assertRaises(TypeError):
            c('a', 3.5, 'A')

    def test_fractional_credit_hours(self):
        r = calculate_gpa([c('lab', '1.5', 'A'), c('th', 3, 'B')], P)
        self.assertEqual(r.gpa, (D(9) * D('1.5') + D(8) * 3) / D('4.5'))

    def test_non_counting_grade_withdrawn(self):
        pol = Policy('t', 'T', {'A': GradeRule('A', D(4)),
                                'W': GradeRule('W', D(0), counts_in_gpa=False, is_pass=False)})
        r = calculate_gpa([c('a', 3, 'A'), c('b', 3, 'W')], pol)
        self.assertEqual(r.gpa, D(4))
        self.assertEqual(r.earned_credits, D(3))


class RoundingTests(SimpleTestCase):
    def _policy(self, rounding):
        return Policy('t', 'T', {'A': GradeRule('A', D('3.665'))}, precision=2, rounding=rounding)

    def test_half_up_boundary(self):
        r = calculate_gpa([c('a', 1, 'A')], self._policy('half_up'))
        self.assertEqual(r.rounded, D('3.67'))

    def test_half_even_boundary(self):
        r = calculate_gpa([c('a', 1, 'A')], self._policy('half_even'))
        self.assertEqual(r.rounded, D('3.66'))

    def test_truncate(self):
        r = calculate_gpa([c('a', 1, 'A')], self._policy('truncate'))
        self.assertEqual(r.rounded, D('3.66'))

    def test_bad_rounding_mode(self):
        with self.assertRaises(EngineError):
            Policy('t', 'T', {}, rounding='nope')


class RetakeTests(SimpleTestCase):
    def _pol(self, rule):
        return Policy('t', 'T', P.grades, retake_rule=rule)

    def setUp(self):
        self.courses = [c('Calc', 3, 'F', 'MATH101', 1), c('Calc', 3, 'B', 'MATH101', 2),
                        c('Phys', 3, 'A', 'PHY101', 1)]

    def test_all_counts_every_attempt(self):
        self.assertEqual(calculate_gpa(self.courses, self._pol('all')).counted_credits, D(9))

    def test_latest_replaces_earlier_attempt(self):
        r = calculate_gpa(self.courses, self._pol('latest'))
        self.assertEqual(r.counted_credits, D(6))
        self.assertEqual(r.gpa, D('8.5'))

    def test_best_keeps_highest(self):
        courses = [c('Calc', 3, 'A', 'M', 1), c('Calc', 3, 'C', 'M', 2)]
        r = calculate_gpa(courses, self._pol('best'))
        self.assertEqual(r.gpa, D(9))
        self.assertEqual(r.counted_credits, D(3))


class CgpaTests(SimpleTestCase):
    def test_cgpa_is_weighted_not_average_of_gpas(self):
        t1 = [c('a', 3, 'A')]
        t2 = [c('b', 1, 'F'), c('c', 6, 'S')]
        cg = calculate_cgpa([t1, t2], P)
        self.assertEqual(cg.gpa, D(87) / D(10))
        avg_of_gpas = (calculate_gpa(t1, P).gpa + calculate_gpa(t2, P).gpa) / 2
        self.assertNotEqual(cg.gpa, avg_of_gpas)

    def test_retake_across_terms_uses_term_order(self):
        pol = Policy('t', 'T', P.grades, retake_rule='latest')
        cg = calculate_cgpa([[c('x', 3, 'F', 'K')], [c('x', 3, 'A', 'K')]], pol)
        self.assertEqual(cg.gpa, D(9))


class PlannerTests(SimpleTestCase):
    def test_required_gpa(self):
        cur = calculate_gpa([c('a', 3, 'B')], P)   # 8.0 over 3 credits
        need = required_gpa(cur, 3, 9, P)           # target 9.0 over 6 credits => 54-24=30 / 3
        self.assertEqual(need, D(10))
        self.assertEqual(max_grade_point(P), D(10))

    def test_requires_positive_upcoming_credits(self):
        with self.assertRaises(InvalidCreditError):
            required_gpa(calculate_gpa([], P), 0, 9, P)
