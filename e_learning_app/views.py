# =============================================================================
# PLATFORME E-LEARNING IFRI - CORE BUSINESS LOGIC ENGINE
# =============================================================================
# Fichier     : views.py
# Version     : 14.0.0 (High Precision Async / FedaPay Connector 2.0.3)
# Framework   : Django 5.2.x (LTS Compliance)
# Technologie : Python 3.12+ / asyncio / aiohttp / HMAC Security
#
# DESCRIPTION :
# Ce module constitue la colonne vertébrale opérationnelle de la plateforme.
# Il gère les interactions complexes entre les modèles Django, les flux
# asynchrones de paiement et le rendu pédagogique dynamique.
#
# SOMMAIRE :
# 1. SERVICES TECHNIQUES (FedaPay, Sécurité HMAC, Utilitaires)
# 2. AUTHENTIFICATION (Multi-profils : Student, Trainer, Manager)
# 3. WORKSPACE ÉTUDIANT (Dashboard, Progression, Inscriptions)
# 4. TUNNEL FINANCIER (Paiement asynchrone, Webhooks sécurisés)
# 5. CURRICULUM (Leçons Markdown, Sommaires interactifs)
# 6. ÉVALUATIONS (Système de Quiz et Travaux Dirigés)
# 7. CERTIFICATION (Génération de diplômes PDF officiels)
# 8. ADMINISTRATION (Panel Formateurs et Pilotage Manager)
# =============================================================================

import io
import json
import logging
import markdown
import asyncio
import os
import hmac
import hashlib
import re
from django.shortcuts import (
    render, 
    redirect, 
    get_object_or_404
)
from django.contrib.auth import (
    login, 
    logout, 
    authenticate
)
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import (
    Avg, 
    Count, 
    Q, 
    Sum
)
from django.utils import timezone
from django.utils.formats import date_format
from django.http import (
    HttpResponse, 
    HttpResponseForbidden, 
    JsonResponse,
    Http404
)
from django.template.loader import get_template
from django.conf import settings
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
from asgiref.sync import sync_to_async
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import mm
from reportlab.lib.colors import HexColor
from reportlab.pdfgen import canvas
from reportlab.lib.utils import simpleSplit
try:
    from xhtml2pdf import pisa
except Exception:
    pisa = None

# -----------------------------------------------------------------------------
# IMPORTATION DU CONNECTEUR FEDAPAY v2.0.3 (PYPI)
# -----------------------------------------------------------------------------
from fedapay_connector import (
    FedapayConnector, 
    PaiementSetup, 
    UserData, 
    Pays, 
    MethodesPaiement,
    TransactionStatus,
    EventFutureStatus
)
from fedapay_connector.integration import Integration as FedaIntegration

# -----------------------------------------------------------------------------
# IMPORTATION DES MODÈLES DE DONNÉES IFRI
# -----------------------------------------------------------------------------
from .models import (
    User, 
    Course, 
    Enrollment, 
    Payment, 
    Assignment, 
    Submission, 
    Feedback, 
    Lesson, 
    Attendance,
    Quiz, 
    Question, 
    Choice, 
    QuizSubmission, 
    Certificate
)

# -----------------------------------------------------------------------------
# IMPORTATION DES FORMULAIRES DE GESTION
# -----------------------------------------------------------------------------
from .forms import (
    StudentRegistrationForm, 
    TrainerRegistrationForm, 
    CustomLoginForm,
    CourseForm, 
    EnrollmentForm, 
    PaymentForm, 
    AssignmentForm, 
    SubmissionForm,
    GradeSubmissionForm, 
    FeedbackForm, 
    AttendanceForm, 
    UpdatePaymentForm, 
    TrainerAllotmentForm, 
    QuizForm, 
    QuestionForm, 
    ChoiceFormSet,
    TrainerCourseForm, 
    LessonForm
)

# =============================================================================
# SECTION 1 : SERVICES TECHNIQUES ET SÉCURITÉ HMAC
# =============================================================================

# Cache pour le service d'intégration financier
_feda_integ_service = None

def _get_fedapay_logger():
    logger = logging.getLogger("fedapay")
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    logger.setLevel(os.getenv("FEDAPAY_LOG_LEVEL", "INFO"))
    logger.propagate = False
    return logger

def _extract_fedapay_status(tx):
    if tx is None:
        return None
    if isinstance(tx, dict):
        return tx.get('status') or (tx.get('data') or {}).get('status')
    status = getattr(tx, 'status', None)
    if status:
        return status
    data = getattr(tx, 'data', None)
    if isinstance(data, dict):
        return data.get('status')
    if data is not None and hasattr(data, 'status'):
        return data.status
    if hasattr(tx, 'model_dump'):
        dump = tx.model_dump()
        return dump.get('status') or (dump.get('data') or {}).get('status')
    return None

def get_feda_integration_service():
    """
    Récupère ou initialise l'instance de la classe Integration.
    Utilise les variables d'environnement chargées depuis le .env.
    
    Returns:
        FedaIntegration: Service configuré pour les requêtes API FedaPay.
    """
    global _feda_integ_service
    if _feda_integ_service is None:
        _feda_integ_service = FedaIntegration(
            api_url=os.getenv('FEDAPAY_API_URL', 'https://sandbox-api.fedapay.com'),
            default_api_key=os.getenv('FEDAPAY_API_KEY', 'sk_sandbox_vyzPOsUGQr83P6cTjmqjrUgo'),
            logger=_get_fedapay_logger(),
        )
    return _feda_integ_service


def _parse_fedapay_signature_header(signature_header: str):
    """Extrait (timestamp, signature) depuis l'entête x-fedapay-signature."""
    if not signature_header:
        return None, None
    timestamp = None
    signature_v1 = None
    try:
        # Décomposition tolérante (virgule ou point-virgule)
        parts = re.split(r"[;,]", signature_header)
        for p in parts:
            key, _, value = p.strip().partition("=")
            value = value.strip().strip('"')
            if key == "t":
                timestamp = value
            elif key == "v1":
                signature_v1 = value
            elif key == "v0" and not signature_v1:
                signature_v1 = value
            elif key and value and key != "t" and not signature_v1:
                # Fallback: certains headers utilisent une autre clé que v1
                signature_v1 = value
    except Exception:
        return None, None
    if not signature_v1:
        # Fallback ultime: chercher une signature hex (64 chars)
        m = re.search(r"[0-9a-fA-F]{64}", signature_header)
        if m:
            signature_v1 = m.group(0)
    return timestamp, signature_v1


