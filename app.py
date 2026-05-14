"""
Finance Credit Follow-Up Email Agent — Streamlit Dashboard.

Provides a visual interface for:
  - Viewing the invoice queue and overdue status
  - Running the agent pipeline with one click
  - Previewing generated emails per stage
  - Monitoring audit trail and escalations
  - Uploading new invoice CSV files

Run with:  streamlit run app.py
"""

import streamlit as st
import pandas as pd
import os
import json
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

from src.database import AuditDB
from src.agent import FinanceEmailAgent
from src.main import main as run_pipeline
from src.utils import format_currency

# ── Page Config ───────────────────────────────────────────────────────
st.set_page_config(
    page_title="Finance Follow-Up Agent",
    page_icon="💼",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ────────────────────────────────────────────────────────
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

    .stApp {
        font-family: 'Inter', sans-serif;
    }

    .main-header {
        background: linear-gradient(135deg, #0d1b2a 0%, #1b263b 50%, #415a77 100%);
        padding: 2rem 2.5rem;
        border-radius: 12px;
        margin-bottom: 1.5rem;
        color: white;
    }
    .main-header h1 {
        margin: 0;
        font-size: 1.8rem;
        font-weight: 700;
    }
    .main-header p {
        margin: 0.3rem 0 0 0;
        font-size: 0.95rem;
        opacity: 0.8;
    }

    .metric-card {
        background: white;
        border-radius: 10px;
        padding: 1.2rem 1.5rem;
        box-shadow: 0 1px 8px rgba(0,0,0,0.06);
        border-left: 4px solid #1565c0;
        text-align: center;
    }
    .metric-card.sent { border-left-color: #2e7d32; }
    .metric-card.escalated { border-left-color: #c62828; }
    .metric-card.skipped { border-left-color: #f9a825; }
    .metric-card.error { border-left-color: #9e9e9e; }

    .metric-value {
        font-size: 2rem;
        font-weight: 700;
        color: #1a237e;
    }
    .metric-label {
        font-size: 0.8rem;
        color: #666;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }

    .stage-badge {
        display: inline-block;
        padding: 4px 12px;
        border-radius: 20px;
        font-size: 0.75rem;
        font-weight: 600;
        color: white;
    }
    .stage-1 { background-color: #43a047; }
    .stage-2 { background-color: #fb8c00; }
    .stage-3 { background-color: #e53935; }
    .stage-4 { background-color: #b71c1c; }
    .stage-5 { background-color: #4a148c; }

    div[data-testid="stExpander"] {
        border: 1px solid #e0e0e0;
        border-radius: 8px;
        margin-bottom: 8px;
    }
</style>
""", unsafe_allow_html=True)


# ── Header ────────────────────────────────────────────────────────────
st.markdown("""
<div class="main-header">
    <h1>💼 Finance Credit Follow-Up Agent</h1>
    <p>AI-powered invoice follow-up email generation with tone escalation</p>
</div>
""", unsafe_allow_html=True)


# ── Sidebar ───────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### ⚙️ Configuration")

    api_key = os.getenv("OPENAI_API_KEY", "")
    has_key = bool(api_key) and api_key != "your_openai_api_key_here"

    if has_key:
        st.success("✅ API Key configured")
    else:
        st.warning("⚠️ Running in MOCK mode")

    st.markdown("---")
    st.markdown("### 📁 Upload Data")

    uploaded_file = st.file_uploader("Upload Invoice CSV", type=["csv"])
    if uploaded_file is not None:
        os.makedirs("data", exist_ok=True)
        df_upload = pd.read_csv(uploaded_file)
        df_upload.to_csv("data/invoices.csv", index=False)
        st.success(f"✅ Uploaded {len(df_upload)} records")

    st.markdown("---")
    st.markdown("### 📊 Quick Stats")

    try:
        db = AuditDB()
        stats = db.get_stats()
        st.metric("Total Processed", stats["total_processed"])
        st.metric("Emails Sent", stats["emails_sent"])
        st.metric("Escalated", stats["escalated"])
    except Exception:
        st.info("No audit data yet. Run the agent first.")


# ── Tabs ──────────────────────────────────────────────────────────────
tab_queue, tab_run, tab_audit, tab_emails = st.tabs([
    "📋 Invoice Queue", "🚀 Run Agent", "📊 Audit Trail", "✉️ Email Preview"
])


# ── Tab 1: Invoice Queue ─────────────────────────────────────────────
with tab_queue:
    st.markdown("### Current Invoice Queue")

    csv_path = "data/invoices.csv"
    if os.path.exists(csv_path):
        df = pd.read_csv(csv_path)

        # Add status column
        agent = FinanceEmailAgent.__new__(FinanceEmailAgent)

        def get_status_label(row):
            stage_info = agent.determine_stage(int(row["days_overdue"]), int(row.get("follow_up_count", 0)))
            stage = stage_info["stage"]
            if stage == 0:
                return "⏭️ Not Overdue"
            elif stage == 5:
                return "🚨 Escalation Flag"
            else:
                tone = stage_info.get("tone", "")
                return f"Stage {stage} — {tone}"

        df["Action Required"] = df.apply(get_status_label, axis=1)
        df["Amount (₹)"] = df["amount"].apply(lambda x: f"₹{x:,.2f}")

        st.dataframe(
            df[["invoice_no", "client_name", "Amount (₹)", "due_date", "days_overdue", "follow_up_count", "Action Required"]],
            use_container_width=True,
            hide_index=True,
        )

        # Summary metrics
        col1, col2, col3, col4 = st.columns(4)
        overdue = df[df["days_overdue"] > 0]
        with col1:
            st.metric("Total Invoices", len(df))
        with col2:
            st.metric("Overdue", len(overdue))
        with col3:
            if len(overdue) > 0:
                st.metric("Total Overdue Amount", f"₹{overdue['amount'].sum():,.2f}")
            else:
                st.metric("Total Overdue Amount", "₹0.00")
        with col4:
            escalation_count = len(df[df["days_overdue"] > 30])
            st.metric("Need Escalation", escalation_count)
    else:
        st.info("No invoice data found. Upload a CSV file in the sidebar.")


# ── Tab 2: Run Agent ──────────────────────────────────────────────────
with tab_run:
    st.markdown("### 🚀 Execute Agent Pipeline")
    st.markdown("Click the button below to process all overdue invoices and generate follow-up emails.")

    col1, col2 = st.columns([1, 3])
    with col1:
        run_button = st.button("▶️ Run Agent", type="primary", use_container_width=True)

    if run_button:
        with st.spinner("Processing invoices..."):
            try:
                results = run_pipeline()
                if results:
                    st.success(f"✅ Processed {len(results)} invoices successfully!")

                    # Display results summary
                    statuses = [r["status"] for r in results]
                    c1, c2, c3, c4 = st.columns(4)
                    with c1:
                        st.markdown(f"""
                        <div class="metric-card">
                            <div class="metric-value">{len(results)}</div>
                            <div class="metric-label">Total Processed</div>
                        </div>
                        """, unsafe_allow_html=True)
                    with c2:
                        st.markdown(f"""
                        <div class="metric-card sent">
                            <div class="metric-value">{statuses.count('generated')}</div>
                            <div class="metric-label">Emails Generated</div>
                        </div>
                        """, unsafe_allow_html=True)
                    with c3:
                        st.markdown(f"""
                        <div class="metric-card escalated">
                            <div class="metric-value">{statuses.count('escalated')}</div>
                            <div class="metric-label">Escalated</div>
                        </div>
                        """, unsafe_allow_html=True)
                    with c4:
                        st.markdown(f"""
                        <div class="metric-card skipped">
                            <div class="metric-value">{statuses.count('skipped')}</div>
                            <div class="metric-label">Skipped</div>
                        </div>
                        """, unsafe_allow_html=True)

                    # Show individual results
                    st.markdown("#### Results Detail")
                    for r in results:
                        status_icon = {"generated": "📧", "escalated": "🚨", "skipped": "⏭️", "error": "❌"}.get(r["status"], "❓")
                        with st.expander(f"{status_icon} {r['invoice_no']} — {r['status'].upper()}"):
                            st.json(r)
                else:
                    st.warning("No results returned.")
            except Exception as e:
                st.error(f"Pipeline error: {str(e)}")


# ── Tab 3: Audit Trail ───────────────────────────────────────────────
with tab_audit:
    st.markdown("### 📊 Audit Trail")

    try:
        db = AuditDB()
        logs = db.get_all_logs()

        if logs:
            df_logs = pd.DataFrame(logs)

            # Stats row
            stats = db.get_stats()
            c1, c2, c3, c4, c5 = st.columns(5)
            with c1:
                st.metric("Total", stats["total_processed"])
            with c2:
                st.metric("Sent", stats["emails_sent"])
            with c3:
                st.metric("Escalated", stats["escalated"])
            with c4:
                st.metric("Skipped", stats["skipped"])
            with c5:
                st.metric("Errors", stats["errors"])

            # Filter
            status_filter = st.selectbox("Filter by status:", ["All", "generated", "escalated", "skipped", "error"])
            if status_filter != "All":
                df_logs = df_logs[df_logs["status"] == status_filter]

            display_cols = ["timestamp", "invoice_no", "client_name", "amount", "days_overdue", "stage", "tone", "status", "send_method"]
            available_cols = [c for c in display_cols if c in df_logs.columns]
            st.dataframe(df_logs[available_cols], use_container_width=True, hide_index=True)

            # Clear button
            if st.button("🗑️ Clear Audit Logs", type="secondary"):
                db.clear_logs()
                st.rerun()
        else:
            st.info("No audit logs yet. Run the agent to generate data.")
    except Exception as e:
        st.error(f"Error loading audit data: {e}")


# ── Tab 4: Email Preview ─────────────────────────────────────────────
with tab_emails:
    st.markdown("### ✉️ Generated Email Preview")

    try:
        db = AuditDB()
        emails = [log for log in db.get_all_logs() if log.get("status") == "generated" and log.get("subject")]

        if emails:
            for email in emails:
                stage = email.get("stage", 0)
                tone = email.get("tone", "Unknown")
                stage_colors = {1: "🟢", 2: "🟡", 3: "🟠", 4: "🔴"}
                icon = stage_colors.get(stage, "⚪")

                with st.expander(f"{icon} Stage {stage} | {email['invoice_no']} — {tone}"):
                    st.markdown(f"**Subject:** {email.get('subject', 'N/A')}")
                    st.markdown(f"**Tone:** {tone} | **Stage:** {stage} | **Method:** {email.get('send_method', 'N/A')}")
                    st.markdown(f"**Timestamp:** {email.get('timestamp', 'N/A')}")
                    st.markdown("---")

                    # Display email body in a styled container
                    body_text = email.get("body", "No body content.")
                    st.markdown(f"""
                    <div style="background: #fafafa; color: #333; padding: 20px; border-radius: 8px; border: 1px solid #e0e0e0; line-height: 1.5; font-size: 14px; white-space: pre-wrap;">{body_text}</div>
                    """, unsafe_allow_html=True)
        else:
            st.info("No generated emails found. Run the agent first.")
    except Exception as e:
        st.error(f"Error loading emails: {e}")


# ── Footer ────────────────────────────────────────────────────────────
st.markdown("---")
st.markdown(
    "<div style='text-align: center; color: #888; font-size: 0.8rem;'>"
    "Finance Credit Follow-Up Email Agent · AI Enablement Internship · Arnav Sharma"
    "</div>",
    unsafe_allow_html=True,
)