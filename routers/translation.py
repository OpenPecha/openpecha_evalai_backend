from fastapi import APIRouter, HTTPException, Depends, Query, Path, Body, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, case
from typing import List, Dict, Any, Optional
from database import get_db
from auth import get_current_active_user
from models.user import User
from models.translation import ModelVersion, TranslationJob, TranslationOutput, Vote
from schemas.translation import (
    TranslationRequest, MultiTranslationRequest,
    LeaderboardResponse, LeaderboardEntry, ModelVersionRead,
    TranslationJobRead, TranslationOutputRead, ModelSuggestionResponse,
    VoteRequest, VoteResponse
)
import uuid
import json
import asyncio
import os
import time
import logging
from sse_starlette import EventSourceResponse
from dotenv import load_dotenv

load_dotenv()
# Set up logging
logger = logging.getLogger(__name__)

# AI Client imports - Python 3.12 compatible
try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False

try:
    import google.generativeai as genai
    GOOGLE_AVAILABLE = True
except ImportError:
    GOOGLE_AVAILABLE = False

router = APIRouter(prefix="/translate", tags=["Translation"])

db_dependency = Depends(get_db)

# Constants - System prompt from environment variable
SYSTEM_PROMPT = os.getenv("SYSTEM_PROMPT", "You are a translation engine. Output only the translated text.")

# Model provider mapping - read from environment variable with fallback
def get_model_providers():
    """Get model providers from environment variable with fallback to default configuration"""
    default_providers = {
        "claude-3-5-sonnet-20241022": "anthropic",
        "gemini-1.5-flash": "google",
    }
    
    model_providers_env = os.getenv("MODEL_PROVIDERS")
    if model_providers_env:
        try:
            return json.loads(model_providers_env)
        except json.JSONDecodeError as e:
            logger.warning(f"Invalid JSON in MODEL_PROVIDERS environment variable: {e}. Using default configuration.")
            return default_providers
    else:
        logger.info("MODEL_PROVIDERS environment variable not set. Using default configuration.")
        return default_providers

MODEL_PROVIDERS = get_model_providers()

# Initialize AI clients conditionally
openai_client = None
anthropic_client = None
google_configured = False
deepseek_client = None

if OPENAI_AVAILABLE and os.getenv("OPENAI_API_KEY"):
    openai_client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

if ANTHROPIC_AVAILABLE and os.getenv("ANTHROPIC_API_KEY"):
    anthropic_client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

if GOOGLE_AVAILABLE and os.getenv("GOOGLE_API_KEY"):
    genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
    google_configured = True

# DeepSeek via Novita AI uses OpenAI-compatible API
if OPENAI_AVAILABLE and os.getenv("DEEPSEEK_API_KEY"):
    deepseek_client = openai.OpenAI(
        api_key=os.getenv("DEEPSEEK_API_KEY"),
        base_url="https://api.novita.ai/openai"
    )

def find_cached_translation(db: Session, text: str, model_version_id, prompt: Optional[str] = None) -> Optional[TranslationOutput]:
    """Find existing translation output for the same input, model, and prompt"""
    try:
        # Find translation outputs for jobs with the same text, prompt, and model version
        existing_output = db.query(TranslationOutput).join(TranslationJob).filter(
            TranslationJob.source_text == text,
            TranslationJob.prompt == prompt,
            TranslationOutput.model_version_id == model_version_id
        ).order_by(TranslationOutput.created_at.desc()).first()  # Get the most recent one
        
        return existing_output
    except Exception as e:
        logger.warning(f"Error checking for cached translation: {str(e)}")
        return None

