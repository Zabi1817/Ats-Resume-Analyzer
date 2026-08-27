import os
import socket
import logging
import urllib.parse
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
import streamlit as st
from supabase import Client, create_client

logger = logging.getLogger('ats_resume_scorer')

# Load .env explicitly from root
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).resolve().parents[2] / '.env'
    load_dotenv(env_path)
except ImportError:
    pass


def _sanitize_url(raw: str) -> str:
    if not raw:
        return ''
    s = raw.strip()
    if (s.startswith('"') and s.endswith('"')) or (s.startswith("'") and s.endswith("'")):
        s = s[1:-1].strip()
    s = s.rstrip('/')
    s = s.replace('/rest/v1', '').replace('/auth/v1', '')
    if s.startswith('supabase://'):
        s = 'https://' + s[len('supabase://'):]
    if s and not s.startswith(('http://', 'https://')):
        s = 'https://' + s.lstrip('/')
    return s


def _secret(key: str, section: str = 'supabase') -> str:
    """Read from env first, then fall back to st.secrets[section][key]."""
    val = os.getenv(key, '')
    if val:
        return val.strip(' "\'')
    try:
        val = st.secrets[section][key]
        return str(val).strip(' "\'')
    except (KeyError, FileNotFoundError, AttributeError):
        return ''


SUPABASE_URL = _sanitize_url(_secret('SUPABASE_URL'))
SUPABASE_ANON_KEY = _secret('SUPABASE_ANON_KEY')

OAUTH_REDIRECT_URL = (
    os.getenv('AUTH_REDIRECT_URL')
    or _secret('redirect_uri', 'google_oauth')
    or 'http://localhost:8501'
)


def _check_dns_resolution(url: str) -> Tuple[bool, str]:
    if not url:
        return False, "SUPABASE_URL is missing or empty"
    try:
        parsed = urllib.parse.urlparse(url)
        hostname = parsed.hostname
        if not hostname:
            return False, f"Invalid SUPABASE_URL: missing hostname in '{url}'"
        
        logger.info(f"Supabase configuration: SUPABASE_URL={url!r}, Hostname={hostname!r}")
        logger.info(f"Verifying DNS resolution for {hostname}...")
        
        socket.gethostbyname(hostname)
        logger.info(f"Successfully resolved DNS for {hostname}")
        return True, ""
    except socket.gaierror as e:
        logger.warning(f"DNS resolution failed for host {url}: {e}")
        return False, f"Could not resolve Supabase domain '{hostname}'. Please verify your SUPABASE_URL in .env and internet connection."
    except Exception as e:
        logger.warning(f"DNS resolution check error for host {url}: {e}")
        return False, f"Supabase host verification failed: {e}"


def _missing_config() -> Optional[str]:
    if not SUPABASE_URL or not SUPABASE_ANON_KEY:
        return 'Supabase is not configured — please set SUPABASE_URL and SUPABASE_ANON_KEY in .env or .streamlit/secrets.toml'
    
    if not SUPABASE_URL.startswith(('http://', 'https://')):
        return f"Invalid SUPABASE_URL format: '{SUPABASE_URL}'. Must start with https://"

    ok, dns_err = _check_dns_resolution(SUPABASE_URL)
    if not ok:
        return dns_err

    return None


@st.cache_resource
def get_client() -> Optional[Client]:
    """Cached singleton — preserves PKCE state across Streamlit reruns."""
    err = _missing_config()
    if err:
        logger.warning(f"Supabase client initialization skipped: {err}")
        return None
    try:
        return create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
    except Exception as exc:
        logger.error(f"Failed to create Supabase client: {exc}")
        return None


def demo_sign_in(email: str = "guest@example.com") -> Dict[str, Any]:
    """Provide local authentication session for guest/demo testing."""
    import jwt
    secret = os.getenv("SUPABASE_JWT_SECRET", "dev-secret-key-for-ats-scorer-32bytes")
    user_id = "00000000-0000-0000-0000-000000000001"
    token = jwt.encode({'sub': user_id, 'email': email, 'aud': 'authenticated'}, secret, algorithm='HS256')
    return {
        'access_token': token,
        'refresh_token': 'demo-refresh-token',
        'user_id': user_id,
        'email': email,
    }


def _session_dict(session, user) -> Dict[str, Any]:
    return {
        'access_token':  session.access_token,
        'refresh_token': session.refresh_token,
        'user_id':       user.id,
        'email':         user.email,
    }


def _is_transient_error(exc: Exception) -> bool:
    msg = str(exc).lower()
    transient_indicators = [
        '502', '503', '504', 'bad gateway', 'service unavailable',
        'gateway timeout', 'connection reset', 'server error'
    ]
    return any(ind in msg for ind in transient_indicators)


