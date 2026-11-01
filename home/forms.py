from django import forms
from .models import Subject


class SubjectForm(forms.ModelForm):
    class Meta:
        model = Subject
        fields = ['name', 'credit', 'grade']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'input', 'placeholder': 'e.g. Data Structures', 'autocomplete': 'off'}),
            'credit': forms.NumberInput(attrs={'class': 'input', 'min': 0, 'inputmode': 'numeric', 'placeholder': '3'}),
            'grade': forms.Select(attrs={'class': 'input'}),
        }
