from django.conf import settings
from django.db import models


class AuthorProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, related_name="author_profile", on_delete=models.CASCADE)
    display_name = models.CharField(max_length=255, blank=True)
    salutation = models.CharField(max_length=255, blank=True)
    signoff = models.CharField(max_length=255, default="Sincerely,")
    organization = models.CharField(max_length=255, blank=True)
    phone = models.CharField(max_length=80, blank=True)
    email = models.EmailField(blank=True)
    address = models.TextField(blank=True)
    signature_image = models.TextField(blank=True)
    preferences = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.display_name or self.user.get_username()
