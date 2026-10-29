from django import forms
from .models import Patient, Exam


class PatientForm(forms.ModelForm):
    class Meta:
        model = Patient
        fields = ['name', 'birth_date', 'weight_kg', 'height_m',
                  'gender', 'phone', 'email', 'notes']
        widgets = {
            'birth_date': forms.DateInput(attrs={'type': 'date'}),
            'notes': forms.Textarea(attrs={'rows': 3}),
        }


class ExamForm(forms.ModelForm):
    class Meta:
        model = Exam
        fields = ['patient', 'doctor', 'exam_type', 'exam_date', 'footwear', 'notes']
        widgets = {
            'exam_date': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'notes': forms.Textarea(attrs={'rows': 3}),
        }