"""Materialize the fixture tree: immutable source, normalized control, mutant.

Layout, per the experiment plan:

    fixtures/F004/
      source/original.docx        immutable Lexis delivery
      source/original.pdf         the as-filed scan, where Lexis supplied one
      normalized/brief.txt        what is actually benchmarked (control)
      normalized/attachments/     authorities Lexis appended after the filing
      mutant/brief.txt            control with exactly one change applied
      mutant/attachments/         byte-identical to normalized/attachments
      fixture.json                the gold label -- never given to the Gym

The builder refuses to write a fixture whose `find` string does not occur
exactly once in the control, and records the character delta of every mutation,
so "minimally altered" is a checked property rather than a claim.
"""

import hashlib
import json
import os
import re
import shutil
import sys
from datetime import date
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "backend"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
import django  # noqa: E402
django.setup()

sys.path.insert(0, str(Path(__file__).resolve().parent))
from normalize import NORMALIZATION_VERSION, normalize_one, sha256_file, sha256_text  # noqa: E402
from filed_document import filing_from_scan, ocr_records  # noqa: E402

CORPUS = ROOT / "lexis_real_briefs"
OUT = CORPUS / "experiment"
FIXTURES = OUT / "fixtures"

# Recorded in every fixture so a later reader knows what produced the mutants.
GENERATOR = {
    "mutations_authored_by": "claude-opus-5",
    "control_text_prepared_by": "claude-opus-5 (selection, normalization and splitting only; no wording changed)",
    "generator_display_name": "Claude Opus 5 (Claude Code)",
    "generator_role": "drafted the candidate mutations and the gold-vulnerability text",
    "authored_on": "2026-09-08",
    "human_review": "none yet",
}


class MutationError(RuntimeError):
    pass


def control_for(record, scans):
    """The control text, and the record filed with it, from either delivery shape.

    Two sources, chosen by how Lexis delivered the filing:

    * `lexis_docx` -- the wrapper carries a transcription of the filed text.
      That transcription is the control. Where the scan that came with it runs
      past the brief, the pages after the certificate of service are carried in
      as the record: Lexis transcribed the brief and dropped the appendix, so
      the appendix exists only in the scan.

    * `ocr_scan` -- the wrapper is a metadata card and the filing is the scan.
      The transcription from Azure Document Intelligence is the control, split
      at the certificate of service, and everything behind it is the record.

    A fixture therefore says which transcription its control came from, because
    OCR text carries misreadings that a Lexis transcription does not. That is a
    difference between strata, not within a pair: control and mutant of one
    fixture always come from the same transcription of the same file.
    """
    scan = next((scans[a["file"]] for a in record["attachments"] if a["file"] in scans), None)
    filing = filing_from_scan(scan) if scan else None

    if record["text_source"] == "ocr_scan":
        return filing["brief"], filing["exhibits"], {
            "control_text_source": "ocr_scan",
            "ocr": filing["ocr"],
            "scan_split_rule": filing["split_rule"],
            "scan_brief_page_count": filing["brief_page_count"],
            "page_furniture_removed": filing["furniture_removed"],
            "normalization_log": None,
        }

    normalized = normalize_one(record)
    exhibits = filing["exhibits"] if filing else []
    return normalized["brief"], exhibits, {
        "control_text_source": "lexis_docx",
        "ocr": filing["ocr"] if filing else None,
        "record_recovered_from_scan": bool(exhibits),
        "scan_split_rule": filing["split_rule"] if filing else None,
        "normalization_log": normalized["log"],
        "appended_authorities": normalized["appended_authorities"],
    }


def apply_mutation(control, spec):
    find = spec["find"]
    count = control.count(find)
    if count != 1:
        raise MutationError(
            f"`find` matched {count} times, expected exactly 1:\n{find[:120]}..."
        )
    mutant = control.replace(find, spec["replace"], 1)
    # A deletion leaves the paragraph separator behind; collapse it so the
    # mutant has no structural tell that the control lacks.
    mutant = mutant.replace("\n\n\n\n", "\n\n").replace("\n\n\n", "\n\n")
    mutant = "\n".join(line.rstrip() for line in mutant.splitlines()).strip() + "\n"
    return mutant


def find_source_pdf(record):
    """The as-filed scan Lexis delivered beside the wrapper, if any.

    Taken from the inventory, which paired wrappers with attachments using the
    delivery's own naming rules, rather than re-guessing from a filename prefix
    -- several deliveries share a prefix and differ only by a copy index.
    """
    attachments = record.get("attachments") or []
    return CORPUS / attachments[0]["file"] if attachments else None


