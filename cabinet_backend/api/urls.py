from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import PrescriptionViewSet, StaffMemberViewSet, EquipmentViewSet, StockItemViewSet, alerts_view
from .views import EmployeeProfileViewSet, MachineViewSet, InventoryViewSet, PartnerClinicViewSet
from .analytics_views import MonthlyBillingCatalogViewSet, MonthlyBillingSummaryViewSet
from .analytics_views import MonthlyStockLossViewSet
from .analytics_views import MonthlyStatementCatalogViewSet, MonthlyFinancialCatalogViewSet
from .views import InventoryTransactionViewSet
from .business_views import (ProductionLotViewSet, BillingPeriodViewSet, StatementLineViewSet,
    FinanceInvoiceViewSet, BillingDisputeViewSet, OutboxViewSet, MessageDeliveryViewSet, CreditNoteViewSet)
from .planning_views import (PlanningTaskViewSet, PlanningEventViewSet, AvailabilityViewSet, QualificationViewSet,
    planning_settings, workload_view, recalculate_view, planning_accounts)

router = DefaultRouter()
router.register(r'planning/tasks', PlanningTaskViewSet, basename='planning-task')
router.register(r'planning/events', PlanningEventViewSet, basename='planning-event')
router.register(r'planning/availability', AvailabilityViewSet, basename='planning-availability')
router.register(r'planning/qualifications', QualificationViewSet, basename='planning-qualification')
router.register(r"prescriptions", PrescriptionViewSet, basename="prescription")
router.register(r"staff", StaffMemberViewSet, basename="staff")
router.register(r"equipment", EquipmentViewSet, basename="equipment")
router.register(r"stock", StockItemViewSet, basename="stock")
router.register(r"employee-profiles", EmployeeProfileViewSet, basename="employee-profile")
router.register(r"machines", MachineViewSet, basename="machine")
router.register(r"inventory", InventoryViewSet, basename="inventory")
router.register(r"inventory-transactions", InventoryTransactionViewSet, basename="inventory-transaction")
router.register(r"analytics/stock-loss", MonthlyStockLossViewSet, basename="stock-loss")
router.register(r"partner-clinics", PartnerClinicViewSet, basename="partner-clinic")
router.register(r"analytics/billing-catalog", MonthlyBillingCatalogViewSet, basename="billing-catalog")
router.register(r"analytics/monthly-billing", MonthlyBillingSummaryViewSet, basename="monthly-billing")
router.register(r'production-lots', ProductionLotViewSet, basename='production-lot')
router.register(r'billing/periods', BillingPeriodViewSet, basename='billing-period')
router.register(r'billing/statement-lines', StatementLineViewSet, basename='statement-line')
router.register(r'billing/invoices', FinanceInvoiceViewSet, basename='finance-invoice')
router.register(r'billing/credit-notes', CreditNoteViewSet, basename='credit-note')
router.register(r'billing/disputes', BillingDisputeViewSet, basename='billing-dispute')
router.register(r'operations/outbox', OutboxViewSet, basename='outbox')
router.register(r'operations/deliveries', MessageDeliveryViewSet, basename='message-delivery')
router.register(r'analytics/monthly-statements', MonthlyStatementCatalogViewSet, basename='monthly-statement-catalog')
router.register(r'analytics/monthly-finances', MonthlyFinancialCatalogViewSet, basename='monthly-financial-catalog')

urlpatterns = [
    path('planning/accounts/', planning_accounts, name='planning-accounts'),
    path('planning/calendar/', PlanningTaskViewSet.as_view({'get':'list'}), name='planning-calendar'),
    path('planning/workload/', workload_view, name='planning-workload'),
    path('planning/settings/', planning_settings, name='planning-settings'),
    path('planning/recalculate/', recalculate_view, name='planning-recalculate'),
    path('alerts/', alerts_view, name='laboratory-alerts'),
    path("", include(router.urls)),
]
