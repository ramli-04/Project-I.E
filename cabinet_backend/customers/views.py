import re
import secrets
import unicodedata
from functools import wraps
from django.core import signing
from django.contrib.auth.hashers import make_password, check_password
from django.contrib.auth.password_validation import validate_password
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from django_tenants.utils import schema_context
from rest_framework import serializers
from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.permissions import AllowAny
from rest_framework.exceptions import AuthenticationFailed, PermissionDenied
from rest_framework.response import Response
from .models import Client, Domain, PlatformAccount, AccessLog, SupportTicket
from .authentication import current_platform_account, issue_session, check_login_rate


def public_schema(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        with schema_context('public'):
            return view(*args, **kwargs)
    return wrapped


def login_key(name):
    text = unicodedata.normalize('NFKD', name).encode('ascii', 'ignore').decode().lower()
    return re.sub(r'[^a-z0-9]', '', text)


def current_account(request, admin=False):
    return current_platform_account(request, admin=admin)


class AccountSerializer(serializers.ModelSerializer):
    laboratory_name = serializers.CharField(source='laboratory.name', read_only=True, default='')
    laboratory_id = serializers.CharField(source='laboratory.schema_name', read_only=True, default='')

    class Meta:
        model = PlatformAccount
        fields = ['id', 'name', 'email', 'role', 'workstation_role', 'laboratory', 'laboratory_id', 'laboratory_name', 'is_active', 'password_reset_at', 'created_at']
        read_only_fields = ['password_reset_at', 'created_at']

    def validate(self, attrs):
        name = attrs.get('name', getattr(self.instance, 'name', ''))
        key = login_key(name)
        if not key:
            raise serializers.ValidationError({'name': 'Renseignez un nom de connexion valide.'})
        duplicates = PlatformAccount.objects.filter(login_key=key)
        if self.instance:
            duplicates = duplicates.exclude(pk=self.instance.pk)
        if duplicates.exists():
            raise serializers.ValidationError({'name': 'Ce nom de connexion est déjà utilisé.'})
        role = attrs.get('role', getattr(self.instance, 'role', None))
        lab = attrs.get('laboratory', getattr(self.instance, 'laboratory', None))
        if role in {'LAB', 'COURIER'} and (not lab or lab.schema_name == 'public' or not lab.is_active):
            raise serializers.ValidationError({'laboratory': 'Affectez ce compte à un laboratoire.'})
        if role not in {'LAB', 'COURIER'}:
            attrs['laboratory'] = None
        attrs['login_key'] = key
        return attrs


class LabSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=100)
    identifier = serializers.RegexField(r'^[a-z][a-z0-9]{0,29}$', max_length=30)

    def validate_identifier(self, value):
        if value == 'public' or Client.objects.filter(schema_name=value).exists():
            raise serializers.ValidationError('Cet identifiant existe déjà ou est réservé.')
        return value


