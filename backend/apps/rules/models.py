from django.conf import settings
from django.db import models


class RuleAuthority(models.Model):
    authority_type = models.CharField(max_length=50)
    citation = models.CharField(max_length=500, blank=True)
    title = models.CharField(max_length=500, blank=True)
    source_url = models.URLField(blank=True)
    source_ref = models.CharField(max_length=500, blank=True)
    pinpoint = models.CharField(max_length=255, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["authority_type", "citation", "title"]

    def __str__(self):
        return self.citation or self.title or self.authority_type


class DecisionTable(models.Model):
    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("proposed", "Proposed"),
        ("approved", "Approved"),
        ("published", "Published"),
        ("retired", "Retired"),
    ]
    HIT_POLICY_CHOICES = [
        ("collect", "Collect"),
        ("first", "First"),
        ("unique", "Unique"),
        ("priority", "Priority"),
    ]
    ENGINE_TYPE_CHOICES = [
        ("dmn_lite", "DMN-lite"),
        ("jsonlogic", "JSONLogic"),
        ("blawx", "Blawx"),
    ]

    key = models.SlugField()
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    workflow_type = models.CharField(max_length=100)
    jurisdiction = models.CharField(max_length=100, blank=True)
    court_scope = models.JSONField(default=list, blank=True)
    version = models.PositiveIntegerField(default=1)
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default="draft")
    hit_policy = models.CharField(max_length=50, choices=HIT_POLICY_CHOICES, default="collect")
    effective_start = models.DateField(null=True, blank=True)
    effective_end = models.DateField(null=True, blank=True)
    authorities = models.ManyToManyField(RuleAuthority, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    change_reason = models.TextField(blank=True)
    engine_type = models.CharField(max_length=50, choices=ENGINE_TYPE_CHOICES, default="dmn_lite")
    external_ruleset_ref = models.CharField(max_length=500, blank=True)

    class Meta:
        unique_together = [("key", "version")]
        ordering = ["key", "-version"]

    def __str__(self):
        return f"{self.key} v{self.version}"


class DecisionRuleRow(models.Model):
    table = models.ForeignKey(DecisionTable, related_name="rows", on_delete=models.CASCADE)
    row_id = models.SlugField()
    label = models.CharField(max_length=255)
    priority = models.IntegerField(default=100)
    conditions = models.JSONField()
    outputs = models.JSONField()
    explanation_template = models.TextField(blank=True)
    enabled = models.BooleanField(default=True)

    class Meta:
        unique_together = [("table", "row_id")]
        ordering = ["priority", "id"]

    def __str__(self):
        return f"{self.table.key}.{self.row_id}"


class DecisionTestCase(models.Model):
    table = models.ForeignKey(DecisionTable, related_name="test_cases", on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    inputs = models.JSONField()
    expected_outputs = models.JSONField()
    enabled = models.BooleanField(default=True)

    class Meta:
        ordering = ["table__key", "name", "id"]

    def __str__(self):
        return f"{self.table}: {self.name}"


class RuleRunLog(models.Model):
    case_id = models.CharField(max_length=255)
    workflow_run_id = models.CharField(max_length=255, blank=True)
    table_key = models.SlugField()
    table_version = models.PositiveIntegerField()
    input_snapshot = models.JSONField()
    matched_rows = models.JSONField(default=list)
    outputs = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["case_id", "workflow_run_id"]),
            models.Index(fields=["table_key", "table_version"]),
        ]

    def __str__(self):
        return f"{self.case_id}: {self.table_key} v{self.table_version}"


