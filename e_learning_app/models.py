from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.validators import MinValueValidator, MaxValueValidator
import uuid # Nécessaire pour générer des codes uniques

# ================= AUTHENTICATION MODELS =================

class User(AbstractUser):
    USER_TYPE_CHOICES = (
        ('student', 'Étudiant'),
        ('trainer', 'Formateur'),
        ('manager', 'Gestionnaire'),
    )
    user_type = models.CharField(max_length=10, choices=USER_TYPE_CHOICES)
    phone = models.CharField(max_length=15, blank=True)
    address = models.TextField(blank=True)
    profile_picture = models.ImageField(upload_to='profiles/', blank=True, null=True)
    
    def __str__(self):
        return f"{self.username} ({self.get_user_type_display()})"

    class Meta:
        verbose_name = "Utilisateur"
        verbose_name_plural = "Utilisateurs"

# ================= COURSE MODELS =================

class Course(models.Model):
    DIFFICULTY_CHOICES = (
        ('beginner', 'Débutant'),
        ('intermediate', 'Intermédiaire'),
        ('advanced', 'Avancé'),
    )
    
    name = models.CharField(max_length=200, verbose_name="Nom du cours")
    description = models.TextField(verbose_name="Description")
    duration_weeks = models.IntegerField(validators=[MinValueValidator(1)], verbose_name="Durée (semaines)")
    difficulty_level = models.CharField(max_length=20, choices=DIFFICULTY_CHOICES, verbose_name="Niveau de difficulté")
    fee = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Frais (XOF)")
    trainer = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, 
                                related_name='courses_teaching', limit_choices_to={'user_type': 'trainer'},
                                verbose_name="Formateur")
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True, verbose_name="Actif")
    
    def __str__(self):
        return self.name
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = "Cours"
        verbose_name_plural = "Cours"

class Lesson(models.Model):
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='lessons')
    title = models.CharField(max_length=200)
    content_text = models.TextField(
        blank=True, 
        null=True, 
        help_text="Rédigez votre cours en Markdown (Titres: #, Gras: **, Tableaux supportés)"
    )
    pdf_file = models.FileField(
        upload_to='course_pdfs/', 
        blank=True, 
        null=True,
        help_text="Téléchargez un support de cours au format PDF"
    )
    order = models.PositiveIntegerField(
        default=0, 
        help_text="Ordre d'affichage de la leçon dans le cours"
    )

    class Meta:
        ordering = ['order']
        verbose_name = "Leçon"
        verbose_name_plural = "Leçons"

    def __str__(self):
        return f"{self.course.name} - {self.title}"

# ================= ENROLLMENT & PROGRESS =================

class Enrollment(models.Model):
    STATUS_CHOICES = (
        ('pending', 'En attente'),
        ('active', 'Actif'),
        ('completed', 'Terminé'),
        ('dropped', 'Abandonné'),
    )
    
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='enrollments',
                                limit_choices_to={'user_type': 'student'})
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='enrollments')
    enrollment_date = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    progress_percentage = models.IntegerField(default=0, validators=[MinValueValidator(0), MaxValueValidator(100)])
    completed_lessons = models.ManyToManyField(Lesson, blank=True, related_name='completed_by')
    
    class Meta:
        unique_together = ('student', 'course')
        ordering = ['-enrollment_date']
        verbose_name = "Inscription"
        verbose_name_plural = "Inscriptions"
    
    def __str__(self):
        return f"{self.student.username} - {self.course.name}"

    def update_progress(self):
        """Calcule et enregistre le pourcentage de progression."""
        total_lessons = self.course.lessons.count()
        if total_lessons > 0:
            done = self.completed_lessons.count()
            self.progress_percentage = int((done / total_lessons) * 100)
            # Marquer comme terminé si 100%
            if self.progress_percentage == 100:
                self.status = 'completed'
            self.save()

# ================= FINANCE & ASSIGNMENTS =================

class Payment(models.Model):
    PAYMENT_STATUS_CHOICES = (
        ('pending', 'En attente'),
        ('completed', 'Terminé'),
        ('failed', 'Échoué'),
        ('refunded', 'Remboursé'),
    )
    PAYMENT_METHOD_CHOICES = (
        ('credit_card', 'Carte de crédit'),
        ('debit_card', 'Carte de débit'),
        ('upi', 'UPI'),
        ('net_banking', 'Virement bancaire'),
        ('cash', 'Espèces'),
    )
    
    enrollment = models.ForeignKey(Enrollment, on_delete=models.CASCADE, related_name='payments')
    amount = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Montant (XOF)")
    payment_date = models.DateTimeField(auto_now_add=True)
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES, verbose_name="Méthode de paiement")
    transaction_id = models.CharField(max_length=100, unique=True, blank=True)
    status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='pending', verbose_name="Statut")
    notes = models.TextField(blank=True)
    
    def __str__(self):
        return f"Paiement pour {self.enrollment} - {self.amount} XOF"

    class Meta:
        verbose_name = "Paiement"
        verbose_name_plural = "Paiements"

