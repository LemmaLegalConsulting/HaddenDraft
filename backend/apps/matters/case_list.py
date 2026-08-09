"""Narrowing the case list to what an advocate is actually working on.

An advocate opening the tool wants the handful of cases in front of them, not
every matter they have ever touched. The list therefore defaults to open cases,
most recently active first, one screen at a time -- and everything else (closed
cases, a colleague's caseload, one legal problem code) is reachable by asking
for it rather than by scrolling past it.

Search is the deliberate exception: someone typing a case number is looking for
a specific case and usually knows it is closed, so a query widens the status
filter instead of narrowing it.

These functions operate on serialized case dicts rather than model instances,
because the list is assembled from three sources -- LegalServer, quick cases,
and demo data -- that share no queryset.
"""

from __future__ import annotations


STATUS_OPEN = "open"
STATUS_CLOSED = "closed"
STATUS_ALL = "all"
STATUS_CHOICES = (STATUS_OPEN, STATUS_CLOSED, STATUS_ALL)

ASSIGNED_MINE = "mine"
ASSIGNED_ALL = "all"
ASSIGNED_CHOICES = (ASSIGNED_MINE, ASSIGNED_ALL)

SORT_ACTIVITY = "activity"
SORT_OPENED = "opened"
SORT_CHOICES = (SORT_ACTIVITY, SORT_OPENED)

#: One screen of cases. "Show more" asks for the next page of the same size.
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 200

#: How many matters to pull from LegalServer per request. Filtering, sorting,
#: and the legal-problem facet all need the whole set the viewer can reach, not
#: the page being shown, so this has to exceed one screen by a wide margin.
SYNC_FETCH_LIMIT = 200


def normalize_status(value, *, searching=False):
    value = str(value or "").strip().casefold()
    if value in STATUS_CHOICES:
        return value
    # A search that silently skipped closed cases would look like the case does
    # not exist, which is worse than showing one the advocate did not want.
    return STATUS_ALL if searching else STATUS_OPEN


def normalize_assigned(value):
    value = str(value or "").strip().casefold()
    return value if value in ASSIGNED_CHOICES else ASSIGNED_ALL


def normalize_sort(value):
    value = str(value or "").strip().casefold()
    return value if value in SORT_CHOICES else SORT_ACTIVITY


def normalize_page_size(value, default=DEFAULT_PAGE_SIZE):
    try:
        size = int(str(value).strip())
    except (TypeError, ValueError):
        return default
    return max(1, min(size, MAX_PAGE_SIZE))


def normalize_offset(value):
    try:
        return max(0, int(str(value).strip()))
    except (TypeError, ValueError):
        return 0


def case_is_open(case):
    # Absent rather than false: a source that says nothing about disposition has
    # not told us the case is closed.
    return bool(case.get("isOpen", True))


def filter_cases(cases, *, status=STATUS_OPEN, assigned=ASSIGNED_ALL, problem_code=""):
    wanted_code = str(problem_code or "").strip().casefold()
    result = []
    for case in cases:
        if status == STATUS_OPEN and not case_is_open(case):
            continue
        if status == STATUS_CLOSED and case_is_open(case):
            continue
        if assigned == ASSIGNED_MINE and not case.get("assignedToViewer"):
            continue
        if wanted_code and str(case.get("legalProblemCode") or "").strip().casefold() != wanted_code:
            continue
        result.append(case)
    return result


def _sort_key(case, sort):
    field = "lastActivityAt" if sort == SORT_ACTIVITY else "openedAt"
    # ISO-8601 strings sort chronologically as text, and a case with no date
    # sorts last rather than jumping to the top of a "most recent first" list.
    return str(case.get(field) or "")


def sort_cases(cases, *, sort=SORT_ACTIVITY):
    # Ties keep a stable, readable order rather than whatever the sources
    # happened to return.
    by_title = sorted(cases, key=lambda case: str(case.get("title") or case.get("client") or "").casefold())
    return sorted(by_title, key=lambda case: _sort_key(case, sort), reverse=True)


def legal_problem_options(cases):
    """Every legal problem code present, so the filter offers only real choices."""
    codes = {str(case.get("legalProblemCode") or "").strip() for case in cases}
    return sorted(code for code in codes if code)


def paginate(cases, *, limit=DEFAULT_PAGE_SIZE, offset=0):
    page = cases[offset : offset + limit]
    return page, len(cases) > offset + len(page)
