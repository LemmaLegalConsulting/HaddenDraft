"""Write the shareable copy of each run's results, beside the full one.

The full `report.json` is 5.7 MB per run, and 169 KB of every 245 KB run is the
`retrieval` field: verbatim dumps of the local statute, ordinance, caselaw and
treatise corpora that the research stage pulled back. Those corpora are not in
this repository and are not ours to publish, and they are not evidence for
anything in the paper -- the research trace, which is, is a fraction of the size
and stays.

So this writes `report.public.json`: the same structure with `retrieval` removed
and a note saying so. Everything a reader needs to check a number in the paper is
in it -- every challenge, every judge assessment, every attack the opponent
proposed, the verdicts, the stage traces and the run manifest.

The analysis tools read `report.json` when it is present and fall back to this,
so a fresh clone of the repository can reproduce every table without the 2.1 GB
of run databases and 239 MB of raw model transcripts that stay local.
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from analyse_2x2 import attacks_given_to_judge  # noqa: E402

ROOT = Path(__file__).resolve().parents[3]
RESULTS = ROOT / "lexis_real_briefs" / "experiment" / "results"

# Dropped: third-party corpus text, bulky and not ours to redistribute.
DROP = ("retrieval",)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", default=str(RESULTS))
    args = parser.parse_args()

    written = kept = dropped = 0
    for report_path in sorted(Path(args.results).glob("*/report.json")):
        report = json.loads(report_path.read_text())
        for result in report["results"]:
            # The number of attacks the judge was handed is only recoverable by
            # parsing its prompt out of the raw call transcripts, and those stay
            # local. Bake it in, or the survival table cannot be computed from a
            # clone -- which is the one table the study turns on.
            run_dir = report_path.parent / f"{result['fixture_id']}-{result['condition']}"
            if run_dir.is_dir() and "attacks_given_to_judge" not in result:
                result["attacks_given_to_judge"] = len(attacks_given_to_judge(run_dir))
            for field in DROP:
                if field in result:
                    dropped += len(json.dumps(result.pop(field), default=str))
        report["public_export"] = {
            "removed_fields": list(DROP),
            "why": "verbatim excerpts of third-party legal corpora retrieved by the "
                   "research stage; not ours to redistribute and not evidence for any "
                   "reported figure",
            "full_record": "report.json, kept locally alongside this file",
        }
        out = report_path.with_name("report.public.json")
        out.write_text(json.dumps(report, indent=2, default=str))
        written += 1
        kept += out.stat().st_size
    print(f"wrote {written} report.public.json files")
    print(f"  committed size {kept / 1e6:.1f} MB; dropped {dropped / 1e6:.0f} MB of retrieval text")
    return 0


if __name__ == "__main__":
    sys.exit(main())
