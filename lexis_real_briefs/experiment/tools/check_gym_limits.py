"""Does every fixture fit through the Gym whole, or does a ceiling bite?

Four ceilings can silently drop part of a brief, and a benchmark that measures
whether the Gym found a defect is worthless if the defect was never sent to it.
This checks all four against every control and mutant actually in the study:

  ingestion.MAX_BRIEF_CHARS        hard cap on stored brief text
  ingestion.BRIEF_PAGE_LIMIT       pages read as brief before the rest is exhibits
  ARGUMENT_GYM_BRIEF_TEXT_CHARS    raw text given to stages that do not read units
  ARGUMENT_GYM_UNIT_BUDGET_CHARS   serialized unit payload given to the model stages
  ARGUMENT_GYM_RECORD_BUDGET_CHARS how much of the ATTACHED RECORD a stage reads,
                                   shared across the materials a run selected

The last one is the one that bites, and it is the reason this check exists in
this shape. It is a hard-coded default argument rather than a setting, it is
6,000 characters, and it is applied per material after the brief-side budgets
have already been satisfied -- so a record can pass every other ceiling and
still reach the model as its first few pages. A record-support fixture whose
evidence sits past that point is not testing what it claims to test.

It also checks the two conditions against each other: a control that fits and a
mutant that is sampled would make the pair incomparable for reasons unrelated to
the mutation.
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

from apps.argument_gym import ingestion, pipeline, record  # noqa: E402
from apps.argument_gym.pipeline import dumps  # noqa: E402

FIXTURES = ROOT / "lexis_real_briefs" / "experiment" / "fixtures"


def gold_phrases(gold, record_text):
    """Distinctive phrases the gold label names that also appear in the record.

    Deliberately crude: quoted spans and capitalised runs from the gold label,
    kept only when they actually occur in the record. It is a tripwire, not a
    semantic check -- its job is to fail loudly when the evidence a fixture
    rests on falls outside what the Gym will read.
    """
    # 12-200: short enough to be a phrase, long enough for a quoted record
    # excerpt. The first version capped at 80 and silently matched nothing,
    # because the quotation this study's own record label depends on is 84.
    candidates = set(re.findall(r'"([^"]{12,200})"', gold))
    candidates |= set(re.findall(r"\b(?:[A-Z][a-z]+ ){0,2}[A-Z]{2,}(?: [A-Z]{2,}){1,4}\b", gold))
    candidates |= set(re.findall(r"\b[A-Z][a-z]+(?: [A-Z][a-z]+){2,4}\b", gold))
    return sorted({c.strip() for c in candidates if c.strip() and c.strip() in record_text})


def measure(text):
    paragraphs = [{"text": line, "page": None} for line in text.split("\n\n") if line.strip()]
    units = ingestion.structure_units(paragraphs)
    limit = pipeline.unit_text_limit()
    whole = len(dumps([pipeline._payload_item(unit, limit) for unit in units]))
    selected, omitted = pipeline.select_units(units)
    return {
        "chars": len(text),
        "units": len(units),
        "whole_payload": whole,
        "units_omitted": omitted,
        "units_over_text_limit": sum(1 for unit in units if len(unit["text"]) > limit),
    }


def main():
    budget = pipeline.unit_budget_chars()
    text_cap = pipeline.brief_text_limit()
    # One material per fixture in this study, so the share is the whole budget.
    material_cap = record.share_of_budget(1)
    rows, problems = [], []

    for home in sorted(FIXTURES.iterdir()):
        if not home.is_dir():
            continue
        # The record is uploaded as its own document, so it meets the same
        # ceilings the brief does. A truncated exhibit would silently remove the
        # evidence a record-support challenge has to be grounded in.
        manifest = json.loads((home / "fixture.json").read_text())
        gold = manifest["mutation"]["gold_vulnerability"]
        for attachment in sorted((home / "normalized" / "attachments").glob("*.txt")):
            text = attachment.read_text()
            row = measure(text) | {"fixture": home.name, "condition": f"att:{attachment.name[:18]}"}
            rows.append(row)
            if row["chars"] > ingestion.MAX_BRIEF_CHARS:
                problems.append(f"{home.name}/{attachment.name}: over MAX_BRIEF_CHARS")
            if row["whole_payload"] > budget:
                problems.append(f"{home.name}/{attachment.name}: unit payload over the budget")
            if row["chars"] > material_cap:
                problems.append(
                    f"{home.name}/{attachment.name}: the record is {row['chars']:,} characters "
                    f"but a stage reads only the first {material_cap:,} "
                    f"({material_cap / row['chars']:.0%}) -- ARGUMENT_GYM_RECORD_BUDGET_CHARS"
                )
            # For a record_support fixture, being truncated is not enough to
            # know: the question is whether the evidence the gold label turns on
            # survives the cap. Checked by locating the distinctive phrases the
            # gold label names.
            if manifest["mutation"]["type"] == "record_support":
                for phrase in gold_phrases(gold, text):
                    where = text.find(phrase)
                    if where >= material_cap:
                        problems.append(
                            f"{home.name}: evidence the gold label depends on "
                            f"(\"{phrase[:44]}...\") begins at character {where:,}, past the "
                            f"{material_cap:,}-character cap -- this fixture cannot test "
                            "what it claims to test"
                        )
        for condition in ("normalized", "mutant"):
            text = (home / condition / "brief.txt").read_text()
            row = measure(text) | {"fixture": home.name, "condition": condition}
            rows.append(row)
            if row["chars"] > ingestion.MAX_BRIEF_CHARS:
                problems.append(f"{home.name}/{condition}: text over MAX_BRIEF_CHARS")
            if row["chars"] > text_cap:
                problems.append(f"{home.name}/{condition}: text over ARGUMENT_GYM_BRIEF_TEXT_CHARS")
            if row["whole_payload"] > budget:
                problems.append(f"{home.name}/{condition}: unit payload over the budget")
            if row["units_omitted"]:
                problems.append(f"{home.name}/{condition}: {row['units_omitted']} units sampled away")
            if row["units_over_text_limit"]:
                problems.append(
                    f"{home.name}/{condition}: {row['units_over_text_limit']} units truncated "
                    "by ARGUMENT_GYM_UNIT_TEXT_CHARS"
                )

    for fixture in {row["fixture"] for row in rows}:
        pair = {row["condition"]: row for row in rows if row["fixture"] == fixture
                and not row["condition"].startswith("att:")}
        if pair["normalized"]["units_omitted"] != pair["mutant"]["units_omitted"]:
            problems.append(f"{fixture}: control and mutant are sampled differently")

    print(f"ingestion.MAX_BRIEF_CHARS         {ingestion.MAX_BRIEF_CHARS:>8}")
    print(f"ingestion.BRIEF_PAGE_LIMIT        {ingestion.BRIEF_PAGE_LIMIT:>8}  (pages; .docx has no page count, so it does not apply)")
    print(f"ARGUMENT_GYM_BRIEF_TEXT_CHARS     {text_cap:>8}")
    print(f"ARGUMENT_GYM_UNIT_BUDGET_CHARS    {budget:>8}")
    print(f"ARGUMENT_GYM_RECORD_BUDGET_CHARS  {record.record_budget_chars():>8}"
          f"  (per material here: {material_cap})")
    print()
    print(f"{'fixture':<8} {'condition':<24} {'chars':>7} {'units':>6} {'payload':>8} {'% budget':>9} {'omitted':>8}")
    for row in rows:
        print(f"{row['fixture']:<8} {row['condition']:<24} {row['chars']:>7} {row['units']:>6} "
              f"{row['whole_payload']:>8} {100 * row['whole_payload'] / budget:>8.1f}% {row['units_omitted']:>8}")
    print()
    headroom = max(row["whole_payload"] for row in rows)
    print(f"largest unit payload in the study : {headroom} ({100 * headroom / budget:.1f}% of budget)")
    print(f"largest brief text in the study   : {max(r['chars'] for r in rows)} "
          f"({100 * max(r['chars'] for r in rows) / ingestion.MAX_BRIEF_CHARS:.1f}% of MAX_BRIEF_CHARS)")
    if problems:
        print("\nPROBLEMS:")
        for problem in problems:
            print("  -", problem)
        return 1
    print("\nNo ceiling bites. Every fixture is read whole, and both conditions of every "
          "pair are read identically.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
