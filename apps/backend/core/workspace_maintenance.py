"""Serialize Studio operations with snapshots in the single-process local runtime."""

from functools import wraps
from threading import RLock

WORKSPACE_LOCK = RLock()


def workspace_operation(function):
    @wraps(function)
    def guarded(*args, **kwargs):
        with WORKSPACE_LOCK:
            return function(*args, **kwargs)

    return guarded


def guarded_workspace_service(cls):
    """Guard complete public operations, before any service-specific locks.

    Connection context managers and static validators are intentionally excluded;
    their callers hold the lock for the entire transaction.
    """
    for name, method in list(vars(cls).items()):
        if (
            not name.startswith("_")
            and name != "connect"
            and callable(method)
            and not isinstance(method, (staticmethod, classmethod))
        ):
            setattr(cls, name, workspace_operation(method))
    return cls
