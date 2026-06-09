import streamlit as st
import os
import base64
import pandas as pd
from tailor_engine import (
    match_and_build_resume, compile_latex_to_pdf,
    generate_cover_letter, analyze_job_description,
    score_projects, PROVIDER_CONFIGS, PROVIDER_MODELS,
)

st.set_page_config(page_title="TOMM-AI Resume G", page_icon="🤖", layout="wide")

# ─── RCB THEME CSS ───────────────────────────────────────────────────────────
st.markdown("""
<style>
/* Main App Background & Text */
.stApp {
    background-color: #0b0b0b;
    color: #e0e0e0;
}

/* Sidebar styling */
[data-testid="stSidebar"] { 
    background: #000000; 
    border-right: 2px solid #C8102E;
}
[data-testid="stSidebar"] * { color: #D4AF37 !important; }

/* Primary Buttons (Red with Gold hover) */
div.stButton > button[kind="primary"] {
    background-color: #C8102E !important;
    color: #ffffff !important;
    border: 1px solid #C8102E !important;
    font-weight: bold;
    border-radius: 4px;
    transition: all 0.3s ease;
}
div.stButton > button[kind="primary"]:hover {
    background-color: #000000 !important;
    color: #D4AF37 !important;
    border: 1px solid #D4AF37 !important;
    box-shadow: 0 0 10px #D4AF37;
}

/* Secondary Buttons */
div.stButton > button {
    background-color: #1a1a1a !important;
    color: #e0e0e0 !important;
    border: 1px solid #333 !important;
}
div.stButton > button:hover {
    border-color: #0033A0 !important;
    color: #0033A0 !important;
}

/* Text Areas (JD Input & Latex Editor) */
div[data-testid="stTextArea"] textarea {
    font-family: 'Courier New', monospace !important;
    font-size: 14px !important;
    line-height: 1.5 !important;
    background: #121212 !important;
    color: #D4AF37 !important; 
    border: 1px solid #333 !important;
    border-radius: 4px !important;
    resize: none !important;
}
div[data-testid="stTextArea"] textarea:focus {
    border-color: #0033A0 !important;
    box-shadow: 0 0 5px #0033A0 !important;
}

/* Editor & Preview Header Bars */
.editor-bar {
    background: #000000;
    color: #C8102E;
    padding: 7px 14px;
    font-family: monospace;
    font-size: 0.85rem;
    font-weight: bold;
    border-radius: 4px 4px 0 0;
    display: flex;
    align-items: center;
    gap: 7px;
    border-top: 2px solid #C8102E;
    border-left: 1px solid #333;
    border-right: 1px solid #333;
}
.dot { width: 12px; height: 12px; border-radius: 50%; display: inline-block; }
.dot-r { background: #C8102E; } 
.dot-y { background: #D4AF37; } 
.dot-b { background: #0033A0; } 

.preview-bar {
    background: #0033A0; 
    color: #ffffff;
    padding: 7px 14px;
    font-family: monospace;
    font-size: 0.85rem;
    font-weight: bold;
    border-radius: 4px 4px 0 0;
    border-bottom: 1px solid #001a57;
}
.preview-empty {
    height: 700px;
    background: #0b0b0b;
    border: 1px solid #333;
    border-top: none;
    border-radius: 0 0 4px 4px;
    display: flex; align-items: center; justify-content: center;
    color: #666; font-family: monospace; font-size: 0.9rem;
}
.pill { display:inline-block; padding:2px 10px; border-radius:20px; font-size:0.75rem; font-weight:600; }
.pill-ok  { background:#0033A0; color:#D4AF37; border: 1px solid #D4AF37; }
.pill-err { background:#C8102E; color:#ffffff; }

/* Status expander */
[data-testid="stStatusWidget"] {
    background-color: #111 !important;
    border: 1px solid #D4AF37 !important;
}
</style>
""", unsafe_allow_html=True)

# ─── Session state ────────────────────────────────────────────────────────────
for k, v in {
    "latex_code": "", "cover_letter": "", "scoring_log": [],
    "jd_schema": {}, "output_name": "Tailored_Resume",
    "compile_status": None, "pdf_ready": False,
    "page": "main",
}.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ─── SIDEBAR ─────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## ⚙️ Inference Settings")
    st.divider()
    provider = st.selectbox("🔌 Provider", list(PROVIDER_CONFIGS.keys()))
    model = st.selectbox("🤖 Model", PROVIDER_MODELS[provider])
    api_key = ""
    if provider != "Local Ollama":
        api_key = st.text_input("🔑 API Key", type="password", placeholder="Bearer token")
    if provider == "Local Ollama":
        st.info("💡 Run `ollama serve` first.")
    st.divider()
    st.caption("🌡️ Temperature locked: 0.2")
    if st.session_state.latex_code:
        st.divider()
        st.markdown("**📄 Output File**")
        st.session_state.output_name = st.text_input(
            "Filename", value=st.session_state.output_name, label_visibility="collapsed"
        )
        if st.button("🔄 New Resume", use_container_width=True):
            for k in ["latex_code","cover_letter","scoring_log","jd_schema","compile_status","pdf_ready"]:
                st.session_state[k] = "" if isinstance(st.session_state[k], str) else ([] if isinstance(st.session_state[k], list) else ({} if isinstance(st.session_state[k], dict) else None))
            st.rerun()

