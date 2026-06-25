from django.db import models
from django.core.validators import FileExtensionValidator


word_template_validator = FileExtensionValidator(["docx", "dotx"])


class DocumentTemplate(models.Model):
    TEMPLATE_KIND_CHOICES = [
        ("answer_counterclaims", "Answer and Counterclaims"),
        ("motion", "Motion"),
        ("brief", "Brief"),
        ("hearing_statement", "Hearing Statement"),
        ("shell", "Drafting shell"),
    ]

    title = models.CharField(max_length=255)
    slug = models.SlugField(unique=True)
    kind = models.CharField(max_length=80, choices=TEMPLATE_KIND_CHOICES)
    description = models.TextField(blank=True)
    jurisdiction = models.CharField(max_length=255, blank=True)
    source_label = models.CharField(max_length=255, default="Internal template")
    metadata = models.JSONField(default=dict, blank=True)
    style_template = models.FileField(
        upload_to="template_styles/",
        blank=True,
        validators=[word_template_validator],
        help_text="Optional .dotx or .docx style source used as the master document for Word exports.",
    )
    replace_child_styles = models.BooleanField(
        default=True,
        help_text="When enabled, composed block documents inherit conflicting styles from the style template.",
    )
    created_from_example = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["title"]

    def __str__(self):
        return self.title


class TemplateBlock(models.Model):
    BLOCK_TYPE_CHOICES = [
        ("caption", "Caption"),
        ("facts", "Facts"),
        ("argument", "Argument"),
        ("relief", "Prayer for Relief"),
        ("signature", "Signature"),
        ("certificate", "Certificate of Service"),
        ("optional_clause", "Optional Clause"),
    ]

    template = models.ForeignKey(DocumentTemplate, related_name="blocks", on_delete=models.CASCADE)
    key = models.SlugField(max_length=120)
    label = models.CharField(max_length=255)
    block_type = models.CharField(max_length=80, choices=BLOCK_TYPE_CHOICES)
    order = models.PositiveIntegerField(default=0)
    body = models.TextField()
    docx_template = models.FileField(
        upload_to="template_blocks/",
        blank=True,
        validators=[word_template_validator],
        help_text="Optional .docx/.dotx Jinja template rendered for this block during Word export.",
    )
    required = models.BooleanField(default=True)
    ai_fill_mode = models.CharField(max_length=80, default="none")
    selection_rule = models.JSONField(default=dict, blank=True)
    supporting_sources = models.JSONField(default=list, blank=True)

    class Meta:
        unique_together = [("template", "key")]
        ordering = ["order", "id"]

    def __str__(self):
        return f"{self.template}: {self.label}"
