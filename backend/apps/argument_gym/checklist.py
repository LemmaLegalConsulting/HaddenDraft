"""Applying an advocate's own checklist, with the lookups an item implies.

A checklist item like "confirm every factual assertion about the notice is
supported by a document in the file" cannot be answered from the four corners of
the brief. So the model answering it can ask for what it needs -- authority from
the research libraries, passages from the case record, passages of the brief --
and answers only once it has looked.

The tool protocol is JSON in the message body rather than provider-native
function calling, matching the rest of this codebase: the same loop has to work
against any OpenAI-compatible endpoint. Lookups are bounded, read-only, and run
under the session's own access, so an item can never reach a case the viewer
cannot.
"""

import json
import re

from apps.ai.openai_client import OpenAIBackendError, OpenAICompatibleClient
from apps.ai.prompt_catalog import PromptCatalogError, render_prompt
from apps.ai.tool_loop import ToolEvaluation, run_tool_with_repair
from apps.argument_gym import record
from apps.argument_gym.pipeline import ai_enabled, choice, clean, dumps, json_object, run_research


MAX_TOOL_CALLS = 3
OUTCOMES = {"pass", "fail", "needs_review", "not_applicable"}
TOOLS = ("search_law", "search_case_record", "quote_brief")


def _terms(text):
    return {term for term in re.findall(r"[a-z0-9]{3,}", str(text or "").casefold())}


def _rank_passages(passages, query, *, limit=4):
    query_terms = _terms(query)
    if not query_terms:
        return passages[:limit]
    scored = [
        (len(query_terms & _terms(passage["text"])), index, passage)
        for index, passage in enumerate(passages)
    ]
    scored = [item for item in scored if item[0]]
    scored.sort(key=lambda item: (-item[0], item[1]))
    return [passage for _score, _index, passage in scored[:limit]]


class ChecklistTools:
    """The read-only lookups a checklist item may make, and a log of what it asked."""

    def __init__(self, *, brief_units, workspace, materials, user=None, request=None, registry=None):
        self.brief_units = brief_units
        self.workspace = workspace
        self.materials = materials
        self.user = user
        self.request = request
        self.registry = registry
        self.calls = []

    def run(self, name, arguments):
        query = str((arguments or {}).get("query") or "").strip()
        if name not in TOOLS:
            result = {"error": f"There is no tool named {name!r}."}
        elif not query:
            result = {"error": "A lookup needs a query."}
        elif name == "quote_brief":
            result = {"passages": self._quote_brief(query)}
        elif name == "search_case_record":
            result = {"passages": self._search_case_record(query)}
        else:
            result = {"sources": self._search_law(query)}
        self.calls.append({"tool": name, "query": query, "result": result})
        return result

    def _quote_brief(self, query):
        passages = [
            {"id": unit["id"], "section": unit["locator"]["section"], "text": unit["text"]}
            for unit in self.brief_units
            if unit["type"] != "section"
        ]
        return _rank_passages(passages, query)

    def _search_case_record(self, query):
        passages = []
        for material in self.materials:
            text = record.material_text(material, workspace=self.workspace, max_chars=4000)
            if text.strip():
                passages.append({"id": material["id"], "title": material["title"], "text": text})
        found = _rank_passages(passages, query, limit=3)
        return [{**passage, "text": passage["text"][:1200]} for passage in found]

    def _search_law(self, query):
        sources, _trace = run_research(
            [{"query": query, "targets": [], "purpose": "A checklist item asked for authority."}],
            matter=self.workspace.matter,
            jurisdiction=self.workspace.jurisdiction,
            user=self.user,
            request=self.request,
            registry=self.registry,
        )
        return [
            {
                "citation": source["citation"] or source["title"],
                "sourceLabel": source["sourceLabel"],
                "snippet": source["snippet"][:600],
                "url": source["url"],
            }
            for source in sources[:5]
        ]


def _fallback_result(item, tools):
    """Without a model, say what the item asks and what was found looking for it."""
    passages = tools.run("quote_brief", {"query": item["text"]}).get("passages") or []
    if passages:
        return {
            "outcome": "needs_review",
            "finding": (
                f"The brief has {len(passages)} passage(s) touching this item, but nothing here read them. "
                "Check the passages below against the item yourself."
            ),
            "evidence": [passage["text"][:200] for passage in passages[:2]],
            "suggestion": "",
        }
    return {
        "outcome": "needs_review",
        "finding": "No passage of the brief matched the words of this item, and nothing here read it.",
        "evidence": [],
        "suggestion": "",
    }


def _parse_reply(text):
    """A reply is either one tool call or one result. Anything else is neither."""
    payload = json_object(text)
    tool = payload.get("tool")
    if isinstance(tool, str) and tool:
        return {"kind": "tool", "tool": tool, "arguments": payload.get("arguments") or {}}
    result = payload.get("result")
    if isinstance(result, dict):
        return {
            "kind": "result",
            "result": {
                "outcome": choice(result.get("outcome"), OUTCOMES, "needs_review"),
                "finding": clean(result.get("finding"), limit=1200),
                "evidence": [clean(item, limit=400) for item in result.get("evidence") or [] if clean(item)],
                "suggestion": clean(result.get("suggestion"), limit=800),
            },
        }
    return {"kind": "unparsed"}


