import os
import sys

current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.abspath(os.path.join(current_dir, ".."))
sys.path.append(root_dir)

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "stylemaxx.settings")

from django.core.wsgi import get_wsgi_application

app = get_wsgi_application()