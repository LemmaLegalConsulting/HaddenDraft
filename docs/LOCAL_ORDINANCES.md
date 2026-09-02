# Local ordinances and court rules

Ohio expressly requires a landlord to comply with applicable local building,
housing, health, and safety codes (R.C. 5321.04(A)(1)), and governmental
findings of those violations feed the tenant remedies in R.C. 5321.07. Local
law is not a footnote to the eviction corpus; it is often the part that decides
the case. This corpus indexes it by how much it can change an outcome rather
than by codifying municipal codes wholesale.

## Where the corpus lives

The corpus is generated, so it is not committed. `scripts/ingest_local_ordinances.py`
rewrites the per-municipality directories wholesale from `scope.yaml`, and the
source documents it reads run to tens of megabytes -- public material, but data
rather than source, handled the way case-law bundles are.

| Path | Committed | Why |
| --- | --- | --- |
| `content/ordinances/scope.yaml` | yes | Hand-maintained coverage; the auditable part |
| `content/ordinances/datasets/*.yaml` | yes | Hand-maintained cross-city comparisons |
| `content/ordinances/_transcriptions/` | yes | Supplied text `scope.yaml` points at, with its source |
| `content/ordinances/<municipality>/` | no | Generated manifests, sections, chunks |
| `content/ordinances/provenance.yaml` | no | Generated freshness ledger |
| `content/ordinances/to_ingest/` | no | Inbox of source documents; nothing reads it |

To publish a regenerated corpus:

```bash
SYNC_ORDINANCES=true ./scripts/deploy_azure_containerapps.sh
```

That uploads into `raw/content/ordinances/`, and the bootstrap job runs
`publish_local_ordinances`, which copies it to `published/content/ordinances/`.
`PUBLISHED_CONTENT_LIBRARY_DIR` points there, and `content_library_roots()`
searches it between the organization's own content and the defaults in the
image -- so a refreshed corpus is picked up without a rebuild, and a site
override still wins over it.

Locally, nothing changes: the corpus sits in `content/ordinances/` and is read
from the image root as before. It is simply untracked.

## What is indexed, and why

Priority is set in [`content/ordinances/scope.yaml`](../content/ordinances/scope.yaml).

| Priority | Material | Why it matters |
| --- | --- | --- |
| 1 | Pay-to-stay / right-to-cure | Can defeat a nonpayment eviction outright |
| 1 | Rental registration, licensing, occupancy certificates | Noncompliance can bar the landlord from maintaining the eviction |
| 1 | Municipal housing/building/health codes | Incorporated into landlord duties and rent escrow |
| 1 | Lead-safe laws | Certification duties, anti-retaliation, eviction-specific protection |
| 2 | Source-of-income and local fair housing | Voucher discrimination creates separate claims and defenses |
| 2 | Local court rules and standing orders | Procedural rules that decide filings, service, escrow, dismissal |
| 2 | Right-to-counsel / access to legal services | Representation eligibility and referral workflow |
| 2 | Chronic nuisance and crime-free housing | Drives lease terminations from police calls |
| 2 | Security deposits and rental agreement terms | Local deposit limits create claims and set-offs, not only defenses |
| 3 | Condemnation, relocation, unsafe buildings | What a tenant is owed when a unit is closed |
| 3 | Local utility, heat, water rules | Habitability and constructive-eviction arguments |

Priority orders the work; it does not gate it. Where a document already in hand
carries housing law that falls outside the table — a security-deposit chapter, a
property maintenance code adopted by reference — it is indexed too, because the
cost of adding a target to a document already retrieved is close to zero and a
chapter nobody indexed is a chapter nobody can find. What stays out is material
with no housing connection at all, and material that is not law: a council
agenda or a newspaper carrying an agenda corroborates that an ordinance passed,
so it belongs in `verification_urls`, never in the search index.

## Where the text comes from

There is no single official publisher of Ohio municipal codes, and the two
commercial codifiers most cities use do not permit automated retrieval:

- **American Legal Publishing** (`codelibrary.amlegal.com`) answers a script
  with a Cloudflare bot challenge (HTTP 403).
- **Municode** (`library.municode.com`) serves code content through an API that
  requires an authenticated token.

