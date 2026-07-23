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
"""

from rest_framework.throttling import (
    AnonRateThrottle, ScopedRateThrottle, UserRateThrottle,
)


class ClientIPIdentMixin:
    """Prefer Cloudflare's CF-Connecting-IP header as the throttle ident."""

    def get_ident(self, request):
        cf_ip = request.META.get('HTTP_CF_CONNECTING_IP', '').strip()
        return cf_ip or super().get_ident(request)


class ClientIPAnonRateThrottle(ClientIPIdentMixin, AnonRateThrottle):
    pass


class ClientIPUserRateThrottle(ClientIPIdentMixin, UserRateThrottle):
    """Rate limit for authenticated traffic, keyed on user id (scope 'user').

    Anonymous requests fall back to the IP ident, but in practice they're
    covered by ClientIPAnonRateThrottle's separate 'anon' bucket.
    """
    pass


class ClientIPScopedRateThrottle(ClientIPIdentMixin, ScopedRateThrottle):
    pass


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
