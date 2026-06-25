from django.contrib import admin

from apps.core.models import AuthorProfile


@admin.register(AuthorProfile)
class AuthorProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "display_name", "organization", "email", "updated_at")
    search_fields = ("user__username", "display_name", "organization", "email")