Neither is a fetch target. Working around either would mean evading an access
control. They remain **citation targets**: every record carries the
`codifier_url` a reader should open to confirm the codified text.

What can be read directly is the city's own legislative record. The ingestion
script has three acquisition adapters:

| Method | Source | `text_basis` |
| --- | --- | --- |
| `legistar` | The city's public Legistar Web API (`webapi.legistar.com/v1/<client>/`) — file number, dates, and full text of the enacted act | `enacted_act` |
| `document` | One official document published by the city or court at a stable URL (PDF/DOCX/HTML) | `published_local_rules`, or as declared |
| `transcription` | Text a person supplied, read from a file under `_transcriptions/` with its provenance front matter | `unverified_transcription` |
| `pending` | Nothing retrieved; the authority is declared with the reason it could not be acquired | `not_acquired` |

Legistar clients confirmed for this corpus: `cityofcleveland`, `columbus`,
`cincinnatioh`, `toledo`, `gahanna`.

### Enacted act is not codified text

A Legistar record is the act the council passed. That is authoritative in the
strongest sense available — it is the legislature's own record — but it is not
the chapter as it stands today. Records generated this way are stamped
`text_basis: enacted_act`, and the ingestion also follows the amendment chain
for the chapter so a reader can see what came after. Toledo's Chapter 1760 was
enacted, repealed and re-enacted twice, then technically corrected; a reader
handed only the first act would be reading law that no longer exists.

Never present an ordinance record as current law without the codifier check.

### Pending is a finding, not a gap in the data

A municipality with a pay-to-stay ordinance and no permitted retrieval route is
recorded as `pending` with the reason. It produces **no chunk**, so retrieval
can never return it as law.

It does, however, answer a search. Ask about Lakewood's pay-to-stay ordinance
against a corpus that cannot reach Lakewood's code, and ranked retrieval will
otherwise hand back Toledo's chapter and Cleveland's section — other cities'
law, on their own terms, with nothing saying Lakewood has its own. That is
worse than silence, because it looks like an answer. So a query that names a
municipality gets a **coverage notice** ranked ahead of the ordinances it would
otherwise be answered with:

- Named authority (`Lakewood Codified Ordinances § 516.22`) and the reason the
  text is not held.
- A **secondary-source summary**, where an attributable one exists — the fields
  in `datasets/` whose basis is not `unknown`, quoted with the source named and
  labelled "secondary source, not the ordinance text". Where nothing describes
  the ordinance, there is no summary rather than a written-up guess, and a
  field nobody has established is omitted rather than filled in.
- A link to the publisher, so the reader goes and reads the real thing.

The notice carries `metadata.resultType: "coverage-notice"` and
`textBasis: not_acquired`, has no chunk id, and its "View full source" is an
external link to the codifier.

Two guards keep this precise. The municipality name must appear in the query,
so a general pay-to-stay question is not buried under notices from every city
the corpus cannot reach. And the longest matched name wins: Ohio's city names
nest ("Cleveland Heights" contains "Cleveland", "South Euclid" contains
"Euclid"), and answering a Cleveland Heights question with a Cleveland notice
is the same substitution the mechanism exists to prevent.

Pending authorities are also visible in `/api/ordinances/coverage/` and in the
municipality's shelf subtitle ("2 declared, not yet acquired").

### Acts that incorporate their substance by exhibit

Some councils enact a chapter by reference: the act recites "Chapter 792 … is
hereby enacted … as set forth in EXHIBIT A", and the chapter itself is an
attachment. Such an act is long enough to pass the length check and contains
none of the law — the worst combination, because it looks like a successful
retrieval. The `legistar` adapter detects the exhibit language and takes the
attachment instead. Where several exhibits exist (proposed, redline, adopted),
pin the right one with `prefer_attachment`.

### Hand-supplied text

Some ordinances reach this corpus because a lawyer went and got them. That text
is often the only copy available, and refusing it would be worse than holding
it — but nothing here has read it off a publisher's page, and treating it like a
retrieved document would launder that.

A transcription lives in `content/ordinances/_transcriptions/<municipality>-<key>.md`
with front matter naming who supplied it, when, the source they assert it came
from, `verified: false`, and the URLs to check it against. It is searchable and
stamped `unverified_transcription` everywhere it surfaces. Set `verified` only
when a person has actually compared it with the publisher's copy. Keep whatever
file they handed over — a `.docx` export, a saved page — beside it in
`_transcriptions/_source/`, so a later reader can see what was transcribed from.
`content/ordinances/to_ingest/` is an inbox for material not yet placed;
nothing reads it.

