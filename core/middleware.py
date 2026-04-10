import logging
import time

logger = logging.getLogger('core.requests')


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

        logger.info(
            '%s %s %s %.0fms',
            request.method,
            path,
            response.status_code,
            duration,
        )
        return response