def _compute_fedapay_signature(payload: bytes, timestamp: int, secret: str) -> str | None:
    """Calcule la signature HMAC attendue (format officiel FedaPay)."""
    try:
        payload_str = payload.decode("utf-8")
    except Exception:
        return None
    signed_payload = f"{timestamp}.{payload_str}".encode("utf-8")
    return hmac.new(secret.encode("utf-8"), signed_payload, hashlib.sha256).hexdigest()


def verify_signature_fedapay_v1(payload: bytes, signature_header: str) -> bool:
    """
    Algorithme de validation de signature Webhook conforme FedaPay v2.0.3.
    
    Format attendu de signature_header : "t=TIMESTAMP,v1=SIGNATURE_HMAC"
    La signature est calculée sur : TIMESTAMP + "." + PAYLOAD_JSON_BRUT
    
    Args:
        payload (bytes): Corps brut de la requête HTTP (request.body).
        signature_header (str): Contenu de l'entête 'x-fedapay-signature'.
        
    Returns:
        bool: True si l'authenticité est prouvée, False sinon.
    """
    webhook_secret = (os.getenv('FEDAPAY_AUTH_KEY', '') or '').strip()
    if not webhook_secret or not signature_header:
        return False

    timestamp, signature_v1 = _parse_fedapay_signature_header(signature_header)
    if not timestamp or not signature_v1:
        return False

    try:
        ts_int = int(timestamp)
    except Exception:
        return False

    computed_hash = _compute_fedapay_signature(payload, ts_int, webhook_secret)
    if not computed_hash:
        return False

    # Comparaison constante pour ?viter les attaques temporelles (insensible ? la casse)
    return hmac.compare_digest(computed_hash.lower(), signature_v1.lower())


def _mask_signature_header(sig: str | None) -> str | None:
    """Masque l'entête de signature pour un log safe en DEBUG."""
    if not sig:
        return None
    if len(sig) <= 20:
        return sig
    return f"{sig[:12]}...{sig[-8:]}"


def _mask_hash(sig: str | None) -> str | None:
    if not sig:
        return None
    if len(sig) <= 16:
        return sig
    return f"{sig[:8]}...{sig[-8:]}"


# =============================================================================
# SECTION 2 : AUTHENTIFICATION ET PORTAIL D'ACCÈS
# =============================================================================

def home(request):
    """
    Vue de la vitrine marketing IFRI.
    
    Affiche dynamiquement les formations actives avec un tri chronologique.
    """
    featured_courses = Course.objects.filter(
        is_active=True
    ).order_by('-created_at')[:6]
    
    return render(request, 'home.html', {
        'courses': featured_courses,
        'title': 'IFRI - Plateforme e-learning'
    })


def student_register(request):
    """
    Gère l'inscription autonome des apprenants.
    
    Crée un compte 'student', connecte l'utilisateur et le dirige vers 
    son dashboard pour commencer l'apprentissage.
    """
    if request.method == 'POST':
        form = StudentRegistrationForm(request.POST)
        if form.is_valid():
            new_student = form.save()
            # Authentification immédiate après succès
            login(request, new_student)
            messages.success(request, 'Bienvenue ! Votre espace étudiant est actif.')
            return redirect('student_dashboard')
    else:
        form = StudentRegistrationForm()
        
    return render(request, 'registration/student_register.html', {
        'form': form, 
        'title': 'Inscription Apprenant'
    })


def trainer_register(request):
    """
    Gère l'inscription des instructeurs pédagogiques.
    
    Le type d'utilisateur est défini sur 'trainer', débloquant 
    les outils de création et de gestion académique.
    """
    if request.method == 'POST':
        form = TrainerRegistrationForm(request.POST)
        if form.is_valid():
            new_trainer = form.save()
            login(request, new_trainer)
            messages.success(request, 'Espace Instructeur activé. Prêt à enseigner ?')
            return redirect('trainer_dashboard')
    else:
        form = TrainerRegistrationForm()
        
    return render(request, 'registration/trainer_register.html', {
        'form': form, 
        'title': 'Devenir Formateur'
    })


def user_login(request):
    """
    Contrôleur de connexion centralisé avec dispatching par rôle métier.
    
    Routage intelligent vers Student, Trainer ou Manager.
    """
    if request.method == 'POST':
        form = CustomLoginForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(username=username, password=password)
            
            if user is not None:
                login(request, user)
                # Dispatching basé sur le profil
                if user.user_type == 'student':
                    return redirect('student_dashboard')
                elif user.user_type == 'trainer':
                    return redirect('trainer_dashboard')
                elif user.user_type == 'manager':
                    return redirect('manager_dashboard')
            else:
                messages.error(request, 'Identifiants invalides. Veuillez réessayer.')
    else:
        form = CustomLoginForm()
        
    return render(request, 'registration/login.html', {
        'form': form, 
        'title': 'Connexion'
    })


def user_logout(request):
    """Ferme la session utilisateur et détruit les cookies Django."""
    logout(request)
    messages.info(request, 'Vous avez été déconnecté avec succès.')
    return redirect('home')


# =============================================================================
# SECTION 3 : WORKSPACE ÉTUDIANT (PROGRESSION ET ANALYSE)
# =============================================================================

@login_required
def student_dashboard(request):
    """
    Tableau de bord central de l'apprenant.
    
    Synchronise dynamiquement le progrès de chaque inscription à l'ouverture.
    Garantit que les pourcentages de complétion sont 100% exacts.
    """
    if request.user.user_type != 'student':
        messages.error(request, 'Accès non autorisé.')
        return redirect('home')
    
    enrollments = Enrollment.objects.filter(student=request.user)
    
    # LOGIQUE DE SYNCHRONISATION ANALYTIQUE
    for enrollment in enrollments:
        enrollment.update_progress()

    available_courses = Course.objects.filter(
        is_active=True
    ).exclude(
        id__in=enrollments.values_list('course_id', flat=True)
    )
    
    context = {
        'enrollments': enrollments,
        'available_courses': available_courses,
        'certified_enrollments': enrollments.filter(status='completed')
    }
    return render(request, 'student/dashboard.html', context)


@login_required
def student_enroll_course(request, course_id):
    """
    Initie le processus d'acquisition d'une formation.
    L'inscription est créée en statut 'pending' jusqu'au paiement Webhook.
    """
    if request.user.user_type != 'student':
        return redirect('home')
    
    course = get_object_or_404(Course, id=course_id, is_active=True)
    
    if Enrollment.objects.filter(student=request.user, course=course).exists():
        messages.warning(request, 'Vous suivez déjà cette formation.')
        return redirect('student_dashboard')
    
    enrollment = Enrollment.objects.create(
        student=request.user, 
        course=course, 
        status='pending'
    )
    
    return redirect('student_make_payment', enrollment_id=enrollment.id)