The stamp says how the text got here, not how good it is. A codifier's rendering
of the section currently in force is often the strongest statement of the
current rule available — better than the enacting act, which may have been
amended, renumbered, or (as in Lakewood) never carried a section number at
all — and it still arrives as `unverified_transcription` when a person pastes
it, because American Legal Publishing and Municode refuse automated retrieval
and nothing here read it off their page. Akron's §§ 150.51–150.52 and Yellow
Springs' Chapter 868 are held this way.

**A supplied copy does not displace a retrieved one.** Where the corpus already
holds a document it fetched, that stays the record; the supplied copy is kept as
a comparison and what the comparison showed is written into the target's
`notes`. Cleveland Heights Chapter 767 is the worked example: the ingested text
is the enacted act from the October 17, 2022 council packet, and the codified
chapter supplied later agrees with it section for section, differing only in
that the act's own index transposes 767.05 and 767.06 relative to its body.

### Repealed and expired provisions

A record can carry `repeal_date`, and a dataset record can carry
`status: repealed` or `status: expired`. This matters more than it looks: a
repealed chapter's fields read exactly like a live one's, and the treatise still
describes provisions that have since been repealed. Where a status is set, the
summary leads with **NOT CURRENT LAW** and the date, and states the terms in the
past tense.

### Packets, and cutting the ordinance out of one

Most of what a city actually publishes is a meeting packet: dozens of pages of
agenda, minutes, and unrelated legislation with the ordinance somewhere in the
middle. Cleveland Heights' Chapter 767 is 5,464 characters inside a 161,822-character
packet. A `document` target may therefore carry an `extract` block with `start`
and `end` text markers (and optionally `pages`), and the record stores what was
cut and from how much.

**A missing marker is a hard failure**, never a silent fallback to the whole
document. Keeping the packet when the marker cannot be found is the exact
outcome extraction exists to prevent, and it would be reported as a success.
Marker matching normalizes whitespace and typographic characters, so a curly
apostrophe in the PDF does not break a marker typed with a straight one.

Text extractors also break lines where no reader would: pypdf renders
Worthington's Ordinance 21-2023 with the first letter of many lines split from
the rest, so `SECTION 2.` comes out as `SE\nCTION 2.` and collapsing whitespace
yields `SE CTION`. When the normalized match fails, matching is retried with
whitespace removed entirely, and the record carries
`matched_without_whitespace: true` — which is worth seeing, because it means the
text layer is rough enough that the extracted characters may be too.

### Skipping pages inside a scan

`ocr.pages` is a list, and a gap in it is honoured. `pdftoppm` only takes a
first and a last page, so the pages in between are rendered and then dropped.

The gap is the point. An amending ordinance shows what it deletes as
struck-through text: South Euclid's Ordinance 12-17 strikes three whole pages of
the chapter it replaces. OCR reads a strikethrough as noise, and the text
underneath it is the old chapter, which is not law either — so recognizing those
pages would put several hundred lines of garble into the corpus under the
heading of an enacted chapter. The target names the pages it wants and says in
its `notes` which it left out and why.

### `source_type`

Every target may declare what kind of document its text came from:
`signed_ordinance`, `council_packet`, `official_minutes`, `codifier`,
`secondary_reproduction`, `transcription`.

This is not bookkeeping. Akron's § 150.52 late-fee cap reads as **8%** in the
codified section now held here and in the treatise, while a secondary
reproduction of the same ordinance says 5% — because that reproduction is headed
`ORDINANCE NO. ____ -2021` with the number left blank, and is a pre-enactment
draft. Both documents are real; only one is law. Without knowing which source is
which, there is no way to say which to believe.

### Official journals

A city's journal of enacted legislation — Cleveland's *City Record* — publishes
the ordinance text itself, which is neither minutes, nor a signed copy, nor a
codifier rendering. It gets its own `source_type: official_publication`.

These are the deepest haystacks in the corpus and the reason extraction has to
be cheap: Cleveland's § 375.02 is 1,467 characters inside a 1,314,914-character
issue, or 0.1%.

