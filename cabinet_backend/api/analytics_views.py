import re
from datetime import date, timedelta

from django.utils import timezone
from rest_framework import serializers, viewsets
from rest_framework.exceptions import ValidationError
from rest_framework.pagination import PageNumberPagination

from .analytics import PIPELINE
from .models import AnalyticsRefreshState, MonthlyBillingCatalog, MonthlyBillingSummary, MonthlyStockLossCatalog
from .models import MonthlyStatementCatalog, MonthlyFinancialCatalog
from .permissions import LaboratoryResourcePermission


class BillingCatalogSerializer(serializers.ModelSerializer):
    class Meta:
        model = MonthlyBillingCatalog
        fields = '__all__'


class BillingSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = MonthlyBillingSummary
        fields = '__all__'


class AnalyticsPagination(PageNumberPagination):
    page_size = 50
    page_size_query_param = 'page_size'
    max_page_size = 200


class BillingAnalyticsViewSet(viewsets.ReadOnlyModelViewSet):
    month_field = 'billing_month'
    clinic_field = 'partner_clinic_id'
    read_roles = {'MANAGER', 'COMPTABILITE'}
    permission_classes = [LaboratoryResourcePermission]
    pagination_class = AnalyticsPagination
    http_method_names = ['get', 'head', 'options']

    def get_queryset(self):
        queryset = super().get_queryset()
        month = self.request.query_params.get('month')
        if month:
            if not re.fullmatch(r'\d{4}-(0[1-9]|1[0-2])', month):
                raise ValidationError({'month': 'Use YYYY-MM.'})
            try:
                month_date = date(int(month[:4]), int(month[5:]), 1)
            except ValueError as exc:
                raise ValidationError({'month': 'Invalid calendar month.'}) from exc
            queryset = queryset.filter(**{self.month_field: month_date})
        if self.month_field == 'loss_month':
            item = self.request.query_params.get('inventory_item')
            if item:
                if not item.isascii() or not item.isdigit() or len(item) > 19 or not 0 < int(item) <= 9223372036854775807:
                    raise ValidationError({'inventory_item': 'Use a positive inventory item ID.'})
                queryset = queryset.filter(inventory_item_id=int(item))
            return queryset
        clinic = self.request.query_params.get('clinic')
        if clinic == 'unassigned':
            queryset = queryset.filter(**{self.clinic_field + '__isnull': True})
        elif clinic:
            if not clinic.isascii() or not clinic.isdigit() or len(clinic) > 19 or not 0 < int(clinic) <= 9223372036854775807:
                raise ValidationError({'clinic': 'Use a positive clinic ID or unassigned.'})
            queryset = queryset.filter(**{self.clinic_field: int(clinic)})
        return queryset

    def list(self, request, *args, **kwargs):
        response = super().list(request, *args, **kwargs)
        state = AnalyticsRefreshState.objects.filter(pipeline=PIPELINE).first()
        last_success = state.last_success_at if state else None
        response.data['analytics'] = {
            'last_refreshed_at': last_success.isoformat() if last_success else None,
            'last_attempt_at': state.last_attempt_at.isoformat() if state and state.last_attempt_at else None,
            'stale': last_success is None or timezone.now() - last_success > timedelta(minutes=20),
            'refresh_failed': bool(state and state.last_error),
            'refresh_interval_seconds': 900,
            'undated_invoice_count': state.undated_invoice_count if state else None,
            'currency': 'MAD',
        }
        return response


class MonthlyBillingCatalogViewSet(BillingAnalyticsViewSet):
    queryset = MonthlyBillingCatalog.objects.all()
    serializer_class = BillingCatalogSerializer


class MonthlyBillingSummaryViewSet(BillingAnalyticsViewSet):
    queryset = MonthlyBillingSummary.objects.all()
    serializer_class = BillingSummarySerializer


class StockLossSerializer(serializers.ModelSerializer):
    class Meta:
        model = MonthlyStockLossCatalog
        fields = '__all__'


class MonthlyStockLossViewSet(BillingAnalyticsViewSet):
    read_roles = {'MANAGER', 'FAO', 'QUALITE', 'COMPTABILITE'}
    month_field = 'loss_month'
    queryset = MonthlyStockLossCatalog.objects.all()
    serializer_class = StockLossSerializer


class StatementCatalogSerializer(serializers.ModelSerializer):
    class Meta:
        model = MonthlyStatementCatalog
        fields = '__all__'


class FinancialCatalogSerializer(serializers.ModelSerializer):
    class Meta:
        model = MonthlyFinancialCatalog
        fields = '__all__'


class MonthlyStatementCatalogViewSet(BillingAnalyticsViewSet):
    month_field = 'closing_month'
    clinic_field = 'clinic_id'
    queryset = MonthlyStatementCatalog.objects.all()
    serializer_class = StatementCatalogSerializer


class MonthlyFinancialCatalogViewSet(BillingAnalyticsViewSet):
    month_field = 'closing_month'
    clinic_field = 'clinic_id'
    queryset = MonthlyFinancialCatalog.objects.all()
    serializer_class = FinancialCatalogSerializer