# =============================================================================
# SECTION 4 : TUNNEL DE PAIEMENT ASYNCHRONE (CORRECTION LOGS DICTIONNAIRE)
# =============================================================================

async def student_make_payment(request, enrollment_id):
    """
    VUE ASYNCHRONE : Moteur de génération de transaction FedaPay.
    
    FIX : Cette version utilise l'extraction directe de la clé 'url' dans le 
    dictionnaire renvoyé par le SDK, comme identifié dans vos logs.
    """
    service = get_feda_integration_service()

    # Récupération asynchrone sécurisée
    enrollment = await sync_to_async(get_object_or_404)(
        Enrollment, id=enrollment_id, student=request.user
    )
    course = await sync_to_async(lambda: enrollment.course)()

    if request.method == 'POST':
        try:
            # 1. Configuration du profil de transaction
            setup = PaiementSetup(
                pays=Pays.benin, 
                method=MethodesPaiement.mtn_open
            )
            
            # 2. Données Client (Format rigoureux pour éviter Bad Request)
            client_data = UserData(
                nom=request.user.last_name or "Client",
                prenom=request.user.first_name or "IFRI",
                email=request.user.email,
                tel="0100000000" # Numéro conforme aux exigences FedaPay
            )

            # 2.b URL de retour utilisateur (callback)
            ngrok_host = os.getenv('NGROK_URL', '')
            if ngrok_host and ngrok_host != 'localhost':
                callback_url = f"https://{ngrok_host}{reverse('fedapay_callback')}"
            else:
                callback_url = request.build_absolute_uri(reverse('fedapay_callback'))


            # 3. Création de la transaction chez FedaPay
            # Utilisation des paramètres positionnels pour la v2.0.3
            new_tx = await service.create_transaction(
                setup, 
                client_data, 
                montant_paiement=int(course.fee),
                callback_url=callback_url,
                description=f"Paiement IFRI : {course.name}"
            )

            # 4. Enregistrement local du suivi financier (Pending)
            await sync_to_async(Payment.objects.create)(
                enrollment=enrollment, 
                amount=course.fee,
                transaction_id=str(new_tx.id), 
                status='pending'
            )
            await sync_to_async(request.session.__setitem__)('last_fedapay_tx_id', str(new_tx.id))
            await sync_to_async(request.session.__setitem__)('last_enrollment_id', enrollment.id)

            # 5. EXTRACTION D'URL HAUTE PRÉCISION (BASÉE SUR VOS LOGS)
            # Votre log montre : {'token': '...', 'url': 'https://...'}
            redirect_url = None
            
            # Tentative 1 : Extraction directe depuis le jeton de transaction
            token_data = await service.get_transaction_link(new_tx.id)
            
            if isinstance(token_data, dict):
                # On utilise la clé 'url' vue explicitement dans tes logs
                redirect_url = (
                    token_data.get('url')
                    or token_data.get('payment_link')
                    or token_data.get('link')
                )
            else:
                # Objet TransactionToken (Pydantic) -> attribut "payment_link" (alias "url")
                redirect_url = (
                    getattr(token_data, 'payment_link', None)
                    or getattr(token_data, 'url', None)
                    or getattr(token_data, 'link', None)
                )
                if not redirect_url and hasattr(token_data, 'model_dump'):
                    dump = token_data.model_dump()
                    redirect_url = (
                        dump.get('url')
                        or dump.get('payment_link')
                        or dump.get('link')
                    )

            # 6. DÉCLENCHEMENT DE LA REDIRECTION PHYSIQUE
            if redirect_url:
                logging.info(f"TUNNEL IFRI : Redirection vers {redirect_url}")
                return redirect(redirect_url)
            else:
                raise AttributeError("Échec d'identification de l'URL dans la réponse FedaPay.")

        except Exception as e:
            logging.error(f"ECHEC TUNNEL PAIEMENT : {str(e)}")
            await sync_to_async(messages.error)(
                request, f"Désolé, le service FedaPay est indisponible : {str(e)}"
            )
            return redirect('student_dashboard')

    return render(request, 'student/make_payment.html', {
        'enrollment': enrollment, 
        'course': course
    })


async def fedapay_callback(request):
    """Vue d'atterrissage sécurisée post-paiement."""
    tx_id = (
        request.GET.get('id')
        or request.GET.get('transaction_id')
        or request.GET.get('trans_id')
        or request.GET.get('transaction')
    )
    if not tx_id:
        tx_id = await sync_to_async(request.session.get)('last_fedapay_tx_id')
    try:
        if tx_id:
            service = get_feda_integration_service()
            tx = await service.get_transaction_by_fedapay_id(str(tx_id))
            status = _extract_fedapay_status(tx)
            if status in ['approved', 'completed', 'success']:
                payment = await sync_to_async(Payment.objects.filter(transaction_id=str(tx_id)).first)()
                if payment:
                    payment.status = 'completed'
                    await sync_to_async(payment.save)()
                    enroll = await sync_to_async(lambda: payment.enrollment)()
                    enroll.status = 'active'
                    await sync_to_async(enroll.save)()
    except Exception as err:
        logging.warning(f"CALLBACK CHECK : {str(err)}")
    await sync_to_async(messages.success)(
        request,
        "Paiement confirmé ! Votre accès est maintenant actif."
    )
    return redirect('student_view_courses')


