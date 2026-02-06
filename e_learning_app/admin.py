from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import (
    User, Course, Enrollment, Payment, Assignment, 
    Submission, Feedback, Attendance, Lesson, 
    Quiz, Question, Choice, QuizSubmission
)

# Branding admin en français
admin.site.site_header = "IFRI - Administration"
admin.site.site_title = "IFRI Admin"
admin.site.index_title = "Tableau de bord"

# ================= 1. LES INLINES (Gestion imbriquée) =================

class ChoiceInline(admin.TabularInline):
    """Permet de définir les réponses directement sous la question."""
    model = Choice
    extra = 4  # Affiche 4 propositions par défaut
    min_num = 2 # Oblige au moins 2 choix

class QuestionInline(admin.TabularInline):
    """Affiche la liste des questions dans la page d'un Quiz."""
    model = Question
    extra = 1
    fields = ['text', 'q_type', 'points', 'order']
    show_change_link = True # Permet d'ouvrir la question pour gérer ses réponses

class QuizInline(admin.TabularInline):
    """
    NOUVEAU : Permet de gérer plusieurs Quiz par leçon.
    Format Tabular pour une vue d'ensemble compacte.
    """
    model = Quiz
    extra = 1
    fields = ['title', 'pass_mark', 'time_limit_mins', 'max_attempts']
    show_change_link = True

class LessonInline(admin.StackedInline):
    """Permet d'ajouter des leçons depuis la page d'un cours."""
    model = Lesson
    extra = 1
    classes = ['collapse']

# ================= 2. CONFIGURATIONS DES QUESTIONS (Le Cœur) =================

@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    """Interface pour configurer une question et ses propositions de réponses."""
    list_display = ['text', 'quiz', 'q_type', 'points', 'order']
    list_filter = ['q_type', 'quiz']
    search_fields = ['text']
    
    inlines = [ChoiceInline] # Permet de définir les réponses ici même
    
    fieldsets = (
        ('Énoncé et Barème', {
            'fields': ('quiz', 'text', 'points', 'q_type', 'order')
        }),
        ('Pédagogie', {
            'fields': ('explanation',),
            'description': "Texte affiché à l'élève dans la correction détaillée."
        }),
    )

# ================= 3. CONFIGURATIONS DES QUIZ (Les Réglages) =================

@admin.register(Quiz)
class QuizAdmin(admin.ModelAdmin):
    """Gestion des paramètres de l'examen."""
    list_display = ['title', 'get_course', 'lesson', 'pass_mark', 'time_limit_mins']
    list_filter = ['lesson__course', 'pass_mark']
    search_fields = ['title', 'lesson__title']
    
    inlines = [QuestionInline]

    def get_course(self, obj):
        return obj.lesson.course if obj.lesson else "Sans cours"
    get_course.short_description = 'Cours'

# ================= 4. AUTRES CONFIGURATIONS =================

@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """Gestion personnalisée des utilisateurs IFRI."""
    list_display = ['username', 'email', 'user_type', 'is_staff']
    list_filter = ['user_type', 'is_staff']
    fieldsets = BaseUserAdmin.fieldsets + (
        ('Infos IFRI', {'fields': ('user_type', 'phone', 'address', 'profile_picture')}),
    )

@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    """Gestion des cours et de leurs leçons."""
    list_display = ['name', 'trainer', 'difficulty_level', 'fee_xof', 'is_active']
    list_filter = ['difficulty_level', 'is_active']
    inlines = [LessonInline]

    def fee_xof(self, obj):
        return f"{obj.fee} XOF" if obj.fee is not None else "-"
    fee_xof.short_description = "Frais (XOF)"

@admin.register(Lesson)
class LessonAdmin(admin.ModelAdmin):
    """Gestion des leçons et de leurs quiz associés."""
    list_display = ['title', 'course', 'order']
    list_filter = ['course']
    # Grâce à la ForeignKey, on peut gérer plusieurs quiz ici
    inlines = [QuizInline]

@admin.register(QuizSubmission)
class QuizSubmissionAdmin(admin.ModelAdmin):
    """Historique des examens (Lecture seule pour la sécurité)."""
    list_display = ['student', 'quiz', 'score', 'is_passed', 'submitted_at']
    readonly_fields = ['student', 'quiz', 'score', 'is_passed', 'submitted_at']

# Enregistrement des modules administratifs restants
@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ['enrollment', 'amount_xof', 'status', 'payment_method', 'payment_date']
    list_filter = ['status', 'payment_method']
    search_fields = ['transaction_id', 'enrollment__student__username', 'enrollment__course__name']

    def amount_xof(self, obj):
        return f"{obj.amount} XOF" if obj.amount is not None else "-"
    amount_xof.short_description = "Montant (XOF)"

admin.site.register(Enrollment)
admin.site.register(Assignment)
admin.site.register(Submission)
admin.site.register(Feedback)
admin.site.register(Attendance)