# ═══════════════════════════════════════════════════════════
# PAGE: HOW TO CREATE master_profile.json
# ═══════════════════════════════════════════════════════════
if st.session_state.page == "guide":
    st.markdown("# 📘 How to Create Your `master_profile.json`")
    st.markdown("---")

    if st.button("← Back to Resume Tailor"):
        st.session_state.page = "main"
        st.rerun()

    st.markdown("""
## What is `master_profile.json`?
It's the **single source of truth** for all your experience. The AI reads it every time to build a perfectly tailored resume.
""")

    if st.button("✅ Got it — Back to Resume Tailor", type="primary"):
        st.session_state.page = "main"
        st.rerun()
    st.stop()

# ═══════════════════════════════════════════════════════════
# PAGE: MAIN
# ═══════════════════════════════════════════════════════════
st.markdown("# TOM-AI Resume Tailoring Agent")

col_title, col_guide = st.columns([3, 1])
with col_guide:
    if st.button("📘 How to create master_profile.json", use_container_width=True):
        st.session_state.page = "guide"
        st.rerun()

st.caption("Paste JD → AI selects & rewrites projects → Edit LaTeX live → Compile → Download")
st.divider()

# ─── STATE A: JD INPUT ───────────────────────────────────────────────────────
if not st.session_state.latex_code:
    spacer_left, col_jd, spacer_right = st.columns([1, 3, 1])

    with col_jd:
        st.markdown("<h3 style='text-align: center; color: #D4AF37;'>📋 Target Job Description</h3>", unsafe_allow_html=True)
        jd_text = st.text_area(
            "jd_input", height=380, label_visibility="collapsed",
            placeholder="Paste the target Job Description here...",
        )
        if st.button("🚀 Generate Tailored Resume", type="primary", use_container_width=True):
            if not jd_text.strip():
                st.error("Paste a Job Description first.")
            elif not os.path.exists("master_profile.json"):
                st.error("master_profile.json not found!")
            else:
                with st.status("🧠 Running RCB Agent Pipeline...", expanded=True) as status:
                    try:
                        status.write("🕵️ Analyzing JD schema...")
                        jd_schema = analyze_job_description(jd_text, provider, model, api_key)
                        st.session_state.jd_schema = jd_schema
                        status.write(f"✅ Track: **{jd_schema.get('track')}** | Domain: **{jd_schema.get('domain')}**")
                        status.write("📊 Scoring & ranking projects...")
                        status.write("✍️ Optimizing bullets (context-isolated)...")
                        latex, schema, log = match_and_build_resume(jd_text, provider, model, api_key)
                        st.session_state.latex_code = latex
                        st.session_state.scoring_log = log
                        status.write("📝 Generating cover letter...")
                        selected_projs = [{"title": s["title"]} for s in log if not s.get("not_selected")]
                        cl = generate_cover_letter(schema, selected_projs, "Alur Manideep", provider, model, api_key)
                        st.session_state.cover_letter = cl
                        status.update(label="✨ Done! Resume ready to edit & compile.", state="complete")
                    except ConnectionError as e:
                        status.update(label="❌ Connection failed", state="error")
                        st.error(str(e))
                    except Exception as e:
                        status.update(label="❌ Error", state="error")
                        st.exception(e)
                if st.session_state.latex_code:
                    st.rerun()

