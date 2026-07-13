import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, Any, List
from database import get_db_connection, get_statistics
from health import run_all_checks, render_health_dashboard, check_ollama, check_whisper
from logger import get_logger

logger = get_logger(__name__)


def get_recent_activity(days: int = 30, limit: int = 50) -> List[Dict[str, Any]]:
    cutoff = (datetime.now() - timedelta(days=days)).isoformat()
    with get_db_connection() as conn:
        rows = conn.execute(
            """SELECT incident_id, officer_name, document_type, submission_timestamp,
                      was_modified_by_human, verification_signature_flag
               FROM legal_audit_logs
               WHERE submission_timestamp >= ?
               ORDER BY submission_timestamp DESC
               LIMIT ?""",
            (cutoff, limit),
        ).fetchall()
        return [dict(r) for r in rows]


def get_report_type_distribution() -> Dict[str, int]:
    stats = get_statistics()
    return stats.get("by_document_type", {})


def get_officer_activity(limit: int = 10) -> List[Dict[str, Any]]:
    with get_db_connection() as conn:
        rows = conn.execute(
            """SELECT officer_name, COUNT(*) as report_count,
                      SUM(was_modified_by_human) as modified_count,
                      SUM(verification_signature_flag) as verified_count,
                      MAX(submission_timestamp) as last_active
               FROM legal_audit_logs
               GROUP BY officer_name
               ORDER BY report_count DESC
               LIMIT ?""",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]


def get_submissions_by_day(days: int = 30) -> pd.DataFrame:
    cutoff = (datetime.now() - timedelta(days=days)).isoformat()
    with get_db_connection() as conn:
        rows = conn.execute(
            """SELECT DATE(submission_timestamp) as day, COUNT(*) as count
               FROM legal_audit_logs
               WHERE submission_timestamp >= ?
               GROUP BY day
               ORDER BY day""",
            (cutoff,),
        ).fetchall()
    df = pd.DataFrame([dict(r) for r in rows])
    if df.empty:
        return df
    df["day"] = pd.to_datetime(df["day"])
    full_range = pd.date_range(start=df["day"].min(), end=df["day"].max(), freq="D")
    df = df.set_index("day").reindex(full_range, fill_value=0).rename_axis("day").reset_index()
    df["count"] = df["count"].astype(int)
    return df


def get_modification_rate() -> float:
    stats = get_statistics()
    total = stats["total_submissions"]
    if total == 0:
        return 0.0
    return round((stats["human_modified"] / total) * 100, 1)


def mode_dashboard():
    try:
        from app import render_department_header, inject_css

        render_department_header()

        st.markdown("<div class='card-header'>System Health</div>", unsafe_allow_html=True)
        checks = run_all_checks()
        render_health_dashboard(checks)

        stats = get_statistics()
        total = stats["total_submissions"]

        if total == 0:
            st.markdown(
                """<div class="empty-state"><div class="icon">\U0001F4CA</div>
                <div class="title">No Data Yet</div>
                <div class="desc">Submit reports to see analytics and trends</div></div>""",
                unsafe_allow_html=True,
            )
            return

        st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
        st.markdown("<div class='card-header'>Overview</div>", unsafe_allow_html=True)

        m1, m2, m3, m4 = st.columns(4)
        with m1:
            mod_rate = get_modification_rate()
            st.markdown(
                f"""<div class="metric"><div class="metric-val">{total}</div>
                <div class="metric-label">Total Reports</div></div>""",
                unsafe_allow_html=True,
            )
        with m2:
            st.markdown(
                f"""<div class="metric"><div class="metric-val">{stats['verified']}</div>
                <div class="metric-label">Verified</div></div>""",
                unsafe_allow_html=True,
            )
        with m3:
            st.markdown(
                f"""<div class="metric"><div class="metric-val">{mod_rate}%</div>
                <div class="metric-label">Modified Rate</div></div>""",
                unsafe_allow_html=True,
            )
        with m4:
            types_count = len(stats.get("by_document_type", {}))
            st.markdown(
                f"""<div class="metric"><div class="metric-val">{types_count}</div>
                <div class="metric-label">Report Types</div></div>""",
                unsafe_allow_html=True,
            )

        st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)

        col_chart, col_types = st.columns([3, 2], gap="large")

        with col_chart:
            st.markdown("<div class='card-header'>30-Day Submission Trend</div>", unsafe_allow_html=True)
            df_daily = get_submissions_by_day(30)
            if not df_daily.empty:
                st.line_chart(df_daily.set_index("day")["count"])
            else:
                st.markdown(
                    "<div style='font-size:0.7rem;opacity:0.4;padding:12px;text-align:center;'>No submissions in the last 30 days</div>",
                    unsafe_allow_html=True,
                )

        with col_types:
            st.markdown("<div class='card-header'>Reports by Type</div>", unsafe_allow_html=True)
            type_dist = get_report_type_distribution()
            if type_dist:
                df_types = pd.DataFrame(
                    {"Type": list(type_dist.keys()), "Count": list(type_dist.values())}
                ).sort_values("Count", ascending=False)
                st.bar_chart(df_types.set_index("Type")["Count"])
            else:
                st.markdown(
                    "<div style='font-size:0.7rem;opacity:0.4;padding:12px;text-align:center;'>No report types recorded</div>",
                    unsafe_allow_html=True,
                )

        st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)

        col_activity, col_officers = st.columns([3, 2], gap="large")

        with col_activity:
            st.markdown("<div class='card-header'>Recent Activity</div>", unsafe_allow_html=True)
            activity = get_recent_activity(days=7, limit=20)
            if activity:
                for r in activity[:10]:
                    ts = r["submission_timestamp"][:16].replace("T", " ")
                    mod = (
                        '<span class="ar-mod ar-mod-yes">edited</span>'
                        if r.get("was_modified_by_human")
                        else '<span class="ar-mod ar-mod-no">draft</span>'
                    )
                    ver = "\u2713" if r.get("verification_signature_flag") else ""
                    st.markdown(
                        f"""<div class="recent-item" style="padding:6px 10px;">
                        <div><span class="ri-id">{r['incident_id'][:25]}</span>
                        <span style="font-size:0.6rem;opacity:0.4;"> {r['officer_name']}</span></div>
                        <div><span style="font-size:0.6rem;">{ts}</span> {mod} {ver}</div></div>""",
                        unsafe_allow_html=True,
                    )
            else:
                st.markdown(
                    "<div style='font-size:0.7rem;opacity:0.4;padding:12px;text-align:center;'>No recent activity</div>",
                    unsafe_allow_html=True,
                )

        with col_officers:
            st.markdown("<div class='card-header'>Officer Activity</div>", unsafe_allow_html=True)
            officers = get_officer_activity(limit=8)
            if officers:
                for o in officers:
                    st.markdown(
                        f"""<div style="display:flex;justify-content:space-between;
                        align-items:center;padding:6px 10px;border:1px solid #1e293b;
                        border-radius:4px;margin-bottom:4px;font-size:0.66rem;">
                        <div><strong>{o['officer_name']}</strong></div>
                        <div style="display:flex;gap:8px;opacity:0.6;">
                        <span>{o['report_count']} reports</span>
                        <span>{o['verified_count']} verified</span></div></div>""",
                        unsafe_allow_html=True,
                    )
            else:
                st.markdown(
                    "<div style='font-size:0.7rem;opacity:0.4;padding:12px;text-align:center;'>No officer data</div>",
                    unsafe_allow_html=True,
                )

    except Exception as e:
        logger.exception("Dashboard error: %s", e)
        st.error(f"Dashboard error: {e}")
