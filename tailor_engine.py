import json
import re
import os
import subprocess
import requests

PROVIDER_CONFIGS = {
    "Local Ollama":   {"url": "http://localhost:11434/v1/chat/completions", "requires_key": False},
    "Groq API":       {"url": "https://api.groq.com/openai/v1/chat/completions", "requires_key": True},
    "OpenRouter API": {"url": "https://openrouter.ai/api/v1/chat/completions", "requires_key": True},
}

PROVIDER_MODELS = {
    "Local Ollama": ["llama3", "llama3.1", "llama3.2", "mistral", "gemma2", "phi3", "codellama", "qwen2.5"],
    "Groq API": [
        "llama-3.3-70b-versatile", "llama-3.1-70b-versatile", "llama-3.1-8b-instant",
        "mixtral-8x7b-32768", "gemma2-9b-it", "llama3-70b-8192", "llama3-8b-8192",
    ],
    "OpenRouter API": [
        "meta-llama/llama-3.3-70b-instruct", "meta-llama/llama-3.1-8b-instruct:free",
        "mistralai/mistral-7b-instruct:free", "google/gemma-2-9b-it:free",
        "microsoft/phi-3-medium-128k-instruct:free", "qwen/qwen-2.5-7b-instruct:free",
    ],
}

RECENCY_WEIGHTS = {"2026": 1.4, "2025": 1.3, "2024": 1.1, "2023": 1.0, "2022": 0.9}
MIN_PROJECTS = 3
MAX_PROJECTS = 5


def query_unified_llm(system_prompt, user_prompt, provider="Local Ollama", model="llama3", api_key=""):
    config = PROVIDER_CONFIGS.get(provider, PROVIDER_CONFIGS["Local Ollama"])
    headers = {"Content-Type": "application/json"}
    if config["requires_key"] and api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    if provider == "OpenRouter API":
        headers["HTTP-Referer"] = "https://resume-tailor.app"
        headers["X-Title"] = "AI Resume Tailoring Agent"
    payload = {
        "model": model,
        "temperature": 0.2,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_prompt},
        ],
    }
    try:
        resp = requests.post(config["url"], json=payload, headers=headers, timeout=120)
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"].strip()
    except requests.exceptions.ConnectionError:
        raise ConnectionError(f"Cannot connect to {provider}. Check Ollama is running or API key is valid.")
    except Exception as e:
        raise RuntimeError(f"LLM error ({provider}): {e}")


def escape_latex(text):
    if not isinstance(text, str):
        return str(text)
    chars = {'&': r'\&', '%': r'\%', '_': r'\_', '$': r'\$', '#': r'\#'}
    for k, v in chars.items():
        text = text.replace(k, v)
    return text


def analyze_job_description(jd, provider, model, api_key):
    system = "You are a technical recruiter. Return ONLY minified valid JSON. No markdown, no fences."
    user = (
        'Analyze this Job Description. Return ONLY a JSON object with exactly:\n'
        '{"track":"<one of: App & Web Development | AI/ML & Intelligent Systems | ML Infra & Data Pipelines>",'
        '"hard_skills":["up to 8 tools/frameworks"],"core_concepts":["up to 5 concepts"],"domain":"<industry focus>"}\n\n'
        f'JD:\n{jd}'
    )
    raw = query_unified_llm(system, user, provider, model, api_key)
    clean = re.sub(r"```(?:json)?|```", "", raw).strip()
    try:
        return json.loads(clean)
    except Exception:
        return {"track": "AI/ML & Intelligent Systems", "hard_skills": [], "core_concepts": [], "domain": "General Engineering"}


