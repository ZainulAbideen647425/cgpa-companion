"""GPA/CGPA calculation engine.

Pure Python: no Django imports, no database access, no floats. A grading
policy (grade -> points, rounding, retake rule) is passed in explicitly, so
the same engine can serve any university once its official policy is loaded.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP, ROUND_HALF_EVEN, ROUND_DOWN
from typing import Dict, Iterable, List, Optional, Sequence

ZERO = Decimal('0')

ROUNDING_MODES = {
    'half_up': ROUND_HALF_UP,
    'half_even': ROUND_HALF_EVEN,
    'truncate': ROUND_DOWN,
}

RETAKE_RULES = ('all', 'latest', 'best')


class EngineError(ValueError):
    """Base class for engine validation errors."""


class UnknownGradeError(EngineError):
    pass


class InvalidCreditError(EngineError):
    pass


def to_decimal(value) -> Decimal:
    """Convert int/str/Decimal to Decimal. Floats are rejected on purpose."""
    if isinstance(value, float):
        raise TypeError('Use str, int or Decimal, not float, for exact arithmetic.')
    return value if isinstance(value, Decimal) else Decimal(str(value))


@dataclass(frozen=True)
class GradeRule:
    """How one grade symbol behaves under a policy."""
    symbol: str
    points: Decimal = ZERO
    counts_in_gpa: bool = True    # False for W (withdrawn), I (incomplete), P/NP, etc.
    is_pass: bool = True          # False means credits are not earned


@dataclass(frozen=True)
class Policy:
    """A grading policy. Real policies must carry their official source."""
    key: str
    name: str
    grades: Dict[str, GradeRule]
    precision: int = 2
    rounding: str = 'half_up'
    retake_rule: str = 'all'      # all | latest | best
    source: str = ''
    verification_status: str = 'unverified'

    def __post_init__(self):
        if self.rounding not in ROUNDING_MODES:
            raise EngineError(f'Unknown rounding mode: {self.rounding}')
        if self.retake_rule not in RETAKE_RULES:
            raise EngineError(f'Unknown retake rule: {self.retake_rule}')

    def rule_for(self, grade: str) -> GradeRule:
        try:
            return self.grades[grade]
        except KeyError:
            raise UnknownGradeError(f'Grade {grade!r} is not defined in policy {self.key!r}')

    def quantize(self, value: Decimal) -> Decimal:
        exp = Decimal(1).scaleb(-self.precision)
        return value.quantize(exp, rounding=ROUNDING_MODES[self.rounding])


@dataclass(frozen=True)
class Course:
    name: str
    credits: Decimal
    grade: Optional[str]          # None = not graded yet, excluded from the calculation
    course_key: str = ''          # same key across terms = a retake of the same course
    term: int = 0                 # ordering used by the 'latest' retake rule

    def __post_init__(self):
        object.__setattr__(self, 'credits', to_decimal(self.credits))
        if self.credits < 0:
            raise InvalidCreditError('Credit hours cannot be negative.')


@dataclass(frozen=True)
class GpaResult:
    quality_points: Decimal       # sum(points * credits) over counted courses
    counted_credits: Decimal      # credits in the GPA denominator
    earned_credits: Decimal       # credits of passed courses
    gpa: Decimal                  # exact, unrounded
    precision: int
    rounding: str

    @property
    def rounded(self) -> Decimal:
        exp = Decimal(1).scaleb(-self.precision)
        return self.gpa.quantize(exp, rounding=ROUNDING_MODES[self.rounding])


def _resolve_retakes(courses: Sequence[Course], policy: Policy) -> List[Course]:
    """Apply the policy's retake rule. Courses without a key are never merged."""
    if policy.retake_rule == 'all':
        return list(courses)
    keyed: Dict[str, Course] = {}
    result: List[Course] = []
    for c in courses:
        if not c.course_key or c.grade is None:
            result.append(c)
            continue
        prev = keyed.get(c.course_key)
        if prev is None:
            keyed[c.course_key] = c
        elif policy.retake_rule == 'latest':
            if c.term >= prev.term:
                keyed[c.course_key] = c
        else:  # best
            if policy.rule_for(c.grade).points > policy.rule_for(prev.grade).points:
                keyed[c.course_key] = c
    return result + list(keyed.values())


def calculate_gpa(courses: Iterable[Course], policy: Policy) -> GpaResult:
    """GPA = sum(points * credits) / sum(counted credits).

    Ungraded courses (grade None) and grades with counts_in_gpa=False are
    excluded. With no counted credits the GPA is 0.
    """
    quality = ZERO
    counted = ZERO
    earned = ZERO
    for c in _resolve_retakes(list(courses), policy):
        if c.grade is None:
            continue
        rule = policy.rule_for(c.grade)
        if rule.is_pass:
            earned += c.credits
        if not rule.counts_in_gpa:
            continue
        quality += rule.points * c.credits
        counted += c.credits
    gpa = quality / counted if counted > 0 else ZERO
    return GpaResult(quality, counted, earned, gpa, policy.precision, policy.rounding)


def calculate_cgpa(terms: Iterable[Iterable[Course]], policy: Policy) -> GpaResult:
    """Cumulative GPA across terms.

    Courses from every term are pooled so retake rules can see repeats, then
    computed as one weighted average (not an average of semester GPAs).
    """
    pooled: List[Course] = []
    for index, term in enumerate(terms):
        for c in term:
            pooled.append(c if c.term else Course(c.name, c.credits, c.grade, c.course_key, index + 1))
    return calculate_gpa(pooled, policy)


def required_gpa(current: GpaResult, upcoming_credits, target_cgpa, policy: Policy) -> Decimal:
    """GPA needed over `upcoming_credits` to reach `target_cgpa`.

    Valid for policies where retakes do not change earlier terms. Returns an
    exact Decimal; the caller decides whether it is achievable (compare it
    with the policy's maximum grade point).
    """
    upcoming = to_decimal(upcoming_credits)
    target = to_decimal(target_cgpa)
    if upcoming <= 0:
        raise InvalidCreditError('Upcoming credits must be greater than zero.')
    needed_points = target * (current.counted_credits + upcoming) - current.quality_points
    return needed_points / upcoming


def max_grade_point(policy: Policy) -> Decimal:
    return max((r.points for r in policy.grades.values() if r.counts_in_gpa), default=ZERO)
