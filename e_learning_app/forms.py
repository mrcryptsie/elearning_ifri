from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.forms import inlineformset_factory
from .models import (
    User, Course, Enrollment, Payment, Assignment, 
    Submission, Feedback, Attendance, Quiz, Question, Choice, Lesson
)

# ================= AUTHENTICATION FORMS =================

class StudentRegistrationForm(UserCreationForm):
    email = forms.EmailField(required=True, widget=forms.EmailInput(attrs={'class': 'form-control'}))
    phone = forms.CharField(max_length=15, required=False, widget=forms.TextInput(attrs={'class': 'form-control'}))
    address = forms.CharField(widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3}), required=False)
    
    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email', 'phone', 'address']
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            css = field.widget.attrs.get('class', '')
            if 'form-control' not in css and not isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs['class'] = f"{css} form-control".strip()
    
    def save(self, commit=True):
        user = super().save(commit=False)
        user.user_type = 'student'
        if commit:
            user.save()
        return user


class TrainerRegistrationForm(UserCreationForm):
    email = forms.EmailField(required=True, widget=forms.EmailInput(attrs={'class': 'form-control'}))
    phone = forms.CharField(max_length=15, required=False, widget=forms.TextInput(attrs={'class': 'form-control'}))
    address = forms.CharField(widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3}), required=False)
    
    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email', 'phone', 'address']
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            css = field.widget.attrs.get('class', '')
            if 'form-control' not in css and not isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs['class'] = f"{css} form-control".strip()
    
    def save(self, commit=True):
        user = super().save(commit=False)
        user.user_type = 'trainer'
        if commit:
            user.save()
        return user