def score_projects(profile, jd_schema):
    kws = [s.lower() for s in jd_schema.get("hard_skills", []) + jd_schema.get("core_concepts", [])]

    jd_text = (
        " ".join(jd_schema.get("hard_skills", []))
        + " "
        + " ".join(jd_schema.get("core_concepts", []))
        + " "
        + jd_schema.get("domain", "")
    ).lower()

    # Expand JD using aliases
    aliases = profile.get("skill_aliases", {})
    expanded_jd = jd_text

    for root_skill, variations in aliases.items():
        if root_skill.lower() in jd_text:
            expanded_jd += " " + " ".join(v.lower() for v in variations)

    scored = []

    for proj in profile["projects_pool"]:

        priority = proj.get("priority", 0)

        domains = [
            d.lower()
            for d in proj.get("domains", [])
        ]

        project_keywords = [
            k.lower()
            for k in proj.get("keywords", [])
        ]

        # Existing scoring
        tech_pts = sum(
            3 for t in proj["technologies"]
            if t.lower() in kws
        )

        text_pts = sum(
            1 for kw in kws
            if kw in " ".join(proj["bullets"]).lower()
        )

        # New scoring
        keyword_pts = sum(
            2 for kw in project_keywords
            if kw in expanded_jd
        )

        domain_pts = 0

        jd_domain = jd_schema.get("domain", "").lower()

        for d in domains:
            if d in jd_domain:
                domain_pts += 5

        priority_bonus = priority * 0.5

        raw = (
            tech_pts
            + text_pts
            + keyword_pts
            + domain_pts
            + priority_bonus
        )

        year = proj.get("timeline", "2023").split("-")[-1].strip()

        mult = RECENCY_WEIGHTS.get(year, 1.0)

        final = raw * mult

        scored.append(
            (
                proj,
                final,
                {
                    "tech_match": tech_pts,
                    "text_context": text_pts,
                    "keyword_pts": keyword_pts,
                    "domain_pts": domain_pts,
                    "priority_bonus": priority_bonus,
                    "recency_multiplier": mult,
                    "raw": raw,
                },
            )
        )

    scored.sort(
        key=lambda x: (
            -x[1],
            -int(x[0].get("timeline", "2023").split("-")[-1])
        )
    )

    above_zero = [
        (p, s, b)
        for p, s, b in scored
        if b["raw"] > 0
    ]

    selected = above_zero[:MAX_PROJECTS]

    if len(selected) < MIN_PROJECTS:
        selected_ids = {p["id"] for p, _, _ in selected}

        extras = [
            (p, s, b)
            for p, s, b in scored
            if p["id"] not in selected_ids
        ]

        for item in extras:
            if len(selected) >= MIN_PROJECTS:
                break
            selected.append(item)

    return selected, scored


def optimize_bullets(proj, jd_schema, provider, model, api_key, used_verbs):
    kws = jd_schema.get("hard_skills", []) + jd_schema.get("core_concepts", [])
    forbidden = ", ".join(used_verbs) if used_verbs else "none"
    system = "You are a resume bullet optimizer. Output ONLY raw LaTeX. No preamble, no explanation."
    user = (
        f'Rewrite EXACTLY 2 bullets for this project using the X-Y-Z formula.\n\n'
        f'PROJECT: {proj["title"]}\n'
        f'ALLOWED TECH: {", ".join(proj["technologies"])}\n'
        f'TARGET KEYWORDS: {", ".join(kws)}\n'
        f'ORIGINAL BULLETS:\n{chr(10).join(proj["bullets"])}\n\n'
        f'RULES:\n'
        f'1. Output EXACTLY 2 lines, each starting with \\item\n'
        f'2. Only mention tools from ALLOWED TECH\n'
        f'3. Do NOT start with these verbs: {forbidden}\n'
        f'4. Keep each bullet under 20 words\n'
        f'5. Output ONLY the 2 \\item lines. Nothing else.'
    )
    raw = query_unified_llm(system, user, provider, model, api_key)
    lines = [l.strip() for l in raw.splitlines() if l.strip().startswith(r"\item")][:2]
    # Fallback to original bullets if LLM output is bad
    for i, orig in enumerate(proj["bullets"][:2]):
        if i >= len(lines):
            lines.append(r"\item " + escape_latex(orig))
    for line in lines:
        words = line.replace(r"\item", "").strip().split()
        if words:
            used_verbs.add(words[0].lower().rstrip(","))
    return "\n".join(lines)


