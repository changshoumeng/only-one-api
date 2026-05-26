import base64
import hashlib
import hmac
import os


PASSWORD_PREFIX = 'pllm_pbkdf2_sha256'
PBKDF2_ITERATIONS = 260000


def _b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode('ascii').rstrip('=')


def _b64decode(value: str) -> bytes:
    padding = '=' * (-len(value) % 4)
    return base64.urlsafe_b64decode((value + padding).encode('ascii'))


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, PBKDF2_ITERATIONS)
    return f'{PASSWORD_PREFIX}${PBKDF2_ITERATIONS}${_b64encode(salt)}${_b64encode(digest)}'


def is_password_hash(value: str) -> bool:
    return isinstance(value, str) and value.startswith(f'{PASSWORD_PREFIX}$')


def verify_password(password: str, stored_password: str) -> bool:
    if not stored_password:
        return False

    if not is_password_hash(stored_password):
        return hmac.compare_digest(password, stored_password)

    try:
        prefix, iterations, salt, digest = stored_password.split('$', 3)
        if prefix != PASSWORD_PREFIX:
            return False
        expected = hashlib.pbkdf2_hmac(
            'sha256',
            password.encode('utf-8'),
            _b64decode(salt),
            int(iterations),
        )
        return hmac.compare_digest(_b64encode(expected), digest)
    except Exception:
        return False