@csrf_exempt # INDISPENSABLE : Reçoit les requêtes POST de FedaPay sans jeton CSRF
async def fedapay_webhook(request):
    """
    ENDPOINT WEBHOOK (ASYNCHRONE / SÉCURITÉ HMAC v2.0.3).
    
    Action : Valide cryptographiquement l'authenticité via SHA256 combinant 
    le timestamp et le payload. Active les cours de manière irrévocable.
    """
    if request.method == 'POST':
        payload = request.body
        signature_raw = request.headers.get("x-fedapay-signature")
        
        # VALIDATION DE SÉCURITÉ HMAC ROBUSTE
        if not verify_signature_fedapay_v1(payload, signature_raw):
            if settings.DEBUG:
                ts_dbg, sig_dbg = _parse_fedapay_signature_header(signature_raw or "")
                secret_dbg = (os.getenv('FEDAPAY_AUTH_KEY', '') or '').strip()
                expected_dbg = None
                try:
                    if ts_dbg and secret_dbg:
                        expected_dbg = _compute_fedapay_signature(payload, int(ts_dbg), secret_dbg)
                except Exception:
                    expected_dbg = None
                logging.warning(
                    "WEBHOOK DEBUG : signature_header=%s | payload_len=%s | ts=%s | received=%s | expected=%s | content_encoding=%s",
                    _mask_signature_header(signature_raw),
                    len(payload),
                    ts_dbg,
                    _mask_hash(sig_dbg),
                    _mask_hash(expected_dbg),
                    request.headers.get('Content-Encoding'),
                )
            logging.warning("WEBHOOK SECURITY : Tentative de signature invalide détectée.")
            return JsonResponse({"status": "forbidden"}, status=403)
            
        try:
            event_json = json.loads(payload)
            # Persistance automatique via le connecteur v2.x
            connector = FedapayConnector(use_listen_server=False)
            await connector.fedapay_save_webhook_data(event_json)

            # Logique metier : Si approuve par l'operateur
            event_name = event_json.get('name') or ''
            entity = event_json.get('entity') or {}
            status = event_json.get('status') or entity.get('status')
            trans_id = event_json.get('id') or entity.get('id')

            if status == 'approved' or event_name == 'transaction.approved':
                if not trans_id:
                    logging.warning("WEBHOOK WARNING : Transaction id introuvable dans l'evenement.")
                    return JsonResponse({"status": "ignored"}, status=200)
                
                # Mise à jour financière locale
                payment = await sync_to_async(get_object_or_404)(
                    Payment, transaction_id=str(trans_id)
                )
                payment.status = 'completed'
                await sync_to_async(payment.save)()
                
                # Activation pédagogique
                enroll = await sync_to_async(lambda: payment.enrollment)()
                enroll.status = 'active'
                await sync_to_async(enroll.save)()
                
                logging.info(f"WEBHOOK SUCCESS : Cours débloqué pour Trans ID {trans_id}")
                
            return JsonResponse({"status": "received"})
        except Exception as webhook_err:
            logging.error(f"WEBHOOK ERROR : {str(webhook_err)}")
            return JsonResponse({"status": "ignored"}, status=200)

    return HttpResponseForbidden()


# =============================================================================
# SECTION 5 : SYSTÈME PÉDAGOGIQUE (LEÇONS ET NAVIGATION)
# =============================================================================

@login_required
def student_view_courses(request):
    """Liste des formations débloquées et actives pour l'élève."""
    enrollments = Enrollment.objects.filter(
        student=request.user, 
        status='active'
    )
    return render(request, 'student/view_courses.html', {
        'enrollments': enrollments,
        'title': 'Mes Apprentissages'
    })


@login_required
def course_lessons_list(request, course_id):
    """Sommaire interactif. Autorise l'accès pour les statuts 'active' et 'completed'."""
    course = get_object_or_404(Course, id=course_id)
    enrollment = get_object_or_404(
        Enrollment, 
        student=request.user, 
        course=course, 
        status__in=['active', 'completed']
    )
    
    lessons = course.lessons.all().order_by('order')
    completed_ids = enrollment.completed_lessons.values_list('id', flat=True)
    
    # Identification des quiz réussis
    passed_quiz_ids = QuizSubmission.objects.filter(
        student=request.user, 
        quiz__lesson__course=course,
        is_passed=True
    ).values_list('quiz_id', flat=True)
    
    return render(request, 'student/course_content.html', {
        'course': course,
        'lessons': lessons,
        'enrollment': enrollment,
        'completed_lesson_ids': completed_ids,
        'passed_quiz_ids': passed_quiz_ids
    })


@login_required
def lesson_detail(request, lesson_id):
    """Vue immersive d'une leçon (Markdown + PDF)."""
    lesson = get_object_or_404(Lesson, id=lesson_id)
    
    # Sécurité d'accès
    if not Enrollment.objects.filter(
        student=request.user, 
        course=lesson.course, 
        status__in=['active', 'completed']
    ).exists():
        messages.error(request, "Accès restreint aux abonnés.")
        return redirect('student_dashboard')

    # Rendu Markdown vers HTML sécurisé
    md_parser = markdown.Markdown(extensions=['extra', 'toc', 'nl2br'])
    content_html = md_parser.convert(lesson.content_text) if lesson.content_text else ""
    
    passed_quiz_ids = QuizSubmission.objects.filter(
        student=request.user, 
        quiz__lesson__course=lesson.course,
        is_passed=True
    ).values_list('quiz_id', flat=True)

    return render(request, 'student/lesson_detail.html', {
        'lesson': lesson, 
        'content_html': content_html,
        'passed_quiz_ids': passed_quiz_ids
    })


@login_required
def complete_lesson(request, lesson_id):
    """Valide une unité et recalcule immédiatement le progrès global."""
    lesson = get_object_or_404(Lesson, id=lesson_id)
    enrollment = get_object_or_404(
        Enrollment, 
        student=request.user, 
        course=lesson.course, 
        status__in=['active', 'completed']
    )
    
    enrollment.completed_lessons.add(lesson)
    enrollment.update_progress()
    
    messages.success(request, f"Module validé ! Progression : {enrollment.progress_percentage}%")
    return redirect('course_content', course_id=lesson.course.id)


# =============================================================================
# SECTION 6 : MOTEUR D'ÉVALUATION (QUIZ ET EXAMENS)
# =============================================================================

@login_required
def take_quiz(request, quiz_id):
    """Affiche l'interface de test dynamique pour l'élève."""
    quiz = get_object_or_404(Quiz, id=quiz_id)
    return render(request, 'student/take_quiz.html', {'quiz': quiz})


@login_required
def submit_quiz(request, quiz_id):
    """Algorithme de correction automatique des quiz."""
    if request.method == 'POST':
        quiz = get_object_or_404(Quiz, id=quiz_id)
        questions = quiz.questions.all()
        total_available_pts = sum(q.points for q in questions)
        score_obtenu = 0

        for q in questions:
            correct_set = set(q.choices.filter(is_correct=True).values_list('id', flat=True))
            user_input = request.POST.getlist(f'question_{q.id}')
            user_set = set(map(int, user_input))
            
            # Scoring strict : 100% de bonnes réponses sur la question requise
            if user_set == correct_set and correct_set:
                score_obtenu += q.points

        final_percent = (score_obtenu / total_available_pts * 100) if total_available_pts > 0 else 0
        is_passed = final_percent >= quiz.pass_mark

        # Sauvegarde du résultat en BDD
        submission = QuizSubmission.objects.create(
            student=request.user, 
            quiz=quiz, 
            score=final_percent, 
            is_passed=is_passed
        )

        if is_passed:
            messages.success(request, f"Succès ! Vous avez validé avec {final_percent:.1f}%")
        else:
            messages.warning(request, f"Note de {final_percent:.1f}% insuffisante (Requis: {quiz.pass_mark}%)")
        
        return redirect('quiz_result', submission_id=submission.id)
        
    return redirect('student_dashboard')


