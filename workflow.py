import re
import json
from typing import TypedDict, List, Dict, Any

from langchain_ollama import ChatOllama
from langchain_core.prompts import PromptTemplate
from langgraph.graph import StateGraph, END


# ── State ─────────────────────────────────────────────────────────────────────

class PipelineState(TypedDict):
    pages: List[Dict[str, Any]]   # [{page_num, text}, ...]
    compliance_rules: str         # user-defined rules from the UI
    page_findings: List[Dict]     # one entry per page
    analysis_report: str


# ── LLM ───────────────────────────────────────────────────────────────────────

llm = ChatOllama(model="llama3", temperature=0.1)

# The prompt hands the user's own rules to the model — nothing is hardcoded here.
_COMPLIANCE_PROMPT = PromptTemplate.from_template(
    "You are a compliance auditor. Apply the rules below to the page text provided.\n\n"
    "COMPLIANCE RULES (defined by the user):\n{compliance_rules}\n\n"
    "PAGE {page_num} TEXT:\n{text}\n\n"
    "SYSTEM NOTE — Encoding/Language pre-check result: {encoding_note}\n\n"
    "For each of the four categories below, determine if it is violated based on the rules above.\n"
    "Reply ONLY with valid JSON — no markdown fences, no extra text:\n"
    '{{'
    '"pii":{{"violated":true_or_false,"details":"findings or None"}},'
    '"confidential":{{"violated":true_or_false,"details":"findings or None"}},'
    '"encoding":{{"violated":true_or_false,"details":"use the system note above"}},'
    '"abusive":{{"violated":true_or_false,"details":"findings or None"}}'
    '}}'
)


# ── Helpers ───────────────────────────────────────────────────────────────────

_PII_PATTERNS = [
    (r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b", "email"),
    (r"\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b", "phone"),
    (r"\b\d{3}-\d{2}-\d{4}\b", "SSN"),
]


def _regex_pii_scan(text: str) -> list[str]:
    """Fast regex scan — augments LLM PII check."""
    hits = []
    for pattern, label in _PII_PATTERNS:
        found = re.findall(pattern, text)
        if found:
            hits.append(f"{label}: {', '.join(found[:5])}")
    return hits


def _encoding_language_check(text: str) -> dict:
    """Pure-Python check — no LLM needed for this deterministic rule."""
    try:
        text.encode("utf-8").decode("utf-8")
        utf8_ok = True
    except Exception:
        utf8_ok = False

    non_ascii = sum(1 for c in text if ord(c) > 127)
    is_english = (non_ascii / max(len(text), 1)) < 0.15

    issues = []
    if not utf8_ok:
        issues.append("Non-UTF-8 encoding found.")
    if not is_english:
        issues.append("Non-English content found (>15% non-ASCII characters).")
    return {
        "violated": bool(issues),
        "details": " ".join(issues) if issues else "UTF-8 and English — OK.",
    }


def _call_llm(page_num: int, text: str, compliance_rules: str,
              encoding_note: str, regex_pii_hits: list[str]) -> dict:
    """Single LLM call per page using the user's compliance rules."""
    if not text.strip():
        return {
            "pii": {"violated": False, "details": "Empty page."},
            "confidential": {"violated": False, "details": "Empty page."},
            "encoding": {"violated": False, "details": encoding_note},
            "abusive": {"violated": False, "details": "Empty page."},
        }

    # Prepend any regex PII hits so the LLM can reference them
    pii_note = ("Regex pre-scan already found: " + "; ".join(regex_pii_hits)
                if regex_pii_hits else "Regex pre-scan found nothing.")
    enriched_rules = f"{compliance_rules}\n\n[System PII pre-scan] {pii_note}"

    try:
        result = (_COMPLIANCE_PROMPT | llm).invoke({
            "compliance_rules": enriched_rules,
            "page_num": page_num,
            "text": text[:3000],        # stay within context window
            "encoding_note": encoding_note,
        })
        raw = result.content
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        if m:
            return json.loads(m.group())
    except Exception:
        pass

    # Fallback — preserve the deterministic encoding result
    return {
        "pii": {"violated": bool(regex_pii_hits), "details": "; ".join(regex_pii_hits) or "None"},
        "confidential": {"violated": False, "details": "LLM parse error."},
        "encoding": {"violated": False, "details": encoding_note},
        "abusive": {"violated": False, "details": "LLM parse error."},
    }


# ── Nodes ─────────────────────────────────────────────────────────────────────

def process_pages_node(state: PipelineState) -> dict:
    """Run all 4 compliance checks per page, driven by user-supplied rules."""
    findings = []
    for page in state["pages"]:
        pn = page["page_num"]
        text = page["text"]

        regex_pii = _regex_pii_scan(text)
        enc = _encoding_language_check(text)

        llm_result = _call_llm(
            page_num=pn,
            text=text,
            compliance_rules=state["compliance_rules"],
            encoding_note=enc["details"],
            regex_pii_hits=regex_pii,
        )

        # Merge regex PII into LLM PII result
        pii = llm_result.get("pii", {})
        if regex_pii and not pii.get("violated"):
            pii = {"violated": True, "details": "; ".join(regex_pii)}
        elif regex_pii:
            pii["details"] = "; ".join(regex_pii) + " | " + pii.get("details", "")

        # Always trust the deterministic encoding check
        encoding_final = enc

        findings.append({
            "page_num": pn,
            "pii": pii,
            "confidential": llm_result.get("confidential", {"violated": False, "details": "None"}),
            "encoding": encoding_final,
            "abusive": llm_result.get("abusive", {"violated": False, "details": "None"}),
        })

    return {"page_findings": findings}


def aggregate_report_node(state: PipelineState) -> dict:
    """Combine per-page findings into a markdown report."""
    lines = ["# Compliance Analysis Report\n",
             f"**Rules applied:**\n{state['compliance_rules']}\n"]
    total_issues = 0

    for pf in state["page_findings"]:
        categories = {
            "pii": "PII / Personal Information",
            "confidential": "Confidential Information",
            "encoding": "Encoding / Language",
            "abusive": "Abusive / Unlawful Content",
        }
        flagged = [k for k in categories if pf[k].get("violated")]
        total_issues += len(flagged)
        status = "FAIL" if flagged else "PASS"

        lines.append(f"\n## Page {pf['page_num']} — {status}")
        for key, label in categories.items():
            icon = "FAIL" if pf[key].get("violated") else "PASS"
            lines.append(f"- **{label}**: {icon} — {pf[key].get('details', 'None')}")

    total_pages = len(state["page_findings"])
    lines.append(f"\n---\n**Summary**: {total_issues} issue(s) found across {total_pages} page(s).")
    return {"analysis_report": "\n".join(lines)}


# ── Graph ──────────────────────────────────────────────────────────────────────

_graph = StateGraph(PipelineState)
_graph.add_node("process_pages", process_pages_node)
_graph.add_node("aggregate_report", aggregate_report_node)
_graph.set_entry_point("process_pages")
_graph.add_edge("process_pages", "aggregate_report")
_graph.add_edge("aggregate_report", END)

compliance_pipeline = _graph.compile()
