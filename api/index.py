import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(BASE_DIR))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "e_learning_platform.settings")

from django.core.wsgi import get_wsgi_application  # noqa: E402

app = get_wsgi_application()
