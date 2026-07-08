# Treatise maintenance

Store received PDFs in `source/<treatise-slug>/<version>.pdf` and generated
derivatives in `markdown/<treatise-slug>/<version>/`. Preserve incoming PDFs;
the full Markdown, heading-aware chunks, and `manifest.yaml` are deterministic,
replaceable derivatives. Generate them with:

```bash
python scripts/chunk_legal_sources.py --all
```

The manifest records the source SHA-256 and generation time. Chunks carry their
PDF page range and complete heading ancestry, and are limited at existing
paragraph boundaries so citation strings and enumerated lists are not split.
Treatises delivered as multiple section-level PDFs may be configured as one
logical corpus. Their manifest includes a `source_files` inventory, and every
chunk records the path and SHA-256 of the specific PDF from which it came.
The HUD profile classifies glossary definitions and appendices/exhibits
separately for retrieval filters. See the parent [`content/README.md`](../README.md)
for naming and provenance requirements.

The application’s `rag` research source reads these manifests through
`CONTENT_LIBRARY_DIR`. Research results retain the chunk ID, source digest,
heading path, and PDF page range; selected results are passed to constrained AI
drafting as citeable excerpts. Retrieval is hybrid: legal-concept expansion
broadens natural-language questions, then (when AI drafting is enabled) an AI
relevance checker reranks candidate heading metadata without using it to answer
the legal question.