def get_or_create_model_version(db: Session, version: str) -> ModelVersion:
    """Get or create a model version in the database"""
    try:
        model_version = db.query(ModelVersion).filter(ModelVersion.version == version).first()
        if not model_version:
            provider = MODEL_PROVIDERS.get(version, "unknown")
            model_version = ModelVersion(version=version, provider=provider)
            db.add(model_version)
            db.commit()
            db.refresh(model_version)
        return model_version
    except Exception as e:
        # If vote_count column doesn't exist, try creating without it
        if "vote_count does not exist" in str(e):
            db.rollback()
            # Try to query without ordering by vote_count
            try:
                from sqlalchemy import text
                result = db.execute(text("SELECT id, version, provider, created_at FROM model_version WHERE version = :version"), {"version": version})
                row = result.fetchone()
                if row:
                    # Create a ModelVersion object manually
                    model_version = ModelVersion()
                    model_version.id = row[0]
                    model_version.version = row[1] 
                    model_version.provider = row[2]
                    model_version.created_at = row[3]
                    return model_version
                else:
                    # Create new model version
                    provider = MODEL_PROVIDERS.get(version, "unknown")
                    result = db.execute(text("INSERT INTO model_version (version, provider) VALUES (:version, :provider) RETURNING id, version, provider, created_at"), 
                                      {"version": version, "provider": provider})
                    row = result.fetchone()
                    db.commit()
                    
                    model_version = ModelVersion()
                    model_version.id = row[0]
                    model_version.version = row[1]
                    model_version.provider = row[2] 
                    model_version.created_at = row[3]
                    return model_version
            except Exception:
                db.rollback()
                # Fallback: try to create ModelVersion without vote_count column
                try:
                    from sqlalchemy import text
                    import uuid
                    
                    # Generate UUID and try to insert directly
                    new_uuid = uuid.uuid4()
                    provider = MODEL_PROVIDERS.get(version, "unknown")
                    
                    # Try to insert into model_version table without vote_count
                    result = db.execute(text("""
                        INSERT INTO model_version (id, version, provider, created_at) 
                        VALUES (:id, :version, :provider, NOW()) 
                        RETURNING id, version, provider, created_at
                    """), {
                        "id": new_uuid,
                        "version": version, 
                        "provider": provider
                    })
                    row = result.fetchone()
                    db.commit()
                    
                    # Create ModelVersion object with the inserted data
                    model_version = ModelVersion()
                    model_version.id = row[0]
                    model_version.version = row[1]
                    model_version.provider = row[2]
                    model_version.created_at = row[3]
                    return model_version
                    
                except Exception:
                    db.rollback()
                    # Last resort: return ModelVersion with special marker for no-DB mode
                    model_version = ModelVersion()
                    model_version.id = None  # Signal that this shouldn't be used for DB operations
                    model_version.version = version
                    model_version.provider = MODEL_PROVIDERS.get(version, "unknown")
                    return model_version
        else:
            db.rollback()
            raise e

async def call_openai_model(model: str, text: str, prompt: Optional[str] = None):
    """Call OpenAI API for translation"""
    if not openai_client:
        yield "Error: OpenAI client not configured"
        return
        
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    if prompt:
        messages.append({"role": "user", "content": f"Translation instruction: {prompt}"})
    messages.append({"role": "user", "content": text})
    
    try:
        stream = openai_client.chat.completions.create(
            model=model,
            messages=messages,
            stream=True,
            max_tokens=2000
        )
        
        for chunk in stream:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
    except Exception as e:
        # Return the actual API error instead of generic message
        yield f"OpenAI API Error: {str(e)}"

async def call_anthropic_model(model: str, text: str, prompt: Optional[str] = None):
    """Call Anthropic API for translation"""
    if not anthropic_client:
        yield "Error: Anthropic client not configured - no API key provided"
        return
        
    user_message = text
    if prompt:
        user_message = f"Translation instruction: {prompt}\n\nText to translate: {text}"
    
    try:
        with anthropic_client.messages.stream(
            model=model,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
            max_tokens=2000
        ) as stream:
            for text_chunk in stream.text_stream:
                yield text_chunk
    except Exception as e:
        # Return the actual API error instead of generic message
        yield f"Anthropic API Error: {str(e)}"

