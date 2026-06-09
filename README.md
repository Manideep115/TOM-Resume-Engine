# TOM-Resume-Engine

![Python](https://img.shields.io/badge/Python-3.10+-blue)
![Streamlit](https://img.shields.io/badge/Streamlit-Frontend-red)
![LLM](https://img.shields.io/badge/LLM-Ollama%20%7C%20Groq%20%7C%20OpenRouter-green)
![LaTeX](https://img.shields.io/badge/PDF-LaTeX-gold)
![Status](https://img.shields.io/badge/Status-Active-success)

An AI-powered Resume Tailoring Engine that converts a Job Description into an ATS-friendly resume using context retrieved from a structured `Master_Profile.json`.

Instead of maintaining multiple resumes, maintain a single profile containing your projects, skills, certifications, achievements, and links. TOM automatically identifies the most relevant information and generates a tailored resume for each application.

---

## ✨ Features

* 🎯 Job Description Analysis
* 🏆 Project & Skill Ranking Engine
* 🧠 Context-Aware Resume Generation
* 📄 ATS-Friendly Resume Writing
* 📝 Automatic LaTeX Generation
* ⚡ Local PDF Compilation
* 📨 Cover Letter Generation
* 🔒 Local LLM Support via Ollama
* ☁️ Cloud LLM Support via Groq & OpenRouter

---

## 🚀 How It Works

Job Description
↓
JD Analysis
↓
Project Scoring & Ranking
↓
Context Selection
↓
AI Resume Generation
↓
LaTeX Generation
↓
ATS-Friendly Resume PDF

---

## ⚡ Quick Start

### 1️⃣ Create Your Master_Profile.json

Collect:

* Projects
* Skills
* Certifications
* Education
* Portfolio Links
* LinkedIn Profile
* GitHub Profile
* Previous Resumes

Use ChatGPT, Claude, or Gemini to convert everything into a structured `Master_Profile.json`.

A sample structure is provided in this repository.

### 2️⃣ Select Your LLM Provider

#### 🔒 Ollama (Local)

* No API key required
* Privacy-friendly
* Supports Llama, Mistral and other local models

#### ⚡ Groq

* Create a Groq API Key
* Paste it into the sidebar

#### ☁️ OpenRouter

* Create an OpenRouter API Key
* Paste it into the sidebar

### 3️⃣ Run TOM

```bash
streamlit run app.py
```

or

```bash
streamlit run app1.py
```

### 4️⃣ Generate Your Resume

* Paste a Job Description
* Select a Model
* Click Generate
* Review the LaTeX
* Compile PDF
* Download Resume

---

## 🧠 Smart Ranking Engine

Instead of sending the entire profile to the LLM, TOM first identifies the most relevant information using:

* Technology Stack Matching
* Domain Relevance Scoring
* Keyword Analysis
* Recency Weighting

Only the highest-ranked projects are selected for generation.

This reduces token usage and improves output quality.

---

## 📸 Screenshots

Add screenshots here.

---

## 🔮 Future Improvements

* ATS Score Analysis
* Multiple Resume Templates
* Desktop Packaging
* SaaS Deployment
* Interview Preparation Assistant

---

## 👨‍💻 Author

**Alur Manideep**

Built to spend less time editing resumes and more time preparing for opportunities.

**One Profile → Any Job → Tailored Resume**
