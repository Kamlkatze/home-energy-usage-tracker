"""Password hashing and session-token helpers for authentication.

Passwords are hashed with Argon2id (OWASP first choice for password
storage; passlib is unmaintained and bcrypt is only "acceptable").
Session tokens are random 256-bit values; the database only ever stores
their SHA-256 hash, the raw token lives exclusively in the HttpOnly
cookie.
"""

import hashlib
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import VerificationError, VerifyMismatchError

# OWASP-recommended Argon2id parameters (defaults are conservative enough
# for a self-hosted, low-traffic application).
_password_hasher = PasswordHasher()

# Fixed dummy hash burned when the username does not exist, so that login
# responses take a comparable amount of CPU time for existing and
# non-existing users (mitigates time-based user enumeration).
_DUMMY_HASH = PasswordHasher().hash("dummy password for timing equalization")

# NIST SP 800-63B: passwords shorter than 15 characters are weak without
# MFA, shorter than 8 characters are weak with MFA. Max length guards
# against long-password denial of service (OWASP Authentication Cheat
# Sheet) while still allowing passphrases comfortably.
PASSWORD_MIN_LENGTH_WITHOUT_MFA = 15
PASSWORD_MIN_LENGTH_WITH_MFA = 8
PASSWORD_MAX_LENGTH = 512


class PasswordStrengthError(ValueError):
    """Raised when a password does not meet the strength policy."""


def hash_password(password: str) -> str:
    return _password_hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _password_hasher.verify(password_hash, password)
    except VerifyMismatchError:
        return False
    except VerificationError:
        # Malformed/unsupported hash - treat like any invalid credential
        return False


def dummy_verify_password() -> None:
    """Burn approximately the same CPU time as a real verify call.

    Used when the username does not exist so that login responses take
    a comparable amount of time for existing and non-existing users
    (mitigates time-based user enumeration).
    """
    try:
        _password_hasher.verify(_DUMMY_HASH, "not the dummy password")
    except VerifyMismatchError:
        pass


def validate_password_strength(password: str, mfa_enabled: bool) -> None:
    """Raise PasswordStrengthError if the password violates the policy."""
    if len(password) > PASSWORD_MAX_LENGTH:
        raise PasswordStrengthError(
            f"Passwort darf maximal {PASSWORD_MAX_LENGTH} Zeichen lang sein."
        )
    minimum = PASSWORD_MIN_LENGTH_WITH_MFA if mfa_enabled else PASSWORD_MIN_LENGTH_WITHOUT_MFA
    if len(password) < minimum:
        raise PasswordStrengthError(
            f"Passwort muss mindestens {minimum} Zeichen lang sein."
        )


def generate_session_token() -> str:
    """Random 256-bit session token for the session cookie."""
    return secrets.token_urlsafe(32)


def hash_session_token(token: str) -> str:
    """SHA-256 hex digest of a session token (stored in the database)."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()