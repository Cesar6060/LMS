"""
ASGI config for gamedev_platform project.

For Phase 5 (WebSockets), this will be updated to include Channels routing.
"""

import os

from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

application = get_asgi_application()
