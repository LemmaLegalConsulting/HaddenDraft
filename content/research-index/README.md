# Research index

What research mode reads before it ranks anything.

Research mode is meant to work as a library: a lawyer can search everything this
application holds with generative AI switched off, and see exactly why each
result came back. Nothing in this directory calls a model, at query time or at
build time, and the code that answers a search
(`backend/apps/sources/research/`) does not import `apps.ai` at all.

## What is maintained here

| File | Maintained by | In git |
| --- | --- | --- |
| `thesaurus.yaml` | a person, reviewed | yes |
| `regression-queries.yaml` | a person, reviewed | yes |
| `term-neighbors.json` | `manage.py build_research_index` | no |

### `thesaurus.yaml`

Terms of art that mean the same thing to a court and different things to a
search index: a researcher types "deficient notice", the opinion says
"defective", the statute says "failed to comply". Groups are symmetric — every
term in a group expands to every other — and each group states its own
`verification` and source, exactly as a court rule or a legal-rule element list
does.

Keep a group narrow. "Rent" and "deposit" both involve money and belong in
separate groups, because a group that is merely topical turns every query about
one into a query about the other.

This file replaced the concept lists that used to sit in Python beside the
scorers, where they could not be reviewed by the people who know the law.

The county and appellate-district vocabulary lives one directory over, in
[`content/jurisdictions/ohio-counties.yaml`](../jurisdictions/ohio-counties.yaml),
because case ingestion needs it as well as research does.

### `regression-queries.yaml`

Known-answer research queries, run by
`backend/apps/sources/test_research_search.py`. Each entry is a question
somebody actually asks and an answer that is checkable without judgement: a
section looked up by its own citation is the first result, an exact phrase
appears in every result that came back, a citation the corpus does not hold
returns nothing and says so.

Add to this file rather than to the test. A query from a CLE session, a question
a colleague could not get an answer to, a citation that should have matched and
did not — each becomes an entry here and is checked from then on. The file's
header lists the supported expectations.

An entry names the corpora it `requires`. A checkout without the case-law import
skips those entries and reports them as skipped; it never reports them as
passing.

### `term-neighbors.json` (generated)

Neighbouring terms learned from how words co-occur across this corpus. This is
counting, not inference: term vectors are TF-IDF over the documents each term is
most characteristic of, compared by cosine.

Build it with:

```bash
.venv/bin/python backend/manage.py build_research_index
.venv/bin/python backend/manage.py build_research_index --status
```

The build takes about ten seconds over a fifteen-thousand-passage corpus and
peaks around 700 MB, because similarity is held as a dense square of the
vocabulary. `--max-vocabulary` controls that square; the other parameters are
recorded in the file it writes and reported through the API.

It is **not committed**, and not because of its size — it is under a megabyte.
It is derived from the imported case-law corpus as well as the content library,
and that corpus differs between deployments. A table built from one deployment's
law would be a confident wrong answer in another.

A checkout without it still searches, and still expands through the reviewed
thesaurus. The API reports the table as unavailable with the command to build
it, because an expansion that silently did not happen reads as a corpus that
does not contain the law.

## How the two expansion layers divide the work

The thesaurus covers the common core — the terms of art a housing lawyer types
every day, which are too frequent for co-occurrence statistics to say anything
useful about. The learned table covers the long tail nobody thought to curate:
it is what knows that `nuisance` travels with `abate` and `3767.41`, and that
`lead` travels with `paint` and `hazards`.

Every expansion is reported with the result set, labelled `thesaurus` (with its
verification) or `distributional` (labelled learned, not reviewed), and every
result says which of the reader's own words it actually contains and which it
does not.

## What research mode does not do here

- It does not rank with a model. Reranking and synthesis are opt-in per search,
  applied on top of a finished result set, and reported in every response
  whether they ran or not.
- It does not treat an exact phrase or a citation as a hint. Both are
  requirements: only text that contains them is returned, and when nothing does,
  the search names what went unmatched instead of ranking something else.
