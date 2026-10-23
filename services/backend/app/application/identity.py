from datetime import datetime, timedelta, timezone
import json
import secrets
from uuid import uuid4

from fastapi.encoders import jsonable_encoder
from sqlalchemy import select, insert, update

from app.domain.identity import DUMMY_HASH, digest, verify_password
from app.infrastructure.db import advisory_lock


def utcnow():
    return datetime.now(timezone.utc)


class DomainError(Exception):
    def __init__(self, status, code, message='Request could not be completed'):
        self.status, self.code, self.message = status, code, message


def audit(session, db, actor, action, aggregate, before=None, after=None):
    # Callers pass only public projections; never token/password/hash.
    session.execute(insert(db.table('audit_events')).values(
        id=uuid4(), actor_type='USER', actor_id=str(actor), aggregate_type='user',
        aggregate_id=aggregate, action=action, before_data=jsonable_encoder(before),
        after_data=jsonable_encoder(after), correlation_id=uuid4()))


def login(session, db, policy, username, password, client_ip):
    username = username.strip().lower()
    now = utcnow()
    limits = db.table('login_limits')
    keys = sorted([digest('username:' + username), digest('ip:' + client_ip)])
    rows = []
    for key in keys:
        advisory_lock(session, 'login:' + key)
        row = session.execute(select(limits).where(limits.c.bucket_key == key).with_for_update()).mappings().first()
        if row and row['locked_until'] and row['locked_until'] > now:
            raise DomainError(429, 'LOGIN_LIMITED', 'Too many attempts; try again later')
        rows.append((key, row))
    users = db.table('users')
    user = session.execute(select(users).where(users.c.username == username).with_for_update()).mappings().first()
    valid = verify_password(user['password_hash'] if user else DUMMY_HASH, password)
    if not user or not valid or user['state'] != 'ACTIVE':
        for key, row in rows:
            reset = not row or now >= row['window_started_at'] + timedelta(seconds=policy['login_window_seconds'])
            failures = 1 if reset else row['failed_count'] + 1
            values = {'failed_count': failures, 'window_started_at': now if reset else row['window_started_at'],
                      'locked_until': now + timedelta(seconds=policy['login_window_seconds'])
                      if failures >= policy['login_max_failures'] else None}
            if row:
                session.execute(update(limits).where(limits.c.bucket_key == key).values(**values))
            else:
                session.execute(insert(limits).values(bucket_key=key, **values))
        session.commit()  # A rejected HTTP request must still persist its failure counters.
        raise DomainError(401, 'INVALID_CREDENTIALS', 'Invalid credentials or unavailable account')
    session.execute(update(limits).where(limits.c.bucket_key == digest('username:' + username))
                    .values(failed_count=0, window_started_at=now, locked_until=None))
    token = secrets.token_urlsafe(48)
    ttl = policy['web_session_ttl_seconds']
    session.execute(insert(db.table('auth_sessions')).values(
        id=uuid4(), user_id=user['id'], token_hash=digest(token), expires_at=now + timedelta(seconds=ttl)))
    audit(session, db, user['id'], 'LOGIN', user['id'])
    return token, ttl, user


def idempotent(session, db, principal, route, key, body, status, execute):
    table = db.table('idempotency_records')
    request_hash = digest(json.dumps(jsonable_encoder(body), sort_keys=True, separators=(',', ':')))
    identity = {'principal': str(principal), 'route': route, 'key': key}
    advisory_lock(session, f'idem:{principal}:{route}:{key}')
    clause = (table.c.principal == str(principal)) & (table.c.route == route) & (table.c.key == key)
    existing = session.execute(select(table).where(clause)).mappings().first()
    if existing:
        if existing['request_hash'] != request_hash:
            raise DomainError(409, 'IDEMPOTENCY_CONFLICT')
        return existing['response_body']
    result = jsonable_encoder(execute())
    session.execute(insert(table).values(**identity, request_hash=request_hash, response_status=status,
                                         response_body=result, expires_at=utcnow() + timedelta(hours=72)))
    return result
