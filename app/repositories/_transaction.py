from __future__ import annotations

from contextlib import contextmanager
import sqlite3
from threading import Lock

_TRANSACTION_DEPTH: dict[int, int] = {}
_TRANSACTION_IMMEDIATE: dict[int, bool] = {}
_TRANSACTION_LOCK = Lock()


def commit_when_unmanaged(conn: sqlite3.Connection) -> None:
    with _TRANSACTION_LOCK:
        unmanaged = _TRANSACTION_DEPTH.get(id(conn), 0) == 0
    if unmanaged:
        conn.commit()


@contextmanager
def transaction(conn: sqlite3.Connection, *, immediate: bool = False):
    key = id(conn)
    with _TRANSACTION_LOCK:
        depth = _TRANSACTION_DEPTH.get(key, 0)
        outer_immediate = _TRANSACTION_IMMEDIATE.get(key, False)
        if depth > 0 and immediate and not outer_immediate:
            raise RuntimeError("Verschachtelte Schreibtransaktion kann nicht nachträglich auf IMMEDIATE wechseln")
        _TRANSACTION_DEPTH[key] = depth + 1
        if depth == 0:
            _TRANSACTION_IMMEDIATE[key] = immediate
    if depth == 0:
        conn.execute("BEGIN IMMEDIATE" if immediate else "BEGIN")
    try:
        yield
    except Exception:
        with _TRANSACTION_LOCK:
            is_outermost = _TRANSACTION_DEPTH.get(key, 0) == 1
        if is_outermost:
            conn.rollback()
        raise
    else:
        with _TRANSACTION_LOCK:
            is_outermost = _TRANSACTION_DEPTH.get(key, 0) == 1
        if is_outermost:
            conn.commit()
    finally:
        with _TRANSACTION_LOCK:
            new_depth = _TRANSACTION_DEPTH[key] - 1
            if new_depth == 0:
                _TRANSACTION_DEPTH.pop(key, None)
                _TRANSACTION_IMMEDIATE.pop(key, None)
            else:
                _TRANSACTION_DEPTH[key] = new_depth
