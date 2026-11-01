"""Business logic for student records. Views stay thin; the engine does the maths."""
from dataclasses import dataclass
from decimal import Decimal, ROUND_CEILING
from typing import List

from calculator.engine import (
    Course, GpaResult, calculate_cgpa, calculate_gpa, max_grade_point, required_gpa,
)
from calculator.policies import get_policy

from .models import Semester


def to_engine_courses(semester: Semester) -> List[Course]:
    return [
        Course(
            name=c.name,
            credits=c.credit_hours,
            grade=c.grade or None,
            course_key=c.code.strip().lower(),
            term=semester.position or semester.id,
        )
        for c in semester.courses.all()
    ]


@dataclass
class SemesterRow:
    semester: Semester
    result: GpaResult
    cgpa_after: GpaResult
    course_count: int


def build_overview(user, policy=None):
    """Per-semester GPA, running CGPA and the final cumulative result for a user."""
    policy = policy or get_policy()
    semesters = list(Semester.objects.filter(user=user).prefetch_related('courses'))
    rows, terms = [], []
    for sem in semesters:
        courses = to_engine_courses(sem)
        terms.append(courses)
        rows.append(SemesterRow(
            semester=sem,
            result=calculate_gpa(courses, policy),
            cgpa_after=calculate_cgpa(terms, policy),
            course_count=len(courses),
        ))
    cumulative = calculate_cgpa(terms, policy)
    return {
        'rows': rows,
        'cumulative': cumulative,
        'chart': build_chart(rows, policy),
        'policy': policy,
    }


def build_chart(rows, policy, width=600, height=220, pad=34):
    """Server-side SVG coordinates for the GPA/CGPA trend (no JS or chart library)."""
    graded = [r for r in rows if r.result.counted_credits > 0]
    top = float(max_grade_point(policy)) or 1.0
    plot_w, plot_h = width - 2 * pad, height - 2 * pad

    def y(v):
        return round(pad + plot_h * (1 - float(v) / top), 1)

    def x(i, n):
        return round(pad + (plot_w / 2 if n == 1 else plot_w * i / (n - 1)), 1)

    n = len(graded)
    dots = [{'x': x(i, n), 'y': y(r.result.gpa), 'cy': y(r.cgpa_after.gpa),
             'label': r.semester.name, 'gpa': r.result.rounded, 'cgpa': r.cgpa_after.rounded}
            for i, r in enumerate(graded)]
    grid = [{'y': y(top * k / 4), 'label': f'{top * k / 4:g}'} for k in range(5)]
    return {
        'width': width, 'height': height, 'pad': pad, 'dots': dots, 'grid': grid,
        'gpa_points': ' '.join(f"{d['x']},{d['y']}" for d in dots),
        'cgpa_points': ' '.join(f"{d['x']},{d['cy']}" for d in dots),
        'has_data': n > 0, 'multi': n > 1,
    }


def plan_target(user, target, upcoming_credits, policy=None):
    """What GPA is needed over `upcoming_credits` to reach `target` CGPA?"""
    policy = policy or get_policy()
    current = build_overview(user, policy)['cumulative']
    needed = required_gpa(current, upcoming_credits, target, policy)
    highest = max_grade_point(policy)
    best_case = (current.quality_points + highest * upcoming_credits) / (current.counted_credits + upcoming_credits)
    cent = Decimal('0.01')
    if needed <= 0:
        status = 'secured'
    elif needed > highest:
        status = 'unreachable'
    else:
        status = 'reachable'
    return {
        'current': current,
        'needed': needed.quantize(cent, rounding=ROUND_CEILING) if status == 'reachable' else needed,
        'status': status,
        'best_case': policy.quantize(best_case),
        'highest': highest,
    }