async def call_google_model(model: str, text: str, prompt: Optional[str] = None):
    """Call Google Gemini API for translation"""
    if not google_configured:
        yield "Error: Google Generative AI not configured - no API key provided"
        return
        
    try:
        # Initialize the model
        google_model = genai.GenerativeModel(model)
        
        # Create the full prompt with system instruction
        user_message = f"{SYSTEM_PROMPT}\n\n"
        if prompt:
            user_message += f"Translation instruction: {prompt}\n\nText to translate: {text}"
        else:
            user_message += f"Text to translate: {text}"
        
        # Generate content with streaming
        response = google_model.generate_content(
            user_message,
            stream=True,
            generation_config=genai.types.GenerationConfig(
                max_output_tokens=2000,
                temperature=0.1,  # Low temperature for consistent translations
            )
        )
        
        for chunk in response:
            if chunk.text:
                yield chunk.text
    except Exception as e:
        # Return the actual API error instead of generic message
        yield f"Google API Error: {str(e)}"

async def call_deepseek_model(model: str, text: str, prompt: Optional[str] = None):
    """Call DeepSeek API via Novita AI for translation (OpenAI-compatible)"""
    if not deepseek_client:
        yield "Error: DeepSeek client not configured - no API key provided"
        return
        
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    if prompt:
        messages.append({"role": "user", "content": f"Translation instruction: {prompt}"})
    messages.append({"role": "user", "content": text})
    
    try:
        stream = deepseek_client.chat.completions.create(
            model=model,
            messages=messages,
            stream=True,
            max_tokens=8192,  # Increased for better translation capacity
            temperature=0.1,  # Low temperature for consistent translations
            top_p=1,
            presence_penalty=0,
            frequency_penalty=0,
            response_format={"type": "text"},
            extra_body={
                "top_k": 50,
                "repetition_penalty": 1,
                "min_p": 0
            }
        )
        
        for chunk in stream:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
    except Exception as e:
        # Return the actual API error instead of generic message
        yield f"DeepSeek API Error: {str(e)}"

async def mock_translation_stream(model: str, text: str, prompt: Optional[str] = None):
    """Mock translation stream for demo purposes"""
    # Simulate translation based on model and content
    if "spanish" in text.lower() or (prompt and "spanish" in prompt.lower()):
        mock_translation = f"[{model}] Hola, ¿cómo estás?"
    elif "french" in text.lower() or (prompt and "french" in prompt.lower()):
        mock_translation = f"[{model}] Bonjour, comment allez-vous?"
    elif "german" in text.lower() or (prompt and "german" in prompt.lower()):
        mock_translation = f"[{model}] Hallo, wie geht es dir?"
    else:
        mock_translation = f"[{model}] This is a demo translation of: {text}"
    
    # Stream character by character to simulate real AI streaming
    for char in mock_translation:
        await asyncio.sleep(0.03)  # Simulate streaming delay
        yield char

async def stream_translation(model: str, text: str, prompt: Optional[str] = None):
    """Stream translation from the specified model - returns errors if not configured"""
    provider = MODEL_PROVIDERS.get(model, "unknown")
    
    # Try real AI - return actual API errors
    if provider == "openai":
        if openai_client:
            async for chunk in call_openai_model(model, text, prompt):
                yield chunk
      
    elif provider == "anthropic":
        if anthropic_client:
            async for chunk in call_anthropic_model(model, text, prompt):
                yield chunk
      
    elif provider == "google":
        if google_configured:
            async for chunk in call_google_model(model, text, prompt):
                yield chunk
    
    elif provider == "deepseek-v3":
        if deepseek_client:
            async for chunk in call_deepseek_model(model, text, prompt):
                yield chunk
      
    else:
        yield f"Configuration Error: Unknown model provider '{provider}' for model '{model}'. Supported providers: openai, anthropic, google, deepseek-v3"

