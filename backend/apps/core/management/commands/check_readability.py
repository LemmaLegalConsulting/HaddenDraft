from pathlib import Path

from django.core.management.base import BaseCommand

from apps.templates_app.models import AdviceLetterSection
from apps.validation.readability import check_readability, summarize


class Command(BaseCommand):
    help = (
        "Score client-facing text against the plain-language rules in "
        "content/drafting-rules/checks/plain-language.yaml."
    )

    def add_arguments(self, parser):
        parser.add_argument("paths", nargs="*", help="Text files to score.")
        parser.add_argument(
            "--advice-sections",
            action="store_true",
            help="Score every indexed advice-letter section instead of files.",
        )
        parser.add_argument("--kind", default="advice", choices=["advice", "action"])
        parser.add_argument("--verbose-findings", action="store_true", help="List every finding.")

    def handle(self, *args, **options):
        targets = []
        if options["advice_sections"]:
            targets = [
                (section.slug, section.body)
                for section in AdviceLetterSection.objects.filter(is_active=True).order_by("slug")
            ]
        for raw in options["paths"]:
            path = Path(raw)
            if not path.is_file():
                self.stderr.write(f"Not a file: {path}")
                continue
            targets.append((path.name, path.read_text()))

        if not targets:
            self.stdout.write("Nothing to score. Pass files or --advice-sections.")
            return

        failing = 0
        for name, text in targets:
            report = check_readability(text, kind=options["kind"])
            style = self.style.SUCCESS if report.passed else self.style.WARNING
            self.stdout.write(style(f"{'ok' if report.passed else 'check':5s} {name[:46]:46s} {summarize(report)}"))
            if not report.passed:
                failing += 1
            findings = report.findings if options["verbose_findings"] else report.warnings
            for finding in findings:
                excerpt = f"  |  {finding.excerpt[:60]}" if finding.excerpt else ""
                self.stdout.write(f"        [{finding.severity}] {finding.message}{excerpt}")

        self.stdout.write(f"\n{len(targets) - failing}/{len(targets)} within the plain-language targets.")
