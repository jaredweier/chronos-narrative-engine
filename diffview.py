import difflib
import streamlit as st
from typing import List, Tuple


def compute_diff(a: str, b: str) -> List[Tuple[str, str]]:
    a_lines = a.splitlines(keepends=True)
    b_lines = b.splitlines(keepends=True)
    diff = list(difflib.ndiff(a_lines, b_lines))
    changes = []
    for line in diff:
        if line.startswith("  "):
            changes.append(("same", line[2:].rstrip()))
        elif line.startswith("- "):
            changes.append(("removed", line[2:].rstrip()))
        elif line.startswith("+ "):
            changes.append(("added", line[2:].rstrip()))
        elif line.startswith("? "):
            continue
    return changes


def render_diff_html(diff: List[Tuple[str, str]]) -> str:
    html_parts = ['<div style="font-family:monospace;font-size:0.72rem;line-height:1.6;">']
    for kind, text in diff:
        if kind == "same":
            html_parts.append(f"<div style='padding:1px 8px;'>{text}</div>")
        elif kind == "removed":
            html_parts.append(
                f"<div style='padding:1px 8px;background:rgba(239,68,68,0.08);"
                f"border-left:3px solid #ef4444;color:#fca5a5;text-decoration:line-through;'>{text}</div>"
            )
        elif kind == "added":
            html_parts.append(
                f"<div style='padding:1px 8px;background:rgba(34,197,94,0.08);"
                f"border-left:3px solid #22c55e;color:#86efac;'>{text}</div>"
            )
    html_parts.append("</div>")
    return "\n".join(html_parts)


def render_diff_viewer(ai_draft: str, final_report: str):
    st.markdown("<div class='card-header'>AI Draft vs Final Report</div>", unsafe_allow_html=True)

    if ai_draft == final_report:
        st.markdown(
            "<div style='font-size:0.7rem;opacity:0.5;padding:8px;text-align:center;'>"
            "No changes \u2014 report was submitted as drafted</div>",
            unsafe_allow_html=True,
        )
        return

    diff = compute_diff(ai_draft, final_report)

    added = sum(1 for k, _ in diff if k == "added")
    removed = sum(1 for k, _ in diff if k == "removed")

    st.markdown(
        f"<div style='display:flex;gap:12px;margin-bottom:10px;font-size:0.66rem;'>"
        f"<span style='color:#22c55e;'>+{added} additions</span>"
        f"<span style='color:#ef4444;'>-{removed} removals</span>"
        f"<span style='opacity:0.4;'>{len(diff)} total lines</span></div>",
        unsafe_allow_html=True,
    )


if __name__ == '__main__':
    a = "Line one\nLine two\nLine three\n"
    b = "Line one\nLine two modified\nLine three\nLine four\n"
    changes = compute_diff(a, b)
    print("Diff test:")
    print(f"  {sum(1 for k,_ in changes if k=='added')} additions, "
          f"{sum(1 for k,_ in changes if k=='removed')} removals")

    view_mode = st.radio(
        "View Mode",
        ["Unified Diff", "Split View"],
        horizontal=True,
        key="diff_view_mode",
        label_visibility="collapsed",
    )

    if view_mode == "Unified Diff":
        st.markdown(render_diff_html(diff), unsafe_allow_html=True)
    else:
        col_a, col_b = st.columns(2, gap="small")
        with col_a:
            st.markdown(
                "<div style='font-size:0.62rem;font-weight:600;color:#94a3b8;"
                "margin-bottom:4px;text-transform:uppercase;letter-spacing:0.06em;'>AI Draft</div>",
                unsafe_allow_html=True,
            )
            st.text_area("AI", ai_draft, height=350, disabled=True, key="diff_ai", label_visibility="collapsed")
        with col_b:
            st.markdown(
                "<div style='font-size:0.62rem;font-weight:600;color:#94a3b8;"
                "margin-bottom:4px;text-transform:uppercase;letter-spacing:0.06em;'>Final Report</div>",
                unsafe_allow_html=True,
            )
            st.text_area("Final", final_report, height=350, disabled=True, key="diff_final", label_visibility="collapsed")


def diff_report_versions(incident_id: str) -> str:
    from database import get_snapshots
    snapshots = get_snapshots(incident_id)
    if len(snapshots) < 2:
        return "<div style='font-family:monospace;font-size:0.72rem;padding:16px;opacity:0.6;'>Less than 2 versions available for diff</div>"
    all_diff_html = []
    for i in range(1, len(snapshots)):
        prev_text = snapshots[i-1].get("snapshot_text", "")
        curr_text = snapshots[i].get("snapshot_text", "")
        prev_label = snapshots[i-1].get("snapshot_label") or snapshots[i-1].get("label", f"Version {i}")
        curr_label = snapshots[i].get("snapshot_label") or snapshots[i].get("label", f"Version {i+1}")
        diff = compute_diff(prev_text, curr_text)
        added = sum(1 for k, _ in diff if k == "added")
        removed = sum(1 for k, _ in diff if k == "removed")
        all_diff_html.append(
            f"<div style='margin:12px 0 4px;font-size:0.66rem;font-family:monospace;'>"
            f"<strong>{prev_label}</strong> \u2192 <strong>{curr_label}</strong>"
            f" <span style='color:#22c55e;'>+{added}</span> <span style='color:#ef4444;'>-{removed}</span>"
            f"</div>"
        )
        all_diff_html.append(render_diff_html(diff))
    return "\n".join(all_diff_html)
