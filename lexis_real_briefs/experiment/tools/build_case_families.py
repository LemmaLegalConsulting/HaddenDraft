"""Step 1A/1E: group filings into case families and pick one focal filing each.

The unit of analysis is the lawsuit, not the file. Lexis returned several
filings from the same matter (both sides of Crenshaw, three filings from
Notarian), and counting those as independent fixtures would inflate n with
correlated observations.

Inclusion, applied to the focal filing only:
  - it must be substantive advocacy (a brief, motion or memorandum that asks
    the court to decide something), not a writ, praecipe, order or docket entry;
  - eviction/possession or an eviction-related defense must be central to an
    argument the court is asked to resolve, judged by whether the eviction
    vocabulary reaches the argument headings and not merely the background;
  - the filing's text must actually be readable, because a scanned image with
    no text layer cannot be benchmarked or minimally edited.

Appellate and trial filings are kept as separate strata rather than pooled:
they are different advocacy tasks and the Gym's court profile differs.
"""

import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "backend"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
import django  # noqa: E402
django.setup()

from apps.argument_gym import ingestion  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from filed_document import filing_from_scan, ocr_records  # noqa: E402

CORPUS = ROOT / "lexis_real_briefs"
OUT = CORPUS / "experiment"

# Two vocabularies, because they answer different questions.
#
# _EVICTION is the broad landlord-tenant field, and on its own it is a bad test:
# in a case captioned landlord v. tenant those words are party labels and appear
# in every paragraph. Texlo v. Gator Hillcrest scored 37% of its argument units
# on that vocabulary while arguing, from first line to last, about whether the
# denial of a motion for judgment on the pleadings is a final appealable order.
#
# _POSSESSION is the vocabulary a filing can only use if possession is actually
# in issue. Requiring both separates an eviction brief from a brief that merely
# happens to be between a landlord and a tenant.
_EVICTION = re.compile(
    r"forcible entry and detainer|forcible entry|\bR\.?C\.? ?1923|chapter 1923|"
    r"\bevict(?:ion|ed|s)?\b|writ of restitution|unlawful detainer|"
    r"three[- ]day notice|3[- ]day notice|notice to leave the premises|"
    r"\bR\.?C\.? ?5321|holdover|possession of the premises|landlord",
    re.IGNORECASE,
)
_POSSESSION = re.compile(
    r"forcible entry and detainer|forcible entry|forcible detainer|\bR\.?C\.? ?1923|"
    r"chapter 1923|\bevict(?:ion|ed|s|ing)?\b|writ of restitution|unlawful detainer|"
    r"three[- ]day notice|3[- ]day notice|notice to leave the premises|"
    r"right (?:of|to) possession|possession of the premises|holdover|"
    r"\bR\.?C\.? ?5321\.(?:02|03|04|15|16|17)",
    re.IGNORECASE,
)
# Documents that resolve nothing and therefore cannot host an argument mutation.
_NON_ADVOCACY = re.compile(
    r"praecipe|writ of restitution|docket|notice of appeal|judgment entry|"
    r"^order\b|exhibit list|no title in original",
    re.IGNORECASE,
)
# A filing that asks the court to decide something.
_ADVOCACY = re.compile(
    r"brief|motion|memorandum|opposition|reply|response", re.IGNORECASE
)


# Centrality thresholds. Both are needed: the count alone passes a very long
# brief that mentions a tenancy in passing a dozen times, and the fraction alone
# passes a two-paragraph filing that happens to say "landlord" once.
MIN_ARGUMENT_HITS = 5
MIN_ARGUMENT_FRACTION = 0.10
MIN_POSSESSION_HITS = 3


def centrality(units, body):
    """Does eviction reach the argument, or only the background?

    A brief that mentions an eviction in its statement of facts and then argues
    about an insurance exclusion is not an eviction brief. The test is the share
    of ARGUMENT units carrying the vocabulary, measured on the same structuring
    the Gym reads.

    Heading hits are recorded but deliberately not required. The first version
    of this test required one, and it rejected Masten v. K&D Mgmt. -- a holdover
    tenancy and Fair Housing retaliation appeal with 64 eviction-bearing
    argument units -- because its headings read "ARGUMENT" and "STATEMENT OF
    FACTS". Generic headings are the norm, so requiring a themed one measures
    drafting convention rather than subject matter.
    """
    heading_hits = argument_hits = argument_units = possession_hits = 0
    for unit in units:
        if unit["type"] == ingestion.ARGUMENT:
            argument_units += 1
            if _POSSESSION.search(unit["text"]):
                possession_hits += 1
        if not _EVICTION.search(unit["text"]):
            continue
        if unit["type"] == ingestion.SECTION:
            heading_hits += 1
        elif unit["type"] == ingestion.ARGUMENT:
            argument_hits += 1
    fraction = argument_hits / max(1, argument_units)
    return {
        "heading_hits": heading_hits,
        "argument_hits": argument_hits,
        "argument_units": argument_units,
        "argument_fraction": round(fraction, 3),
        "possession_hits": possession_hits,
        "total_mentions": len(_EVICTION.findall(body)),
        "central": (argument_hits >= MIN_ARGUMENT_HITS
                    and fraction >= MIN_ARGUMENT_FRACTION
                    and possession_hits >= MIN_POSSESSION_HITS),
    }


