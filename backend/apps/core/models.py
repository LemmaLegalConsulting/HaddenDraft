from django.conf import settings
from django.db import models


class AuthorProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, related_name="author_profile", on_delete=models.CASCADE)
    display_name = models.CharField(max_length=255, blank=True)
    salutation = models.CharField(max_length=255, blank=True)
    signoff = models.CharField(max_length=255, default="Sincerely,")
    organization = models.CharField(max_length=255, blank=True)
    # Letterhead and signature-block fields. A letterhead prints the advocate's
    # title and fax, and a filing signature block prints the bar number, so both
    # have to live on the profile rather than being typed per document.
    title = models.CharField(
        max_length=255,
        blank=True,
        help_text='Job title as it appears on letterhead, e.g. "Staff Attorney".',
    )
    bar_number = models.CharField(max_length=80, blank=True)
    phone = models.CharField(max_length=80, blank=True)
    fax = models.CharField(
        max_length=80,
        blank=True,
        help_text="Leave empty to hide the fax line on the letterhead.",
    )
    email = models.EmailField(blank=True)
    office_name = models.CharField(
        max_length=255,
        blank=True,
        help_text='Which office the advocate works from, e.g. "Cleveland" or "Elyria".',
    )
    address = models.TextField(blank=True)
    signature_image = models.TextField(blank=True)
    default_jurisdiction = models.CharField(max_length=255, blank=True)
    preferences = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.display_name or self.user.get_username()


class OrganizationSettings(models.Model):
    """Single-row operational defaults, editable through Django admin."""

    default_jurisdiction = models.CharField(max_length=255, blank=True)

    class Meta:
        verbose_name = "organization settings"
        verbose_name_plural = "organization settings"

    def __str__(self):
        return "Organization settings"
