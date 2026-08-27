# ATS Resume Scorer

A web app that scores how well a resume matches a job description and returns actionable feedback. Built with FastAPI + Streamlit, using spaCy and Sentence Transformers for NLP and the Groq API for LLM-generated suggestions.

## What it does

1. Upload a resume (PDF / DOC / DOCX) and paste a job description.
2. The backend parses the resume, extracts skills and experience, and compares them to the JD using semantic similarity.
3. You get an ATS score, a breakdown by category (formatting, keywords, content, skill validation, ATS compatibility), and LLM-written suggestions for what to improve.
4. Past analyses are saved to your account so you can revisit them.

## Tech stack

- **Frontend:** Streamlit
- **Backend:** FastAPI (Python)
- **NLP:** spaCy (`en_core_web_md`), Sentence Transformers (`all-MiniLM-L6-v2`)
- **LLM:** Groq API (Llama 3)
- **Auth + Database:** Supabase (email/password and Google OAuth)
- **PDF report export:** Playwright (Chromium) + Jinja2

## Project structure

```
ATS_SCORER/
├── backend/              FastAPI app, NLP services, API routes
├── frontend/             Streamlit app, views, components
├── templates/            HTML templates for report generation
├── jupyter notebooks/    Research and dataset prep (not used at runtime)
├── requirements.txt      Combined backend + frontend dependencies
└── .env                  Environment variables configuration
```

## Setup

### 1. Clone and create a virtual environment

```bash
git clone <repo-url>
cd ATS_SCORER
python -m venv venv
.\venv\Scripts\activate         # Linux/macOS: source venv/bin/activate
```

### 2. Install dependencies & models

```bash
pip install -r requirements.txt
python -m playwright install chromium
python -m spacy download en_core_web_md
```

### 3. Configure environment variables

Ensure your `.env` file exists at project root containing Supabase & Groq API credentials:

```env
SUPABASE_URL=...
SUPABASE_KEY=...
SUPABASE_ANON_KEY=...
SUPABASE_JWT_SECRET=...
GROQ_API_KEY=...
```

### 4. Run the backend

From the project root:

```bash
python -m uvicorn backend.main:app --reload
```

The API will run at `http://localhost:8000`.

### 5. Run the frontend

In a new terminal (with the venv activated):

```bash
streamlit run frontend/streamlit_app.py
```

The app opens at `http://localhost:8501`.

## Notes for students

- **Never commit `.env` or `secrets.toml`** — they hold API keys. Both are in `.gitignore`; check before you push.
- The first run downloads the Sentence Transformer model (~80 MB). It's cached afterwards.
- If you don't have a Groq key yet, the scoring still works — only the LLM suggestions section will be empty.
- `jupyter notebooks/` and `ml model/` are for experimentation and aren't required to run the app.