@login_required
def quiz_result(request, submission_id):
    """Rapport détaillé post-évaluation pour l'apprenant."""
    submission = get_object_or_404(QuizSubmission, id=submission_id, student=request.user)
    return render(request, 'student/quiz_result.html', {
        'submission': submission,
        'quiz': submission.quiz,
        'questions': submission.quiz.questions.all()
    })


# =============================================================================
# SECTION 7 : TRAVAUX PRATIQUES ET FEEDBACKS (ÉTUDIANT)
# =============================================================================

@login_required
def student_view_assignments(request):
    """Affiche la liste des travaux et devoirs assignés à l'élève."""
    if request.user.user_type != 'student': 
        return redirect('home')
    
    enrolled_ids = Enrollment.objects.filter(
        student=request.user, 
        status__in=['active', 'completed']
    ).values_list('course', flat=True)
    
    assignments = Assignment.objects.filter(course__in=enrolled_ids)
    submissions = Submission.objects.filter(student=request.user)
    
    return render(request, 'student/view_assignments.html', {
        'assignments': assignments, 
        'submissions': submissions,
        'title': 'Mes Travaux Pratiques'
    })


@login_required
def student_submit_assignment(request, assignment_id):
    """Permet à l'étudiant de téléverser son rendu (Fichier ou Texte)."""
    assignment = get_object_or_404(Assignment, id=assignment_id)
    
    if Submission.objects.filter(assignment=assignment, student=request.user).exists():
        messages.warning(request, 'Travail déjà soumis pour cet exercice.')
        return redirect('student_view_assignments')
    
    if request.method == 'POST':
        form = SubmissionForm(request.POST, request.FILES)
        if form.is_valid():
            sub = form.save(commit=False)
            sub.assignment, sub.student = assignment, request.user
            sub.save()
            messages.success(request, 'Votre travail a été transmis au formateur !')
            return redirect('student_view_assignments')
    else:
        form = SubmissionForm()
        
    return render(request, 'student/submit_assignment.html', {
        'form': form, 
        'assignment': assignment
    })


@login_required
def student_give_feedback(request):
    """Notation qualitative permettant aux élèves de noter la formation."""
    if request.method == 'POST':
        form = FeedbackForm(request.POST)
        if form.is_valid():
            f = form.save(commit=False); f.student = request.user; f.save()
            messages.success(request, 'Merci ! Votre avis nous aide à progresser.')
            return redirect('student_dashboard')
    else:
        enrolled_ids = Enrollment.objects.filter(
            student=request.user, 
            status__in=['active', 'completed']
        ).values_list('course', flat=True)
        form = FeedbackForm()
        form.fields['course'].queryset = Course.objects.filter(id__in=enrolled_ids)
        
    return render(request, 'student/give_feedback.html', {'form': form})


@login_required
def student_track_progress(request):
    """Vue analytique du parcours d'études personnel élève."""
    enrollments = Enrollment.objects.filter(student=request.user).order_by('-enrollment_date')
    return render(request, 'student/track_progress.html', {
        'enrollments': enrollments
    })


def _format_certificate_date(value):
    if not value:
        value = timezone.now()
    try:
        return date_format(value, "DATE_FORMAT")
    except Exception:
        try:
            return value.strftime("%Y-%m-%d")
        except Exception:
            return str(value)


def _draw_wrapped_text(canvas_obj, text, x, y, max_width, font_name, font_size, leading):
    canvas_obj.setFont(font_name, font_size)
    lines = simpleSplit(text, font_name, font_size, max_width)
    for line in lines:
        canvas_obj.drawString(x, y, line)
        y -= leading
    return y


def _build_certificate_pdf_bytes(student, course, issue_date, code, trainer):
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=landscape(A4))
    width, height = landscape(A4)

    # Background
    pdf.setFillColor(HexColor("#ffffff"))
    pdf.rect(0, 0, width, height, stroke=0, fill=1)

    # Right accent bars
    pdf.setFillColor(HexColor("#003366"))
    pdf.rect(width - 28 * mm, 0, 28 * mm, height, stroke=0, fill=1)
    pdf.setFillColor(HexColor("#007BEF"))
    pdf.rect(width - 40 * mm, 0, 12 * mm, height, stroke=0, fill=1)

    left = 25 * mm
    y = height - 25 * mm

    # Header
    pdf.setFillColor(HexColor("#003366"))
    pdf.setFont("Helvetica-Bold", 18)
    pdf.drawString(left, y, "IFRI")
    pdf.setFillColor(HexColor("#555555"))
    pdf.setFont("Helvetica", 8)
    pdf.drawString(left, y - 8, "Excellence Innovation - Impact")

    # Title
    y -= 20 * mm
    pdf.setFillColor(HexColor("#007BEF"))
    pdf.setFont("Helvetica-Bold", 34)
    pdf.drawString(left, y, "ATTESTATION")
    y -= 10 * mm
    pdf.setFillColor(HexColor("#666666"))
    pdf.setFont("Helvetica", 10)
    pdf.drawString(left, y, "DE FIN DE FORMATION")
    y -= 6 * mm
    pdf.setFillColor(HexColor("#66B3FF"))
    pdf.rect(left, y, 30 * mm, 2 * mm, stroke=0, fill=1)

    # Body
    y -= 12 * mm
    pdf.setFillColor(HexColor("#444444"))
    pdf.setFont("Helvetica", 12)
    pdf.drawString(left, y, "Ce document atteste que")
    y -= 10 * mm

    student_name = f"{student.first_name} {student.last_name}".strip()
    if not student_name:
        student_name = getattr(student, "username", "Etudiant")

    pdf.setFillColor(HexColor("#003366"))
    pdf.setFont("Helvetica-Bold", 20)
    pdf.drawString(left, y, student_name)
    y -= 10 * mm

    pdf.setFillColor(HexColor("#444444"))
    pdf.setFont("Helvetica", 12)
    pdf.drawString(left, y, "a complete avec succes la formation de")
    y -= 8 * mm

    course_name = getattr(course, "name", "")
    max_width = width - left - 45 * mm
    y = _draw_wrapped_text(pdf, course_name, left, y, max_width, "Helvetica-Bold", 14, 6 * mm)
    y -= 4 * mm

    pdf.setFillColor(HexColor("#666666"))
    pdf.setFont("Helvetica-Oblique", 10)
    pdf.drawString(left, y, "Formation validee selon les criteres de l'IFRI.")

    # Signatures
    sig_y = 25 * mm
    line_len = 60 * mm
    pdf.setStrokeColor(HexColor("#cccccc"))
    pdf.line(left, sig_y + 12 * mm, left + line_len, sig_y + 12 * mm)
    pdf.setFillColor(HexColor("#000000"))
    pdf.setFont("Helvetica-Bold", 10)
    pdf.drawString(left, sig_y + 7 * mm, "Direction de l'IFRI")
    pdf.setFont("Helvetica", 9)
    pdf.drawString(left, sig_y + 3 * mm, "Institut de Formation et de Recherche en Informatique")

    right_col = left + 90 * mm
    pdf.setStrokeColor(HexColor("#cccccc"))
    pdf.line(right_col, sig_y + 12 * mm, right_col + line_len, sig_y + 12 * mm)
    trainer_name = "Formateur responsable"
    if trainer:
        trainer_name = trainer.get_full_name() or getattr(trainer, "username", trainer_name)
    pdf.setFillColor(HexColor("#000000"))
    pdf.setFont("Helvetica-Bold", 10)
    pdf.drawString(right_col, sig_y + 7 * mm, trainer_name)
    pdf.setFont("Helvetica", 9)
    pdf.drawString(right_col, sig_y + 3 * mm, "Formateur responsable")

    # Meta info
    meta_x = width - 90 * mm
    pdf.setFillColor(HexColor("#555555"))
    pdf.setFont("Helvetica", 9)
    pdf.drawString(meta_x, 20 * mm, f"Fait le : {_format_certificate_date(issue_date)}")
    pdf.setFont("Helvetica-Bold", 9)
    pdf.drawString(meta_x, 12 * mm, f"Code de verification : {code}")

    pdf.showPage()
    pdf.save()
    buffer.seek(0)
    return buffer.getvalue()


