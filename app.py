import streamlit as st
from pdf_processor import extract_pages_from_pdf
from workflow import compliance_pipeline
from database import init_db, save_scan, get_history, delete_scan

st.set_page_config(page_title="AI Compliance Pipeline", layout="wide")
init_db()

# ── Sidebar ───────────────────────────────────────────────────────────────────

st.sidebar.header("User")
username = st.sidebar.text_input("Your name / user ID", value="", placeholder="e.g. alice")

st.sidebar.header("Compliance Rules")
st.sidebar.caption("Edit these rules — the AI applies exactly what you write here, page by page.")

DEFAULT_RULES = """\
1. PII: Flag any personal identifiable information (emails, phone numbers, SSNs, names paired with addresses or account numbers).
2. Confidential Info: Flag sensitive business information such as trade secrets, unreleased financials, internal IP addresses, or proprietary company details.
3. Encoding / Language: All text must be UTF-8 encoded and in English only. Flag non-English content or non-UTF-8 encoding.
4. Abusive Content: Flag offensive, abusive, discriminatory, or unlawful language of any kind.\
"""

compliance_rules = st.sidebar.text_area(
    "Active compliance rules:",
    value=DEFAULT_RULES,
    height=260,
)

st.sidebar.markdown("---")
st.sidebar.caption("Powered by LangGraph + Ollama (llama3) — fully local, no API keys.")

# ── Main ──────────────────────────────────────────────────────────────────────

st.title("AI-Accelerated Compliance Pipeline")

tab_new, tab_history = st.tabs(["New Analysis", "History"])

# ── Tab 1: New Analysis ───────────────────────────────────────────────────────

with tab_new:
    st.subheader("Upload a PDF Document")
    uploaded_file = st.file_uploader("Select a PDF to check", type=["pdf"])

    if uploaded_file:
        st.success(f"Uploaded: **{uploaded_file.name}**")

        if st.button("Run Compliance Check", type="primary"):
            if not username.strip():
                st.warning("Enter a user ID in the sidebar to save your analysis to history.")

            with st.spinner("Extracting pages and running compliance checks — this may take a moment..."):
                pdf_bytes = uploaded_file.read()
                pages = extract_pages_from_pdf(pdf_bytes)

                result = compliance_pipeline.invoke({
                    "pages": pages,
                    "compliance_rules": compliance_rules,
                    "page_findings": [],
                    "analysis_report": "",
                })

            st.subheader("Compliance Report")

            # Summary banner
            all_findings = result["page_findings"]
            total_issues = sum(
                1 for pf in all_findings
                for k in ["pii", "confidential", "encoding", "abusive"]
                if pf[k].get("violated")
            )
            if total_issues == 0:
                st.success(f"All {len(all_findings)} page(s) passed every compliance check.")
            else:
                st.error(f"{total_issues} violation(s) found across {len(all_findings)} page(s).")

            # Per-page expandable cards
            CHECK_LABELS = {
                "pii": "PII",
                "confidential": "Confidential",
                "encoding": "Encoding / Lang",
                "abusive": "Abusive",
            }
            for pf in all_findings:
                has_issues = any(pf[k].get("violated") for k in CHECK_LABELS)
                with st.expander(
                    f"Page {pf['page_num']} — {'FAIL' if has_issues else 'PASS'}",
                    expanded=has_issues,
                ):
                    cols = st.columns(4)
                    for col, (key, label) in zip(cols, CHECK_LABELS.items()):
                        with col:
                            if pf[key].get("violated"):
                                st.error(f"**{label}**: FAIL")
                            else:
                                st.success(f"**{label}**: PASS")
                            st.caption(pf[key].get("details", ""))

            # Download
            st.download_button(
                "Download Full Report",
                data=result["analysis_report"],
                file_name=f"compliance_{uploaded_file.name}.txt",
                mime="text/plain",
            )

            # Persist to history
            if username.strip():
                save_scan(username.strip(), uploaded_file.name,
                          compliance_rules, result["analysis_report"])
                st.info(f"Report saved to history for **{username.strip()}**.")

# ── Tab 2: History ────────────────────────────────────────────────────────────

with tab_history:
    if not username.strip():
        st.info("Enter a user ID in the sidebar to view your analysis history.")
    else:
        st.subheader(f"History for: {username.strip()}")
        records = get_history(username.strip())

        if not records:
            st.info("No past analyses found for this user.")
        else:
            for item in records:
                with st.expander(
                    f"{item['pdf_name']}  ·  {item['created_at']}",
                    expanded=False,
                ):
                    with st.container():
                        col_rules, col_report = st.columns([1, 2])
                        with col_rules:
                            st.markdown("**Rules used:**")
                            st.code(item["rules"], language=None)
                        with col_report:
                            st.markdown(item["report"])

                    btn_col, del_col = st.columns([3, 1])
                    with btn_col:
                        st.download_button(
                            "Download Report",
                            data=item["report"],
                            file_name=f"report_{item['id']}.txt",
                            mime="text/plain",
                            key=f"dl_{item['id']}",
                        )
                    with del_col:
                        if st.button("Delete", key=f"del_{item['id']}"):
                            delete_scan(item["id"])
                            st.rerun()