@api_view(['POST'])
@authentication_classes([])
@permission_classes([AllowAny])
@public_schema
def demo_login(request):
    name = str(request.data.get('name', '')).strip()[:150]
    key = login_key(name)
    role = request.data.get('role')
    check_login_rate(request, key)
    if role is not None and role not in {'ADMIN', 'DENTIST', 'LAB', 'COURIER'}:
        return Response({'detail': 'Sélectionnez un espace valide.'}, status=400)
    candidates = PlatformAccount.objects.select_related('laboratory').filter(is_active=True)
    if role:
        candidates = candidates.filter(role=role)
    if role in {'LAB', 'COURIER'}:
        laboratory = str(request.data.get('laboratory', ''))
        if not laboratory:
            return Response({'detail': 'Sélectionnez votre laboratoire.'}, status=400)
        candidates = candidates.filter(laboratory__schema_name=laboratory, laboratory__is_active=True).exclude(laboratory__schema_name='public')
        matches = []
        for candidate in candidates:
            aliases = {candidate.login_key, login_key(candidate.name)}
            parts = re.split(r'\s+[-–—]\s+', candidate.name, maxsplit=1)
            if len(parts) == 2:
                aliases.add(login_key(parts[1]))
            for prefix in [candidate.laboratory.name, candidate.laboratory.schema_name]:
                prefix_key = login_key(prefix)
                if prefix_key and login_key(candidate.name).startswith(prefix_key):
                    aliases.add(login_key(candidate.name)[len(prefix_key):])
            if key and key in aliases:
                matches.append(candidate)
        account = matches[0] if len(matches) == 1 else None
    else:
        account = candidates.filter(login_key=key).first() if key else None
    password = request.data.get('password', '')
    password = password if isinstance(password, str) and len(password) <= 256 else ''
    valid = check_password(password, account.password_hash if account and account.password_hash else make_password(None))
    if not account or not valid or not password:
        AccessLog.objects.create(name=name, event='LOGIN', success=False, details='Compte inconnu ou désactivé')
        return Response({'detail': 'Identification ou mot de passe incorrect.'}, status=401)
    AccessLog.objects.create(account=account, name=account.name, event='LOGIN', details='Authenticated session')
    token = issue_session(account)
    return Response({'account': AccountSerializer(account).data, 'token': token})


@api_view(['POST'])
@public_schema
def demo_logout(request):
    account = current_account(request)
    request.auth.revoked_at = timezone.now()
    request.auth.save(update_fields=['revoked_at'])
    AccessLog.objects.create(account=account, name=account.name, event='LOGOUT', details='Déconnexion')
    return Response(status=204)


@api_view(['GET', 'POST'])
@permission_classes([AllowAny])
@public_schema
def laboratories(request):
    if request.method == 'POST':
        actor = current_account(request, admin=True)
        serializer = LabSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            lab = Client.objects.create(schema_name=serializer.validated_data['identifier'], name=serializer.validated_data['name'])
            Domain.objects.create(domain=f'{lab.schema_name}.localhost', tenant=lab, is_primary=True)
            AccessLog.objects.create(account=actor, name=actor.name, event='LAB_CREATED', details=f'{lab.schema_name} : {lab.name}')
        return Response({'id': lab.pk, 'identifier': lab.schema_name, 'name': lab.name}, status=201)
    return Response([{'id': lab.pk, 'identifier': lab.schema_name, 'name': lab.name} for lab in Client.objects.filter(is_active=True).exclude(schema_name='public').order_by('name')])


@api_view(['GET', 'POST', 'PATCH'])
@public_schema
def accounts(request, account_id=None):
    actor = current_account(request, admin=True)
    if request.method == 'GET':
        return Response(AccountSerializer(PlatformAccount.objects.select_related('laboratory').all(), many=True).data)
    account = None
    previous_sensitive = {}
    if request.method == 'PATCH':
        account = PlatformAccount.objects.filter(pk=account_id).first()
        if not account:
            return Response({'detail': 'Compte introuvable.'}, status=404)
        if account.pk == actor.pk and (request.data.get('is_active') is False or request.data.get('role', actor.role) != 'ADMIN'):
            return Response({'detail': 'Vous ne pouvez pas désactiver votre propre accès administrateur.'}, status=400)
        previous_sensitive = {
            'is_active': account.is_active,
            'role': account.role,
            'laboratory_id': account.laboratory_id,
            'workstation_role': account.workstation_role,
        }
    serializer = AccountSerializer(account, data=request.data, partial=request.method == 'PATCH')
    serializer.is_valid(raise_exception=True)
    account = serializer.save()
    temporary_password = None
    if request.method == 'POST':
        temporary_password = secrets.token_urlsafe(16)
        account.password_hash = make_password(temporary_password)
        account.password_reset_at = timezone.now()
        account.save(update_fields=['password_hash', 'password_reset_at'])
    elif request.method == 'PATCH' and (
        account.is_active != previous_sensitive.get('is_active')
        or account.role != previous_sensitive.get('role')
        or account.laboratory_id != previous_sensitive.get('laboratory_id')
        or account.workstation_role != previous_sensitive.get('workstation_role')
    ):
        account.sessions.filter(revoked_at__isnull=True).update(revoked_at=timezone.now())
    AccessLog.objects.create(account=actor, name=actor.name, event='ACCOUNT_UPDATED' if request.method == 'PATCH' else 'ACCOUNT_CREATED', details=account.name)
    result = dict(AccountSerializer(account).data)
    if temporary_password:
        result['temporary_password'] = temporary_password
    return Response(result, status=200 if request.method == 'PATCH' else 201)


