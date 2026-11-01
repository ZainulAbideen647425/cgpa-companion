"""Built-in policies.

LEGACY_10_POINT reproduces what the original CGPA Companion calculated
(S=10 ... F=0). It is NOT a claim about any university's official policy.
Official university policies are added in Phase 3 with a cited source.
"""
from decimal import Decimal

from .engine import GradeRule, Policy

LEGACY_10_POINT = Policy(
    key='legacy-10-point',
    name='Legacy 10-point scale (original CGPA Companion)',
    grades={
        'S': GradeRule('S', Decimal('10')),
        'A': GradeRule('A', Decimal('9')),
        'B': GradeRule('B', Decimal('8')),
        'C': GradeRule('C', Decimal('7')),
        'D': GradeRule('D', Decimal('6')),
        'F': GradeRule('F', Decimal('0'), is_pass=False),
    },
    source='Original project code (home/views.py GRADE_POINTS)',
    verification_status='unverified',
)
