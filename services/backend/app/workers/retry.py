"""Bounded retry outside tick's transaction/session contexts.

Never replay an HTTP call directly. Each tick re-reads durable inbox/outbox state.
Only PostgreSQL lock-not-available is retryable here; other failures propagate.
"""
import logging
import time

from sqlalchemy.exc import OperationalError

logger = logging.getLogger(__name__)
BACKOFF_SECONDS = (1.0, 2.0)


def run_tick(operation, worker):
    for attempt in range(1, len(BACKOFF_SECONDS) + 2):
        try:
            result = operation()
        except OperationalError as error:
            # SQLAlchemy session contexts have rolled back/closed before this
            # boundary. Do not log exception text, SQL, payloads or credentials.
            code = getattr(error.orig, 'sqlstate', None)
            if code != '55P03':
                logger.error('worker_db_fatal worker=%s sqlstate=%s', worker, code)
                raise
            if attempt > len(BACKOFF_SECONDS):
                logger.error('worker_lock_exhausted worker=%s attempt=%s sqlstate=%s', worker, attempt, code)
                raise
            delay = BACKOFF_SECONDS[attempt - 1]
            logger.warning('worker_lock_retry worker=%s attempt=%s sqlstate=%s delay_seconds=%s',
                           worker, attempt, code, delay)
            time.sleep(delay)
        else:
            if attempt > 1:
                logger.warning('worker_lock_recovered worker=%s attempt=%s', worker, attempt)
            return result