@api_view(['POST'])
@public_schema
def reset_password(request, account_id):
    actor = current_account(request, admin=True)
    account = PlatformAccount.objects.filter(pk=account_id).first()
    if not account:
        return Response({'detail': 'Compte introuvable.'}, status=404)
    password = secrets.token_urlsafe(12)
    account.password_hash = make_password(password)
    account.password_reset_at = timezone.now()
    account.save(update_fields=['password_hash', 'password_reset_at'])
    account.sessions.filter(revoked_at__isnull=True).update(revoked_at=timezone.now())
    AccessLog.objects.create(account=actor, name=actor.name, event='PASSWORD_RESET', details=f'Compte : {account.name}')
    data = {'temporary_password': password, 'detail': 'Mot de passe réinitialisé. Anciennes sessions révoquées.'}
    if account.pk == actor.pk:
        data['token'] = issue_session(account)
    return Response(data)


@api_view(['GET'])
@public_schema
def overview(request):
    current_account(request, admin=True)
    from api.models import Prescription
    labs = []
    for lab in Client.objects.exclude(schema_name='public').order_by('name'):
        row = {'id': lab.pk, 'identifier': lab.schema_name, 'name': lab.name, 'account_count': PlatformAccount.objects.filter(laboratory=lab).count()}
        with schema_context(lab.schema_name):
            row['order_count'] = Prescription.objects.count()
            row['paused_count'] = Prescription.objects.filter(is_paused=True).count()
        labs.append(row)
    return Response({'laboratories': labs, 'dentist_count': PlatformAccount.objects.filter(role='DENTIST').count(), 'account_count': PlatformAccount.objects.count(), 'open_tickets': SupportTicket.objects.exclude(status='RESOLVED').count()})


@api_view(['GET'])
@public_schema
def logs(request):
    current_account(request, admin=True)
    return Response(list(AccessLog.objects.values('id', 'name', 'event', 'success', 'details', 'created_at')[:200]))


@api_view(['GET', 'POST', 'PATCH'])
@public_schema
def support(request, ticket_id=None):
    account = current_account(request)
    if request.method == 'POST':
        class TicketInput(serializers.Serializer):
            subject = serializers.CharField(max_length=150)
            message = serializers.CharField(max_length=5000)
        serializer = TicketInput(data=request.data)
        serializer.is_valid(raise_exception=True)
        ticket = SupportTicket.objects.create(account=account, **serializer.validated_data)
        return Response({'id': ticket.pk}, status=201)
    if request.method == 'PATCH':
        if account.role != 'ADMIN':
            raise PermissionDenied('Accès administrateur requis.')
        ticket = SupportTicket.objects.filter(pk=ticket_id).first()
        if not ticket:
            return Response({'detail': 'Signalement introuvable.'}, status=404)
        choice = request.data.get('status')
        if choice not in ['OPEN', 'IN_PROGRESS', 'RESOLVED']:
            return Response({'detail': 'Statut invalide.'}, status=400)
        ticket.status = choice
        ticket.save(update_fields=['status'])
        return Response({'id': ticket.pk, 'status': ticket.status})
    items = SupportTicket.objects.select_related('account', 'account__laboratory')
    if account.role != 'ADMIN':
        items = items.filter(account=account)
    return Response([{'id': item.pk, 'name': item.account.name, 'laboratory': item.account.laboratory.name if item.account.laboratory else '', 'subject': item.subject, 'message': item.message, 'status': item.status, 'created_at': item.created_at} for item in items[:200]])


