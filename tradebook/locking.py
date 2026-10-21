import threading
from contextlib import contextmanager

from tradebook import config


class LockTimeout(Exception):
    pass


_registry_guard = threading.Lock()
_locks = {}


def _lock_for(account_id):
    with _registry_guard:
        return _locks.setdefault(account_id, threading.RLock())


@contextmanager
def hold(account_id):
    lock = _lock_for(account_id)
    if not lock.acquire(timeout=config.LOCK_TIMEOUT_MS / 1000):
        raise LockTimeout("Lock timeout")
    try:
        yield
    finally:
        lock.release()
