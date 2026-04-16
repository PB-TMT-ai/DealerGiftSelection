"""PIN-based authentication for the Q4 Gift Selection Portal."""

from __future__ import annotations

import time

import db


MAX_ATTEMPTS = 3
LOCKOUT_SECONDS = 30


def verify_pin(pin: str) -> dict | None:
    """Look up a user by PIN. Returns user dict or None."""
    if not pin or not pin.strip():
        return None
    return db.get_user_by_pin(pin.strip())


def is_locked_out(session_state) -> tuple[bool, int]:
    """
    Check if the user is locked out due to too many failed attempts.
    Returns (is_locked, seconds_remaining).
    """
    lockout_until = session_state.get("lockout_until", 0)
    if lockout_until > time.time():
        remaining = int(lockout_until - time.time()) + 1
        return True, remaining
    return False, 0


def record_failed_attempt(session_state) -> int:
    """
    Increment failed attempt counter. If threshold reached, set lockout.
    Returns the current attempt count.
    """
    attempts = session_state.get("failed_attempts", 0) + 1
    session_state["failed_attempts"] = attempts

    if attempts >= MAX_ATTEMPTS:
        session_state["lockout_until"] = time.time() + LOCKOUT_SECONDS
        session_state["failed_attempts"] = 0  # Reset counter for next round

    return attempts


def reset_attempts(session_state) -> None:
    """Clear failed attempt counter on successful login."""
    session_state["failed_attempts"] = 0
    session_state["lockout_until"] = 0