def main():
    records = json.loads((OUT / "inventory.json").read_text())
    families = {}

    scans = ocr_records()
    for record in records:
        path = CORPUS / record["wrapper_file"]
        if record["text_source"] == "ocr_scan":
            # The wrapper is a metadata card; the filing is the transcribed scan.
            entry = next(scans[a["file"]] for a in record["attachments"] if a["file"] in scans)
            body = filing_from_scan(entry)["brief"]
            body_lines = body.split("\n\n")
        else:
            extracted = ingestion.extract_document(path.read_bytes(), filename=path.name)
            lines = [p["text"] for p in extracted["paragraphs"]]
            body_lines = lines[record["header_line_count"]:]
            body = "\n".join(body_lines)
        units = ingestion.structure_units(
            [{"text": line, "page": None} for line in body_lines if line.strip()]
        )

        readable = record["body_chars"] > 5000
        advocacy = bool(_ADVOCACY.search(record["title"])) and not _NON_ADVOCACY.search(record["title"])
        theme = centrality(units, body) if readable else {
            "heading_hits": 0, "argument_hits": 0, "argument_units": 0,
            "argument_fraction": 0.0, "possession_hits": 0,
            "total_mentions": record["eviction_term_count"], "central": False,
        }

        reasons = []
        if not readable:
            reasons.append(
                "no readable text: the Lexis wrapper is a metadata card and the filing "
                "itself is a scanned PDF" + ("" if record["attachment_text_layer"] else " with no text layer")
            )
        if not advocacy:
            reasons.append("not a substantive advocacy filing")
        if readable and not theme["central"]:
            reasons.append(
                f"eviction is not central: {theme['argument_hits']} of "
                f"{theme['argument_units']} argument units carry landlord-tenant "
                f"vocabulary ({theme['argument_fraction']:.0%}), "
                f"{theme['possession_hits']} put possession in issue"
            )

        entry = {
            "wrapper_file": record["wrapper_file"],
            "text_source": record["text_source"],
            "has_record": bool((record.get("scan_filing") or {}).get("record_exhibits")),
            "title": record["title"],
            "lexis_type": record["lexis_type"],
            "filed": record["filed"],
            "body_chars": record["body_chars"],
            "units": len(units),
            "readable": readable,
            "advocacy": advocacy,
            "theme": theme,
            "eligible": readable and advocacy and theme["central"],
            "excluded_because": reasons,
        }

        key = (record["case_name"].strip(), record["docket"].strip())
        family = families.setdefault(key, {
            "case_family_id": "",
            "case_name": record["case_name"].strip(),
            "docket": record["docket"].strip(),
            "court": record["court"],
            "stratum": record["level"],
            "documents": [],
        })
        family["documents"].append(entry)

    ordered = []
    for (name, docket), family in sorted(families.items()):
        slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:40]
        docket_slug = re.sub(r"[^a-z0-9]+", "-", docket.lower()).strip("-")
        family["case_family_id"] = f"{slug}--{docket_slug}" if docket_slug else slug
        eligible = [d for d in family["documents"] if d["eligible"]]
        # One lawsuit, one statistical unit: the longest eligible advocacy filing
        # is the focal one, because a longer brief carries more argument to
        # mutate. The rest stay in the family as development material.
        family["focal"] = max(eligible, key=lambda d: d["body_chars"])["wrapper_file"] if eligible else None
        family["eligible_count"] = len(eligible)
        family["document_count"] = len(family["documents"])
        ordered.append(family)

    ordered.sort(key=lambda f: (f["focal"] is None, -max((d["theme"]["argument_hits"] for d in f["documents"]), default=0)))
    (OUT / "case_families.json").write_text(json.dumps(ordered, indent=2) + "\n")

    usable = [f for f in ordered if f["focal"]]
    print(f"wrote {OUT / 'case_families.json'}")
    print(f"  case families        : {len(ordered)}")
    print(f"  filings              : {sum(f['document_count'] for f in ordered)}")
    print(f"  families with a focal: {len(usable)}")
    for f in usable:
        doc = next(d for d in f["documents"] if d["wrapper_file"] == f["focal"])
        print(f"    [{f['stratum']:>9}] {f['case_name'][:30]:<30} "
              f"{doc['theme']['argument_hits']:>3}/{doc['theme']['argument_units']:<3} "
              f"({doc['theme']['argument_fraction']:>4.0%}) poss={doc['theme']['possession_hits']:>3} "
              f"chars={doc['body_chars']:>6} "
              f"{doc['text_source']:<9} rec={'Y' if doc['has_record'] else '-'}  {doc['title'][:26]}")
    print("  families with no eligible filing:")
    for f in ordered:
        if f["focal"]: continue
        why = sorted({r.split(":")[0] for d in f["documents"] for r in d["excluded_because"]})
        print(f"    [{f['stratum']:>9}] {f['case_name'][:40]:<40} n={f['document_count']}  {'; '.join(why)[:60]}")


if __name__ == "__main__":
    main()
