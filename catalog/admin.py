from django.contrib import admin

from .models import Item, ServiceCategory, ServicePrice


class ServicePriceInline(admin.TabularInline):
    model = ServicePrice
    extra = 1
    autocomplete_fields = ["item"]


@admin.register(ServiceCategory)
class ServiceCategoryAdmin(admin.ModelAdmin):
    list_display = ["name", "standard_turnaround_hours", "express_available",
                    "express_surcharge_percent", "express_turnaround_hours", "sort_order", "is_active"]
    list_editable = ["sort_order", "is_active"]
    prepopulated_fields = {"slug": ["name"]}
    search_fields = ["name"]
    inlines = [ServicePriceInline]
    fieldsets = (
        (None, {"fields": ("name", "slug", "description", "icon", "sort_order", "is_active")}),
        ("Turnaround & Express", {"fields": ("standard_turnaround_hours", "express_available",
                                              "express_surcharge_percent", "express_turnaround_hours")}),
    )


@admin.register(Item)
class ItemAdmin(admin.ModelAdmin):
    list_display = ["name", "group", "unit", "sort_order", "is_active"]
    list_editable = ["sort_order", "is_active"]
    list_filter = ["group", "is_active"]
    search_fields = ["name"]


@admin.register(ServicePrice)
class ServicePriceAdmin(admin.ModelAdmin):
    list_display = ["item", "category", "price", "is_active"]
    list_editable = ["price", "is_active"]
    list_filter = ["category", "item__group", "is_active"]
    search_fields = ["item__name", "category__name"]
    autocomplete_fields = ["item", "category"]
    list_select_related = ["item", "category"]
