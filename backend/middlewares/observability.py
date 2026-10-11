"""Aggregate timings without exposing SQL, credentials or record contents."""
from time import perf_counter
from flask import g, has_request_context, request


def record_timing(name, duration):
    if has_request_context():
        timings = getattr(g, 'audit_timings', {})
        timings[name] = timings.get(name, 0.0) + duration
        g.audit_timings = timings


def register_observability(app):
    @app.before_request
    def start_request():
        g.audit_started = perf_counter()

    @app.after_request
    def finish_request(response):
        if request.path.startswith('/api/'):
            elapsed = (perf_counter() - g.audit_started) * 1000
            timings = getattr(g, 'audit_timings', {})
            parts = [f'{name};dur={value:.1f}' for name, value in timings.items()]
            parts.append(f'request;dur={elapsed:.1f}')
            previous = response.headers.get('Server-Timing')
            response.headers['Server-Timing'] = ', '.join(([previous] if previous else []) + parts)
            response.headers['Cache-Control'] = 'no-store'
            response.headers['X-Content-Type-Options'] = 'nosniff'
            response.headers['Referrer-Policy'] = 'no-referrer'
            app.logger.info('api timing path=%s status=%s request_ms=%.1f db_connect_ms=%.1f db_execute_ms=%.1f',
                            request.path, response.status_code, elapsed,
                            timings.get('db_connect', 0), timings.get('db_execute', 0))
        return response
