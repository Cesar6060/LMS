"""
ASGI config for gamedev_platform project.

Plain Django ASGI — the app serves HTTP only. Production runs gunicorn (WSGI);
this module exists for ASGI-capable hosts and for `manage.py` introspection.
"""

import os

from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

application = get_asgi_application()
