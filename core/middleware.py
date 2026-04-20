import logging
import re
import time

from asgiref.sync import iscoroutinefunction, markcoroutinefunction

logger = logging.getLogger('core.requests')

BOT_PATTERNS = re.compile(
    r'bot|crawl|spider|slurp|semrush|ahrefs|bytespider|dotbot|mj12|gptbot|'
    r'bingpreview|yandex|baiduspider|duckduckbot|facebookexternalhit|twitterbot|'
    r'linkedinbot|applebot|google|mediapartners',
    re.IGNORECASE,
)

SKIP_PATHS = ('/static/',)
SKIP_EXACT = {'/health', '/favicon.ico'}


def _detect_bot(user_agent: str) -> str | None:
    """Return the bot name from User-Agent, or None if not a bot."""
    match = BOT_PATTERNS.search(user_agent)
    return match.group(0) if match else None


def _log(request, response, duration_ms):
    path = request.path
    if path in SKIP_EXACT or path.startswith(SKIP_PATHS):
        return
    ua = request.META.get('HTTP_USER_AGENT', '')
    bot = _detect_bot(ua)
    if bot:
        logger.info(
            '[BOT:%s] %s %s %s %.0fms ua="%s"',
            bot, request.method, path, response.status_code, duration_ms, ua[:200],
        )
    else:
        logger.info(
            '%s %s %s %.0fms',
            request.method, path, response.status_code, duration_ms,
        )


class RequestLoggingMiddleware:
    """Logs every request. Async-capable so django-bolt's ASGI chain stays
    async end-to-end — avoids hopping through the asgiref thread pool on
    every request, which piles up under load."""

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
        start = time.time()
        response = self.get_response(request)
        _log(request, response, (time.time() - start) * 1000)
        return response

    async def _acall(self, request):
        start = time.time()
        response = await self.get_response(request)
        _log(request, response, (time.time() - start) * 1000)
        return response
