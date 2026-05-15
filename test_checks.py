"""
Deterministic unit tests for the regex PII and encoding/language checks.
Run with: python test_checks.py
"""
from workflow import _regex_pii_scan, _encoding_language_check

PASS = "\033[92mPASS\033[0m"
FAIL = "\033[91mFAIL\033[0m"

results = []

def check(name: str, got, expected):
    ok = got == expected
    results.append(ok)
    print(f"  {'OK' if ok else 'FAIL'}  {name}")
    if not ok:
        print(f"        expected: {expected}")
        print(f"        got     : {got}")

# ── PII regex tests ────────────────────────────────────────────────────────────
print("\n[PII Regex]")

hits = _regex_pii_scan("Contact me at alice@example.com for details.")
check("detects email", len(hits) > 0, True)

hits = _regex_pii_scan("Call 212-555-0192 or 415.555.0348 anytime.")
check("detects phone (dash format)", any("phone" in h for h in hits), True)

hits = _regex_pii_scan("SSN on file: 547-82-3910")
check("detects SSN", any("SSN" in h for h in hits), True)

hits = _regex_pii_scan("The quarterly revenue was strong this year.")
check("clean text → no PII hits", hits, [])

# ── Encoding / Language tests ──────────────────────────────────────────────────
print("\n[Encoding / Language]")

r = _encoding_language_check("This is a clean English document with no issues.")
check("all-English text → no violation", r["violated"], False)

# Simulate high non-ASCII ratio (non-English content)
non_english = "Das ist ein deutscher Text. " * 20   # ~100% non-ASCII letters like ä,ö but even without them ratio test
mixed = "a" * 50 + "é" * 50   # 50% non-ASCII → should flag
r = _encoding_language_check(mixed)
check("50% non-ASCII → violation", r["violated"], True)

r = _encoding_language_check("")
check("empty page → no violation", r["violated"], False)

# ── Summary ────────────────────────────────────────────────────────────────────
print(f"\nResults: {sum(results)}/{len(results)} passed\n")