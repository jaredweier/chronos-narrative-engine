
def render_animated_evidence_card(title, details, icon="📄", color_theme="blue"):
    html_content = f"""
    <div class="evidence-card {color_theme}" onmouseover="this.classList.add('hover')" onmouseout="this.classList.remove('hover')">
        <div class="ec-icon">{icon}</div>
        <div class="ec-content">
            <div class="ec-title">{h(title)}</div>
            <div class="ec-details">{h(details)}</div>
        </div>
        <div class="ec-action">
            <button class="ec-btn" onclick="alert('Viewing: {h(title)}')">View</button>
        </div>
    </div>
    <style>
    .evidence-card {{
        display: flex; align-items: center; gap: 16px; padding: 16px; margin-bottom: 12px;
        background: var(--bg-card-alt, rgba(15,23,42,0.4));
        border: 1px solid var(--border-color, #1e293b);
        border-radius: 10px; transition: all 0.3s cubic-bezier(0.25, 0.8, 0.25, 1);
        cursor: pointer; overflow: hidden; position: relative;
    }}
    .evidence-card::before {{
        content: ''; position: absolute; left: 0; top: 0; bottom: 0; width: 4px;
        background: transparent; transition: all 0.3s ease;
    }}
    .evidence-card.blue::before {{ background: #3b82f6; }}
    .evidence-card.green::before {{ background: #10b981; }}
    .evidence-card.amber::before {{ background: #f59e0b; }}
    
    .evidence-card.hover {{
        transform: translateY(-2px);
        box-shadow: 0 10px 20px rgba(0,0,0,0.2);
        border-color: var(--border-accent, rgba(59,130,246,0.5));
    }}
    .ec-icon {{ font-size: 24px; opacity: 0.8; transition: transform 0.3s ease; }}
    .evidence-card.hover .ec-icon {{ transform: scale(1.1); opacity: 1; }}
    
    .ec-content {{ flex: 1; }}
    .ec-title {{ font-size: 0.9rem; font-weight: 600; color: var(--text-primary, #e2e8f0); margin-bottom: 4px; }}
    .ec-details {{ font-size: 0.75rem; color: var(--text-secondary, #94a3b8); }}
    
    .ec-btn {{
        background: transparent; border: 1px solid var(--border-color, #1e293b);
        color: var(--text-primary, #e2e8f0); padding: 6px 12px; border-radius: 6px;
        font-size: 0.7rem; font-weight: 600; cursor: pointer; transition: all 0.2s ease;
    }}
    .ec-btn:hover {{
        background: rgba(59,130,246,0.1); border-color: #3b82f6; color: #3b82f6;
    }}
    
    /* Ripple Effect JS injected globally */
    </style>
    """
    st.markdown(html_content, unsafe_allow_html=True)


def inject_button_animations():
    js = """
    <script>
    document.addEventListener('DOMContentLoaded', (event) => {
        const attachRipple = () => {
            const buttons = window.parent.document.querySelectorAll('button[data-testid="baseButton-secondary"], button[data-testid="baseButton-primary"]');
            buttons.forEach(btn => {
                if (!btn.classList.contains('ripple-attached')) {
                    btn.classList.add('ripple-attached');
                    btn.addEventListener('click', function(e) {
                        let ripple = document.createElement('span');
                        ripple.classList.add('custom-ripple');
                        this.appendChild(ripple);
                        let x = e.clientX - e.target.offsetLeft;
                        let y = e.clientY - e.target.offsetTop;
                        ripple.style.left = `${x}px`;
                        ripple.style.top = `${y}px`;
                        setTimeout(() => { ripple.remove() }, 600);
                    });
                }
            });
        };
        setInterval(attachRipple, 1000);
    });
    </script>
    <style>
    .custom-ripple {
        position: absolute; background: rgba(255,255,255,0.3); border-radius: 50%;
        transform: scale(0); animation: ripple-anim 600ms linear; pointer-events: none;
    }
    @keyframes ripple-anim {
        to { transform: scale(4); opacity: 0; }
    }
    button[data-testid="baseButton-primary"] {
        transition: transform 0.15s ease, box-shadow 0.15s ease;
    }
    button[data-testid="baseButton-primary"]:active {
        transform: scale(0.96);
    }
    button[data-testid="baseButton-primary"]:hover {
        box-shadow: 0 4px 12px rgba(59,130,246,0.3);
    }
    </style>
    """
    st.markdown(js, unsafe_allow_html=True)
