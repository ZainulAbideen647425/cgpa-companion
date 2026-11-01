from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from calculator.engine import calculate_gpa
from calculator.policies import get_policy

from .forms import CourseForm, PlannerForm, SemesterForm
from .models import CourseEntry, Semester
from .services import build_overview, plan_target, to_engine_courses


def _own_semester(request, pk):
    return get_object_or_404(Semester, pk=pk, user=request.user)


@login_required
def semester_list(request):
    form = SemesterForm(user=request.user)
    if request.method == 'POST':
        form = SemesterForm(request.POST, user=request.user)
        if form.is_valid():
            sem = form.save()
            messages.success(request, f'Added {sem.name}. Now add its courses.')
            return redirect('semester_detail', pk=sem.pk)
    return render(request, 'records/semester_list.html', {'form': form, **build_overview(request.user)})


@login_required
def semester_detail(request, pk):
    semester = _own_semester(request, pk)
    form = CourseForm()
    if request.method == 'POST':
        form = CourseForm(request.POST)
        if form.is_valid():
            course = form.save(commit=False)
            course.semester = semester
            course.save()
            return redirect('semester_detail', pk=semester.pk)
    policy = get_policy()
    result = calculate_gpa(to_engine_courses(semester), policy)
    overview = build_overview(request.user, policy)
    return render(request, 'records/semester_detail.html', {
        'semester': semester, 'courses': semester.courses.all(), 'form': form,
        'result': result, 'cumulative': overview['cumulative'],
    })


@login_required
@require_POST
def semester_delete(request, pk):
    semester = _own_semester(request, pk)
    name = semester.name
    semester.delete()
    messages.success(request, f'Deleted {name}.')
    return redirect('semester_list')


@login_required
def course_edit(request, pk):
    course = get_object_or_404(CourseEntry, pk=pk, semester__user=request.user)
    form = CourseForm(request.POST or None, instance=course)
    if request.method == 'POST' and form.is_valid():
        form.save()
        return redirect('semester_detail', pk=course.semester_id)
    return render(request, 'records/course_form.html', {'form': form, 'course': course})


@login_required
@require_POST
def course_delete(request, pk):
    course = get_object_or_404(CourseEntry, pk=pk, semester__user=request.user)
    semester_id = course.semester_id
    course.delete()
    return redirect('semester_detail', pk=semester_id)


@login_required
def planner(request):
    overview = build_overview(request.user)
    form = PlannerForm(request.GET or None)
    plan = None
    if request.GET and form.is_valid():
        plan = plan_target(request.user, form.cleaned_data['target'], form.cleaned_data['credits'])
    return render(request, 'records/planner.html', {
        'form': form, 'plan': plan, 'cumulative': overview['cumulative'], 'policy': overview['policy'],
    })