class CustomLoginForm(AuthenticationForm):
    username = forms.CharField(widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': "Nom d'utilisateur"}))
    password = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Mot de passe'}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            css = field.widget.attrs.get('class', '')
            if 'form-control' not in css and not isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs['class'] = f"{css} form-control".strip()


# ================= TRAINER CORE MANAGEMENT (COURS & LEÇONS) =================

class TrainerCourseForm(forms.ModelForm):
    """Permet à l'enseignant de créer ou modifier son cours."""
    class Meta:
        model = Course
        fields = ['name', 'description', 'duration_weeks', 'difficulty_level', 'fee', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: Intelligence Artificielle pour débutants'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'duration_weeks': forms.NumberInput(attrs={'class': 'form-control'}),
            'difficulty_level': forms.Select(attrs={'class': 'form-control'}),
            'fee': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

class LessonForm(forms.ModelForm):
    """Permet à l'enseignant de rédiger le contenu d'un module."""
    class Meta:
        model = Lesson
        fields = ['title', 'content_text', 'pdf_file', 'order']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Titre de la leçon'}),
            'content_text': forms.Textarea(attrs={'class': 'form-control', 'rows': 10, 'placeholder': 'Utilisez Markdown pour formater votre texte...'}),
            'pdf_file': forms.FileInput(attrs={'class': 'form-control'}),
            'order': forms.NumberInput(attrs={'class': 'form-control'}),
        }


# ============= SYSTEM MANAGEMENT FORMS (ADMIN/MANAGER) =============

class CourseForm(forms.ModelForm):
    class Meta:
        model = Course
        fields = ['name', 'description', 'duration_weeks', 'difficulty_level', 'fee', 'trainer', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'duration_weeks': forms.NumberInput(attrs={'class': 'form-control'}),
            'difficulty_level': forms.Select(attrs={'class': 'form-control'}),
            'fee': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'trainer': forms.Select(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

class EnrollmentForm(forms.ModelForm):
    class Meta:
        model = Enrollment
        fields = ['course']
        widgets = {
            'course': forms.Select(attrs={'class': 'form-control'}),
        }

class PaymentForm(forms.ModelForm):
    class Meta:
        model = Payment
        fields = ['amount', 'payment_method', 'transaction_id', 'notes']
        widgets = {
            'amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'payment_method': forms.Select(attrs={'class': 'form-control'}),
            'transaction_id': forms.TextInput(attrs={'class': 'form-control'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

# ================= QUIZ MODULE FORMS (POUR LE TEACHER) =================

class QuizForm(forms.ModelForm):
    class Meta:
        model = Quiz
        fields = ['lesson', 'title', 'description', 'pass_mark', 'time_limit_mins', 'max_attempts']
        widgets = {
            'lesson': forms.Select(attrs={'class': 'form-control'}),
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: Quiz Final - Module 1'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'pass_mark': forms.NumberInput(attrs={'class': 'form-control'}),
            'time_limit_mins': forms.NumberInput(attrs={'class': 'form-control'}),
            'max_attempts': forms.NumberInput(attrs={'class': 'form-control'}),
        }

class QuestionForm(forms.ModelForm):
    class Meta:
        model = Question
        fields = ['text', 'q_type', 'points', 'explanation', 'order']
        widgets = {
            'text': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Saisissez votre question ici...'}),
            'q_type': forms.Select(attrs={'class': 'form-control'}),
            'points': forms.NumberInput(attrs={'class': 'form-control'}),
            'explanation': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Expliquez pourquoi la réponse est correcte...'}),
            'order': forms.NumberInput(attrs={'class': 'form-control'}),
        }

class ChoiceForm(forms.ModelForm):
    class Meta:
        model = Choice
        fields = ['text', 'is_correct']
        widgets = {
            'text': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Réponse possible'}),
            'is_correct': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

ChoiceFormSet = inlineformset_factory(
    Question, 
    Choice, 
    form=ChoiceForm,
    extra=4,
    can_delete=True
)

# ================= ASSIGNMENTS & EVALUATION FORMS =================

class AssignmentForm(forms.ModelForm):
    class Meta:
        model = Assignment
        fields = ['course', 'title', 'description', 'due_date', 'max_marks']
        widgets = {
            'course': forms.Select(attrs={'class': 'form-control'}),
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'due_date': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
            'max_marks': forms.NumberInput(attrs={'class': 'form-control'}),
        }

class SubmissionForm(forms.ModelForm):
    class Meta:
        model = Submission
        fields = ['submission_file', 'submission_text']
        widgets = {
            'submission_file': forms.FileInput(attrs={'class': 'form-control'}),
            'submission_text': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
        }

class GradeSubmissionForm(forms.ModelForm):
    class Meta:
        model = Submission
        fields = ['marks_obtained', 'feedback']
        widgets = {
            'marks_obtained': forms.NumberInput(attrs={'class': 'form-control'}),
            'feedback': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
        }

class FeedbackForm(forms.ModelForm):
    class Meta:
        model = Feedback
        fields = ['course', 'rating', 'comment']
        widgets = {
            'course': forms.Select(attrs={'class': 'form-control'}),
            'rating': forms.Select(attrs={'class': 'form-control'}),
            'comment': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
        }

class AttendanceForm(forms.ModelForm):
    class Meta:
        model = Attendance
        fields = ['enrollment', 'date', 'status', 'notes']
        widgets = {
            'enrollment': forms.Select(attrs={'class': 'form-control'}),
            'date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'status': forms.Select(attrs={'class': 'form-control'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }

class UpdatePaymentForm(forms.ModelForm):
    class Meta:
        model = Payment
        fields = ['amount', 'payment_method', 'status', 'transaction_id', 'notes']
        widgets = {
            'amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'payment_method': forms.Select(attrs={'class': 'form-control'}),
            'status': forms.Select(attrs={'class': 'form-control'}),
            'transaction_id': forms.TextInput(attrs={'class': 'form-control'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

class TrainerAllotmentForm(forms.ModelForm):
    class Meta:
        model = Course
        fields = ['trainer']
        widgets = {
            'trainer': forms.Select(attrs={'class': 'form-control'}),
        }