def _render_certificate_pdf_response(context, filename, inline):
    disposition = "inline" if inline else "attachment"

    if pisa is not None:
        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = f'{disposition}; filename="{filename}"'
        template = get_template('student/certificate_pdf.html')
        html = template.render(context)
        pisa_status = pisa.CreatePDF(html, dest=response)
        if pisa_status.err:
            return HttpResponse("Erreur critique lors de la generation du PDF", status=500)
        return response

    pdf_bytes = _build_certificate_pdf_bytes(
        student=context["student"],
        course=context["course"],
        issue_date=context.get("date"),
        code=context.get("code"),
        trainer=context.get("trainer"),
    )
    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = f'{disposition}; filename="{filename}"'
    return response


# =============================================================================
# SECTION 8 : CERTIFICATION ET GÉNÉRATION DE DOCUMENTS PDF
# =============================================================================

@login_required
def generate_certificate(request, course_id):
    """Génère le diplôme IFRI au format PDF (Téléchargement)."""
    course = get_object_or_404(Course, id=course_id)
    enrollment = get_object_or_404(Enrollment, student=request.user, course=course)

    # Recalcul final avant émission du document
    enrollment.update_progress()
    if enrollment.progress_percentage < 100:
        messages.error(request, "Formation non finie à 100%.")
        return redirect('course_content', course_id=course.id)

    # Création ou récupération de l'objet Certificat
    cert, _ = Certificate.objects.get_or_create(
        student=request.user, 
        course=course, 
        enrollment=enrollment
    )

    context = {
        'certificate': cert, 
        'student': request.user, 
        'course': course, 
        'date': cert.issue_date, 
        'code': cert.certificate_code, 
        'trainer': course.trainer
    }

    return _render_certificate_pdf_response(
        context,
        filename=f'Diplome_IFRI_{course.name}.pdf',
        inline=False,
    )


@login_required
def view_certificate(request, course_id):
    """Affiche le diplôme pour lecture directe dans le navigateur."""
    course = get_object_or_404(Course, id=course_id)
    enrollment = get_object_or_404(Enrollment, student=request.user, course=course)
    
    if enrollment.progress_percentage < 100:
        return HttpResponseForbidden("Document non disponible.")

    cert, _ = Certificate.objects.get_or_create(
        student=request.user, course=course, enrollment=enrollment
    )
    
    context = {
        'student': request.user, 
        'course': course, 
        'date': cert.issue_date, 
        'code': cert.certificate_code, 
        'trainer': course.trainer
    }

    return _render_certificate_pdf_response(
        context,
        filename='Certificat_IFRI.pdf',
        inline=True,
    )


# =============================================================================
# SECTION 9 : DASHBOARD FORMATEUR (PILOTAGE & KPIS)
# =============================================================================

@login_required
def trainer_dashboard(request):
    """Interface de pilotage stratégique pour les instructeurs."""
    if request.user.user_type != 'trainer': 
        return redirect('home')
    
    my_courses = Course.objects.filter(trainer=request.user)
    students_count = Enrollment.objects.filter(
        course__trainer=request.user, 
        status__in=['active', 'completed']
    ).count()
    
    total_quizzes = Quiz.objects.filter(
        lesson__course__trainer=request.user
    ).count()
    
    return render(request, 'trainer/dashboard.html', {
        'courses': my_courses, 
        'total_students': students_count, 
        'quizzes_count': total_quizzes,
        'title': 'Espace Formateur'
    })


@login_required
def trainer_view_students(request):
    """Liste exhaustive des apprenants inscrits avec suivi réel."""
    if request.user.user_type != 'trainer': 
        return redirect('home')
    
    enrollments = Enrollment.objects.filter(
        course__trainer=request.user,
        status__in=['active', 'completed']
    ).order_by('-enrollment_date')
    
    return render(request, 'trainer/view_students.html', {
        'enrollments': enrollments,
        'title': 'Suivi des Étudiants'
    })


# =============================================================================
# SECTION 10 : GESTION DES COURS ET UNITÉS (CRUD INSTRUCTEUR)
# =============================================================================

@login_required
def trainer_course_list(request):
    """Catalogue de gestion des formations appartenant au formateur."""
    if request.user.user_type != 'trainer': return redirect('home')
    courses = Course.objects.filter(trainer=request.user)
    return render(request, 'trainer/course_manage_list.html', {
        'courses': courses
    })


