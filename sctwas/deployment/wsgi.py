"""WSGI entry point for the standalone scTWAS application."""
import os
from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sctwas.deployment.settings')
application = get_wsgi_application()