@api_view(['GET', 'POST'])
@public_schema
def dentist_orders(request):
    account = current_account(request)
    if account.role != 'DENTIST':
        raise PermissionDenied('Accès réservé aux dentistes.')
    from api.models import Prescription
    from api.serializers import PrescriptionSerializer
    if request.method == 'POST':
        lab = Client.objects.exclude(schema_name='public').filter(schema_name=request.data.get('laboratory_id'), is_active=True).first()
        if not lab:
            return Response({'laboratory_id': ['Choisissez un laboratoire valide.']}, status=400)
        with schema_context(lab.schema_name):
            import uuid, hashlib, json
            from django.db import connection
            from api.models import CaseCommandReceipt
            try:
                key = uuid.UUID(request.headers.get('Idempotency-Key', ''))
            except ValueError as exc:
                raise serializers.ValidationError('A UUID Idempotency-Key is required.') from exc
            digest = hashlib.sha256(json.dumps(request.data, sort_keys=True, default=str).encode()).hexdigest()
            with transaction.atomic():
                with connection.cursor() as cursor:
                    cursor.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))', [f'create:{lab.schema_name}:{key}'])
                receipt = CaseCommandReceipt.objects.filter(pk=key).first()
                if receipt:
                    order = receipt.prescription
                    if order.dentist_account_id != account.pk or receipt.command != 'CREATE' or receipt.payload_digest != digest:
                        raise serializers.ValidationError('This idempotency key belongs to a different submission.')
                    data = dict(PrescriptionSerializer(order).data)
                else:
                    serializer = PrescriptionSerializer(data={**request.data, 'dentist_name': account.name}, context={'request': request})
                    serializer.is_valid(raise_exception=True)
                    order = serializer.save(dentist_account=account)
                    CaseCommandReceipt.objects.create(idempotency_key=key, prescription=order, command='CREATE', payload_digest=digest, result={'id': str(order.pk)})
                    data = dict(PrescriptionSerializer(order).data)
                    data['delivery_pin_once'] = order._new_delivery_pin
        return Response({**data, 'laboratory_name': lab.name, 'laboratory_id': lab.schema_name}, status=201)
    data = []
    for lab in Client.objects.filter(is_active=True).exclude(schema_name='public'):
        with schema_context(lab.schema_name):
            orders = Prescription.objects.filter(dentist_account_id=account.pk)
            data.extend({**row, 'laboratory_name': lab.name, 'laboratory_id': lab.schema_name} for row in PrescriptionSerializer(orders, many=True).data)
    return Response(sorted(data, key=lambda row: row['created_at'], reverse=True))


@api_view(['GET'])
@public_schema
def pricing_catalog(request):
    from api.pricing import BASE_PRICES, EXPRESS_RATE
    return Response({'materials': {name: str(price) for name, price in BASE_PRICES.items()},
                     'express_rate': str(EXPRESS_RATE), 'next_day': 'MANUAL_QUOTE', 'currency': 'MAD'})


@api_view(['GET'])
@public_schema
def dentist_directory(request):
    account = current_account(request)
    if account.role not in {'LAB', 'ADMIN'} or (account.role == 'LAB' and account.workstation_role not in {'MANAGER', 'RECEPTION'}):
        raise PermissionDenied('Reception or administrator access required.')
    return Response(list(PlatformAccount.objects.filter(role='DENTIST', is_active=True).values('id', 'name')))


@api_view(['GET'])
@public_schema
def dentist_clinics(request):
    account = current_account(request)
    if account.role != 'DENTIST':
        raise PermissionDenied('Dentist access required.')
    lab = Client.objects.filter(schema_name=request.query_params.get('laboratory'), is_active=True).exclude(schema_name='public').first()
    if not lab:
        raise serializers.ValidationError('Choose an active laboratory.')
    from api.models import PartnerClinic
    with schema_context(lab.schema_name):
        return Response(list(PartnerClinic.objects.filter(platform_dentist=account).values('id', 'name', 'pickup_address')))


