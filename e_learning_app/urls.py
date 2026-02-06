from django.urls import path
from . import views

urlpatterns = [
    # ================= ACCUEIL ET AUTHENTIFICATION =================
    path('', views.home, name='home'),
    path('student/register/', views.student_register, name='student_register'),
    path('trainer/register/', views.trainer_register, name='trainer_register'),
    path('login/', views.user_login, name='login'),
    path('logout/', views.user_logout, name='logout'),
    
    # ================= URLS ÉTUDIANT (WORKSPACE) =================
    path('student/dashboard/', views.student_dashboard, name='student_dashboard'),
    path('student/enroll/<int:course_id>/', views.student_enroll_course, name='student_enroll_course'),
    path('student/payment/<int:enrollment_id>/', views.student_make_payment, name='student_make_payment'),
    path('student/courses/', views.student_view_courses, name='student_view_courses'),
    
    # --- Accès au contenu (Salle de classe) ---
    path('student/course/<int:course_id>/content/', views.course_lessons_list, name='course_content'),
    
    # --- Détail d'une leçon (Markdown + PDF) ---
    path('lesson/<int:lesson_id>/', views.lesson_detail, name='lesson_detail'),
    
    # --- Validation de progression ---
    path('lesson/<int:lesson_id>/complete/', views.complete_lesson, name='complete_lesson'),

    # ================= MODULE QUIZ (EXAMENS) =================
    path('quiz/<int:quiz_id>/take/', views.take_quiz, name='take_quiz'),
    path('quiz/<int:quiz_id>/submit/', views.submit_quiz, name='submit_quiz'),
    path('quiz/result/<int:submission_id>/', views.quiz_result, name='quiz_result'),
    
    # ================= DEVOIRS ET PROGRESSION ÉTUDIANT =================
    path('student/assignments/', views.student_view_assignments, name='student_view_assignments'),
    path('student/submit/<int:assignment_id>/', views.student_submit_assignment, name='student_submit_assignment'),
    path('student/feedback/', views.student_give_feedback, name='student_give_feedback'),
    path('student/progress/', views.student_track_progress, name='student_track_progress'),

    # ================= GESTION DU COURS PAR L'ENSEIGNANT (TRAINER CRUD) =================
    # Ces routes donnent l'autonomie totale au formateur sur ses formations
    path('trainer/my-courses/', views.trainer_course_list, name='trainer_course_list'),
    path('trainer/course/add/', views.trainer_course_create, name='trainer_course_create'),
    path('trainer/course/<int:course_id>/edit/', views.trainer_course_edit, name='trainer_course_edit'),
    
    # --- Gestion des leçons ---
    path('trainer/course/<int:course_id>/lesson/add/', views.trainer_lesson_add, name='trainer_lesson_add'),
    path('trainer/lesson/<int:lesson_id>/edit/', views.trainer_lesson_edit, name='trainer_lesson_edit'),
    
    # ================= URLS FORMATEUR (AUTRES GESTIONS) =================
    path('trainer/dashboard/', views.trainer_dashboard, name='trainer_dashboard'),
    path('trainer/students/', views.trainer_view_students, name='trainer_view_students'),
    path('trainer/assignment/create/', views.trainer_create_assignment, name='trainer_create_assignment'),
    path('trainer/assignments/', views.trainer_manage_assignments, name='trainer_manage_assignments'),
    path('trainer/submissions/<int:assignment_id>/', views.trainer_view_submissions, name='trainer_view_submissions'),
    path('trainer/grade/<int:submission_id>/', views.trainer_grade_submission, name='trainer_grade_submission'),
    path('trainer/attendance/', views.trainer_mark_attendance, name='trainer_mark_attendance'),
    path('trainer/progress/<int:enrollment_id>/', views.trainer_update_progress, name='trainer_update_progress'),

    # ================= GESTION DES QUIZ (TRAINER) =================
    path('trainer/quizzes/', views.trainer_quiz_list, name='trainer_quiz_list'),
    path('trainer/quiz/add/', views.trainer_quiz_create, name='trainer_quiz_create'),
    path('trainer/quiz/<int:quiz_id>/edit/', views.trainer_quiz_edit, name='trainer_quiz_edit'),
    path('trainer/quiz/<int:quiz_id>/delete/', views.trainer_quiz_delete, name='trainer_quiz_delete'),
    
    # --- Gestion des questions & réponses ---
    path('trainer/quiz/<int:quiz_id>/question/add/', views.trainer_question_manage, name='trainer_question_add'),
    path('trainer/quiz/<int:quiz_id>/question/<int:question_id>/edit/', views.trainer_question_manage, name='trainer_question_edit'),

    # ================= CERTIFICATION (ACTIVÉ) =================
    # Route pour générer le certificat une fois le cours terminé à 100%
    path('student/course/<int:course_id>/certificate/', views.generate_certificate, name='generate_certificate'),
    path('student/course/<int:course_id>/certificate/view/', views.view_certificate, name='view_certificate'),
    
    # ================= URLS GESTIONNAIRE (MANAGER) =================
    path('manager/dashboard/', views.manager_dashboard, name='manager_dashboard'),
    path('manager/course/add/', views.manager_add_course, name='manager_add_course'),
    path('manager/courses/', views.manager_manage_courses, name='manager_manage_courses'),
    path('manager/allot-trainer/<int:course_id>/', views.manager_allot_trainer, name='manager_allot_trainer'),
    path('manager/feedbacks/', views.manager_view_feedbacks, name='manager_view_feedbacks'),
    path('manager/progress/', views.manager_analyse_progress, name='manager_analyse_progress'),
    path('manager/payments/', views.manager_view_payments, name='manager_view_payments'),
    path('manager/payment/update/<int:payment_id>/', views.manager_update_payment, name='manager_update_payment'),
    path('student/payment/webhook/', views.fedapay_webhook, name='fedapay_webhook'),
    path('student/payment/callback/', views.fedapay_callback, name='fedapay_callback'),
]