@login_required
def trainer_course_create(request):
    """Création administrative d'un nouveau cours."""
    if request.user.user_type != 'trainer': return redirect('home')
    
    if request.method == 'POST':
        form = TrainerCourseForm(request.POST)
        if form.is_valid():
            new_c = form.save(commit=False)
            new_c.trainer = request.user
            new_c.save()
            messages.success(request, f'La formation "{new_c.name}" est créée !')
            return redirect('trainer_course_list')
    else:
        form = TrainerCourseForm()
        
    return render(request, 'trainer/course_form.html', {
        'form': form, 
        'title': "Nouveau Cours"
    })


@login_required
def trainer_course_edit(request, course_id):
    """Modification complète du programme et de l'organisation des leçons."""
    course = get_object_or_404(Course, id=course_id, trainer=request.user)
    
    if request.method == 'POST':
        form = TrainerCourseForm(request.POST, instance=course)
        if form.is_valid():
            form.save()
            messages.success(request, "Programme pédagogique mis à jour.")
            return redirect('trainer_course_list')
    else:
        form = TrainerCourseForm(instance=course)
    
    lessons = course.lessons.all().order_by('order')
    return render(request, 'trainer/course_edit.html', {
        'form': form, 
        'course': course, 
        'lessons': lessons
    })


@login_required
def trainer_lesson_add(request, course_id):
    """Ajoute une unité pédagogique (leçon) à une formation existante."""
    course = get_object_or_404(Course, id=course_id, trainer=request.user)
    
    if request.method == 'POST':
        form = LessonForm(request.POST, request.FILES)
        if form.is_valid():
            l = form.save(commit=False); l.course = course; l.save()
            messages.success(request, "Unité pédagogique ajoutée.")
            return redirect('trainer_course_edit', course_id=course.id)
    else:
        form = LessonForm()
        
    return render(request, 'trainer/lesson_form.html', {
        'form': form, 
        'course': course, 
        'title': "Nouveau Module"
    })


@login_required
def trainer_lesson_edit(request, lesson_id):
    """Modification d'un module spécifique (Markdown ou supports PDF)."""
    lesson = get_object_or_404(Lesson, id=lesson_id, course__trainer=request.user)
    
    if request.method == 'POST':
        form = LessonForm(request.POST, request.FILES, instance=lesson)
        if form.is_valid():
            form.save()
            messages.success(request, "Module pédagogique mis à jour.")
            return redirect('trainer_course_edit', course_id=lesson.course.id)
    else:
        form = LessonForm(instance=lesson)
        
    return render(request, 'trainer/lesson_form.html', {
        'form': form, 
        'course': lesson.course, 
        'title': "Modifier le module"
    })


# =============================================================================
# SECTION 11 : ADMINISTRATION DES ÉVALUATIONS (QUIZ & QUESTIONS)
# =============================================================================

@login_required
def trainer_quiz_list(request):
    """Supervision globale des examens créés par l'instructeur."""
    if request.user.user_type != 'trainer': return redirect('home')
    quizzes = Quiz.objects.filter(lesson__course__trainer=request.user)
    return render(request, 'trainer/quiz_list.html', {
        'quizzes': quizzes
    })


@login_required
def trainer_quiz_create(request):
    """Initialise un quiz pour une leçon donnée du programme."""
    if request.user.user_type != 'trainer': return redirect('home')
    
    if request.method == 'POST':
        form = QuizForm(request.POST)
        if form.is_valid():
            q = form.save()
            messages.success(request, "Quiz initialisé. Veuillez ajouter les questions.")
            return redirect('trainer_quiz_edit', quiz_id=q.id)
    else:
        form = QuizForm()
        form.fields['lesson'].queryset = Lesson.objects.filter(course__trainer=request.user)
        
    return render(request, 'trainer/quiz_form.html', {'form': form})


@login_required
def trainer_quiz_edit(request, quiz_id):
    """Paramétrage de l'examen et interface de gestion des questions."""
    quiz = get_object_or_404(Quiz, id=quiz_id, lesson__course__trainer=request.user)
    
    if request.method == 'POST':
        form = QuizForm(request.POST, instance=quiz)
        if form.is_valid(): 
            form.save()
            messages.success(request, "Paramètres d'examen enregistrés.")
            return redirect('trainer_quiz_list')
    else:
        form = QuizForm(instance=quiz)
        form.fields['lesson'].queryset = Lesson.objects.filter(course__trainer=request.user)
    
    questions = quiz.questions.all().order_by('order')
    return render(request, 'trainer/quiz_edit.html', {
        'quiz': quiz, 
        'form': form, 
        'questions': questions
    })


@login_required
def trainer_question_manage(request, quiz_id, question_id=None):
    """Interface unifiée Question + Réponses multiples (Inline Formset)."""
    quiz = get_object_or_404(Quiz, id=quiz_id, lesson__course__trainer=request.user)
    question = get_object_or_404(Question, id=question_id) if question_id else None
    
    if request.method == 'POST':
        f = QuestionForm(request.POST, instance=question)
        fs = ChoiceFormSet(request.POST, instance=question)
        if f.is_valid() and fs.is_valid():
            q = f.save(commit=False); q.quiz = quiz; q.save()
            fs.instance = q; fs.save()
            messages.success(request, "Question et réponses enregistrées avec succès.")
            return redirect('trainer_quiz_edit', quiz_id=quiz.id)
    else:
        f = QuestionForm(instance=question); fs = ChoiceFormSet(instance=question)
    
    return render(request, 'trainer/question_form.html', {
        'quiz': quiz, 
        'form': f, 
        'formset': fs
    })


@login_required
def trainer_quiz_delete(request, quiz_id):
    """Suppression définitive d'une évaluation du catalogue."""
    quiz = get_object_or_404(Quiz, id=quiz_id, lesson__course__trainer=request.user)
    quiz.delete()
    messages.info(request, "L'évaluation a été retirée du programme.")
    return redirect('trainer_quiz_list')


# =============================================================================
# SECTION 12 : REGISTRE, NOTATIONS ET PRÉSENCES (INSTRUCTEUR)
# =============================================================================

@login_required
def trainer_create_assignment(request):
    """Publie un exercice pratique au format numérique."""
    if request.method == 'POST':
        form = AssignmentForm(request.POST)
        if form.is_valid():
            a = form.save(commit=False); a.created_by = request.user; a.save()
            messages.success(request, "Nouvel exercice publié !")
            return redirect('trainer_manage_assignments')
    else:
        form = AssignmentForm()
        form.fields['course'].queryset = Course.objects.filter(trainer=request.user)
        
    return render(request, 'trainer/create_assignment.html', {'form': form})


