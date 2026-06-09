import streamlit as st
import os
import base64
from tailor_engine import (
    match_and_build_resume, compile_latex_to_pdf,
    generate_cover_letter, analyze_job_description,
    score_projects, PROVIDER_CONFIGS, PROVIDER_MODELS,
)

st.set_page_config(page_title="AI Resume Tailor", page_icon="💼", layout="wide")

# ─── CSS ─────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
[data-testid="stSidebar"] { background: #1a1a2e; }
[data-testid="stSidebar"] * { color: #e0e0e0 !important; }

/* Overleaf-style editor: dark textarea */
div[data-testid="stTextArea"] textarea {
    font-family: 'Courier New', monospace !important;
    font-size: 13px !important;
    line-height: 1.5 !important;
    background: #1e1e1e !important;
    color: #d4d4d4 !important;
    border: none !important;
    border-radius: 0 !important;
    resize: none !important;
}
div[data-testid="stTextArea"] { border-radius: 0 !important; }

.editor-bar {
    background: #2d2d2d;
    color: #4ec9b0;
    padding: 7px 14px;
    font-family: monospace;
    font-size: 0.82rem;
    border-radius: 4px 4px 0 0;
    display: flex;
    align-items: center;
    gap: 7px;
    border-bottom: 1px solid #444;
}
.dot { width: 12px; height: 12px; border-radius: 50%; display: inline-block; }
.dot-r { background: #ff5f56; }
.dot-y { background: #ffbd2e; }
.dot-g { background: #27c93f; }

.preview-bar {
    background: #252526;
    color: #569cd6;
    padding: 7px 14px;
    font-family: monospace;
    font-size: 0.82rem;
    border-radius: 4px 4px 0 0;
    border-bottom: 1px solid #3c3c3c;
}
.preview-empty {
    height: 700px;
    background: #1a1a1a;
    border: 1px solid #3c3c3c;
    border-top: none;
    border-radius: 0 0 4px 4px;
    display: flex; align-items: center; justify-content: center;
    color: #444; font-family: monospace; font-size: 0.9rem;
}
.pill { display:inline-block; padding:2px 10px; border-radius:20px; font-size:0.75rem; font-weight:600; }
.pill-ok  { background:#1a4731; color:#4ade80; }
.pill-err { background:#4a1a1a; color:#f87171; }
.how-to-btn {
    display: inline-block;
    background: #0f4c75;
    color: white !important;
    padding: 6px 16px;
    border-radius: 6px;
    font-size: 0.82rem;
    text-decoration: none;
    border: 1px solid #1b6ca8;
    cursor: pointer;
    margin-bottom: 10px;
}
.how-to-btn:hover { background: #1b6ca8; }
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

It's the **single source of truth** for all your experience — projects, skills, education, certifications, and awards.  
The AI reads it every time to build a perfectly tailored resume for any job description you paste.

---

## Step-by-step Instructions

### Step 1 — Gather all your resume material
Collect everything you have:
- Old resumes / CV (PDF or Word)
- LinkedIn profile text
- Any project descriptions, GitHub READMEs
- Certificates, awards, achievements

---

### Step 2 — Use the prompt below with any AI assistant

Copy the prompt below, then open one of these AI assistants:
""")

    col1, col2, col3 = st.columns(3)
    with col1:
        st.link_button("🤖 Open ChatGPT", "https://chat.openai.com", use_container_width=True)
    with col2:
        st.link_button("✨ Open Gemini", "https://gemini.google.com", use_container_width=True)
    with col3:
        st.link_button("🧠 Open Claude", "https://claude.ai", use_container_width=True)

    st.markdown("---")
    st.markdown("### Step 3 — Paste this prompt + all your details into the AI")

    MASTER_PROMPT = '''You are a JSON schema generator. I will give you all my resume details.
Convert everything into this exact JSON structure. Return ONLY valid JSON, no explanation.

{
  "personal_info": {
    "name": "YOUR FULL NAME",
    "email": "your@email.com",
    "phone": "+XX XXXXXXXXXX",
    "linkedin": "linkedin.com/in/your-profile",
    "location": "City, State"
  },
  "profile_summaries": [
    {
      "focus": "App & Web Development",
      "text": "2-3 sentence summary focused on web/app skills"
    },
    {
      "focus": "AI/ML & Intelligent Systems",
      "text": "2-3 sentence summary focused on AI/ML skills"
    },
    {
      "focus": "ML Infra & Data Pipelines",
      "text": "2-3 sentence summary focused on ML infra/pipelines"
    }
  ],
  "skills_pool": {
    "programming_languages": ["Language1", "Language2"],
    "web_technologies": ["HTML", "CSS", "MySQL"],
    "mobile_development": ["Android Studio"],
    "ai_ml_nlp": ["OpenCV", "TensorFlow"],
    "tools_and_infra": ["Docker", "AWS"],
    "core_concepts": ["DSA", "OOPS", "DBMS"],
    "soft_skills": ["Problem-solving", "Teamwork"]
  },
  "education": [
    {
      "institution": "University Name",
      "degree": "B.Tech CSE",
      "timeline": "2022--2026",
      "metrics": ["CGPA: 8.5"]
    }
  ],
  "projects_pool": [
    {
      "id": "unique_id_snake_case",
      "title": "Project Title",
      "timeline": "2024",
      "technologies": ["Python", "TensorFlow"],
      "bullets": [
        "First bullet: what you built and what it does, max 20 words.",
        "Second bullet: key result or technical detail, max 20 words."
      ]
    }
  ],
  "certifications": [
    {
      "name": "Certificate Name",
      "issuer": "Issuing Organization",
      "date": "Month Year"
    }
  ],
  "awards_and_achievements": [
    {
      "title": "Award Title",
      "organization": "Organization Name",
      "detail": "One sentence describing the achievement."
    }
  ]
}

--- PASTE ALL YOUR RESUME DETAILS BELOW THIS LINE ---
'''

    st.code(MASTER_PROMPT, language="text")
    st.markdown("""
---

### Step 4 — Save the output

1. The AI will return a JSON object
2. Copy the entire JSON
3. Paste it into a new file named exactly: **`master_profile.json`**
4. Save it in the **same folder** as `app.py` and `tailor_engine.py`

---

### Tips for better results

- Add **2 bullets per project** — keep each under 20 words
- Include **all projects** even old ones — the AI picks the best ones per JD
- The `id` field must be unique snake_case (e.g. `my_project_2024`)
- You can always update and re-run — the system reads it fresh every time

---
""")

    if st.button("✅ Got it — Back to Resume Tailor", type="primary"):
        st.session_state.page = "main"
        st.rerun()

    st.stop()

# ═══════════════════════════════════════════════════════════
# PAGE: MAIN
# ═══════════════════════════════════════════════════════════
st.markdown("# 💼 AI Resume Tailoring Agent")

# How-to button in top area
col_title, col_guide = st.columns([3, 1])
with col_guide:
    if st.button("📘 How to create master_profile.json", use_container_width=True):
        st.session_state.page = "guide"
        st.rerun()

st.caption("Paste JD → AI selects & rewrites projects → Edit LaTeX live → Compile → Download")
st.divider()

# ─── STATE A: JD INPUT ───────────────────────────────────────────────────────
if not st.session_state.latex_code:
    col_jd, col_info = st.columns([1.2, 0.8], gap="large")

    with col_jd:
        st.subheader("📋 Job Description")
        jd_text = st.text_area(
            "jd_input", height=420, label_visibility="collapsed",
            placeholder="We are looking for an AI Engineer proficient in Python, YOLOv8, OpenCV...",
        )
        if st.button("🚀 Generate Tailored Resume", type="primary", use_container_width=True):
            if not jd_text.strip():
                st.error("Paste a Job Description first.")
            elif not os.path.exists("master_profile.json"):
                st.error("master_profile.json not found! Click '📘 How to create master_profile.json' above to get started.")
            else:
                with st.status("🧠 Running agent pipeline...", expanded=True) as status:
                    try:
                        status.write("🕵️ Analyzing JD schema...")
                        jd_schema = analyze_job_description(jd_text, provider, model, api_key)
                        st.session_state.jd_schema = jd_schema
                        status.write(f"✅ Track: **{jd_schema.get('track')}** | Domain: **{jd_schema.get('domain')}**")
                        status.write("📊 Scoring & ranking projects (min 3, max 5)...")
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

    with col_info:
        st.subheader("ℹ️ How it works")
        st.markdown("""
**1. Paste JD** → AI extracts track, skills, domain

**2. Smart Scoring** → Projects ranked by:
- +3 pts per matching tech tag
- +1 pt per keyword in bullets
- Recency multiplier (2026 = 1.4×)
- Minimum 3, maximum 5 projects selected

**3. Bullet Optimizer** → Rewritten with X-Y-Z formula

**4. Live Editor** → Edit LaTeX like Overleaf

**5. Download** → PDF + .tex source
        """)
        st.divider()
        st.markdown(f"**Provider:** `{provider}`")
        st.markdown(f"**Model:** `{model}`")

# ─── STATE B: OVERLEAF-STYLE EDITOR ─────────────────────────────────────────
else:
    out = st.session_state.output_name

    # Info bar
    info_l, info_r = st.columns([3, 1])
    with info_l:
        if st.session_state.jd_schema:
            s = st.session_state.jd_schema
            st.markdown(
                f"**Track:** `{s.get('track','—')}` &nbsp;|&nbsp; "
                f"**Domain:** `{s.get('domain','—')}` &nbsp;|&nbsp; "
                f"**Skills:** {', '.join(s.get('hard_skills',[])[:5])}"
            )
    with info_r:
        if st.session_state.compile_status == "ok":
            st.markdown('<span class="pill pill-ok">✓ Compiled — 1 page</span>', unsafe_allow_html=True)
        elif st.session_state.compile_status == "error":
            st.markdown('<span class="pill pill-err">✗ Compile Error</span>', unsafe_allow_html=True)

    st.divider()

    # ── Main editor + preview ──────────────────────────────────────────────
    editor_col, preview_col = st.columns([1, 1], gap="small")

    with editor_col:
        st.markdown(
            '<div class="editor-bar">'
            '<span class="dot dot-r"></span>'
            '<span class="dot dot-y"></span>'
            '<span class="dot dot-g"></span>'
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

        # Button row
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

        if compile_clicked:
            with st.spinner("⚙️ Compiling LaTeX..."):
                success, log_out = compile_latex_to_pdf(edited_latex, out)
            st.session_state.compile_status = "ok" if success else "error"
            st.session_state.pdf_ready = success
            if not success:
                with st.expander("🔴 Compiler Log", expanded=True):
                    errors = [l for l in log_out.split("\n") if "error" in l.lower() or l.startswith("!")]
                    st.code("\n".join(errors[:20]) if errors else log_out[:1000], language="text")
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
                '<div style="font-size:3rem; margin-bottom:12px;">📄</div>'
                '<div>Click ▶ Compile to preview PDF here</div>'
                '</div></div>',
                unsafe_allow_html=True,
            )

    st.divider()

    # ── Tabs: Cover letter + Scoring ──────────────────────────────────────
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
" style="background:#0e4c92;color:white;border:none;padding:7px 16px;border-radius:5px;cursor:pointer;font-size:13px;margin-top:4px;">
📋 Copy to Clipboard
</button>""", unsafe_allow_html=True)
        else:
            st.info("Cover letter will appear here after generation.")

    with tab2:
        if st.session_state.scoring_log:
            log = st.session_state.scoring_log
            md = (
            "| # | Project | Tech | Context | Keyword | Domain | Priority | Recency× | Score | Status |\n"
        )

        md += (
            "|---|---------|------|---------|---------|--------|----------|----------|-------|--------|\n"
        )

        for i, s in enumerate(log, 1):

            status_str = "✅ Selected" if not s.get("not_selected") else "—"

            md += (
                f"| {i} | {s['title']} | "
                f"{s['tech_match_pts']} | "
                f"{s['text_context_pts']} | "
                f"{s['keyword_pts']} | "
                f"{s['domain_pts']} | "
                f"{s['priority_bonus']} | "
                f"{s['recency_multiplier']}× | "
                f"**{s['final_score']}** | "
                f"{status_str} |\n"
            )
            st.markdown(md)
            st.caption(
    "Score = (Tech + Context + Keyword + Domain + Priority) × Recency multiplier."
)