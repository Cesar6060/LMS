"""Throttle classes that identify clients correctly behind Cloudflare.

All *.onrender.com traffic passes through Cloudflare, which appends a
per-request edge IP to X-Forwarded-For. DRF's default get_ident() keys
anonymous throttle buckets on the whole X-Forwarded-For chain (unless
NUM_PROXIES is configured), so behind Cloudflare every request lands in
a fresh bucket and rate limits never trigger.

Cloudflare sets CF-Connecting-IP to the real client address and
overwrites any client-supplied value, so on a Cloudflare-fronted
deployment it is authoritative. Prefer it; fall back to DRF's default
ident when it's absent (local dev, tests, non-Cloudflare hosts).

That "authoritative" only holds where the edge is genuinely in front of
every request. Off a Cloudflare-fronted host the header is just client
input, and honouring it would let a caller mint a fresh throttle bucket
per request by varying it. So the trust is gated on an explicit
``TRUST_CF_HEADERS`` setting (default: on wherever DEBUG is off) rather
than left implied by this docstring.
"""

from django.conf import settings
from django.core.cache import caches

from rest_framework.throttling import (
    AnonRateThrottle, ScopedRateThrottle, UserRateThrottle,
)

from core.demo import is_demo_user


class ClientIPIdentMixin:
    """Prefer Cloudflare's CF-Connecting-IP header as the throttle ident.

    Only when ``settings.TRUST_CF_HEADERS`` is on; otherwise the header is
    ignored entirely and DRF's default ident applies.

    Also redirects counter storage off the default cache. DRF's
    ``SimpleRateThrottle`` declares ``cache = default_cache`` as a plain class
    attribute, so overriding it here reaches every throttle in this module at
    once. The default cache is a per-process LocMemCache and production runs two
    gunicorn workers, which meant each worker enforced its own copy of every
    rate; the ``throttle`` alias is shared across the workers in a container.
    See the CACHES block in config/settings.py for the full reasoning.

    Resolved per access rather than bound at import: ``caches`` hands out a
    per-thread backend instance, and a property keeps ``override_settings``
    working in tests. Tests that need to clear throttle history must clear
    ``caches['throttle']`` — clearing the default cache no longer reaches it.
    """

    @property
    def cache(self):
        return caches['throttle']

    def get_ident(self, request):
        if getattr(settings, 'TRUST_CF_HEADERS', False):
            cf_ip = request.META.get('HTTP_CF_CONNECTING_IP', '').strip()
            if cf_ip:
                return cf_ip
        return super().get_ident(request)


class ClientIPAnonRateThrottle(ClientIPIdentMixin, AnonRateThrottle):
    pass


class ClientIPUserRateThrottle(ClientIPIdentMixin, UserRateThrottle):
    """Rate limit for authenticated traffic, keyed on user id (scope 'user').

    Anonymous requests fall back to the IP ident, but in practice they're
    covered by ClientIPAnonRateThrottle's separate 'anon' bucket.

    The shared demo account is keyed on client IP instead of pk: every
    visitor authenticates as the same user, so a pk key would pool all demo
    traffic into one bucket — one hammering visitor exhausts the rate for
    everyone (and can do so deliberately).
    """

    def get_cache_key(self, request, view):
        if is_demo_user(request.user):
            return self.cache_format % {
                'scope': self.scope,
                'ident': f'demo:{self.get_ident(request)}',
            }
        return super().get_cache_key(request, view)


class ClientIPScopedRateThrottle(ClientIPIdentMixin, ScopedRateThrottle):
    pass


# Phase 73: naming any throttle on a view *replaces* DEFAULT_THROTTLE_CLASSES
# rather than adding to it, so a view that lists only its scoped throttle
# silently drops the global anon/user ceiling — the scoped rate becomes the only
# limit, and any request shape the scope does not cover is unlimited. Spread
# this alongside the scoped class instead of listing it alone.
GLOBAL_THROTTLES = (ClientIPAnonRateThrottle, ClientIPUserRateThrottle)


class ClientIPScopedWriteRateThrottle(ClientIPScopedRateThrottle):
    """Scoped throttle that exempts safe methods.

    For views where a rate-limited write shares a URL (and therefore a view)
    with reads that must stay unthrottled — e.g. the invite endpoint, where
    POST sends email but GET just lists invites for the roster page.
    """

    def allow_request(self, request, view):
        if request.method in ('GET', 'HEAD', 'OPTIONS'):
            return True
        return super().allow_request(request, view)