def build_latex(profile, jd_schema, final_projects, provider, model, api_key):
    track = jd_schema.get("track", "AI/ML & Intelligent Systems")
    selected_summary = profile["profile_summaries"][1]["text"]
    for s in profile["profile_summaries"]:
        if s["focus"].lower() in track.lower() or track.lower() in s["focus"].lower():
            selected_summary = s["text"]
            break

    used_verbs = set()
    project_tex = ""
    for proj in final_projects[:MAX_PROJECTS]:
        title = escape_latex(proj["title"])
        techs = escape_latex(", ".join(proj["technologies"]))
        bullets = optimize_bullets(proj, jd_schema, provider, model, api_key, used_verbs)
        project_tex += (
            f"\\noindent\n"
            f"\\textbf{{{title}}} ({escape_latex(proj['timeline'])})\n"
            f"\\begin{{itemize}}\n"
            f"{bullets}\n"
            f"\\item Technologies: {techs}\n"
            f"\\end{{itemize}}\n\n"
        )

    sk = profile["skills_pool"]
    pi = profile["personal_info"]
    linkedin_raw = pi["linkedin"]
    linkedin_url = linkedin_raw if linkedin_raw.startswith("http") else f"https://{linkedin_raw}"
    linkedin_label = escape_latex(linkedin_raw.replace("https://", "").replace("http://", ""))

    cert_items = "".join(
        f"    \\item \\textbf{{{escape_latex(c['name'])}}} --- {escape_latex(c['issuer'])} ({escape_latex(c['date'])})\n"
        for c in profile["certifications"]
    )
    award_items = "".join(
        f"    \\item \\textbf{{{escape_latex(a['title'])}}}, {escape_latex(a['organization'])} --- {escape_latex(a['detail'])}\n"
        for a in profile["awards_and_achievements"]
    )
    edu_items = "".join(
        f"    \\item \\textbf{{{escape_latex(e['institution'])}}} --- {escape_latex(e['degree'])}, {escape_latex(', '.join(e['metrics']))} ({escape_latex(e['timeline'])})\n"
        for e in profile["education"]
    )

    latex = (
        r"\documentclass[a4paper,9.5pt]{article}" + "\n"
        r"\usepackage[top=0.45in,bottom=0.45in,left=0.6in,right=0.6in]{geometry}" + "\n"
        r"\usepackage{titlesec}" + "\n"
        r"\usepackage[hidelinks]{hyperref}" + "\n"
        r"\usepackage{enumitem}" + "\n"
        r"\usepackage{microtype}" + "\n"
        "\n"
        r"\titleformat{\section}{\large\bfseries}{}{0em}{}[\titlerule]" + "\n"
        r"\titleformat{\subsection}{\normalsize\bfseries}{}{0em}{}" + "\n"
        r"\setlist[itemize]{noitemsep, topsep=0pt, parsep=0pt}" + "\n"
        r"\setlength{\parskip}{2pt}" + "\n"
        r"\titlespacing*{\section}{0pt}{5pt}{3pt}" + "\n"
        "\n"
        r"\begin{document}" + "\n"
        r"\pagenumbering{gobble}" + "\n"
        "\n"
        r"\begin{center}" + "\n"
        r"    {\Huge \textbf{" + escape_latex(pi["name"]) + r"}}\\" + "\n"
        r"    \vspace{2pt}" + "\n"
        r"    \href{mailto:" + pi["email"] + r"}{" + pi["email"] + r"} \,|\, " + "\n"
        r"    " + escape_latex(pi["phone"]) + r" \,|\, " + "\n"
        r"    \href{" + linkedin_url + r"}{" + linkedin_label + r"} \\" + "\n"
        r"    " + escape_latex(pi.get("location", pi.get("address", ""))) + "\n"
        r"\end{center}" + "\n"
        "\n"
        r"\section*{Profile}" + "\n"
        + escape_latex(selected_summary) + "\n"
        "\n"
        r"\section*{Skills}" + "\n"
        r"\begin{itemize}" + "\n"
        r"    \item \textbf{Core Concepts:} " + escape_latex(", ".join(sk["core_concepts"])) + "\n"
        r"    \item \textbf{Programming:} " + escape_latex(", ".join(sk["programming_languages"])) + "\n"
        r"    \item \textbf{Machine Learning (Project-based):} " + escape_latex(", ".join(sk["ai_ml_nlp"])) + "\n"
        r"    \item \textbf{Tools \& Technologies:} " + escape_latex(", ".join(sk["tools_and_infra"] + sk.get("web_technologies", [])[:2])) + "\n"
        r"    \item \textbf{Soft Skills:} " + escape_latex(", ".join(sk["soft_skills"])) + "\n"
        r"\end{itemize}" + "\n"
        "\n"
        r"\section*{\textbf{Certifications}}" + "\n"
        r"\begin{itemize}" + "\n"
        + cert_items +
        r"\end{itemize}" + "\n"
        "\n"
        r"\section*{Awards \& Achievements}" + "\n"
        r"\begin{itemize}" + "\n"
        + award_items +
        r"\end{itemize}" + "\n"
        "\n"
        r"\section*{Projects}" + "\n"
        "\n"
        + project_tex +
        r"\section*{Education}" + "\n"
        r"\begin{itemize}" + "\n"
        + edu_items +
        r"\end{itemize}" + "\n"
        "\n"
        r"\end{document}"
    )
    return latex