### OCR

Much of what a small municipality publishes is a photograph of paper: public,
fetchable, and unreadable to everything downstream. A `document` or `browser`
target may carry `ocr: {dpi: 300}`, which renders pages with `pdftoppm` and
recognizes them with `tesseract` (both must be on PATH).

OCR output is derived text, not the publisher's characters — it mistakes digits,
drops diacritics, and mangles tables. Everything it produces is stamped
`text_basis: ocr_text` so a section number or a dollar figure read out of a scan
is never mistaken for one read off a page, and it is rechecked on the same
90-day cadence as anything else nobody has confirmed.

Athens is the case that motivates preferring OCR over a partial text layer: its
scan's embedded text covers the WHEREAS clauses and none of the operative
sections, so extracting rather than recognizing would have produced a preamble
that reads like the ordinance.

### Browser acquisition

Some municipal portals hand the file to JavaScript: the row is rendered
client-side and the download goes through a token-gated API whose response the
page turns into a blob. Euclid's Ord. 125-2022 is one —
`apidocprod.egovlink.com/documents/download/490041` answers a bare request with
`401`, because the token lives in the page. There is no address to put in a
config file.

So the page is the client. A `browser` target takes a `url` and a `click`
selector, drives headless Chromium through Playwright, and captures the
download:

```yaml
acquire:
  method: browser
  url: https://www.cityofeuclid.gov/city-council-agendas-minutes
  click: '#dwf490041'
  ocr: {dpi: 300}
```

This is not evasion: the browser does exactly what a person clicking Download
does, with no credential the site did not hand it, and it is used only where the
publisher intends the document to be downloadable. The blob URL is per-session
and meaningless later, so the record stores the page and the selector — those
are what reproduce the retrieval.

### Scanned sources

Several official PDFs are image-only with no text layer — Maple Heights'
Ord. 2021-25 packet, South Euclid's Ord. 17-22 packet, Reynoldsburg's signed
Ord. 26-2022, Chauncey's Ord. 2024-02, and the COHHIO Pay-to-Stay Technical
Guide.

Athens' Ord. O-85-22 is the worst shape of all: a **partial** text layer. Its
WHEREAS clauses extract cleanly and the operative sections — the tender
defenses, the late-fee limit, severability — do not. Ingesting it would produce
a preamble that reads like the ordinance, so it stays pending. A partial text
layer is more dangerous than none, because it succeeds. They are public and
fetchable but cannot be ingested without OCR, which this pipeline does not do.
They are recorded as `pending` with that as the stated reason and the URL in
`verification_urls`, so the obstacle is legible rather than looking like a
missing link.

## Reviewing and correcting the corpus in Django admin

Ingestion will always be behind the people using it: a clerk answers a records
request, someone finds the signed ordinance a packet only summarized, a codifier
reissues a chapter. Two admin models let that arrive without a code change.

**Ordinance documents** (`/admin/sources/ordinancedocument/`) attach documents to
one authority, addressed by `municipality_slug` + `target_key` — the same keys
`scope.yaml` uses. Add a publisher URL, upload a PDF, or both. Uploads go through
`apps.core.storage` under the `ordinances/` prefix and are keyed by content hash,
so re-uploading the same file is idempotent. Each document carries its own
`extract_start` / `extract_end` / `extract_pages`.

Documents are never edited in place and never silently replaced. A better copy
**supersedes** the one it replaces and both stay on the record — which document
an assertion rested on is part of the assertion, and the Akron discrepancy was
only visible because two sources disagreed and both were still there to compare.
Bulk actions mark documents verified, superseded, or active.

**Ordinance overrides** (`/admin/sources/ordinanceoverride/`) correct an
authority's generated metadata: citation, title, enacting act, `enacted_as`,
dates, legal status, and the whole preemption block.

An override is a **patch, not a replacement** — a blank admin field means "leave
the generated value alone", so a later ingestion improving an untouched field is
not silently reverted by an old edit. The admin list shows exactly which fields
each override changes, and the API returns them as `overriddenFields`.

Setting `legal_status` to `repealed` or `expired` reaches all the way into
search: the coverage notice for that authority leads with **NOT CURRENT LAW** and
the date.

`verified` on either model means a person compared the text against the
publisher's copy. Nothing automated ever sets it.