# ─── STATE B: OVERLEAF-STYLE EDITOR ─────────────────────────────────────────
else:
    out = st.session_state.output_name

    info_l, info_r = st.columns([3, 1])
    with info_l:
        if st.session_state.jd_schema:
            s = st.session_state.jd_schema
            st.markdown(
                f"**Track:** `<span style='color:#D4AF37'>{s.get('track','—')}</span>` &nbsp;|&nbsp; "
                f"**Domain:** `<span style='color:#D4AF37'>{s.get('domain','—')}</span>` &nbsp;|&nbsp; "
                f"**Skills:** {', '.join(s.get('hard_skills',[])[:5])}",
                unsafe_allow_html=True
            )
    with info_r:
        if st.session_state.compile_status == "ok":
            st.markdown('<span class="pill pill-ok">✓ Compiled — 1 page</span>', unsafe_allow_html=True)
        elif st.session_state.compile_status == "error":
            st.markdown('<span class="pill pill-err">✗ Compile Error</span>', unsafe_allow_html=True)

    st.divider()

    editor_col, preview_col = st.columns([1, 1], gap="small")

    with editor_col:
        st.markdown(
            '<div class="editor-bar">'
            '<span class="dot dot-r"></span>'
            '<span class="dot dot-y"></span>'
            '<span class="dot dot-b"></span>'
            '&nbsp; resume.tex — LaTeX Editor'
            '</div>',
            unsafe_allow_html=True,
        )
        edited_latex = st.text_area(
            label="latex_src",
            value=st.session_state.latex_code,
            height=700,
            label_visibility="collapsed",
            key="latex_editor_area",
        )
        st.session_state.latex_code = edited_latex

        b1, b2, b3 = st.columns(3)
        with b1:
            compile_clicked = st.button("▶ Compile", type="primary", use_container_width=True)
        with b2:
            st.download_button(
                "📄 .tex", data=edited_latex,
                file_name=f"{out}.tex", mime="text/plain",
                use_container_width=True,
            )
        with b3:
            pdf_path = f"{out}.pdf"
            if st.session_state.pdf_ready and os.path.exists(pdf_path):
                with open(pdf_path, "rb") as f:
                    st.download_button(
                        "📥 PDF", data=f,
                        file_name=f"{out}.pdf", mime="application/pdf",
                        use_container_width=True,
                    )
            else:
                st.button("📥 PDF", disabled=True, use_container_width=True, help="Compile first")

        # ─── RESTORED UNFILTERED LOG VIEWER ───
        if compile_clicked:
            with st.spinner("⚙️ Compiling LaTeX..."):
                success, log_out = compile_latex_to_pdf(edited_latex, out)
            st.session_state.compile_status = "ok" if success else "error"
            st.session_state.pdf_ready = success
            if not success:
                st.error("🔴 LaTeX Compilation Failed!")
                with st.expander("📝 View Full Unfiltered Compiler Log", expanded=True):
                    st.code(log_out, language="text")
            st.rerun()

    with preview_col:
        st.markdown('<div class="preview-bar">📄 PDF Preview — Live</div>', unsafe_allow_html=True)
        pdf_path = f"{out}.pdf"
        if st.session_state.pdf_ready and os.path.exists(pdf_path):
            with open(pdf_path, "rb") as f:
                b64 = base64.b64encode(f.read()).decode()
            st.markdown(
                f'<iframe src="data:application/pdf;base64,{b64}#toolbar=0&view=FitH" '
                f'width="100%" height="714px" '
                f'style="border:1px solid #3c3c3c; border-top:none; border-radius:0 0 4px 4px; display:block;"></iframe>',
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                '<div class="preview-empty">'
                '<div style="text-align:center;">'
                '<div style="font-size:3rem; margin-bottom:12px;">🏏</div>'
                '<div>Click ▶ Compile to preview PDF here</div>'
                '</div></div>',
                unsafe_allow_html=True,
            )

    st.divider()

    tab1, tab2 = st.tabs(["📝 Cover Letter", "🕵️ Score Breakdown"])

    with tab1:
        if st.session_state.cover_letter:
            st.text_area(
                "Tailored Cover Letter (editable — copy manually):",
                value=st.session_state.cover_letter,
                height=240,
                key="cl_area",
            )
            st.markdown("""
<button onclick="
  var t = document.querySelector('#cl_area textarea') || document.querySelectorAll('[data-testid=stTextArea] textarea')[1];
  if(!t){ var all=document.querySelectorAll('textarea'); for(var i=0;i<all.length;i++){ if(all[i].value.length>200){t=all[i];break;} } }
  if(t){ navigator.clipboard.writeText(t.value).then(()=>{
    this.textContent='✅ Copied!';
    setTimeout(()=>{this.textContent='📋 Copy to Clipboard'},2000);
  }); }
" style="background:#C8102E;color:white;border:1px solid #D4AF37;padding:7px 16px;border-radius:5px;cursor:pointer;font-size:13px;margin-top:4px;font-weight:bold;">
📋 Copy to Clipboard
</button>""", unsafe_allow_html=True)
        else:
            st.info("Cover letter will appear here after generation.")

    with tab2:
        if st.session_state.scoring_log:
            log = st.session_state.scoring_log
            table_data = []
            for i, s in enumerate(log, 1):
                status_str = "✅ Selected" if not s.get("not_selected") else "—"
                table_data.append({
                    "#": i,
                    "Project": s['title'],
                    "Tech": s['tech_match_pts'],
                    "Context": s['text_context_pts'],
                    "Keyword": s['keyword_pts'],
                    "Domain": s['domain_pts'],
                    "Priority": s['priority_bonus'],
                    "Recency×": f"{s['recency_multiplier']}×",
                    "Score": s['final_score'],
                    "Status": status_str
                })
            
            df = pd.DataFrame(table_data)
            df.set_index("#", inplace=True)
            
            def highlight_selected(row):
                color = 'background-color: rgba(46, 204, 113, 0.25)' if row['Status'] == '✅ Selected' else ''
                return [color] * len(row)
            
            styled_df = df.style.apply(highlight_selected, axis=1)
            st.dataframe(styled_df, use_container_width=True)
            st.caption("Score = (Tech + Context + Keyword + Domain + Priority) × Recency multiplier.")
        else:
            st.info("Score breakdown will appear here after generation.")