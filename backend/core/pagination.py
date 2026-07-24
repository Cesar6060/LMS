"""Pagination classes for the endpoints that genuinely grow without bound.

There is deliberately no ``DEFAULT_PAGINATION_CLASS`` in settings: setting one
would reshape *every* list response into ``{count, next, previous, results}``
and break the frontend everywhere at once. Instead the two endpoints whose
result sets have no natural ceiling opt in individually (Phase 55, A6).
"""

from rest_framework.pagination import PageNumberPagination


class NotificationPagination(PageNumberPagination):
    """Notifications accumulate per user forever and are never pruned.

    The only consumer is the notification bell's dropdown, which shows the
    newest handful, so a small page is the natural fit.
    """

    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


class RosterPagination(PageNumberPagination):
    """Student roster — bounded per response, but sized so a whole class fits.

    The roster page renders every student at once and has no paging UI, so the
    client walks ``next`` until it is exhausted. The point here is bounding any
    single response, not paging the instructor through their own class list.
    """

    page_size = 100
    page_size_query_param = 'page_size'
    max_page_size = 500
