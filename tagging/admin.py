from django.contrib import admin, messages

from .models import CountCheck, Garment, MismatchAlert
from .services import TaggingError, record_count


@admin.register(Garment)
class GarmentAdmin(admin.ModelAdmin):
    list_display = ["tag_code", "order", "category", "item", "has_stain", "has_damage", "tagged_by", "tagged_at"]
    list_filter = ["has_stain", "has_damage", "category", "order__store"]
    search_fields = ["tag_code", "order__code", "description"]
    list_select_related = ["order", "category", "item", "tagged_by"]
    readonly_fields = ["order", "seq", "tag_code", "category", "item", "unit_price", "express_surcharge",
                       "tagged_by", "tagged_at"]

    def has_add_permission(self, request):
        return False  # garments are tagged from the staff panel


@admin.register(CountCheck)
class CountCheckAdmin(admin.ModelAdmin):
    """Counts can be entered here too (e.g. the pickup count until the agent app exists).
    Saving goes through record_count(), so mismatch alerts are still raised."""

    list_display = ["order", "checkpoint", "count", "recorded_by", "recorded_at"]
    list_filter = ["checkpoint"]
    search_fields = ["order__code"]
    autocomplete_fields = ["order"]
    fields = ["order", "checkpoint", "count", "note"]

    def save_model(self, request, obj, form, change):
        try:
            _, alert = record_count(obj.order, obj.checkpoint, obj.count, request.user, obj.note)
        except TaggingError as e:
            messages.error(request, str(e))
            return
        if alert:
            messages.warning(request, f"Count mismatch! Alert raised: {alert}")


@admin.register(MismatchAlert)
class MismatchAlertAdmin(admin.ModelAdmin):
    list_display = ["order", "checkpoint", "expected_count", "actual_count", "status", "created_at", "resolved_by"]
    list_filter = ["status", "checkpoint", "order__store"]
    search_fields = ["order__code"]
    # Resolve alerts from Staff panel -> Mismatch alerts (it records who and when).
    readonly_fields = ["order", "checkpoint", "expected_count", "actual_count", "status", "created_at",
                       "resolved_by", "resolved_at", "resolution_note"]

    def has_add_permission(self, request):
        return False
