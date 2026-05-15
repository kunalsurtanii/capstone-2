"""
Golden-set evaluation for the compliance pipeline.

Creates 4 test documents with known violations, runs each through the pipeline,
then prints a per-check confusion matrix with Precision, Recall, F1, and FNR.

Run from the project root (venv must be active):
    python evaluate.py
"""

import fitz  # PyMuPDF
from workflow import compliance_pipeline

# ── Default rules (same as app.py sidebar defaults) ───────────────────────────
RULES = """\
1. PII: Flag any personal identifiable information (emails, phone numbers, SSNs,
   names paired with addresses or account numbers).
2. Confidential Info: Flag sensitive business information such as trade secrets,
   unreleased financials, internal IP addresses, or proprietary company details.
3. Encoding / Language: All text must be UTF-8 encoded and in English only.
4. Abusive Content: Flag offensive, abusive, discriminatory, or unlawful language.\
"""

CHECKS = ["pii", "confidential", "encoding", "abusive"]

# ── Ground truth ───────────────────────────────────────────────────────────────
# Each doc maps check → True (should be flagged) or False (should be clean)
GROUND_TRUTH = {
    "Doc A — Clean": {
        "pii": False, "confidential": False, "encoding": False, "abusive": False
    },
    "Doc B — PII only": {
        "pii": True,  "confidential": False, "encoding": False, "abusive": False
    },
    "Doc C — Abusive only": {
        "pii": False, "confidential": False, "encoding": False, "abusive": True
    },
    "Doc D — All violated": {
        "pii": True,  "confidential": True,  "encoding": True,  "abusive": True
    },
}

# ── PDF content for each test document ────────────────────────────────────────
DOC_CONTENT = {

    "Doc A — Clean": """\
ACME CORPORATION — QUARTERLY BUSINESS REVIEW
Period: Q1 2026

Executive Summary
-----------------
Overall performance for Q1 2026 met expectations across all business units.
The operations team successfully completed the infrastructure migration on schedule.
Customer satisfaction scores improved by 4 points compared to the prior quarter.

Key Highlights
--------------
- Product launch completed on time with positive market reception.
- Operational costs reduced by 7% through process improvements.
- Three new enterprise accounts onboarded in the EMEA region.
- Employee engagement survey response rate reached 87%.

Next Steps
----------
The leadership team will meet in April to review Q2 targets. Department heads
should submit budget forecasts by the 15th. All documentation must follow the
standard template available on the internal wiki.

This report is intended for internal planning purposes only.
""",

    "Doc B — PII only": """\
HR DEPARTMENT — EMPLOYEE CONTACT REGISTER
Confidentiality Level: Internal

The following employees are enrolled in the Q2 training programme.
Please ensure all communications use the contact details listed below.

Employee Records
----------------
Name  : James Thornton
Email : james.thornton@acmecorp.com
Phone : 212-555-0134
SSN   : 482-91-3075

Name  : Linda Perez
Email : linda.perez@acmecorp.com
Phone : 415-555-0289
SSN   : 319-54-7820

Name  : External Trainer — Dr. Anil Shah
Email : a.shah@trainingpartners.io
Phone : 646-555-9001

All personal data is processed in line with our data protection policy.
Please do not forward this document outside the HR department.
""",

    "Doc C — Abusive only": """\
INTERNAL FEEDBACK PORTAL — UNMODERATED SUBMISSIONS
Report Period: March 2026

The following comments were submitted via the anonymous feedback tool
and have NOT yet been reviewed by HR.

Submission #2201:
"The senior management team are a bunch of useless idiots who have no
clue what they are doing. This company is run by absolute morons."

Submission #2202:
"I swear to God if they cut bonuses again those crooked bastards will
hear from my lawyer. This is outright fraud."

Submission #2203:
"The CEO should be fired immediately. Anyone that stupid has no right
to be running a company. What a colossal disaster of leadership."

Submission #2204:
"These incompetent fools are going to drive this business straight into
the ground. Complete and utter failures, every single one of them."

HR will review and action these submissions by end of month.
""",

    "Doc D — All violated": """\
ACME CORPORATION — STRICTLY CONFIDENTIAL BRIEFING NOTE
Project Nightingale — Phase 2 Initiation

SECTION 1: EMPLOYEE PII
-----------------------
Deal lead: Sarah Mitchell — sarah.mitchell@acmecorp.internal
Phone: 212-555-0192   SSN: 547-82-3910
External counsel: d.chu@whitehallpartners.com — 646-555-7701

SECTION 2: CONFIDENTIAL BUSINESS INFORMATION
---------------------------------------------
Acquisition target (codename CANARY) valuation: $1,200,000,000
Unpublished EBITDA forecast FY2026: 34.7% — DO NOT DISCLOSE before SEC filing.
Internal VPN: 10.22.0.0/16  |  Admin password: Acme@Prod#2026!
Proprietary WACC model (patent pending): 8.3%

SECTION 3: NON-ENGLISH CONTENT (ENCODING VIOLATION)
-----------------------------------------------------
Frankfurt: "Die Quartalszahlen sind voellig inakzeptabel."
Tokyo: "このプロジェクトは失敗した。" (approx 22% non-ASCII on this page)
Paris: "Les résultats sont en dessous des prévisions du trimestre."

SECTION 4: ABUSIVE / UNLAWFUL CONTENT
--------------------------------------
Anonymous submission: "These incompetent bastards are committing fraud.
Someone should report these damn crooks to the SEC immediately."
Legal note: this content may constitute defamation and is unlawful.
""",
}


