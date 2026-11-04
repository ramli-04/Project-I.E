import logging

from django.db import DatabaseError, connection, transaction
from django.utils import timezone
from django_tenants.utils import get_public_schema_name, get_tenant_model, schema_context, tenant_context
from psycopg2 import sql

from .models import AnalyticsRefreshState, MonthlyBillingCatalog

logger = logging.getLogger(__name__)
PIPELINE = 'monthly_billing_catalog'


def refresh_billing_catalog(schema_name):
    if schema_name == get_public_schema_name():
        return {'schema_name': schema_name, 'status': 'skipped', 'reason': 'public_schema'}
    with schema_context(get_public_schema_name()):
        tenant = get_tenant_model().objects.filter(schema_name=schema_name, is_active=True).first()
    if tenant is None:
        return {'schema_name': schema_name, 'status': 'skipped', 'reason': 'inactive_or_missing_tenant'}

    with tenant_context(tenant):
        attempt = timezone.now()
        try:
            # Atomic publication keeps detail, monthly totals and freshness aligned.
            with transaction.atomic():
                with connection.cursor() as cursor:
                    cursor.execute(
                        'SELECT pg_try_advisory_xact_lock(hashtextextended(%s, 0))',
                        [f'cabinet:billing-refresh:{schema_name}'],
                    )
                    if not cursor.fetchone()[0]:
                        return {'schema_name': schema_name, 'status': 'skipped', 'reason': 'already_refreshing'}
                    cursor.execute("SET LOCAL statement_timeout = '120s'")
                    cursor.execute("SET LOCAL lock_timeout = '5s'")
                    for name in ('monthly_billing_catalog', 'monthly_billing_summary', 'monthly_stock_loss_catalog', 'monthly_statement_catalog', 'monthly_financial_catalog'):
                        cursor.execute(sql.SQL('REFRESH MATERIALIZED VIEW CONCURRENTLY {}').format(
                            sql.Identifier(schema_name, name),
                        ))
                AnalyticsRefreshState.objects.update_or_create(
                    pipeline=PIPELINE,
                    defaults={
                        'last_attempt_at': attempt,
                        'last_success_at': timezone.now(),
                        'last_error': '',
                        'undated_invoice_count': MonthlyBillingCatalog.objects.filter(legacy_invoice_without_date=True).count(),
                    },
                )
        except DatabaseError as exc:
            try:
                AnalyticsRefreshState.objects.update_or_create(
                    pipeline=PIPELINE,
                    defaults={'last_attempt_at': attempt, 'last_error': str(exc)[:2000]},
                )
            except DatabaseError:
                logger.exception('Could not record billing refresh failure for tenant %s', schema_name)
            raise
    return {'schema_name': schema_name, 'status': 'refreshed'}
