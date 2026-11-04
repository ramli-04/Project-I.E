"""Public-schema authentication. Opaque tokens are stored only as SHA-256 digests."""
import hashlib
import secrets
from datetime import timedelta

from django.db import transaction
from django.utils import timezone
from django_tenants.utils import schema_context
from rest_framework.authentication import BaseAuthentication, get_authorization_header
from rest_framework.exceptions import AuthenticationFailed, PermissionDenied, Throttled

from .models import LoginRateLimit, PlatformSession


def issue_session(account):
    token = secrets.token_urlsafe(48)
    with schema_context('public'):
        PlatformSession.objects.create(account=account, token_digest=hashlib.sha256(token.encode()).hexdigest(),
                                       expires_at=timezone.now() + timedelta(hours=12))
    return token


class PlatformBearerAuthentication(BaseAuthentication):
    def authenticate_header(self, request):
        return 'Bearer'

    def authenticate(self, request):
        header = get_authorization_header(request).split()
        if not header or header[0].lower() != b'bearer':
            return None
        if len(header) != 2 or len(header[1]) > 256:
            raise AuthenticationFailed('Invalid session.')
        digest = hashlib.sha256(header[1]).hexdigest()
        with schema_context('public'):
            session = PlatformSession.objects.select_related('account', 'account__laboratory').filter(
                token_digest=digest, revoked_at__isnull=True, expires_at__gt=timezone.now(), account__is_active=True,
            ).first()
        if not session:
            raise AuthenticationFailed('Session expired. Sign in again.')
        account = session.account
        if account.role in {'LAB', 'COURIER'} and (not account.laboratory_id or not account.laboratory.is_active):
            raise AuthenticationFailed('Laboratory unavailable.')
        return account, session


def current_platform_account(request, admin=False):
    account = getattr(request, 'user', None)
    from .models import PlatformAccount
    if not isinstance(account, PlatformAccount) or not account.is_active:
        raise AuthenticationFailed('Sign in using a platform account.')
    if admin and account.role != 'ADMIN':
        raise PermissionDenied('Administrator access required.')
    return account


def check_login_rate(request, identity):
    now = timezone.now()
    address = request.META.get('REMOTE_ADDR', '')  # Never trust client-supplied forwarding headers.
    for value, limit in [(address, 60), (address + ':' + identity, 10)]:
        key = hashlib.sha256(value.encode()).hexdigest()
        with transaction.atomic():
            state, _ = LoginRateLimit.objects.select_for_update().get_or_create(
                key=key, defaults={'window_started_at': now},
            )
            if now - state.window_started_at >= timedelta(minutes=15):
                state.window_started_at, state.attempts = now, 0
            if state.attempts >= limit:
                raise Throttled(wait=max(1, int(900 - (now - state.window_started_at).total_seconds())))
            state.attempts += 1
            state.save(update_fields=['window_started_at', 'attempts'])