@router.post("/stream")
async def translate_text(
    model: str = Query(..., description="Model version to use for translation"),
    request: TranslationRequest = Body(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Translate text using the specified model with streaming response.
    For multi-model translation, use model=multi and provide models in request body.
    
    Returns errors if AI clients are not configured.
    """
    
    # Log credential status when endpoint is triggered
    logger.info(f"Translation endpoint triggered for model: {model}")
    logger.info("Credential status check:")
    logger.info(f"  OPENAI_API_KEY exists: {'OPENAI_API_KEY' in os.environ}")
    logger.info(f"  GOOGLE_API_KEY exists: {'GOOGLE_API_KEY' in os.environ}")
    logger.info(f"  ANTHROPIC_API_KEY exists: {'ANTHROPIC_API_KEY' in os.environ}")
    logger.info(f"  DEEPSEEK_API_KEY (Novita AI) exists: {'DEEPSEEK_API_KEY' in os.environ}")
    
    if os.getenv("OPENAI_API_KEY"):
        logger.info(f"  OPENAI_API_KEY: {os.getenv('OPENAI_API_KEY')[:10]}...")
    else:
        logger.info("  OPENAI_API_KEY: Not found")
        
    if os.getenv("GOOGLE_API_KEY"):
        logger.info(f"  GOOGLE_API_KEY: {os.getenv('GOOGLE_API_KEY')[:10]}...")
    else:
        logger.info("  GOOGLE_API_KEY: Not found")
        
    if os.getenv("ANTHROPIC_API_KEY"):
        logger.info(f"  ANTHROPIC_API_KEY: {os.getenv('ANTHROPIC_API_KEY')[:10]}...")
    else:
        logger.info("  ANTHROPIC_API_KEY: Not found")
        
    if os.getenv("DEEPSEEK_API_KEY"):
        logger.info(f"  DEEPSEEK_API_KEY (Novita AI): {os.getenv('DEEPSEEK_API_KEY')[:10]}...")
    else:
        logger.info("  DEEPSEEK_API_KEY (Novita AI): Not found")
    
    logger.info("Client initialization status:")
    logger.info(f"  openai_client: {openai_client is not None}")
    logger.info(f"  anthropic_client: {anthropic_client is not None}")
    logger.info(f"  google_configured: {google_configured}")
    logger.info(f"  deepseek_client (Novita AI): {deepseek_client is not None}")
    
    if model == "multi":
        # Handle multi-model translation with random model selection
        import random
        available_models = list(MODEL_PROVIDERS.keys())
        
        if len(available_models) >= 2:
            # Randomly select 2 different models for comparison
            selected_models = random.sample(available_models, 2)
        else:
            # Fallback if insufficient models
            selected_models = ["claude-3-5-sonnet-20241022", "gemini-1.5-pro"]
        
        multi_request = MultiTranslationRequest(**request.dict(), models=selected_models)
        return translate_multi_model(multi_request, db, current_user)
    
    # Validate model
    print(model)
    print(MODEL_PROVIDERS)
    if model not in MODEL_PROVIDERS:
        raise HTTPException(
            status_code=400, 
            detail=f"Unsupported model: {model}. Supported models: {list(MODEL_PROVIDERS.keys())}"
        )
    
    # Create translation job
    job = TranslationJob(
        source_text=request.text,
        prompt=request.prompt,
        user_id=current_user.id
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    
    # Get or create model version
    model_version = get_or_create_model_version(db, model)
    
    # Store IDs to avoid session issues in async generator
    job_id = job.id
    model_version_id = model_version.id
    
    # Safety check: ensure we have valid IDs that exist in database
    if model_version_id is None:
        # ModelVersion couldn't be saved to database, so skip TranslationOutput creation
        # This prevents foreign key constraint violations
        model_version_id = "skip_db_operations"  # Special marker
    
    # Check for cached translation before making API call
    cached_output = None
    if model_version_id != "skip_db_operations":
        cached_output = find_cached_translation(db, request.text, model_version_id, request.prompt)
        
    if cached_output:
        logger.info(f"Found cached translation for model {model}, returning cached result")
        
        # Return cached result as streaming response
        async def generate_cached_stream():
            cached_text = cached_output.streamed_text
            
            # Stream the cached text character by character to simulate real streaming
            for char in cached_text:
                yield f"{json.dumps({'chunk': char, 'model': model, 'cached': True})}\n"
                await asyncio.sleep(0.01)  # Small delay to simulate streaming
            
            # Send completion event with existing output ID
            yield f"{json.dumps({'complete': True, 'output_id': str(cached_output.id), 'model': model, 'cached': True})}\n"
        
        return EventSourceResponse(generate_cached_stream())
    
    async def generate_stream():
        full_text = ""
        has_error = False
        error_message = None
        
        try:
            async for chunk in stream_translation(model, request.text, request.prompt):
                full_text += chunk
                
                # Check if this chunk is an error message
                if chunk.startswith("OpenAI API Error:") or chunk.startswith("Anthropic API Error:") or chunk.startswith("Google API Error:") or chunk.startswith("DeepSeek API Error:") or chunk.startswith("Configuration Error:"):
                    has_error = True
                    error_message = chunk
                    # Send error in structured format
                    yield f"{json.dumps({'error': chunk, 'model': model, 'error_type': 'api_error'})}\n"
                else:
                    # Send normal chunk
                    yield f"{json.dumps({'chunk': chunk, 'model': model})}\n"
            
            # Only proceed with database operations if no error occurred
            if not has_error:
                # Create new database session for the async context
                from database import SessionLocal
                async_db = SessionLocal()
                try:
                    # Check if we can safely create TranslationOutput (valid foreign key)
                    if model_version_id != "skip_db_operations":
                        # Create translation output record
                        output = TranslationOutput(
                            job_id=job_id,
                            model_version_id=model_version_id,
                            streamed_text=full_text
                        )
                        async_db.add(output)
                        async_db.commit()
                        async_db.refresh(output)
                        
                        # Send completion event with output ID
                        yield f"{json.dumps({'complete': True, 'output_id': str(output.id), 'model': model})}\n"
                    else:
                        # Skip database operations due to missing ModelVersion
                        # Send completion event without output ID
                        yield f"{json.dumps({'complete': True, 'model': model, 'note': 'Translation completed but not saved to database'})}\n"
                finally:
                    async_db.close()
            else:
                # Send error completion event
                yield f"{json.dumps({'complete': True, 'model': model, 'error': error_message, 'success': False})}\n"
            
        except Exception as e:
            yield f"{json.dumps({'error': str(e), 'model': model, 'error_type': 'system_error'})}\n"
    
    return EventSourceResponse(generate_stream())

def translate_multi_model(
    request: MultiTranslationRequest,
    db: Session,
    current_user: User
):
    """Handle multi-model translation with concurrent streaming"""
    
    # Validate models
    for model in request.models:
        if model not in MODEL_PROVIDERS:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported model: {model}. Supported models: {list(MODEL_PROVIDERS.keys())}"
            )
    
    # Create translation job
    job = TranslationJob(
        source_text=request.text,
        prompt=request.prompt,
        user_id=current_user.id
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    
    # Get or create model versions and check for cached translations
    model_versions = {}
    model_version_ids = {}
    cached_outputs = {}
    
    for model in request.models:
        model_version = get_or_create_model_version(db, model)
        model_versions[model] = model_version
        
        # Safety check: ensure we have valid IDs that exist in database
        model_version_id = model_version.id
        if model_version_id is None:
            # ModelVersion couldn't be saved to database, so skip TranslationOutput creation
            # This prevents foreign key constraint violations
            model_version_id = "skip_db_operations"  # Special marker
        
        model_version_ids[model] = model_version_id
        
        # Check for cached translation for this model
        if model_version_id != "skip_db_operations":
            cached_output = find_cached_translation(db, request.text, model_version_id, request.prompt)
            if cached_output:
                cached_outputs[model] = cached_output
                logger.info(f"Found cached translation for model {model} in multi-model request")
    
    # Store job ID to avoid session issues
    job_id = job.id
    
    async def generate_multi_stream():
        model_outputs = {}
        completed_models = set()
        
        async def stream_model(model: str, channel: str):
            full_text = ""
            has_error = False
            error_message = None
            
            # Check if we have cached result for this model
            if model in cached_outputs:
                cached_output = cached_outputs[model]
                cached_text = cached_output.streamed_text
                
                # Stream the cached text character by character
                for char in cached_text:
                    yield f"{json.dumps({'chunk': char, 'model': model, 'channel': channel, 'cached': True})}\n"
                    await asyncio.sleep(0.01)  # Small delay to simulate streaming
                
                # Mark as completed and add to outputs
                model_outputs[model] = cached_output.id
                completed_models.add(model)
                
                # Send completion event for cached result
                yield f"{json.dumps({'complete': True, 'output_id': str(cached_output.id), 'model': model, 'channel': channel, 'cached': True})}\n"
                return
            
            try:
                async for chunk in stream_translation(model, request.text, request.prompt):
                    full_text += chunk
                    
                    # Check if this chunk is an error message
                    if chunk.startswith("OpenAI API Error:") or chunk.startswith("Anthropic API Error:") or chunk.startswith("Google API Error:") or chunk.startswith("DeepSeek API Error:") or chunk.startswith("Configuration Error:"):
                        has_error = True
                        error_message = chunk
                        # Send error in structured format
                        yield f"{json.dumps({'error': chunk, 'model': model, 'channel': channel, 'error_type': 'api_error'})}\n"
                    else:
                        # Send normal chunk
                        yield f"{json.dumps({'chunk': chunk, 'model': model, 'channel': channel})}\n"
                
                # Only proceed with database operations if no error occurred
                if not has_error:
                    # Create new database session for the async context
                    from database import SessionLocal
                    async_db = SessionLocal()
                    try:
                        # Check if we can safely create TranslationOutput (valid foreign key)
                        if model_version_ids[model] != "skip_db_operations":
                            # Create translation output record
                            output = TranslationOutput(
                                job_id=job_id,
                                model_version_id=model_version_ids[model],
                                streamed_text=full_text
                            )
                            async_db.add(output)
                            async_db.commit()
                            async_db.refresh(output)
                            
                            model_outputs[model] = output.id
                            completed_models.add(model)
                            
                            # Send completion event
                            yield f"{json.dumps({'complete': True, 'output_id': str(output.id), 'model': model, 'channel': channel})}\n"
                        else:
                            # Skip database operations due to missing ModelVersion
                            completed_models.add(model)
                            
                            # Send completion event without output ID
                            yield f"{json.dumps({'complete': True, 'model': model, 'channel': channel, 'note': 'Translation completed but not saved to database'})}\n"
                    finally:
                        async_db.close()
                else:
                    # Mark as completed with error
                    completed_models.add(model)
                    
                    # Send error completion event
                    yield f"{json.dumps({'complete': True, 'model': model, 'channel': channel, 'error': error_message, 'success': False})}\n"
                
            except Exception as e:
                # Mark as completed with system error
                completed_models.add(model)
                yield f"{json.dumps({'error': str(e), 'model': model, 'channel': channel, 'error_type': 'system_error'})}\n"
        
        # Create concurrent streams for both models
        model_a, model_b = request.models[0], request.models[1]
        
        try:
            # Alternative: Simple interleaved approach for demo
            # Note: For true concurrency, could use asyncio.create_task() here
            generators = {
                "A": stream_model(model_a, "A"),
                "B": stream_model(model_b, "B")
            }
            
            active_generators = list(generators.keys())
            
            while active_generators:
                for channel in active_generators[:]:
                    try:
                        chunk = await generators[channel].__anext__()
                        yield chunk
                    except StopAsyncIteration:
                        active_generators.remove(channel)
                    except Exception as e:
                        yield f"{json.dumps({'error': str(e), 'channel': channel})}\n"
                        active_generators.remove(channel)
                    
                    await asyncio.sleep(0.01)  # Small delay between chunks
                    
        except Exception as e:
            yield f"{json.dumps({'error': str(e)})}\n"
    
    return EventSourceResponse(generate_multi_stream())

# 5-star rating vote endpoint  
from pydantic import BaseModel, Field
from typing import List

class ModelVoteRequest(BaseModel):
    model_versions: List[str] = Field(..., description="List of model version names to vote for (e.g., ['gpt-4o-mini', 'claude-3-5-sonnet-20241022'])")
    translation_output_id: str = Field(..., description="Required translation output ID to associate the vote with")

class ModelVoteResponseEntry(BaseModel):
    message: str
    model_version: str
    user_score: int
    average_score: float
    total_votes: int
    score_percentage: float

class ModelVoteResponse(BaseModel):
    results: List[ModelVoteResponseEntry]

@router.post("/vote", response_model=ModelVoteResponse)
def vote_for_models(
    vote_request: ModelVoteRequest = Body(..., description="Vote for one or more model versions (score is always 5)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Submit a 5-star rating for one or more model versions.
    Each user can only vote once per translation output.
    
    Note: translation_output_id is required and must be a valid UUID of an existing translation output.
    """
    # Validate translation_output_id format first
    try:
        from uuid import UUID
        output_uuid = UUID(vote_request.translation_output_id)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid translation_output_id format: {vote_request.translation_output_id}. Must be a valid UUID."
        )
    
    # Validate that translation_output_id exists in database
    existing_output = db.query(TranslationOutput).filter(TranslationOutput.id == output_uuid).first()
    if not existing_output:
        raise HTTPException(
            status_code=404,
            detail=f"Translation output with ID {vote_request.translation_output_id} not found."
        )
    
    # Check if user has already voted for this translation output
    existing_vote = db.query(Vote).filter(
        Vote.user_id == current_user.id,
        Vote.translation_output_id == output_uuid
    ).first()
    if existing_vote:
        raise HTTPException(
            status_code=409,  # Conflict
            detail=f"User has already voted for translation output {vote_request.translation_output_id}. Only one vote per translation output is allowed."
        )
    
    results = []
    for model_version_name in vote_request.model_versions:
        # Get or create model version
        model_version = get_or_create_model_version(db, model_version_name)
        
        if model_version.id is None:
            raise HTTPException(
                status_code=500,
                detail=f"Database schema error: Unable to create or retrieve model version '{model_version_name}'"
            )

        # Create new vote (allow multiple votes per user per model)
        new_vote = Vote(
            user_id=current_user.id,
            model_version_id=model_version.id,
            translation_output_id=output_uuid,
            score=5
        )
        
        try:
            db.add(new_vote)
            db.commit()
            db.refresh(new_vote)
        except Exception as e:
            db.rollback()
            # Check if this is a unique constraint violation for duplicate vote
            if "unique_user_translation_vote" in str(e).lower():
                raise HTTPException(
                    status_code=409,
                    detail="User has already voted for this translation output. Only one vote per translation output is allowed."
                )
            else:
                raise HTTPException(
                    status_code=500,
                    detail=f"Database error while recording vote for model '{model_version_name}': {str(e)}"
                )
        
        # Calculate updated statistics
        try:
            from sqlalchemy import func
            stats = db.query(
                func.avg(Vote.score).label('avg_score'),
                func.count(Vote.id).label('total_votes')
            ).filter(Vote.model_version_id == model_version.id).first()
            
            average_score = float(stats.avg_score) if stats.avg_score else 5.0
            total_votes = int(stats.total_votes) if stats.total_votes else 1
            score_percentage = (average_score / 5.0) * 100.0
            
            results.append(ModelVoteResponseEntry(
                message="Vote recorded successfully",
                model_version=model_version.version,
                user_score=5,
                average_score=round(average_score, 2),
                total_votes=total_votes,
                score_percentage=round(score_percentage, 1)
            ))
        except Exception as e:
            # If stats calculation fails, still consider the vote successful
            # but throw error to be consistent with user's request
            raise HTTPException(
                status_code=500,
                detail=f"Vote recorded but statistics calculation failed for model '{model_version_name}': {str(e)}"
            )
            
    return ModelVoteResponse(results=results)

# Leaderboard endpoint with 5-star rating percentages
@router.get("/score", response_model=LeaderboardResponse)
def get_leaderboard(db: Session = Depends(get_db)):
    """
    Get leaderboard showing model performance with 5-star ratings and percentages
    """
    try:
        # Get all model versions with their vote statistics
        from sqlalchemy import func
        
        # Query to get average scores and vote counts for each model
        stats_query = db.query(
            ModelVersion.id,
            ModelVersion.version,
            ModelVersion.provider,
            func.avg(Vote.score).label('avg_score'),
            func.count(Vote.id).label('total_votes'),
            func.count(case((Vote.score == 1, 1))).label('score_1'),
            func.count(case((Vote.score == 2, 1))).label('score_2'),
            func.count(case((Vote.score == 3, 1))).label('score_3'),
            func.count(case((Vote.score == 4, 1))).label('score_4'),
            func.count(case((Vote.score == 5, 1))).label('score_5')
        ).outerjoin(Vote, ModelVersion.id == Vote.model_version_id) \
         .group_by(ModelVersion.id, ModelVersion.version, ModelVersion.provider) \
         .order_by(func.avg(Vote.score).desc().nullslast()) \
         .all()
        
        leaderboard = []
        for stat in stats_query:
            avg_score = float(stat.avg_score) if stat.avg_score else 0.0
            total_votes = int(stat.total_votes) if stat.total_votes else 0
            score_percentage = (avg_score / 5.0) * 100.0 if avg_score > 0 else 0.0
            
            # Create score breakdown
            score_breakdown = {
                1: int(stat.score_1) if stat.score_1 else 0,
                2: int(stat.score_2) if stat.score_2 else 0,
                3: int(stat.score_3) if stat.score_3 else 0,
                4: int(stat.score_4) if stat.score_4 else 0,
                5: int(stat.score_5) if stat.score_5 else 0
            }
            
            leaderboard.append(LeaderboardEntry(
                model_version=stat.version,
                provider=stat.provider,
                total_votes=total_votes,
                average_score=round(avg_score, 2),
                score_percentage=round(score_percentage, 1),
                score_breakdown=score_breakdown
            ))
        
        return LeaderboardResponse(leaderboard=leaderboard)
        
    except Exception:
        # Fallback: try to get models without vote data
        try:
            model_versions = db.query(ModelVersion).all()
            
            leaderboard = []
            for model_version in model_versions:
                leaderboard.append(LeaderboardEntry(
                    model_version=model_version.version,
                    provider=model_version.provider,
                    total_votes=0,
                    average_score=0.0,
                    score_percentage=0.0,
                    score_breakdown={1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
                ))
            
            return LeaderboardResponse(leaderboard=leaderboard)
            
        except Exception:
            # Ultimate fallback: empty leaderboard
            return LeaderboardResponse(leaderboard=[])

@router.get("/suggest_model", response_model=ModelSuggestionResponse)
def suggest_model_pair():
    """
    Suggest two random models for comparison from all possible combinations.
    Uses only MODEL_PROVIDERS and randomly selects from all possible pairs.
    """
    import itertools
    import random
    
    # Get available models from MODEL_PROVIDERS only
    available_models = list(MODEL_PROVIDERS.keys())
    
    if len(available_models) < 2:
        # Fallback if insufficient models
        return {
            "model_a": "claude-3-5-sonnet-20241022",
            "model_b": "gemini-1.5-pro",
            "selection_method": "fallback",
            "note": "Insufficient models in MODEL_PROVIDERS"
        }
    
    # Generate all possible combinations (A,B) and (B,A) to ensure fairness
    all_combinations = []
    for combo in itertools.combinations(available_models, 2):
        # Add both (A,B) and (B,A) to ensure every model can be in either position
        all_combinations.append((combo[0], combo[1]))
        all_combinations.append((combo[1], combo[0]))
    
    # Randomly select one combination from all possibilities
    selected_combination = random.choice(all_combinations)
    
    return {
        "model_a": selected_combination[0],
        "model_b": selected_combination[1],
        "selection_method": "random",
        "total_combinations": len(all_combinations),
        "note": f"Randomly selected from {len(all_combinations)} possible combinations"
    }

@router.get("/status")
def get_system_status():
    """
    Get the current status of AI integrations
    """
    return {
        "openai_available": OPENAI_AVAILABLE and openai_client is not None,
        "anthropic_available": ANTHROPIC_AVAILABLE and anthropic_client is not None,
        "google_available": GOOGLE_AVAILABLE and os.getenv("GOOGLE_API_KEY") is not None,
        "deepseek_available": OPENAI_AVAILABLE and deepseek_client is not None,
        "supported_models": list(MODEL_PROVIDERS.keys()),
        "mode": "production" if any([
            OPENAI_AVAILABLE and openai_client,
            ANTHROPIC_AVAILABLE and anthropic_client,
            GOOGLE_AVAILABLE and os.getenv("GOOGLE_API_KEY"),
            OPENAI_AVAILABLE and deepseek_client
        ]) else "demo"
    }