def apply_item(item, *, tools, brief_text, matter_summary, jurisdiction, llm_client=None):
    """Answer one checklist item, letting it look things up first."""
    tool_results = []

    def execute(plan):
        if plan["method"] == "deterministic":
            return {"method": "deterministic", "result": _fallback_result(item, tools), "toolCalls": []}
        client = llm_client or OpenAICompatibleClient()
        for _round in range(MAX_TOOL_CALLS + 1):
            try:
                prompt = render_prompt(
                    "argument_gym.checklist",
                    jurisdiction=jurisdiction or "the filing jurisdiction",
                    matter_summary=matter_summary,
                    item=dumps({"id": item["id"], "text": item["text"]}),
                    brief_excerpts=brief_text[:12000],
                    tool_results=dumps(tool_results) if tool_results else "Nothing yet.",
                    max_tool_calls=MAX_TOOL_CALLS,
                )
                reply = client.complete(
                    system=prompt.system,
                    user=prompt.user,
                    temperature=0.1,
                    model=prompt.default_model,
                    reasoning_level=prompt.default_reasoning_level,
                )
            except (OpenAIBackendError, PromptCatalogError):
                return {"method": "llm", "result": None, "toolCalls": tool_results}
            parsed = _parse_reply(reply)
            if parsed["kind"] == "result":
                return {"method": "llm", "result": parsed["result"], "toolCalls": tool_results}
            if parsed["kind"] != "tool" or len(tool_results) >= MAX_TOOL_CALLS:
                # Out of lookups, or a reply that is neither. Ask once more with
                # what it has; the loop's repair handles a second failure.
                return {"method": "llm", "result": None, "toolCalls": tool_results}
            outcome = tools.run(parsed["tool"], parsed["arguments"])
            tool_results.append({"tool": parsed["tool"], "arguments": parsed["arguments"], "result": outcome})
        return {"method": "llm", "result": None, "toolCalls": tool_results}

    def evaluate(_plan, outcome):
        if not outcome["result"]:
            return ToolEvaluation(False, "checklist_item_unanswered", "The item was not answered.")
        return ToolEvaluation(True, "checklist_item_answered", "The item was answered.")

    def repair(plan, _outcome, evaluation):
        if plan["method"] == "deterministic" or evaluation.code != "checklist_item_unanswered":
            return None
        return {"method": "deterministic"}

    loop = run_tool_with_repair(
        {"method": "llm" if ai_enabled() else "deterministic"},
        execute=execute,
        evaluate=evaluate,
        repair=repair,
        max_attempts=2,
    )
    result = loop.result["result"] or _fallback_result(item, tools)
    return {
        "itemId": item["id"],
        "item": item["text"],
        **result,
        "method": loop.result["method"],
        "lookups": [
            {"tool": call["tool"], "query": call["arguments"].get("query", "")}
            for call in loop.result["toolCalls"]
        ],
    }


def apply_checklist(
    checklist,
    *,
    brief_text,
    brief_units,
    workspace,
    materials,
    matter_summary,
    jurisdiction="",
    user=None,
    request=None,
    registry=None,
    llm_client=None,
):
    """Apply every item of one checklist, and report what each lookup asked for."""
    items = [item for item in (checklist.items or []) if str(item.get("text") or "").strip()]
    if not items:
        return {"checklistId": checklist.id, "title": checklist.title, "results": [], "lookups": []}
    tools = ChecklistTools(
        brief_units=brief_units,
        workspace=workspace,
        materials=materials,
        user=user,
        request=request,
        registry=registry,
    )
    results = [
        apply_item(
            {"id": str(item.get("id") or index), "text": str(item["text"]).strip()},
            tools=tools,
            brief_text=brief_text,
            matter_summary=matter_summary,
            jurisdiction=jurisdiction,
            llm_client=llm_client,
        )
        for index, item in enumerate(items, start=1)
    ]
    return {
        "checklistId": checklist.id,
        "title": checklist.title,
        "results": results,
        # Every lookup the checklist made, so an advocate can see what it read
        # before believing what it says.
        "lookups": tools.calls,
    }


def checklist_challenges(applied, *, limit=3):
    """A failed checklist item is a challenge like any other."""
    attacks = []
    for result in applied.get("results", []):
        if result["outcome"] != "fail":
            continue
        attacks.append(
            {
                "itemId": result["itemId"],
                "argument": f"Your own checklist is not satisfied: {result['item']} {result['finding']}".strip(),
                "whyItMatters": "This is a check the advocate chose to apply to this brief.",
                "suggestion": result.get("suggestion", ""),
            }
        )
    return attacks[:limit]