def _execute_with_retry(fn, max_retries: int = 2, backoff_sec: float = 1.0):
    import time
    for attempt in range(max_retries + 1):
        try:
            return fn()
        except Exception as exc:
            if _is_transient_error(exc) and attempt < max_retries:
                logger.warning(f"Transient Supabase error (attempt {attempt + 1}/{max_retries + 1}): {exc}. Retrying in {backoff_sec}s...")
                time.sleep(backoff_sec)
                continue
            raise exc


def sign_in_with_password(email: str, password: str) -> Dict[str, Any]:
    err = _missing_config()
    if err:
        return {'error': err}
    client = get_client()
    if not client:
        return {'error': 'Supabase client is not available. Please verify SUPABASE_URL in .env.'}
    try:
        resp = _execute_with_retry(
            lambda: client.auth.sign_in_with_password({'email': email, 'password': password})
        )
        if not resp.session or not resp.user:
            return {'error': 'Invalid credentials'}
        return _session_dict(resp.session, resp.user)
    except Exception as exc:
        logger.warning(f'sign_in_with_password failed: {exc}')
        return {'error': _humanize(exc)}


def sign_up_with_password(email: str, password: str) -> Dict[str, Any]:
    err = _missing_config()
    if err:
        return {'error': err}
    client = get_client()
    if not client:
        return {'error': 'Supabase client is not available. Please verify SUPABASE_URL in .env.'}
    try:
        resp = _execute_with_retry(
            lambda: client.auth.sign_up({'email': email, 'password': password})
        )
        if resp.session and resp.user:
            return _session_dict(resp.session, resp.user)
        if resp.user:
            return {'pending_confirmation': True, 'email': email}
        return {'error': 'Sign-up failed'}
    except Exception as exc:
        logger.warning(f'sign_up failed: {exc}')
        return {'error': _humanize(exc)}


def google_oauth_url() -> Dict[str, Any]:
    err = _missing_config()
    if err:
        return {'error': err}
    client = get_client()
    if not client:
        return {'error': 'Supabase client is not available.'}
    try:
        resp = _execute_with_retry(
            lambda: client.auth.sign_in_with_oauth({
                'provider': 'google',
                'options': {'redirect_to': OAUTH_REDIRECT_URL},
            })
        )
        return {'url': resp.url}
    except Exception as exc:
        logger.warning(f'oauth url generation failed: {exc}')
        return {'error': _humanize(exc)}


def exchange_code_for_session(auth_code: str) -> Dict[str, Any]:
    """Called once after the OAuth provider redirects back with `?code=...`."""
    err = _missing_config()
    if err:
        return {'error': err}
    client = get_client()
    if not client:
        return {'error': 'Supabase client is not available.'}
    try:
        storage_key = f'{client.auth._storage_key}-code-verifier'
        code_verifier = client.auth._storage.get_item(storage_key) or ''
        resp = _execute_with_retry(
            lambda: client.auth.exchange_code_for_session({
                'auth_code': auth_code,
                'code_verifier': code_verifier,
                'redirect_to': OAUTH_REDIRECT_URL,
            })
        )
        if not resp.session or not resp.user:
            return {'error': 'OAuth exchange returned no session'}
        return _session_dict(resp.session, resp.user)
    except Exception as exc:
        logger.warning(f'exchange_code_for_session failed: {exc}')
        return {'error': _humanize(exc)}


def sign_out() -> None:
    client = get_client()
    if not client:
        return
    try:
        client.auth.sign_out()
    except Exception as exc:
        logger.warning(f'sign_out failed: {exc}')


def _humanize(exc: Exception) -> str:
    msg = str(exc)
    low = msg.lower()
    if any(k in low for k in ['502', '503', '504', 'bad gateway', 'service unavailable', 'gateway timeout']):
        return "Supabase authentication service is currently unavailable (502 Bad Gateway). Please verify your Supabase project status in the Supabase dashboard or use Demo Mode."
    if 'getaddrinfo failed' in low or 'nameresolutionerror' in low or 'gaierror' in low:
        return "Cannot connect to Supabase: DNS lookup failed for the configured SUPABASE_URL. Please verify SUPABASE_URL in .env."
    if 'connecterror' in low or 'connection refused' in low or 'connecttimeout' in low:
        return "Cannot connect to Supabase: Network request failed. Check your internet connection and SUPABASE_URL."
    if 'invalid_grant' in low or 'invalid login' in low or 'invalid credentials' in low:
        return 'Wrong email or password'
    if 'user already registered' in low or 'already been registered' in low:
        return 'An account with this email already exists — try signing in'
    if 'password should be at least' in low:
        return 'Password too short (Supabase default is 6 characters)'
    return msg