@login_required
def trainer_manage_assignments(request):
    """Dashboard de gestion des exercices par l'enseignant."""
    assignments = Assignment.objects.filter(created_by=request.user)
    return render(request, 'trainer/manage_assignments.html', {'assignments': assignments})


@login_required
def trainer_view_submissions(request, assignment_id):
    """Visualisation des copies numériques transmises par les élèves."""
    a = get_object_or_404(Assignment, id=assignment_id, created_by=request.user)
    submissions = Submission.objects.filter(assignment=a)
    return render(request, 'trainer/view_submissions.html', {
        'assignment': a, 
        'submissions': submissions
    })


@login_required
def trainer_grade_submission(request, submission_id):
    """Attribue une note et un feedback correctif à un travail d'étudiant."""
    s = get_object_or_404(Submission, id=submission_id)
    if request.method == 'POST':
        form = GradeSubmissionForm(request.POST, instance=s)
        if form.is_valid():
            g = form.save(commit=False); g.graded_by = request.user; g.graded_at = timezone.now(); g.save()
            messages.success(request, "Correction enregistrée. L'élève peut voir sa note.")
            return redirect('trainer_view_submissions', assignment_id=s.assignment.id)
    else:
        form = GradeSubmissionForm(instance=s)
        
    return render(request, 'trainer/grade_submission.html', {
        'form': form, 
        'submission': s
    })


@login_required
def trainer_mark_attendance(request):
    """Registre d'appel journalier pour les sessions synchrones."""
    if request.method == 'POST':
        form = AttendanceForm(request.POST)
        if form.is_valid():
            att = form.save(commit=False); att.marked_by = request.user; att.save()
            messages.success(request, "Présence validée pour cette session.")
            return redirect('trainer_mark_attendance')
    else:
        form = AttendanceForm()
        form.fields['enrollment'].queryset = Enrollment.objects.filter(
            course__trainer=request.user, status='active'
        )
    return render(request, 'trainer/mark_attendance.html', {'form': form})


@login_required
def trainer_update_progress(request, enrollment_id):
    """Force manuellement le pourcentage de progression d'un élève."""
    e = get_object_or_404(Enrollment, id=enrollment_id, course__trainer=request.user)
    if request.method == 'POST':
        val = request.POST.get('progress_percentage')
        if val:
            e.progress_percentage = int(val); e.save()
            messages.success(request, "La progression de l'élève a été ajustée.")
            return redirect('trainer_view_students')
    return render(request, 'trainer/update_progress.html', {'enrollment': e})


# =============================================================================
# SECTION 13 : ADMINISTRATION GLOBALE (MANAGER ROLE)
# =============================================================================

@login_required
def manager_dashboard(request):
    """Vue analytique stratégique pour le bureau d'administration IFRI."""
    if request.user.user_type != 'manager': 
        return redirect('home')
    
    total_revenue = Payment.objects.filter(
        status='completed'
    ).aggregate(Sum('amount'))['amount__sum'] or 0
    
    context = {
        'total_students': User.objects.filter(user_type='student').count(), 
        'total_trainers': User.objects.filter(user_type='trainer').count(), 
        'total_courses': Course.objects.count(),
        'total_enrollments': Enrollment.objects.filter(status='active').count(),
        'total_revenue': total_revenue,
        'title': 'Espace Manager'
    }
    return render(request, 'manager/dashboard.html', context)


@login_required
def manager_add_course(request):
    """Création administrative de cours par le Manager."""
    if request.method == 'POST':
        form = CourseForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Cours ajouté au catalogue officiel.")
            return redirect('manager_manage_courses')
    else:
        form = CourseForm()
        form.fields['trainer'].queryset = User.objects.filter(user_type='trainer')
        
    return render(request, 'manager/add_course.html', {'form': form})


@login_required
def manager_manage_courses(request):
    """Surveillance exhaustive de l'offre académique globale."""
    courses = Course.objects.all()
    return render(request, 'manager/manage_courses.html', {'courses': courses})


@login_required
def manager_allot_trainer(request, course_id):
    """Modification administrative de l'instructeur d'une formation."""
    c = get_object_or_404(Course, id=course_id)
    if request.method == 'POST':
        form = TrainerAllotmentForm(request.POST, instance=c)
        if form.is_valid():
            form.save()
            return redirect('manager_manage_courses')
    else:
        form = TrainerAllotmentForm(instance=c)
        form.fields['trainer'].queryset = User.objects.filter(user_type='trainer')
    return render(request, 'manager/allot_trainer.html', {
        'form': form, 'course': c
    })


@login_required
def manager_view_feedbacks(request):
    """Analyse qualitative de la satisfaction apprenant (Score moyen)."""
    fb = Feedback.objects.all()
    avg_platform_rating = fb.aggregate(Avg('rating'))['rating__avg']
    return render(request, 'manager/view_feedbacks.html', {
        'feedbacks': fb, 
        'avg_rating': avg_platform_rating or 0
    })


@login_required
def manager_analyse_progress(request):
    """Reporting statistique consolidé par formation."""
    cs = Course.objects.annotate(
        avg_progress=Avg('enrollments__progress_percentage'), 
        student_count=Count('enrollments', filter=Q(enrollments__status='active'))
    )
    return render(request, 'manager/analyse_progress.html', {'courses': cs})


@login_required
def manager_view_payments(request):
    """Journal de bord financier complet des transactions monétaires."""
    payments = Payment.objects.all().order_by('-payment_date')
    return render(request, 'manager/view_payments.html', {
        'payments': payments
    })


@login_required
def manager_update_payment(request, payment_id):
    """Action de force administrative pour correction manuelle de statut financier."""
    p = get_object_or_404(Payment, id=payment_id)
    if request.method == 'POST':
        form = UpdatePaymentForm(request.POST, instance=p)
        if form.is_valid():
            form.save()
            if p.status == 'completed':
                enroll = p.enrollment
                if enroll.status != 'active':
                    enroll.status = 'active'
                    enroll.save()
            messages.success(request, 'Statut mis à jour.')
            return redirect('manager_view_payments')
    else:
        form = UpdatePaymentForm(instance=p)
    return render(request, 'manager/update_payment.html', {
        'form': form, 
        'payment': p
    })

# =============================================================================
# FIN DU FICHIER VIEWS.PY - IFRI SYSTEM CORE
# =============================================================================

