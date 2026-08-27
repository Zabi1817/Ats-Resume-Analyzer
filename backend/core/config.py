import os
import re
from pathlib import Path
import logging
from urllib.parse import urlparse

# Load .env from the project root (two levels up from this file) explicitly —
# load_dotenv() with no args relies on caller-frame inspection that can fail
# silently under uvicorn reload, leaving env vars unset.
try:
    from dotenv import load_dotenv
    _ENV_PATH = Path(__file__).resolve().parents[2] / '.env'
    load_dotenv(_ENV_PATH)
except ImportError:
    pass

#api metadata
APP_TITLE='ATS RESUME ANALYZER API'
APP_VERSION='1.0.0'
APP_DESCRIPTION='analyse resumes against job description using nlp + ml'

ALLOWED_ORIGINS = [
    'https://appapppy-ktwxupi73vqhjzweksze9d.streamlit.app/',
    'http://localhost:8501',
    'http://127.0.0.1:8501'
]  

#file 
MAX_FILE_SIZE_MB=5
MAX_FILE_SIZE_BYTES=MAX_FILE_SIZE_MB*1024*1024

#Supported MIME types and their short names
SUPPORTED_MIME_TYPES = {
    'application/pdf': 'pdf',
    'application/msword': 'doc',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document': 'docx',
}

SUPPORTED_EXTENSIONS = {'.pdf', '.doc', '.docx'}

SPACY_MODEL_PRIMARY="en_core_web_md" #better accuracy
SPACY_MODEL_SECONDARY="en_core_web_sm" 
SENTENCE_TRANSFORMER_MODEL = os.getenv("SENTENCE_TRANSFORMER_MODEL", "all-MiniLM-L6-v2")

# Score component weights — this is business logic treated as config
SCORE_WEIGHTS = {
    "formatting": 20, "keywords": 25, "content": 25,
    "skill_validation": 15, "ats_compatibility": 15,
}

JD_KEYWORD_WEIGHT=0.6
JD_SEMANTIC_WEIGHT=0.4

SUPABASE_URL       = os.getenv('SUPABASE_URL', '')
SUPABASE_KEY       = os.getenv('SUPABASE_KEY', '')          # service_role — DB writes (bypasses RLS)
SUPABASE_ANON_KEY  = os.getenv('SUPABASE_ANON_KEY', '')     # public anon — frontend auth calls
SUPABASE_JWT_SECRET= os.getenv('SUPABASE_JWT_SECRET', '')   # used by backend to verify access tokens
GROQ_API_KEY       = os.getenv('GROQ_API_KEY', '')
GROQ_MODEL         = os.getenv('GROQ_MODEL', 'groq/compound')


def _sanitize_supabase_url(raw: str) -> str:
    """Sanitize SUPABASE_URL from various user inputs.

    - Strip whitespace and surrounding quotes
    - Accept "supabase://..." and convert to https://
    - Ensure scheme is http/https (default to https)
    - Remove any path like /rest/v1 or /auth/v1, leaving only the base domain
    - Return empty string if input falsy
    """
    if not raw:
        return ''
    s = raw.strip()
    # remove surrounding quotes
    if (s.startswith('"') and s.endswith('"')) or (s.startswith("'") and s.endswith("'")):
        s = s[1:-1].strip()
        
    s = s.replace('/rest/v1', '').replace('/auth/v1', '').rstrip('/')
    
    # convert supabase:// scheme to https://
    if s.startswith('supabase://'):
        s = 'https://' + s[len('supabase://'):]

    # ensure there's a scheme, default to https
    parsed = urlparse(s)
    if not parsed.scheme:
        s = 'https://' + s.lstrip('/')
        parsed = urlparse(s)

    if parsed.scheme not in ('http', 'https'):
        # fallback to https and strip any non-http scheme prefix
        s = re.sub(r'^[^:/]+://', '', s)
        s = 'https://' + s.lstrip('/')
        parsed = urlparse(s)

    # extract hostname (netloc) and reconstruct base url
    netloc = parsed.netloc or parsed.path.split('/')[0]
    if not netloc:
        return ''
    base = f'https://{netloc}'
    return base.rstrip('/')


# sanitize SUPABASE_URL loaded from env
SUPABASE_URL = _sanitize_supabase_url(os.getenv('SUPABASE_URL', ''))
# Construct the canonical JWKS URL for Supabase
SUPABASE_JWKS_URL = f"{SUPABASE_URL}/auth/v1/.well-known/jwks.json" if SUPABASE_URL else ''

# Log the sanitized values at import time so startup shows the configured values
_logger = logging.getLogger('ats_resume_scorer')
if SUPABASE_URL:
    _logger.info(f"SUPABASE_URL (sanitized)={SUPABASE_URL!r}")
    _logger.info(f"SUPABASE_JWKS_URL={SUPABASE_JWKS_URL}")


