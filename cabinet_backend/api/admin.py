from django.contrib import admin
from .models import Prescription


@admin.register(Prescription)
class PrescriptionAdmin(admin.ModelAdmin):
    list_display = ["patient_ref", "tooth_number", "shade", "material", "is_fast_track", "total_price", "status", "created_at"]
    list_filter = ["status", "material", "disinfected", "is_fast_track"]
    search_fields = ["patient_ref"]
    readonly_fields = ['billing_stage', 'total_price', 'workflow_history', 'delivery_pin']

    def save_model(self, request, obj, form, change):
        from .signals import prescription_audit_context
        from .case_serializers import actor_identity
        with prescription_audit_context(actor_identity(request), 'Django Admin change', {'role': 'MANAGER', 'action': 'TRANSITION'}):
            super().save_model(request, obj, form, change)
