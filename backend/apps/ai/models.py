from django.db import models


class PromptOverride(models.Model):
    """An optional database override for a file-backed prompt catalog entry."""

    key = models.CharField(max_length=120, unique=True)
    system = models.TextField()
    user = models.TextField()
    default_model = models.CharField(max_length=120, blank=True)
    default_reasoning_level = models.CharField(max_length=40, blank=True)
    enabled = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["key"]

    def __str__(self):
        return self.key
