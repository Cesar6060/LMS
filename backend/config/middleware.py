"""Project-level middleware."""


class PermissionsPolicyMiddleware:
    """Deny powerful browser features on every Django-served page.

    The API host serves only JSON and the Django admin — neither has any
    business using the camera, microphone, or geolocation. One static header
    beats a dependency for a policy this small.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        response['Permissions-Policy'] = (
            'camera=(), microphone=(), geolocation=()'
        )
        return response
