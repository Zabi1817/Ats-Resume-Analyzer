import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.core.config import(
    ALLOWED_ORIGINS, 
    APP_DESCRIPTION, 
    APP_TITLE, 
    APP_VERSION, 
    SPACY_MODEL_PRIMARY, 
    SPACY_MODEL_SECONDARY, SENTENCE_TRANSFORMER_MODEL
)
from backend.api.routes import router

logger=logging.getLogger('ats_resume_scorer')

@asynccontextmanager
async def lifespan(app:FastAPI):
    logger.info('Starting ATS Resume Analyzer API...')

    import spacy
    logger.info(f'Loading spaCy NLP model: {SPACY_MODEL_PRIMARY}')
    try:
        app.state.nlp = spacy.load(SPACY_MODEL_PRIMARY)
        logger.info(f'Loaded primary spaCy model: {SPACY_MODEL_PRIMARY}')
    except Exception as err:
        logger.warning(f'Primary spaCy model {SPACY_MODEL_PRIMARY} unavailable ({err}) — trying secondary: {SPACY_MODEL_SECONDARY}')
        try:
            app.state.nlp = spacy.load(SPACY_MODEL_SECONDARY)
            logger.info(f'Loaded secondary spaCy model: {SPACY_MODEL_SECONDARY}')
        except Exception as err_sec:
            logger.warning(f'Secondary spaCy model unavailable ({err_sec}) — attempting automatic download of en_core_web_sm')
            try:
                from spacy.cli import download
                download('en_core_web_sm')
                app.state.nlp = spacy.load('en_core_web_sm')
                logger.info('Loaded en_core_web_sm after automatic download')
            except Exception as dl_err:
                logger.error(f'Automatic download failed ({dl_err}). Falling back to blank English spaCy pipeline.')
                app.state.nlp = spacy.blank('en')

    logger.info(f'Loading SentenceTransformer: {SENTENCE_TRANSFORMER_MODEL}')
    from sentence_transformers import SentenceTransformer
    app.state.embedder = SentenceTransformer(SENTENCE_TRANSFORMER_MODEL)
    logger.info(f'Loaded {SENTENCE_TRANSFORMER_MODEL}')

    logger.info('All models loaded. API is ready to serve requests.')

    yield

    logger.info('shutting down the api!!')

app=FastAPI(
    title=APP_TITLE, 
    description=APP_DESCRIPTION, 
    version=APP_VERSION, 
    lifespan=lifespan,
    docs_url='/docs',
    redoc_url='/redoc'
)

app.add_middleware(
    CORSMiddleware, 
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True, 
    allow_methods     = ['*'],
    allow_headers     = ['*'],

)

app.include_router(router)

@app.get('/')
async def root():
    return {
        'name':      'ATS Resume Analyzer API',
        'version':   '2.0.0',
        'endpoints': {
            'POST   /api/v1/analyze-resume': 'Analyze a resume',
            'GET    /api/v1/history':        'Get user history',
            'DELETE /api/v1/history/:id':    'Delete a history entry',
            'GET    /api/v1/health':         'Health check',
            'POST   /api/v1/generate-pdf':   'Generate PDF report from data',
        },
    }

if __name__=='__main__':
    import os
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(
        'backend.main:app',
        host    = '0.0.0.0',
        port    = port,
        reload  = True,    # Auto-restart on code changes (dev only)
    )

