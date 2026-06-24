from django.core.management.base import BaseCommand

from apps.rules.models import DecisionTestCase
from apps.rules.services import run_decision_test_case


class Command(BaseCommand):
    help = "Run enabled decision-table test cases for proposed and published tables."

    def handle(self, *args, **options):
        test_cases = DecisionTestCase.objects.filter(
            enabled=True,
            table__status__in=["proposed", "published"],
        ).select_related("table")

        total = 0
        failures = []
        for test_case in test_cases:
            total += 1
            result = run_decision_test_case(test_case)
            label = f"{test_case.table.key} v{test_case.table.version}: {test_case.name}"
            if result["passed"]:
                self.stdout.write(self.style.SUCCESS(f"PASS {label}"))
            else:
                failures.append(result)
                self.stdout.write(self.style.ERROR(f"FAIL {label}"))
                self.stdout.write(f"  expected: {result['expected_outputs']}")
                self.stdout.write(f"  actual:   {result['actual_outputs']}")

        if failures:
            raise SystemExit(1)

        self.stdout.write(self.style.SUCCESS(f"{total} rule test case(s) passed."))
