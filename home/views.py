from django.shortcuts import render, redirect, get_object_or_404
from .models import Subject
from .forms import SubjectForm
from django.http import HttpResponse, JsonResponse, HttpResponseRedirect
from django.contrib import messages
from django.contrib.auth import login, authenticate
from django.contrib.auth.decorators import login_required 
from django.contrib.auth.models import User
from django.contrib.auth import logout
from django.utils.http import url_has_allowed_host_and_scheme

from calculator.engine import Course, calculate_gpa
from calculator.policies import LEGACY_10_POINT


def _user_subjects(request):
    """Subjects owned by the logged-in user (data isolation)."""
    return Subject.objects.filter(user=request.user).order_by('id')


def _summarize(subjects):
    """CGPA and credit totals via the calculation engine (legacy 10-point scale)."""
    courses = [Course(s.name, s.credit, s.grade) for s in subjects]
    result = calculate_gpa(courses, LEGACY_10_POINT)
    return result


def _save_subject_for(request, form):
    subject = form.save(commit=False)
    subject.user = request.user
    subject.save()
    return subject


@login_required(login_url='/login/')
def cgpa_calculator(request):
    form = SubjectForm()

    if request.method == 'POST':
        form = SubjectForm(request.POST)
        if form.is_valid():
            _save_subject_for(request, form)
            return redirect('cgpa_calculator')

    subjects = _user_subjects(request)
    summary = _summarize(subjects)

    context = {
        'subjects': subjects,
        'form': form,
        'cgpa': summary.rounded,
        'total_credits': summary.counted_credits,
    }

    return render(request, 'index.html', context)


@login_required(login_url='/login/')
def edit_subject(request, subject_id):
    subject = get_object_or_404(Subject, id=subject_id, user=request.user)

    if request.method == 'POST':
        form = SubjectForm(request.POST, instance=subject)
        if form.is_valid():
            form.save()
            return redirect('cgpa_calculator')
    else:
        form = SubjectForm(instance=subject)

    context = {
        'form': form,
        'subject_id': subject_id,
    }

    return render(request, 'edit_subject.html', context)

@login_required(login_url='/login/')
def delete_subject(request, subject_id):
    subject = get_object_or_404(Subject, id=subject_id, user=request.user)
    subject.delete()
    return redirect('cgpa_calculator')


@login_required(login_url='/login/')
def result(request):
    subjects = _user_subjects(request)
    summary = _summarize(subjects)

    context = {
        'subjects': subjects,
        'cgpa': summary.rounded,
        'total_credits': summary.counted_credits,
    }

    return render(request, 'pdf.html', context)


#login page for user
def login_page(request):
    if request.method == "POST":
        try:
            username = request.POST.get('username')
            password = request.POST.get('password')
            user_obj = User.objects.filter(username=username)
            if not user_obj.exists():
                messages.error(request, "Username not found")
                return redirect('/login/')
            user_obj = authenticate(username=username, password=password)
            if user_obj:
                login(request, user_obj)
                next_url = request.POST.get('next') or request.GET.get('next')
                if next_url and url_has_allowed_host_and_scheme(
                        next_url, allowed_hosts={request.get_host()},
                        require_https=request.is_secure()):
                    return redirect(next_url)
                return redirect('cgpa_calculator')
            messages.error(request, "Wrong Password")
            return redirect('/login/')
        except Exception as e:
            messages.error(request, "Something went wrong")
            return redirect('/register/')
    return render(request, "login.html")


#register page for user
def register_page(request):
    if request.method == "POST":
        try:
            username = request.POST.get('username')
            password = request.POST.get('password')
            user_obj = User.objects.filter(username=username)
            if user_obj.exists():
                messages.error(request, "Username is taken")
                return redirect('/register/')
            user_obj = User.objects.create(username=username)
            user_obj.set_password(password)
            user_obj.save()
            messages.success(request, "Account created")
            return redirect('/login')
        except Exception as e:
            messages.error(request, "Something went wrong")
            return redirect('/register')
    return render(request, "register.html")


#logout function
def custom_logout(request):
    logout(request)
    return redirect('login')