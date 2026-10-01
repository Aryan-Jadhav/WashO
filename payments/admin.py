from django.contrib import admin

from .models import Payment


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    """Read-only: payments are recorded by the agent at delivery."""

    list_display = ["order", "amount", "method", "collected_by", "collected_at", "reference"]
    list_filter = ["method", "collected_at", "order__store"]
    search_fields = ["order__code", "reference", "collected_by__phone"]
    list_select_related = ["order", "collected_by"]
    date_hierarchy = "collected_at"
    readonly_fields = ["order", "method", "amount", "collected_by", "collected_at", "reference"]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False  # money records are never deleted
