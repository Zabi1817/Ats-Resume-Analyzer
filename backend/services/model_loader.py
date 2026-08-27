import logging
import threading
from typing import Optional
from backend.core.config import (
    SPACY_MODEL_PRIMARY,
    SPACY_MODEL_SECONDARY,
    SENTENCE_TRANSFORMER_MODEL,
)

logger = logging.getLogger('ats_resume_scorer')

_nlp_model = None
_embedder_model = None

_nlp_lock = threading.Lock()
_embedder_lock = threading.Lock()

_nlp_error: Optional[str] = None
_embedder_error: Optional[str] = None


def get_nlp():
    """
    Lazily load spaCy model thread-safely.
    Falls back gracefully if primary/secondary models are missing.
    """
    global _nlp_model, _nlp_error
    if _nlp_model is not None:
        return _nlp_model

    with _nlp_lock:
        if _nlp_model is not None:
            return _nlp_model

        logger.info(f"Loading spaCy model: {SPACY_MODEL_PRIMARY}...")
        import spacy
        try:
            _nlp_model = spacy.load(SPACY_MODEL_PRIMARY)
            logger.info(f"Loaded primary spaCy model: {SPACY_MODEL_PRIMARY}")
            return _nlp_model
        except Exception as err:
            logger.warning(
                f"Primary spaCy model {SPACY_MODEL_PRIMARY} unavailable ({err}) — trying secondary: {SPACY_MODEL_SECONDARY}"
            )
            try:
                _nlp_model = spacy.load(SPACY_MODEL_SECONDARY)
                logger.info(f"Loaded secondary spaCy model: {SPACY_MODEL_SECONDARY}")
                return _nlp_model
            except Exception as err_sec:
                logger.warning(
                    f"Secondary spaCy model unavailable ({err_sec}) — attempting automatic download of en_core_web_sm"
                )
                try:
                    from spacy.cli import download
                    download("en_core_web_sm")
                    _nlp_model = spacy.load("en_core_web_sm")
                    logger.info("Loaded en_core_web_sm after automatic download")
                    return _nlp_model
                except Exception as dl_err:
                    _nlp_error = str(dl_err)
                    logger.error(
                        f"Automatic download failed ({dl_err}). Falling back to blank English spaCy pipeline."
                    )
                    _nlp_model = spacy.blank("en")
                    return _nlp_model


def get_embedder():
    """
    Lazily load SentenceTransformer model thread-safely.
    """
    global _embedder_model, _embedder_error
    if _embedder_model is not None:
        return _embedder_model

    with _embedder_lock:
        if _embedder_model is not None:
            return _embedder_model

        logger.info(f"Loading SentenceTransformer: {SENTENCE_TRANSFORMER_MODEL}...")
        try:
            from sentence_transformers import SentenceTransformer
            _embedder_model = SentenceTransformer(SENTENCE_TRANSFORMER_MODEL)
            logger.info(f"Loaded SentenceTransformer: {SENTENCE_TRANSFORMER_MODEL}")
            return _embedder_model
        except Exception as exc:
            _embedder_error = str(exc)
            logger.error(f"Failed to load SentenceTransformer model {SENTENCE_TRANSFORMER_MODEL}: {exc}")
            raise RuntimeError(f"Embedding model '{SENTENCE_TRANSFORMER_MODEL}' could not be loaded: {exc}")


def is_nlp_loaded() -> bool:
    """Return True if spaCy NLP model has been loaded into memory."""
    return _nlp_model is not None


def is_embedder_loaded() -> bool:
    """Return True if SentenceTransformer model has been loaded into memory."""
    return _embedder_model is not None


def preload_models_async():
    """
    Spawns a background thread to begin loading spaCy and SentenceTransformer
    models asynchronously without blocking server port binding or HTTP requests.
    """
    def _preload():
        logger.info("Background preloading of AI models started...")
        try:
            get_nlp()
        except Exception as e:
            logger.error(f"Background NLP preloading error: {e}")

        try:
            get_embedder()
        except Exception as e:
            logger.error(f"Background embedder preloading error: {e}")

        logger.info("Background preloading of AI models completed.")

    thread = threading.Thread(target=_preload, daemon=True)
    thread.start()