class Assignment(models.Model):
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='assignments')
    title = models.CharField(max_length=200)
    description = models.TextField()
    due_date = models.DateTimeField()
    max_marks = models.IntegerField(validators=[MinValueValidator(1)])
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, limit_choices_to={'user_type': 'trainer'})
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.course.name} - {self.title}"

    class Meta:
        verbose_name = "Devoir"
        verbose_name_plural = "Devoirs"

class Submission(models.Model):
    assignment = models.ForeignKey(Assignment, on_delete=models.CASCADE, related_name='submissions')
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='submissions',
                                limit_choices_to={'user_type': 'student'})
    submission_file = models.FileField(upload_to='submissions/')
    submission_text = models.TextField(blank=True)
    submitted_at = models.DateTimeField(auto_now_add=True)
    marks_obtained = models.IntegerField(null=True, blank=True)
    feedback = models.TextField(blank=True)
    graded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                  related_name='graded_submissions', limit_choices_to={'user_type': 'trainer'})
    graded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Soumission"
        verbose_name_plural = "Soumissions"

# ================= FEEDBACK & ATTENDANCE =================

class Feedback(models.Model):
    RATING_CHOICES = [(i, str(i)) for i in range(1, 6)]
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='feedbacks_given',
                                limit_choices_to={'user_type': 'student'})
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='feedbacks')
    rating = models.IntegerField(choices=RATING_CHOICES)
    comment = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Avis"
        verbose_name_plural = "Avis"

class Attendance(models.Model):
    STATUS_CHOICES = (
        ('present', 'Présent'),
        ('absent', 'Absent'),
        ('late', 'En retard'),
    )
    
    enrollment = models.ForeignKey(Enrollment, on_delete=models.CASCADE, related_name='attendances')
    date = models.DateField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES)
    notes = models.TextField(blank=True) 
    marked_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True,
                                  limit_choices_to={'user_type': 'trainer'})
    
    class Meta:
        unique_together = ('enrollment', 'date')
        ordering = ['-date']
        verbose_name = "Présence"
        verbose_name_plural = "Présences"
    
    def __str__(self):
        return f"{self.enrollment.student.username} - {self.date} - {self.status}"

# ================= QUIZ MODULE (MULTI-QUIZ PAR LEÇON) =================

class Quiz(models.Model):
    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE, related_name='quizzes', null=True, blank=True)
    title = models.CharField(max_length=200, verbose_name="Nom de l'évaluation")
    description = models.TextField(blank=True, verbose_name="Instructions pour l'élève")
    
    pass_mark = models.IntegerField(default=50, help_text="Score minimum requis (%)", verbose_name="Note de passage")
    time_limit_mins = models.PositiveIntegerField(default=15, help_text="Temps alloué en minutes", verbose_name="Durée")
    max_attempts = models.PositiveIntegerField(default=1, verbose_name="Nombre de tentatives")
    
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Quiz"
        verbose_name_plural = "Quiz"

    def __str__(self):
        return self.title

class Question(models.Model):
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name='questions')
    text = models.TextField(verbose_name="Énoncé (La question)")
    q_type = models.CharField(max_length=3, choices=(('qcu', 'Choix Unique'), ('qcm', 'Choix Multiples')), default='qcu', verbose_name="Format")
    points = models.IntegerField(default=1, verbose_name="Points")
    explanation = models.TextField(blank=True, verbose_name="Explication corrective")
    order = models.PositiveIntegerField(default=0, verbose_name="Position")

    class Meta:
        ordering = ['order']
        verbose_name = "Question d'examen"

    def __str__(self):
        return f"Q: {self.text[:50]}"

class Choice(models.Model):
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='choices')
    text = models.CharField(max_length=255, verbose_name="Texte de la réponse")
    is_correct = models.BooleanField(default=False, verbose_name="Réponse vraie ?")

    class Meta:
        verbose_name = "Option de réponse"
        verbose_name_plural = "Options de réponse"

    def __str__(self):
        return self.text

class QuizSubmission(models.Model):
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='quiz_results')
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE)
    score = models.FloatField(verbose_name="Score final (%)")
    is_passed = models.BooleanField(default=False)
    submitted_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.student.username} - {self.quiz.title} ({self.score}%)"

    class Meta:
        verbose_name = "Résultat de quiz"
        verbose_name_plural = "Résultats de quiz"

# ================= CERTIFICATION MODULE =================

class Certificate(models.Model):
    """Modèle pour enregistrer les diplômes obtenus par les élèves."""
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='certificates')
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='certificates')
    enrollment = models.OneToOneField(Enrollment, on_delete=models.CASCADE, related_name='certificate')
    
    issue_date = models.DateTimeField(auto_now_add=True)
    certificate_code = models.CharField(max_length=50, unique=True, blank=True)

    def save(self, *args, **kwargs):
        """Génère un code de vérification unique à la création."""
        if not self.certificate_code:
            uid = str(uuid.uuid4()).upper().split('-')
            self.certificate_code = f"AK-{uid[0][:4]}-{uid[1]}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Diplôme - {self.student.username} - {self.course.name}"

    class Meta:
        verbose_name = "Certificat"
        verbose_name_plural = "Certificats"
