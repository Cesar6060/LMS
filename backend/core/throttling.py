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

from rest_framework.throttling import AnonRateThrottle, ScopedRateThrottle


class ClientIPIdentMixin:
    """Prefer Cloudflare's CF-Connecting-IP header as the throttle ident."""

    def get_ident(self, request):
        cf_ip = request.META.get('HTTP_CF_CONNECTING_IP', '').strip()
        return cf_ip or super().get_ident(request)


class ClientIPAnonRateThrottle(ClientIPIdentMixin, AnonRateThrottle):
    pass


class ClientIPScopedRateThrottle(ClientIPIdentMixin, ScopedRateThrottle):
    pass
