# IFRI E-Learning Platform

Plateforme e-learning Django de l'Institut de Formation et de Recherche en Informatique (IFRI)
pour etudiants, formateurs et managers. Elle couvre
l'inscription, le paiement FedaPay, les cours en Markdown, les quiz, les devoirs,
le suivi de progression et la generation de certificats PDF.

## Fonctionnalites

- Etudiant: inscription, paiement, cours, quiz, devoirs, progression, certificats
- Formateur: creation des cours/lecons, quiz, devoirs, notation, presence
- Manager: dashboards, gestion des cours, attribution des formateurs, paiements, feedbacks

## Stack

- Python 3.8+
- Django 5.2.7
- SQLite en developpement (PostgreSQL possible en production)
- Bootstrap (templates)
- Pillow (uploads)
- markdown + django-markdownify (contenu Markdown)
- xhtml2pdf (certificats)
- fedapay-connector (paiements)

## Demarrage rapide

1. Cloner le depot
2. Creer et activer un venv
3. Installer les dependances
4. Creer le fichier `.env`
5. Appliquer les migrations
6. Creer un superuser et le passer en role `manager`
7. Lancer le serveur

```bash
git clone <url-du-depot>
cd e-learning-platform

python -m venv .venv
# Windows
.\.venv\Scripts\Activate.ps1
# Linux/Mac
source .venv/bin/activate

pip install -r requirements.txt

python manage.py makemigrations
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Apres creation du superuser, connecte-toi a `http://127.0.0.1:8000/admin/` et
change le champ `user_type` du compte en `manager`.

## Variables d'environnement

Copie `.env.example` en `.env` a la racine du projet, puis ajuste les valeurs:

```env
SECRET_KEY=change-me
DEBUG=True

# Ngrok (pour tester les webhooks en externe)
NGROK_URL=example.ngrok-free.app

# FedaPay
FEDAPAY_API_KEY=sk_sandbox_xxx
FEDAPAY_API_URL=https://sandbox-api.fedapay.com
FEDAPAY_AUTH_KEY=wh_sandbox_xxx
FEDAPAY_ENVIRONMENT=sandbox
```

Notes:
- `NGROK_URL` doit etre uniquement le host (sans https). En local, mets `localhost`.
- `FEDAPAY_AUTH_KEY` sert a verifier la signature HMAC des webhooks.

## Paiement FedaPay

- Webhook: `POST /student/payment/webhook/`
- Callback: `GET /student/payment/callback/`

Pour les tests distants, pointe le webhook FedaPay vers l'URL publique Ngrok
et assure-toi que `NGROK_URL` est bien configure.

## Commandes utiles

```bash
python manage.py test
python manage.py collectstatic
```

## Arborescence

```
e-learning-platform/
  e_learning_platform/    # Settings Django
  e_learning_app/         # App principale (models, views, urls)
  static/                 # Assets (CSS/JS/images)
  media/                  # Fichiers uploades
  staticfiles/            # Collectstatic
  manage.py
  requirements.txt
  README.md
```

## Contribution

1. Fork
2. Cree une branche
3. Fais tes changements
4. Ouvre une PR

## Notes

Si tu rencontres un `ModuleNotFoundError` lie a Markdown, FedaPay ou PDF,
ajoute les dependances manquantes dans `requirements.txt` puis reinstalle.