## Provenance ledger

Every ingest run rebuilds `content/ordinances/provenance.yaml` from every
manifest — not only the municipalities touched, so a single-city refresh never
leaves a partial view. One row per authority: citation, status, acquisition
method, text basis, source URL, retrieval timestamp, content hash, enacting act,
amendment date, who supplied it, and `recheck_after`.

`recheck_after` is a review cadence, not an expiry date — a codified chapter can
change the day after it is read. Unverified transcriptions and unacquired
authorities are set to 90 days; retrieved acts and published documents to 180.
`verified` means a person confirmed the text against the publisher; nothing in
the pipeline sets it true.

## Running the ingestion

```bash
.venv/bin/python scripts/ingest_local_ordinances.py --all
.venv/bin/python scripts/ingest_local_ordinances.py --municipality toledo
.venv/bin/python scripts/ingest_local_ordinances.py --topic pay-to-stay
.venv/bin/python scripts/ingest_local_ordinances.py --priority 1 --dry-run
```

Refresh is differential: a target whose normalized text has not changed keeps
its earlier retrieval stamp rather than claiming a fresh read. `--force`
rewrites anyway. `--all` also prunes manifest sections whose key no longer
appears in `scope.yaml`.

Generated output per municipality, under `content/ordinances/<slug>/`:

```text
manifest.yaml     # sections (including pending ones) and the chunk inventory
sections/<key>.md # the whole retrieved text, provenance-stamped
chunks/*.md       # retrieval-sized pieces with the same front matter
```

Do not hand-edit any of it. Correct `scope.yaml` or the script and regenerate.

## Structured datasets

Whether a city "has pay-to-stay" tells an advocate almost nothing. What decides
a live case is when tender may be made, what it must cover, whether a
rental-assistance guarantee counts, and whether dismissal is required. Those
live in [`content/ordinances/datasets/`](../content/ordinances/datasets/) as
reviewable YAML, one record per municipality, with a **basis** per field:

- `ordinance-text` — read from ingested text of the ordinance itself
- `transcription` — read from hand-supplied text nobody has verified against a
  publisher; as specific as `ordinance-text` and as unconfirmed as a rumour, so
  it gets its own rung
- `treatise` — stated in the indexed treatise section named in `source`
- `secondary` — a compilation or advocacy source; a lead, not authority
- `unknown` — not yet established

`unknown` is a first-class answer and is never omitted. A missing field would
read as "no such limit"; an unknown one reads as "nobody has checked".

Read it at `GET /api/ordinances/datasets/pay-to-stay/`, which resolves each
field's `source` into an openable citation without upgrading its basis.

## Cross references

`GET /api/sources/content/<slug>/<chunkId>/related/` resolves links in both
directions:

- **Outward from an ordinance** — the Revised Code sections it operates against
  (R.C. 5321.19 for preemption, R.C. 1923 for the eviction it defends), the
  treatise section that discusses it, and the cases named for it. A case this
  corpus does not hold is reported as unresolved rather than dropped.
- **Inbound to a statute or treatise section** — every ordinance that names it.
  Opening R.C. 5321.19 surfaces the local provisions exposed to it, and opening
  the treatise's § XXII.J.2 (pay-to-stay) surfaces the ordinances it describes.

## Preemption

R.C. 5321.19 bars political subdivisions from regulating landlord/tenant rights
already regulated by R.C. Chapter 5321, while expressly preserving local
housing, building, health, and safety codes. Every ingested section carries a
`preemption` block (`status`, `note`, `controlling_case`, `court_treatment`,
`confidence`), defaulting to `unadjudicated` / `unreviewed`.

The tool must not tell a lawyer that an ordinance is valid. The useful answer
is: this ordinance is codified here, this is the governing text and the act it
came from, here is R.C. 5321.19, here are any cases addressing it, and here is
how the local court currently treats it.

## Retrieval

Ordinances are a logical research source, `ohio-ordinances`, routed by
[`content/research-sources/auto-source-guidance.yaml`](../content/research-sources/auto-source-guidance.yaml)
and selectable in the research source picker under "Local law". Selection is by
the `content_kind` a manifest declares rather than by a list of slugs, so a
newly ingested municipality is searchable as soon as its manifest exists.
