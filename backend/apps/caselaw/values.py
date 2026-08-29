"""One comparable string per entry in an extracted list field.

``issues``, ``statutes_cited``, ``cases_cited`` and their neighbours were
filled by a model reading scanned opinions one document at a time against no
schema.  Most entries came back as plain strings.  A minority came back as
objects, and not as one shape of object: a cited case arrives as
``{"case_name", "citation"}`` on one decision, ``{"citation", "description"}``
on the next, and ``{"cite", "court", "reporter", "year"}`` on a third.

Nothing downstream expected that.  ``Counter`` raised ``unhashable type:
'dict'`` on the facet counts, which is why ``/api/caselaw/browse/`` answered
500 for every seed decision; the catalog's facets grouped by ``str(dict)`` and
so shelved one authority under its Python repr; and the frontend renders these
lists an item at a time, which React refuses to do for an object.

The stored rows keep the shape they arrived in -- the description an object
carries is evidence about where the value came from, and rewriting the corpus
would throw it away.  Everything that counts, groups, scores, or shows one of
these fields reads it through here instead, and gets the identity of the entry:
the statute, the case, the issue -- not the commentary attached to it.
"""

from __future__ import annotations

#: Keys that carry the entry itself, most specific first.  A statute's identity
#: is its number and an issue's is its text, so the object's other keys
#: (``description``, ``context``, ``jurisdiction``) are commentary and are left
#: out of the value that gets counted and grouped.
IDENTITY_KEYS = (
    "statute",
    "regulation",
    "rule",
    "rule_text",
    "issue",
    "issue_text",
    "holding",
    "holding_text",
    "statement",
    "short",
    "case_name",
    "case",
    "name",
    "party",
    "title",
    "label",
    "text",
    "value",
)

CITATION_KEYS = ("citation", "cite")

#: What a party is in the case. ``party_roles`` is nothing but this, so an
#: entry reduced to the name alone would say the same thing as ``parties`` and
#: lose the only fact the field exists to carry.
ROLE_KEYS = (
    "role",
    "roles",
    "role_description",
    "role_detail",
    "role_label",
    "role_in_case",
    "role_type",
    "party_role",
    "party_role_detail",
    "party_type",
)


def _scalar(value):
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, dict):
        return text_value(value)
    if isinstance(value, (list, tuple)):
        return "; ".join(part for part in (_scalar(item) for item in value) if part)
    return str(value).strip()


def _first(item, keys):
    for key in keys:
        text = _scalar(item.get(key))
        if text:
            return text
    return ""


def text_value(item):
    """The display string for one entry, whatever shape it arrived in."""
    if not isinstance(item, dict):
        return _scalar(item)
    identity = _first(item, IDENTITY_KEYS)
    citation = _first(item, CITATION_KEYS)
    # A cited case is named by both halves -- "Pepper Pike v. Doe" and the
    # reporter cite identify it together, and either alone is how the same
    # case ends up shelved twice.
    if identity and citation and citation not in identity:
        return f"{identity}, {citation}"
    role = _first(item, ROLE_KEYS)
    if identity and role:
        return f"{identity} — {role}"
    if identity or citation:
        return identity or citation
    # An object with no key this knows about still holds a value a reader can
    # recognize, so show it rather than dropping the entry.
    return "; ".join(part for part in (_scalar(value) for value in item.values()) if part)


def text_values(value):
    """Every entry of a JSON list field as a string, with the empties dropped."""
    if not isinstance(value, list):
        return []
    return [text for text in (text_value(item) for item in value) if text]
