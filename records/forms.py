from django import forms

from calculator.policies import get_policy

from .models import CourseEntry, Semester


def grade_choices(policy=None):
    policy = policy or get_policy()
    return [('', 'Not graded yet')] + [(g, g) for g in policy.grades]


class SemesterForm(forms.ModelForm):
    class Meta:
        model = Semester
        fields = ['name']
        widgets = {'name': forms.TextInput(attrs={
            'class': 'input', 'placeholder': 'e.g. Fall 2025', 'autocomplete': 'off'})}

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user

    def clean_name(self):
        name = self.cleaned_data['name'].strip()
        qs = Semester.objects.filter(user=self.user, name__iexact=name)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError('You already have a semester with this name.')
        return name

    def save(self, commit=True):
        sem = super().save(commit=False)
        sem.user = self.user
        if not sem.pk:
            last = Semester.objects.filter(user=self.user).order_by('-position').first()
            sem.position = (last.position if last else 0) + 1
        if commit:
            sem.save()
        return sem


class CourseForm(forms.ModelForm):
    grade = forms.ChoiceField(required=False, widget=forms.Select(attrs={'class': 'input'}))

    class Meta:
        model = CourseEntry
        fields = ['code', 'name', 'credit_hours', 'grade']
        widgets = {
            'code': forms.TextInput(attrs={'class': 'input', 'placeholder': 'e.g. CS-201 (optional)', 'autocomplete': 'off'}),
            'name': forms.TextInput(attrs={'class': 'input', 'placeholder': 'e.g. Data Structures', 'autocomplete': 'off'}),
            'credit_hours': forms.NumberInput(attrs={'class': 'input', 'step': '0.5', 'min': 0, 'max': 30, 'placeholder': '3'}),
        }
        labels = {'code': 'Course code', 'credit_hours': 'Credit hours'}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['grade'].choices = grade_choices()


class PlannerForm(forms.Form):
    target = forms.DecimalField(
        label='Target CGPA', min_value=0, max_digits=4, decimal_places=2,
        widget=forms.NumberInput(attrs={'class': 'input', 'step': '0.01', 'placeholder': '8.50'}))
    credits = forms.DecimalField(
        label='Credit hours you will still take', min_value=0.5, max_value=300, max_digits=5, decimal_places=1,
        widget=forms.NumberInput(attrs={'class': 'input', 'step': '0.5', 'placeholder': '18'}))