class CourtProfile(models.Model):
    """One court's identity and its deterministic filing requirements.

    Two jobs: recognizing that a document is headed to this court, and saying
    what a document filed here has to look like. These are format rules -- what
    a clerk would reject -- not law, and they live here rather than in a feature
    app because draft validation wants the same answers the Argument Gym does.

    A profile states its own verification status because a wrong local rule is
    worse than a missing one: it reports a filing as clean when it is not. Only
    a verified profile's requirements are reported as errors.
    """

    MUNICIPAL = "municipal"
    COUNTY = "county"
    COMMON_PLEAS = "common_pleas"
    APPELLATE = "appellate"
    SUPREME = "supreme"
    FEDERAL_DISTRICT = "federal_district"
    FEDERAL_APPELLATE = "federal_appellate"
    ADMINISTRATIVE = "administrative"
    COURT_TYPE_CHOICES = [
        (MUNICIPAL, "Municipal court"),
        (COUNTY, "County court"),
        (COMMON_PLEAS, "Court of common pleas"),
        (APPELLATE, "Court of appeals"),
        (SUPREME, "Supreme court"),
        (FEDERAL_DISTRICT, "Federal district court"),
        (FEDERAL_APPELLATE, "Federal court of appeals"),
        (ADMINISTRATIVE, "Administrative tribunal"),
    ]
    # A municipality identifies a trial court and means nothing for an appellate
    # district or a state-wide court, so those types never ask for one.
    MUNICIPAL_TYPES = {MUNICIPAL, COUNTY, COMMON_PLEAS, ADMINISTRATIVE}

    VERIFIED = "verified"
    UNVERIFIED = "unverified"
    VERIFICATION_CHOICES = [
        (VERIFIED, "Checked against the court's published rules"),
        (UNVERIFIED, "Starter profile, not checked against this court's rules"),
    ]

    slug = models.SlugField(max_length=140, unique=True)
    name = models.CharField(max_length=255)
    court_type = models.CharField(max_length=40, choices=COURT_TYPE_CHOICES)
    state = models.CharField(max_length=120, blank=True)
    county = models.CharField(max_length=120, blank=True)
    municipality = models.CharField(max_length=120, blank=True)
    division = models.CharField(max_length=160, blank=True)
    aliases = models.JSONField(default=list, blank=True, help_text="Other names this court is written under.")
    verification = models.CharField(max_length=30, choices=VERIFICATION_CHOICES, default=UNVERIFIED)
    source = models.CharField(max_length=500, blank=True, help_text="The local rule these requirements come from.")
    source_url = models.URLField(blank=True)
    verified_on = models.DateField(null=True, blank=True)
    pleading_types = models.JSONField(default=list, blank=True)
    formatting = models.JSONField(default=dict, blank=True)
    required_elements = models.JSONField(default=list, blank=True)
    notes = models.TextField(blank=True)
    active = models.BooleanField(default=True)
    is_locally_edited = models.BooleanField(
        default=False,
        help_text="Set when this profile was edited here. Re-seeding from the content library skips it.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["state", "name"]

    def __str__(self):
        return self.name

    @property
    def uses_municipality(self):
        return self.court_type in self.MUNICIPAL_TYPES

    def label(self):
        parts = [self.name]
        if self.division and self.division not in self.name:
            parts.append(self.division)
        return ", ".join(parts)

    def place(self):
        """The geography that identifies this court, omitting what does not apply."""
        parts = []
        if self.uses_municipality and self.municipality:
            parts.append(self.municipality)
        if self.county:
            parts.append(f"{self.county} County")
        if self.state:
            parts.append(self.state)
        return ", ".join(parts)


class LegalRuleProfile(models.Model):
    """A legal rule, the elements it requires, and how to tell it was invoked.

    An advocate who cites a rule has taken on its elements. This is the
    checklist that makes that auditable: which words in a brief mean the rule
    was invoked, and what has to be pleaded and supported once it was.

    Elements can also be pulled from a published `DecisionTable` row, so a rule
    the issue-selection tables already encode is not written down twice. The
    table says which facts a row depends on and what is still missing; this
    reads the same list as an element checklist for the brief.

    Like `CourtProfile`, a profile states its own verification. These elements
    are substantive law, and an unverified list is a starting point for someone
    who will check it, not an authority.
    """

    STATUTE = "statute"
    CIVIL_RULE = "civil_rule"
    LOCAL_RULE = "local_rule"
    DOCTRINE = "doctrine"
    RULE_TYPE_CHOICES = [
        (STATUTE, "Statute"),
        (CIVIL_RULE, "Rule of procedure"),
        (LOCAL_RULE, "Local rule"),
        (DOCTRINE, "Common-law doctrine"),
    ]

    slug = models.SlugField(max_length=140, unique=True)
    name = models.CharField(max_length=255)
    citation = models.CharField(max_length=255, help_text="How the rule is cited, e.g. R.C. 1923.04.")
    rule_type = models.CharField(max_length=40, choices=RULE_TYPE_CHOICES, default=STATUTE)
    jurisdiction = models.CharField(max_length=160, blank=True)
    summary = models.TextField(blank=True)
    citation_patterns = models.JSONField(
        default=list,
        blank=True,
        help_text="Regular expressions that mean this rule was cited.",
    )
    aliases = models.JSONField(
        default=list,
        blank=True,
        help_text="Phrases that invoke the rule without citing it, e.g. 'three-day notice'.",
    )
    elements = models.JSONField(
        default=list,
        blank=True,
        help_text="[{'id', 'label', 'requirement', 'patterns', 'needs_record_support', 'note'}]",
    )
    decision_table_key = models.SlugField(
        max_length=140,
        blank=True,
        help_text="A published decision table whose row already encodes this rule's requirements.",
    )
    decision_table_row = models.SlugField(max_length=140, blank=True)
    verification = models.CharField(
        max_length=30,
        choices=CourtProfile.VERIFICATION_CHOICES,
        default=CourtProfile.UNVERIFIED,
    )
    source = models.CharField(max_length=500, blank=True)
    source_url = models.URLField(blank=True)
    verified_on = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)
    active = models.BooleanField(default=True)
    is_locally_edited = models.BooleanField(
        default=False,
        help_text="Set when this profile was edited here. Re-seeding from the content library skips it.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["jurisdiction", "citation", "name"]

    def __str__(self):
        return f"{self.citation} - {self.name}"

    def label(self):
        return f"{self.name} ({self.citation})" if self.citation else self.name
