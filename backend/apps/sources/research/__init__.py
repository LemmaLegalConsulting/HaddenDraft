"""Deterministic legal research over the maintained corpus.

Research mode is a library, not an assistant: a lawyer can search everything
this application holds with generative AI switched off, and see exactly why
each result came back. The modules here never import ``apps.ai``.
"""

from apps.sources.research.engine import ai_report, search
from apps.sources.research.expansion import status as expansion_status
from apps.sources.research.index import (
    corpus_fingerprint,
    corpus_identity,
    peek_index,
    research_index,
    reset_index,
    warm_index,
)

__all__ = [
    "ai_report",
    "corpus_fingerprint",
    "corpus_identity",
    "expansion_status",
    "peek_index",
    "research_index",
    "reset_index",
    "search",
    "warm_index",
]