def match_and_build_resume(jd, provider="Local Ollama", model="llama3", api_key=""):
    with open("master_profile.json", "r", encoding="utf-8") as f:
        profile = json.load(f)

    jd_schema = analyze_job_description(jd, provider, model, api_key)
    selected, all_scored = score_projects(profile, jd_schema)
    final_projects = [p for p, _, _ in selected]

    latex = build_latex(profile, jd_schema, final_projects, provider, model, api_key)

    selected_ids = {p["id"] for p, _, _ in selected}
    log = []
    for proj, score, bd in all_scored:
        log.append({
            "title": proj["title"],
            "final_score": round(score, 2),
            "tech_match_pts": bd["tech_match"],
            "text_context_pts": bd["text_context"],
            "keyword_pts": bd["keyword_pts"],
            "domain_pts": bd["domain_pts"],
            "priority_bonus": bd["priority_bonus"],
            "recency_multiplier": bd["recency_multiplier"],
            "not_selected": proj["id"] not in selected_ids,
        })

    return latex, jd_schema, log


def compile_latex_to_pdf(latex_code, output_filename="Tailored_Resume"):
    tex_file = f"{output_filename}.tex"
    with open(tex_file, "w", encoding="utf-8") as f:
        f.write(latex_code)
    try:
        result = subprocess.run(
            ["pdflatex", "-interaction=nonstopmode", tex_file],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60,
        )
        for ext in [".aux", ".log", ".out"]:
            p = f"{output_filename}{ext}"
            if os.path.exists(p):
                os.remove(p)
        return result.returncode == 0, result.stdout.decode("utf-8", errors="ignore")
    except FileNotFoundError:
        return False, "pdflatex not found. Install TeX Live or use Overleaf."
    except Exception as e:
        return False, str(e)


def generate_cover_letter(jd_schema, selected_projects, name, provider, model, api_key):
    titles = ", ".join(p["title"] for p in selected_projects[:3])
    system = "You are a professional cover letter writer. Write exactly 3 short paragraphs. No salutation, no sign-off."
    user = (
        f"Write a 3-paragraph cover letter for {name}.\n"
        f"Role: {jd_schema.get('domain','Engineering')} | Track: {jd_schema.get('track','')}\n"
        f"Skills: {', '.join(jd_schema.get('hard_skills',[])[:6])}\n"
        f"Projects: {titles}\n"
        f"Each paragraph: 3-4 sentences. Confident, professional tone."
    )
    return query_unified_llm(system, user, provider, model, api_key)