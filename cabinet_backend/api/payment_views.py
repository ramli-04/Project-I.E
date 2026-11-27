from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError
from rest_framework import viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from .business_views import BusinessPagination, translate_error
from .case_serializers import actor_identity
from .models import Payment
from .payment_serializers import PaymentSerializer, ReversalSerializer, ReceivablesSerializer
from .payments import PaymentConflict, record_payment, reverse_payment, receivables
from .permissions import LaboratoryResourcePermission


class PaymentPermission(LaboratoryResourcePermission):
    def has_permission(self, request, view):
        view.read_roles = view.write_roles = {'MANAGER', 'COMPTABILITE'}
        return super().has_permission(request, view)


class PaymentViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [PaymentPermission]
    pagination_class = BusinessPagination
    serializer_class = PaymentSerializer
    queryset = Payment.objects.select_related('clinic', 'reversal').prefetch_related('allocations').order_by('-created_at', 'pk')

    def create(self, request):
        try:
            payment = record_payment(request.data, actor_identity(request), request.headers.get('Idempotency-Key'))
        except PaymentConflict as exc:
            return Response({'detail': exc.messages[0]}, status=409)
        except DjangoValidationError as exc:
            raise translate_error(exc) from exc
        except IntegrityError as exc:
            raise ValidationError('Invalid payment payload.') from exc
        return Response(self.get_serializer(self.get_queryset().get(pk=payment.pk)).data, status=201)

    @action(detail=True, methods=['post'])
    def reverse(self, request, pk=None):
        payment = self.get_object()
        if not isinstance(request.data, dict):
            raise ValidationError('Choose a payment reversal reason.')
        notes = request.data.get('notes', '')
        if not isinstance(notes, str):
            raise ValidationError('Invalid payment payload.')
        try:
            result = reverse_payment(payment.pk, request.data.get('reason'), notes.strip(), actor_identity(request))
        except DjangoValidationError as exc:
            raise translate_error(exc) from exc
        return Response(ReversalSerializer(result).data, status=201)


@api_view(['GET'])
@permission_classes([PaymentPermission])
def receivables_view(request):
    return Response(ReceivablesSerializer(receivables(), many=True).data)
