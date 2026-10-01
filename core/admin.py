from django.contrib import admin

from .models import FAQ, ContactMessage


@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    list_display = ["subject", "name", "email", "phone", "is_resolved", "created_at"]
    list_filter = ["is_resolved", "created_at"]
    list_editable = ["is_resolved"]
    search_fields = ["name", "email", "phone", "subject"]
    readonly_fields = ["created_at"]


@admin.register(FAQ)
class FAQAdmin(admin.ModelAdmin):
    list_display = ["question", "sort_order", "is_active"]
    list_editable = ["sort_order", "is_active"]
    search_fields = ["question", "answer"]
