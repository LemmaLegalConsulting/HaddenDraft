from django.db import models
from django.core.validators import FileExtensionValidator


word_template_validator = FileExtensionValidator(["docx", "dotx"])


class DocumentTemplate(models.Model):
    SOURCE_KIND_CHOICES = [
        ("database", "Database/admin managed"),
        ("content_library", "Content library"),
    ]
    TEMPLATE_KIND_CHOICES = [
        ("answer_counterclaims", "Answer and Counterclaims"),
        ("motion", "Motion"),
        ("brief", "Brief"),
        ("hearing_statement", "Hearing Statement"),
        ("shell", "Drafting shell"),
    ]

    title = models.CharField(max_length=255)
    slug = models.SlugField(max_length=120, unique=True)
    kind = models.CharField(max_length=80, choices=TEMPLATE_KIND_CHOICES)
    description = models.TextField(blank=True)
    jurisdiction = models.CharField(max_length=255, blank=True)
    source_label = models.CharField(max_length=255, default="Internal template")
    metadata = models.JSONField(default=dict, blank=True)
    source_kind = models.CharField(max_length=40, choices=SOURCE_KIND_CHOICES, default="database")
    content_path = models.CharField(
        max_length=500,
        blank=True,
        help_text="Provider-relative path to a prepared template manifest.",
    )
    source_checksum = models.CharField(max_length=64, blank=True)
    is_active = models.BooleanField(default=True)
    last_synced_at = models.DateTimeField(null=True, blank=True)
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
    content_path = models.CharField(
        max_length=500,
        blank=True,
        help_text="Provider-relative path to this block's DOCX snippet, when present.",
    )
    source_checksum = models.CharField(max_length=64, blank=True)
    input_schema = models.JSONField(default=dict, blank=True)
    lexical_config = models.JSONField(default=dict, blank=True)
    editable = models.BooleanField(default=True)

    class Meta:
        unique_together = [("template", "key")]
        ordering = ["order", "id"]

    def __str__(self):
        return f"{self.template}: {self.label}"
