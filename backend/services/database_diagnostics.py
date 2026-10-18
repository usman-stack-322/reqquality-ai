"""Safe database diagnostics: never format driver errors or connection strings."""
import logging
import os
import traceback
from pathlib import Path
from time import perf_counter

import psycopg

LOGGER = logging.getLogger('reqquality.database')


def exception_details(error):
    state = getattr(error, 'sqlstate', None)
    # Classify locally; never include the original text in a log or response.
    message = str(error).lower()
    category = ('authentication_rejected' if state in ('28P01', '28000') else
                'missing_table_or_column' if state in ('42P01', '42703') else
                'server_connection_limit' if state == '53300' else
                'query_cancelled_or_timed_out' if state == '57014' else
                'network_access_denied' if any(v in message for v in ('permission denied', 'access permissions', '10013')) else
                'dns_failure' if any(v in message for v in ('failed to resolve', 'getaddrinfo', 'name or service not known')) else
                'connection_timeout' if isinstance(error, psycopg.errors.ConnectionTimeout) else 'unclassified')
    return dict(exception_type=type(error).__name__, sqlstate=state, category=category,
                frames=[f'{Path(frame.filename).name}:{frame.lineno}:{frame.name}'
                        for frame in traceback.extract_tb(error.__traceback__)])


class DiagnosticConnection(psycopg.Connection):
    @classmethod
    def connect(cls, *args, **kwargs):
        started = perf_counter()
        try:
            return super().connect(*args, **kwargs)
        except Exception as error:
            LOGGER.error('database stage=driver_connect pid=%s elapsed_ms=%.1f diagnostic=%s',
                         os.getpid(), (perf_counter()-started)*1000, exception_details(error))
            raise


class SafePoolLogFilter(logging.Filter):
    """psycopg_pool otherwise interpolates raw driver errors into its logs."""
    def filter(self, record):
        errors = [arg for arg in record.args if isinstance(arg, BaseException)] if isinstance(record.args, tuple) else []
        category = ('connect_failed' if 'error connecting' in str(record.msg) else
                    'reconnect_exhausted' if 'reconnection attempt' in str(record.msg) else 'pool_event')
        record.msg = 'database pool event=%s exception_type=%s'
        record.args = (category, type(errors[-1]).__name__ if errors else 'none')
        record.exc_info = None
        record.exc_text = None
        return True


logging.getLogger('psycopg.pool').addFilter(SafePoolLogFilter())
