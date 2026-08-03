from django.contrib import admin

from apps.core.models import AuthorProfile, OrganizationSettings


@admin.register(AuthorProfile)
class AuthorProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "display_name", "organization", "email", "default_jurisdiction", "updated_at")
    search_fields = ("user__username", "display_name", "organization", "email", "default_jurisdiction")


@admin.register(OrganizationSettings)
class OrganizationSettingsAdmin(admin.ModelAdmin):
    list_display = ("__str__", "default_jurisdiction", "letter_filename_pattern")
    fields = ("default_jurisdiction", "letter_filename_pattern", "letter_filename_section_limit")

    def has_add_permission(self, request):
        return not OrganizationSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False