# ── Helper: build a single-page PDF bytes object ──────────────────────────────
def _make_pdf(text: str) -> bytes:
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((40, 40), text, fontsize=9.5)
    return doc.tobytes()


# ── Run the pipeline on a PDF bytes object ────────────────────────────────────
def _run_pipeline(pdf_bytes: bytes) -> dict:
    """Returns {check: violated_bool} aggregated across all pages."""
    import fitz as _fitz
    raw_doc = _fitz.open(stream=pdf_bytes, filetype="pdf")
    pages = [{"page_num": i + 1, "text": p.get_text()} for i, p in enumerate(raw_doc)]

    result = compliance_pipeline.invoke({
        "pages": pages,
        "compliance_rules": RULES,
        "page_findings": [],
        "analysis_report": "",
    })

    # A check is violated if ANY page flagged it
    aggregated = {c: False for c in CHECKS}
    for pf in result["page_findings"]:
        for c in CHECKS:
            if pf[c].get("violated"):
                aggregated[c] = True
    return aggregated


# ── Confusion matrix ──────────────────────────────────────────────────────────
def _compute_matrix(predictions: dict) -> dict:
    """
    predictions: {doc_name: {check: predicted_bool}}
    Returns per-check counts: {check: {TP, FP, TN, FN}}
    """
    matrix = {c: {"TP": 0, "FP": 0, "TN": 0, "FN": 0} for c in CHECKS}
    for doc_name, pred in predictions.items():
        truth = GROUND_TRUTH[doc_name]
        for c in CHECKS:
            p = pred[c]
            t = truth[c]
            if t and p:
                matrix[c]["TP"] += 1
            elif t and not p:
                matrix[c]["FN"] += 1
            elif not t and p:
                matrix[c]["FP"] += 1
            else:
                matrix[c]["TN"] += 1
    return matrix


def _metrics(m: dict) -> tuple:
    tp, fp, tn, fn = m["TP"], m["FP"], m["TN"], m["FN"]
    precision  = tp / (tp + fp) if (tp + fp) else 0.0
    recall     = tp / (tp + fn) if (tp + fn) else 0.0
    f1         = (2 * precision * recall / (precision + recall)
                  if (precision + recall) else 0.0)
    fnr        = fn / (tp + fn) if (tp + fn) else 0.0
    return precision, recall, f1, fnr


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    print("\n" + "=" * 60)
    print("  COMPLIANCE PIPELINE — GOLDEN SET EVALUATION")
    print("=" * 60)

    predictions = {}
    for doc_name, content in DOC_CONTENT.items():
        print(f"\nRunning: {doc_name} ...", flush=True)
        pdf_bytes = _make_pdf(content)
        predictions[doc_name] = _run_pipeline(pdf_bytes)

        truth = GROUND_TRUTH[doc_name]
        pred  = predictions[doc_name]
        for c in CHECKS:
            t_str = "FAIL" if truth[c] else "PASS"
            p_str = "FAIL" if pred[c]  else "PASS"
            match = "OK " if truth[c] == pred[c] else "WRONG"
            print(f"  {c:<14} expected={t_str:<4}  got={p_str:<4}  [{match}]")

    # Per-check confusion matrix
    matrix = _compute_matrix(predictions)

    print("\n" + "=" * 60)
    print("  CONFUSION MATRIX  (across all 4 test documents)")
    print("=" * 60)
    print(f"\n{'CHECK':<16} {'TP':>4} {'FP':>4} {'TN':>4} {'FN':>4} "
          f"{'PRECISION':>10} {'RECALL':>8} {'F1':>6} {'FNR':>6}")
    print("-" * 68)

    for c in CHECKS:
        m = matrix[c]
        precision, recall, f1, fnr = _metrics(m)
        label = c.upper()
        print(f"{label:<16} {m['TP']:>4} {m['FP']:>4} {m['TN']:>4} {m['FN']:>4} "
              f"{precision:>10.2f} {recall:>8.2f} {f1:>6.2f} {fnr:>6.2f}")

    print("-" * 68)
    print("\nTP=True Positive  FP=False Positive  TN=True Negative  FN=False Negative")
    print("FNR=False Negative Rate (missed violations — aim for 0.00)\n")

    # Highlight any weak checks
    print("DIAGNOSIS:")
    any_issue = False
    for c in CHECKS:
        _, recall, _, fnr = _metrics(matrix[c])
        if recall < 0.8:
            print(f"  ! {c.upper()}: recall={recall:.2f} — model is missing real violations. Tune prompt.")
            any_issue = True
        if matrix[c]["FP"] > 0:
            print(f"  ! {c.upper()}: {matrix[c]['FP']} false positive(s) — model is over-flagging clean content.")
            any_issue = True
    if not any_issue:
        print("  All checks passed evaluation thresholds.")
    print()


if __name__ == "__main__":
    main()
