from django.db import models
from django.core.validators import FileExtensionValidator


word_template_validator = FileExtensionValidator(["docx", "dotx"])

AI_LATITUDE_CHOICES = [
    ("locked", "Locked - render the maintained wording verbatim"),
    ("guided", "Guided - maintained wording, rewritable on review"),
    ("generate", "Generate - the model writes this block"),
]


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
        ("worksheet", "Spreadsheet exhibit"),
    ]

    title = models.CharField(max_length=255)
    slug = models.SlugField(max_length=120, unique=True)
    kind = models.CharField(max_length=80, choices=TEMPLATE_KIND_CHOICES)
    description = models.TextField(blank=True)
    goal = models.TextField(blank=True)
    negative_goal = models.TextField(blank=True)
    aliases = models.JSONField(default=list, blank=True)
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


class Letterhead(models.Model):
    """An organization's stationery, parameterized by advocate.

    One record serves every advocate. The masthead, margins, and section setup
    come from the DOCX; the contact block is filled from the author's profile at
    render time, so adding an advocate does not mean adding a document.
    """

    SOURCE_KIND_CHOICES = [
        ("database", "Uploaded through admin"),
        ("content_library", "Content library"),
    ]

    slug = models.SlugField(max_length=120, unique=True)
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    organization = models.CharField(max_length=255, blank=True)
    docx = models.FileField(
        upload_to="letterheads/",
        blank=True,
        validators=[word_template_validator],
        help_text=(
            "A .docx/.dotx whose advocate contact lines are Jinja variables. "
            "Upload an ordinary letterhead and the admin will parameterize it."
        ),
    )
    content_path = models.CharField(
        max_length=500,
        blank=True,
        help_text="Provider-relative path when the letterhead ships in the content library.",
    )
    source_kind = models.CharField(max_length=40, choices=SOURCE_KIND_CHOICES, default="database")
    is_default = models.BooleanField(
        default=False,
        help_text="Used for letters when the advocate's office does not name its own.",
    )
    is_active = models.BooleanField(default=True)
    is_placeholder = models.BooleanField(
        default=False,
        help_text="A neutral stand-in shipped so a fresh install can draft letters.",
    )
    variables = models.JSONField(default=list, blank=True)
    preparation_report = models.JSONField(
        default=dict,
        blank=True,
        help_text="What the parameterizer replaced, kept for auditing an upload.",
    )
    source_checksum = models.CharField(max_length=64, blank=True)
    last_synced_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-is_default", "title"]

    def __str__(self):
        return self.title


class AdviceLetterSection(models.Model):
    """One interchangeable piece of a client advice letter.

    Kept separate from DocumentTemplate because these are not filings. A letter
    is a wrapper plus however many of these the tenant's situation calls for, so
    the unit that gets picked, ranked, and reviewed is the section rather than
    the document.
    """

    ROLE_CHOICES = [
        ("intro", "Opening"),
        ("body", "Advice section"),
        ("closing", "Closing"),
    ]
    LETTER_TYPE_CHOICES = [
        ("brief_advice", "Brief advice"),
        ("full_rep", "Full representation action item"),
    ]
    STATUS_CHOICES = [
        ("ready", "Ready to send"),
        ("needs_review", "Needs review - had tracked changes or comments"),
        ("ai_drafted", "Drafted by AI - attorney review required"),
        ("stub", "Stub - not enough content to send"),
    ]

    slug = models.SlugField(max_length=140, unique=True)
    title = models.CharField(max_length=255)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default="body")
    topic = models.CharField(max_length=120, blank=True)
    letter_type = models.CharField(max_length=40, choices=LETTER_TYPE_CHOICES, default="brief_advice")
    region = models.CharField(
        max_length=20,
        blank=True,
        help_text='"CLE", "NEO", or blank when the section applies anywhere.',
    )
    cleveland_specific = models.BooleanField(default=False)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="ready")
    body = models.TextField(blank=True)
    content_path = models.CharField(max_length=500, blank=True)
    order = models.PositiveIntegerField(default=0)
    fields = models.JSONField(default=list, blank=True)
    slots = models.JSONField(
        default=list,
        blank=True,
        help_text="Authoring notes pointing at another section, e.g. [Insert next defense].",
    )
    variants = models.JSONField(default=list, blank=True)
    selection_hints = models.JSONField(
        default=dict,
        blank=True,
        help_text="Triggers, requirements, and conflicts used to rank this section.",
    )
    readability = models.JSONField(default=dict, blank=True)
    notes = models.JSONField(default=list, blank=True)
    word_count = models.PositiveIntegerField(default=0)
    source_kind = models.CharField(max_length=40, default="content_library")
    source_checksum = models.CharField(max_length=64, blank=True)
    is_active = models.BooleanField(default=True)
    last_synced_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["topic", "order", "title"]

    def __str__(self):
        return self.title

    @property
    def sendable(self):
        """Whether the section may be offered without a warning."""
        return self.is_active and self.status == "ready"


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
    ai_latitude = models.CharField(
        max_length=20,
        choices=AI_LATITUDE_CHOICES,
        default="locked",
        help_text=(
            "How much of this block the model may write. Locked blocks render the "
            "maintained wording verbatim; guided blocks render it but accept a "
            "reviewed rewrite; generate blocks are written from the instructions."
        ),
    )
    ai_instructions = models.JSONField(
        default=list,
        blank=True,
        help_text="Drafting directions the template author wrote into this block.",
    )
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
