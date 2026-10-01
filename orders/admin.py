from django.contrib import admin, messages

from .models import Coupon, DailySlot, Order, OrderItem, OrderStatusHistory, TimeSlot
from .services import InvalidTransition, cancel_order, change_status, next_status


@admin.register(TimeSlot)
class TimeSlotAdmin(admin.ModelAdmin):
    list_display = ["__str__", "start_time", "end_time", "capacity", "is_active"]
    list_editable = ["capacity", "is_active"]


@admin.register(DailySlot)
class DailySlotAdmin(admin.ModelAdmin):
    """Read-only view of how full each slot is. Counts are changed only by bookings."""

    list_display = ["date", "time_slot", "area", "booked_count", "capacity"]
    list_filter = ["date", "area__store", "time_slot"]
    readonly_fields = ["date", "time_slot", "area", "booked_count"]
    list_select_related = ["time_slot", "area"]

    @admin.display(description="Capacity")
    def capacity(self, obj):
        return obj.time_slot.capacity

    def has_add_permission(self, request):
        return False


@admin.register(Coupon)
class CouponAdmin(admin.ModelAdmin):
    list_display = ["code", "description", "discount_type", "value", "min_order_value",
                    "valid_from", "valid_until", "usage_limit", "used", "is_active"]
    list_filter = ["is_active", "discount_type"]
    search_fields = ["code", "description"]

    @admin.display(description="Times used")
    def used(self, obj):
        return obj.times_used()


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ["category", "item", "quantity", "unit_price", "express_surcharge", "line_total"]
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


class StatusHistoryInline(admin.TabularInline):
    model = OrderStatusHistory
    extra = 0
    readonly_fields = ["from_status", "to_status", "changed_by", "note", "changed_at"]
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.action(description="Move selected orders to their NEXT status")
def advance_status(modeladmin, request, queryset):
    moved = 0
    for order in queryset:
        nxt = next_status(order)
        if nxt is None:
            continue
        try:
            change_status(order, nxt, by=request.user, note="Updated from admin site")
            moved += 1
        except InvalidTransition as e:
            messages.warning(request, f"{order}: {e}")
    messages.success(request, f"{moved} order(s) moved to the next status.")


@admin.action(description="Cancel selected orders (only before pickup)")
def cancel_orders(modeladmin, request, queryset):
    for order in queryset:
        try:
            cancel_order(order, by=request.user, reason="Cancelled by admin")
        except InvalidTransition as e:
            messages.warning(request, f"{order}: {e}")


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ["code", "customer", "status", "store", "pickup_date", "is_express", "total", "created_at"]
    list_filter = ["status", "store", "is_express", "created_at"]
    search_fields = ["code", "customer__phone", "customer__first_name", "customer__last_name"]
    list_select_related = ["customer", "store", "pickup_slot"]
    date_hierarchy = "created_at"
    actions = [advance_status, cancel_orders]
    inlines = [OrderItemInline, StatusHistoryInline]
    # WHY status is read-only here: it must only change through change_status(),
    # which checks the allowed order of statuses. Use the actions above instead.
    readonly_fields = ["code", "customer", "address", "address_snapshot", "store", "pickup_slot", "status",
                       "coupon", "estimated_total", "subtotal", "express_charge", "discount", "total",
                       "bill_finalised", "created_at", "updated_at"]
    fields = ["code", "status", "customer", "address_snapshot", "store", "pickup_slot", "is_express",
              "coupon", "estimated_total", "subtotal", "express_charge", "discount", "total",
              "bill_finalised", "customer_note", "created_at", "updated_at"]

    @admin.display(description="Pickup date", ordering="pickup_slot__date")
    def pickup_date(self, obj):
        return obj.pickup_slot.date

    def has_add_permission(self, request):
        return False  # orders are created through the booking page


@admin.register(OrderStatusHistory)
class OrderStatusHistoryAdmin(admin.ModelAdmin):
    list_display = ["order", "from_status", "to_status", "changed_by", "changed_at", "note"]
    list_filter = ["to_status", "changed_at"]
    search_fields = ["order__code"]
    list_select_related = ["order", "changed_by"]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False  # an audit trail must never be edited