def main():
    spec = yaml.safe_load((OUT / "mutations.yaml").read_text())
    inventory = {r["wrapper_file"]: r for r in json.loads((OUT / "inventory.json").read_text())}

    if FIXTURES.exists():
        shutil.rmtree(FIXTURES)
    FIXTURES.mkdir(parents=True)

    built = []
    scans = ocr_records()
    for fixture in spec["fixtures"]:
        record = inventory[fixture["source_file"]]
        control, record_exhibits, text_meta = control_for(record, scans)
        mutant = apply_mutation(control, fixture["mutation"])

        home = FIXTURES / fixture["fixture_id"]
        (home / "source").mkdir(parents=True)
        (home / "normalized" / "attachments").mkdir(parents=True)
        (home / "mutant" / "attachments").mkdir(parents=True)

        source_docx = CORPUS / fixture["source_file"]
        shutil.copy2(source_docx, home / "source" / f"original{source_docx.suffix}")
        source_pdf = find_source_pdf(record)
        if source_pdf:
            shutil.copy2(source_pdf, home / "source" / "as-filed-scan.pdf")

        (home / "normalized" / "brief.txt").write_text(control)
        (home / "mutant" / "brief.txt").write_text(mutant)

        # Attachments are written identically into both conditions. That is the
        # point of the design: if the record is byte-identical and only the brief
        # differs, a challenge about the relationship between them can only have
        # come from the brief.
        attachment_hashes, attachment_notes = {}, []
        def attach(name, text, note):
            for side in ("normalized", "mutant"):
                (home / side / "attachments" / name).write_text(text)
            attachment_hashes[name] = sha256_text(text)
            attachment_notes.append({"file": name, "chars": len(text), "note": note})

        if text_meta.get("appended_authorities"):
            attach("appended-authorities.txt", text_meta["appended_authorities"],
                   "full-text authorities Lexis appended after the certificate of service")
        for index, exhibit in enumerate(record_exhibits, start=1):
            label = re.sub(r"[^a-z0-9]+", "-", exhibit["label"].lower()).strip("-") or "record"
            attach(f"record-{index:02d}-{label}.txt", exhibit["text"] + "\n",
                   f"pages {exhibit['page_range'][0]}-{exhibit['page_range'][1]} of the as-filed "
                   f"scan, transcribed by Azure Document Intelligence")

        manifest = {
            "fixture_id": fixture["fixture_id"],
            "case_family_id": fixture["case_family_id"],
            "stratum": fixture["stratum"],
            "document": fixture["document"],
            "files": {
                "source": f"source/original{source_docx.suffix}",
                "source_scan": "source/as-filed-scan.pdf" if source_pdf else None,
                "control": "normalized/brief.txt",
                "mutant": "mutant/brief.txt",
                "attachments": sorted(attachment_hashes),
                "attachment_notes": attachment_notes,
            },
            "mutation": {
                key: value
                for key, value in fixture["mutation"].items()
                if key not in ("find", "replace")
            } | {
                "target_location": {
                    "section": fixture["mutation"]["section"],
                    "control_excerpt": fixture["mutation"]["find"],
                    "mutant_excerpt": fixture["mutation"]["replace"],
                },
                "characters_changed": abs(len(mutant) - len(control)),
                "control_chars": len(control),
                "mutant_chars": len(mutant),
                "fraction_of_brief_changed": round(
                    abs(len(mutant) - len(control)) / max(1, len(control)), 5
                ),
            },
            "gold": {
                "control_has_target_defect": False,
                "mutant_has_target_defect": True,
                "expected_direction": fixture["mutation"]["expected_direction"],
                "materiality": fixture["mutation"]["materiality"],
                "verified_by": [],
                "verification_status": "unverified",
                "verification_note": (
                    "Drafted by a language model and not yet adjudicated. The four "
                    "reviewer questions in REGISTER.md (pair identical but for the "
                    "intended change; control free of the target defect; mutant "
                    "contains it; a competent opponent could raise it) have not been "
                    "answered, so this fixture is development material, not benchmark."
                ),
            },
            "provenance": {
                "source_sha256": sha256_file(source_docx),
                "source_scan_sha256": sha256_file(source_pdf) if source_pdf else None,
                "control_sha256": sha256_text(control),
                "mutant_sha256": sha256_text(mutant),
                "attachment_sha256": attachment_hashes,
                "normalization_version": NORMALIZATION_VERSION,
                "text": text_meta,
                "mutation_version": spec["version"],
                "generator": GENERATOR,
                "built_on": date.today().isoformat(),
            },
        }
        (home / "fixture.json").write_text(json.dumps(manifest, indent=2) + "\n")
        built.append(manifest)

    (OUT / "fixtures_index.json").write_text(json.dumps(
        [{
            "fixture_id": m["fixture_id"],
            "case_family_id": m["case_family_id"],
            "stratum": m["stratum"],
            "control_text_source": m["provenance"]["text"]["control_text_source"],
            "attachments": len(m["files"]["attachments"]),
            "mutation_type": m["mutation"]["type"],
            "control_chars": m["mutation"]["control_chars"],
            "characters_changed": m["mutation"]["characters_changed"],
            "verification_status": m["gold"]["verification_status"],
        } for m in built], indent=2) + "\n")

    print(f"built {len(built)} fixtures in {FIXTURES}")
    print(f"{'id':<6} {'mutation':<24} {'chars':>7} {'changed':>8} {'%':>7} {'src':<10} {'att':>3}  case")
    for m in built:
        mu = m["mutation"]
        print(f"{m['fixture_id']:<6} {mu['type']:<24} {mu['control_chars']:>7} "
              f"{mu['characters_changed']:>8} {mu['fraction_of_brief_changed']*100:>6.2f}% "
              f"{m['provenance']['text']['control_text_source']:<10} "
              f"{len(m['files']['attachments']):>3}  {m['case_family_id'][:30]}")


if __name__ == "__main__":
    main()