@api_view(['GET', 'POST'])
@public_schema
def dentist_case_action(request, schema_name, case_id, operation):
    from django.shortcuts import get_object_or_404
    from django.core.exceptions import ValidationError as DjangoValidationError
    from django.http import FileResponse, HttpResponse
    from api.case_commands import execute_case_command
    from api.case_serializers import PrescriptionSerializer, actor_identity
    from api.models import Prescription
    from api.business_views import translate_error
    account = current_account(request)
    if account.role != 'DENTIST':
        raise PermissionDenied('Dentist access required.')
    lab = get_object_or_404(Client, schema_name=schema_name, is_active=True)
    if lab.schema_name == 'public':
        raise PermissionDenied('Choose a laboratory.')
    with schema_context(lab.schema_name):
        order = get_object_or_404(Prescription, pk=case_id, dentist_account=account)
        try:
            if operation == 'command' and request.method == 'POST':
                order, result = execute_case_command(order.pk, request.data.get('action'), request.data.get('data', {}),
                    actor_identity(request), 'DENTIST', request.headers.get('Idempotency-Key'))
                if result.get('error'):
                    return Response({'detail': result['error']}, status=result.get('http_status', 400))
                return Response({'case': PrescriptionSerializer(order, context={'request': request}).data, 'result': result})
            if operation == 'attachments':
                if request.method == 'POST':
                    from api.documents import save_attachment
                    with transaction.atomic():
                        record = save_attachment(order, request.FILES.get('file'), request.data.get('kind'), actor_identity(request))
                    return Response({'id': str(record.pk), 'kind': record.kind}, status=201)
                return Response(list(order.attachments.values('id', 'kind', 'original_name', 'sha256', 'created_at')))
            if operation == 'evidence' and request.method == 'GET':
                return Response({'design_reviews': list(order.design_reviews.values()),
                                 'notifications': list(order.notifications.order_by('-created_at').values()[:100]),
                                 'reworks': list(order.reworks.values())})
            if operation == 'qr' and request.method == 'GET':
                from api.documents import qr_png
                return HttpResponse(qr_png(order), content_type='image/png')
            if operation == 'invoice' and request.method == 'GET':
                from api.documents import private_open
                line = getattr(order, 'statement_line', None)
                invoice = getattr(line.period, 'invoice', None) if line else None
                if invoice is None or invoice.period.clinic.platform_dentist_id != account.pk:
                    return Response({'detail': 'Invoice not available.'}, status=404)
                if not hasattr(invoice, 'document'):
                    return Response({'status': 'PDF_PENDING'}, status=202)
                return FileResponse(private_open(invoice.document.storage_name), content_type='application/pdf', as_attachment=True, filename=invoice.number + '.pdf')
        except (DjangoValidationError, ValueError, TypeError) as exc:
            raise translate_error(exc) from exc
    return Response({'detail': 'Unsupported case operation.'}, status=405)


@api_view(['GET'])
@public_schema
def dentist_attachment(request, schema_name, case_id, attachment_id):
    from django.shortcuts import get_object_or_404
    from django.http import FileResponse
    account = current_account(request)
    if account.role != 'DENTIST':
        raise PermissionDenied('Dentist access required.')
    lab = get_object_or_404(Client, schema_name=schema_name, is_active=True)
    if lab.schema_name == 'public':
        raise PermissionDenied('Choose a laboratory.')
    with schema_context(lab.schema_name):
        from api.models import Prescription, CaseAttachment
        from api.documents import private_open
        order = get_object_or_404(Prescription, pk=case_id, dentist_account=account)
        record = get_object_or_404(CaseAttachment, pk=attachment_id, prescription=order)
        return FileResponse(private_open(record.storage_name), content_type=record.content_type,
                            as_attachment=True, filename=record.original_name)