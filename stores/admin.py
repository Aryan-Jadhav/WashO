from django.contrib import admin

from .models import City, ServiceArea, Store


@admin.register(City)
class CityAdmin(admin.ModelAdmin):
    list_display = ["name", "state", "is_active"]
    prepopulated_fields = {"slug": ["name"]}
    search_fields = ["name"]


class ServiceAreaInline(admin.TabularInline):
    model = ServiceArea
    extra = 1


@admin.register(Store)
class StoreAdmin(admin.ModelAdmin):
    list_display = ["name", "city", "locality", "pincode", "phone", "opening_time", "closing_time", "is_active"]
    list_filter = ["city", "is_active"]
    search_fields = ["name", "locality", "pincode", "address"]
    prepopulated_fields = {"slug": ["name"]}
    inlines = [ServiceAreaInline]


@admin.register(ServiceArea)
class ServiceAreaAdmin(admin.ModelAdmin):
    list_display = ["name", "pincode", "store", "is_active"]
    list_filter = ["store", "is_active"]
    search_fields = ["name", "pincode"]
    list_select_related = ["store"]
