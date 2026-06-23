from django.db import models


class Matter(models.Model):
    external_id = models.CharField(max_length=80, unique=True)
    client_name = models.CharField(max_length=255)
    matter_type = models.CharField(max_length=255)
    jurisdiction = models.CharField(max_length=255)
    posture = models.CharField(max_length=255, blank=True)
    risk = models.CharField(max_length=120, blank=True)
    summary = models.TextField(blank=True)
    source_system = models.CharField(max_length=120, default="LegalServer")
    raw_payload = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["client_name"]

    def __str__(self):
        return f"{self.external_id} - {self.client_name}"


class MatterFact(models.Model):
    matter = models.ForeignKey(Matter, related_name="facts", on_delete=models.CASCADE)
    slug = models.SlugField(max_length=120)
    title = models.CharField(max_length=255)
    text = models.TextField()
    source_label = models.CharField(max_length=255)
    confidence = models.CharField(max_length=80, default="candidate")
    ai_suggested = models.BooleanField(default=False)
    selected_by_default = models.BooleanField(default=True)

    class Meta:
        unique_together = [("matter", "slug")]
        ordering = ["id"]

    def __str__(self):
        return self.title
