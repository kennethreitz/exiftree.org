import logging
import re
import time

from asgiref.sync import iscoroutinefunction, markcoroutinefunction, sync_to_async
from django.db import InterfaceError, OperationalError, connections

logger = logging.getLogger('core.requests')

BOT_PATTERNS = re.compile(
    r'bot|crawl|spider|slurp|semrush|ahrefs|bytespider|dotbot|mj12|gptbot|'
    r'bingpreview|yandex|baiduspider|duckduckbot|facebookexternalhit|twitterbot|'
    r'linkedinbot|applebot|google|mediapartners',
    re.IGNORECASE,
)


def _detect_bot(user_agent: str) -> str | None:
    """Return the bot name from User-Agent, or None if not a bot."""
    match = BOT_PATTERNS.search(user_agent)
    return match.group(0) if match else None


def _drop_connections():
    for conn in connections.all(initialized_only=True):
        conn.close()


class DbRetryMiddleware:
    """Retry once on stale DB connections (e.g. after Postgres restart).

    Supports both sync and async request paths — django-bolt mounts Django
    under ASGI, so middleware must handle both.
    """

    sync_capable = True
    async_capable = True

    def __init__(self, get_response):
        self.get_response = get_response
        self.async_mode = iscoroutinefunction(get_response)
        if self.async_mode:
            markcoroutinefunction(self)

    def __call__(self, request):
        if self.async_mode:
            return self._acall(request)
        try:
            return self.get_response(request)
        except (OperationalError, InterfaceError):
            _drop_connections()
            return self.get_response(request)

    async def _acall(self, request):
        try:
            return await self.get_response(request)
        except (OperationalError, InterfaceError):
            await sync_to_async(_drop_connections)()
            return await self.get_response(request)


class RequestLoggingMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        start = time.time()
        response = self.get_response(request)
        duration = (time.time() - start) * 1000

        # Skip static/health/favicon
        path = request.path
        if path.startswith('/static/') or path == '/health' or path == '/favicon.ico':
            return response

        ua = request.META.get('HTTP_USER_AGENT', '')
        bot = _detect_bot(ua)

        if bot:
            logger.info(
                '[BOT:%s] %s %s %s %.0fms ua="%s"',
                bot,
                request.method,
                path,
                response.status_code,
                duration,
                ua[:200],
            )
        else:
            logger.info(
                '%s %s %s %.0fms',
                request.method,
                path,
                response.status_code,
                duration,
            )
        return response
