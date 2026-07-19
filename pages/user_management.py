import streamlit as st
from html import escape as h
from database import get_all_users, upsert_user, deactivate_user, activate_user, get_user_sessions, get_login_audit_logs
from auth import register_officer, officer_exists
from ui import render_department_header


def render():
    try:
        render_department_header()
        role = st.session_state.get('_user_role', 'officer')
        if role != 'admin':
            st.error("Access denied. Admin role required.")
            return

        st.markdown("<div class='card-header'>User Management</div>", unsafe_allow_html=True)

        tab_list, tab_add, tab_audit = st.tabs(["Users", "Add User", "Audit Log"])

        with tab_list:
            users = get_all_users()
            if not users:
                st.markdown(
                    """<div class="empty-state"><div class="icon">&#128101;</div>
                    <div class="title">No Users Registered</div>
                    <div class="desc">Users appear here after their first login</div></div>""",
                    unsafe_allow_html=True,
                )
            else:
                for u in users:
                    with st.container():
                        cols = st.columns([2, 1, 1, 1, 0.8, 0.8])
                        with cols[0]:
                            status_icon = "\U0001F7E2" if u.get('is_active') else "\U0001F534"
                            st.markdown(f"{status_icon} **{h(u.get('name', ''))}**<br><span style='font-size:0.6rem;opacity:0.4;'>{h(u.get('badge_id', ''))}</span>", unsafe_allow_html=True)
                        with cols[1]:
                            st.markdown(f"<div style='font-size:0.72rem;'>{h(u.get('role', 'officer'))}</div>", unsafe_allow_html=True)
                        with cols[2]:
                            st.markdown(f"<div style='font-size:0.6rem;opacity:0.4;'>{h(u.get('email', '-'))}</div>", unsafe_allow_html=True)
                        with cols[3]:
                            st.markdown(f"<div style='font-size:0.6rem;opacity:0.4;'>{u.get('created_at','')[:10] if u.get('created_at') else '-'}</div>", unsafe_allow_html=True)
                        with cols[4]:
                            if u.get('is_active'):
                                if st.button("Deactivate", key=f"deact_{u['badge_id']}", use_container_width=True):
                                    deactivate_user(u['badge_id'])
                                    st.rerun()
                            else:
                                if st.button("Activate", key=f"act_{u['badge_id']}", use_container_width=True):
                                    activate_user(u['badge_id'])
                                    st.rerun()
                        with cols[5]:
                            with st.expander("Sessions", expanded=False):
                                sessions = get_user_sessions(u['badge_id'], limit=5)
                                for s in sessions:
                                    st.markdown(f"<div style='font-size:0.6rem;opacity:0.4;'>{s['login_at'][:16].replace('T',' ')} - {'Active' if s['is_active'] else 'Inactive'}</div>", unsafe_allow_html=True)

        with tab_add:
            st.markdown("<div class='card-header'>Register New User</div>", unsafe_allow_html=True)
            new_name = st.text_input("Full Name", key="um_name", placeholder="Officer name")
            new_id = st.text_input("Badge Number", key="um_id", placeholder="Badge ID")
            new_pw = st.text_input("Password", key="um_pw", type="password", placeholder="Choose password")
            new_role = st.selectbox("Role", ["officer", "supervisor", "admin"], key="um_role")
            new_email = st.text_input("Email (optional)", key="um_email", placeholder="officer@agency.gov")
            new_phone = st.text_input("Phone (optional)", key="um_phone", placeholder="(555) 123-4567")
            if st.button("Register User", type="primary", use_container_width=True):
                if new_name and new_id and new_pw:
                    if officer_exists(new_id):
                        st.error("Badge ID already exists")
                    else:
                        success, msg = register_officer(new_name, new_id, new_pw, role=new_role)
                        if success:
                            upsert_user(new_id, new_name, new_role, new_email, new_phone, True)
                            st.success(f"Registered {new_name} as {new_role}")
                            st.rerun()
                        elif msg:
                            st.error(msg)
                else:
                    st.error("Name, Badge ID, and Password required")

        with tab_audit:
            st.markdown("<div class='card-header'>Login Audit Log</div>", unsafe_allow_html=True)
            filter_badge = st.text_input("Filter by Badge ID (leave blank for all)", key="audit_filter", placeholder="Badge ID")
            logs = get_login_audit_logs(limit=200, badge_id=filter_badge)
            if logs:
                for log in logs[:100]:
                    success = "\U0001F7E2" if log.get('success') else "\U0001F534"
                    reason = f" - {log.get('failure_reason', '')}" if not log.get('success') else ""
                    st.markdown(
                        f"""<div style="display:flex;justify-content:space-between;padding:4px 8px;
                        border-bottom:1px solid #1e293b;font-size:0.68rem;">
                        <span>{success} {h(log.get('badge_id', ''))} {h(log.get('officer_name', '') or '')}{h(reason)}</span>
                        <span style="opacity:0.4;">{log.get('attempt_time', '')[:19].replace('T', ' ')}</span>
                        </div>""", unsafe_allow_html=True
                    )
            else:
                st.markdown("<div style='font-size:0.65rem;opacity:0.4;padding:8px;'>No audit log entries found</div>", unsafe_allow_html=True)
    except Exception as e:
        st.error(f"User management error: {e}")
