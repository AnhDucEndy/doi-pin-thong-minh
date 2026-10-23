from enum import StrEnum
import hashlib
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import VerificationError, InvalidHashError


class Role(StrEnum):
    ADMIN = 'ADMIN'
    CUSTOMER = 'CUSTOMER'
    TECHNICIAN = 'TECHNICIAN'


class AccountState(StrEnum):
    ACTIVE = 'ACTIVE'
    LOCKED = 'LOCKED'
    INACTIVE = 'INACTIVE'


hasher = PasswordHasher()
DUMMY_HASH = hasher.hash(secrets.token_urlsafe(32))


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def verify_password(encoded, password):
    try:
        return hasher.verify(encoded, password)
    except (VerificationError, InvalidHashError):
        return False


def public_user(row):
    return {k: row[k] for k in ('id', 'username', 'role', 'state', 'version', 'created_at')}


def permits(user, role):
    return user['role'] == role  # ADMIN never implicitly inherits TECHNICIAN.
