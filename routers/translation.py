from fastapi import APIRouter, HTTPException, Depends, Query, Path, Body, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, case
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from database import get_db, get_redis
from auth import get_current_active_user
from models.user import User
from models.translation import ModelVersion, TranslationJob, TranslationOutput, Vote
from schemas.translation import (
    TranslationRequest, MultiTranslationRequest,
    LeaderboardResponse, LeaderboardEntry, ModelVersionRead,
    TranslationJobRead, TranslationOutputRead, ModelSuggestionResponse
    # VoteRequest, VoteResponse  # No longer used - replaced with comparison voting
)
import uuid
import json
import datetime
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
    from google import genai
    GOOGLE_AVAILABLE = True
except ImportError:
    GOOGLE_AVAILABLE = False

router = APIRouter(prefix="/translate", tags=["Translation"])

db_dependency = Depends(get_db)

# Constants - System prompt from environment variable
SYSTEM_PROMPT = os.getenv("SYSTEM_PROMPT","Be a helpful assistant")

# Model provider mapping - read from environment variable with fallback to default configuration
def get_model_providers():
    """Get model providers from environment variable with fallback to default configuration"""
    default_providers = {"deepseek/deepseek-v3.1": "deepseek-v3",
                         "claude-3-5-sonnet-20241022": "anthropic",
                         "claude-3-5-haiku-20241022": "anthropic",
                         "claude-3-opus-20240229": "anthropic",
                         "claude-sonnet-4-20250514": "anthropic",
                         "claude-3-7-sonnet-latest": "anthropic",
                         "claude-3-7-sonnet-latest-thinking": "anthropic",
                         "gemini-2.5-pro-thinking": "google",
                         "gemini-2.5-flash": "google",
                         "gemini-2.0-flash": "google",
                         "gemini-2.5-flash-thinking": "google"}
    
    model_providers_env = os.getenv("MODEL_PROVIDERS")
    if model_providers_env:
        try:
            return json.loads(model_providers_env)
        except json.JSONDecodeError:
            return default_providers
    else:
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
    client = genai.Client(
        api_key=os.environ.get("GEMINI_API_KEY"),
    )
    # genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
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
            if chunk.choices[0].delta.content is not None:
                content = chunk.choices[0].delta.content
                if content:  # Also check for empty strings
                    yield content
    except Exception as e:
        # Return the actual API error instead of generic message
        yield f"OpenAI API Error: {str(e)}"

async def call_anthropic_model(model: str, text: str, prompt: Optional[str] = None):
    """Call Anthropic API for translation"""
    if not anthropic_client:
        yield "Error: Anthropic client not configured - no API key provided"
        return
       
    is_thinking_model = "thinking" in model.lower()
    model = model.replace("-thinking", "")
    try:
        with anthropic_client.messages.stream(
            model=model,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": text}],
            max_tokens=4000,
            thinking= {
                "type": "enabled",
                "budget_tokens": 2000
            } if is_thinking_model else {"type":"disabled"}
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
    model = model.replace("-thinking", "")
    try:
        # Initialize the model
        client = genai.Client(
            api_key=os.environ.get("GEMINI_API_KEY"),
        )

        content = [
            genai.types.Content(
                role="user",
                parts=[
                    genai.types.Part.from_text(text=text),
                ],
            ),
        ]

      
        # Set thinking_budget based on whether "-thinking" is in the model name
        thinking_budget = -1 if "-thinking" in model else 0
        generate_content_config = genai.types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                thinking_config=genai.types.ThinkingConfig(
                    thinking_budget=thinking_budget,
                ),
            )

        for chunk in client.models.generate_content_stream(
            model=model,
            contents=content,
            config=generate_content_config,
        ):
            if chunk.text is not None and chunk.text:  # Check for None and empty
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
        messages.append({"role": "user", "content": prompt})
    messages.append({"role": "user", "content": text})
    
    print(f"DeepSeek API call - Original model: {model}")
    
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
            # Defensive: check chunk.choices exists and is non-empty
            if hasattr(chunk, "choices") and chunk.choices and len(chunk.choices) > 0:
                # Defensive: check .delta and .content exist
                delta = getattr(chunk.choices[0], "delta", "")
                print(delta)
                if delta and hasattr(delta, "content"):
                    content = delta.content
                    if content is not None and content:  # More explicit check
                        yield content
              
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
    provider = MODEL_PROVIDERS.get(model, "unknown")
    
    # Debug logging for model and provider detection
    print(f"Stream translation - Model: {model}, Provider: {provider}")
    print(f"Available MODEL_PROVIDERS: {MODEL_PROVIDERS}")
    
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
            try:
                async for chunk in call_google_model(model, text, prompt):
                    yield chunk
            except Exception as e:
                # Retry once if there is an error
                try:
                    async for chunk in call_google_model(model, text, prompt):
                        yield chunk
                except Exception as e2:
                    yield f"Google API Error: {str(e2)}"
    
    elif provider == "deepseek-v3":
        if deepseek_client:
            try:
                async for chunk in call_deepseek_model(model, text, prompt):
                    yield chunk
            except Exception as e:
                yield f"DeepSeek API Error: {str(e)}"
        else:
            yield "Error: DeepSeek client not configured - no API key provided"
      
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
    if model not in MODEL_PROVIDERS:
        raise HTTPException(
            status_code=400, 
            detail=f"Unsupported model: {model}. Supported models: {list(MODEL_PROVIDERS.keys())}"
        )
    
    # Create translation job
    job = TranslationJob(
        source_text=request.text,
        prompt=request.prompt,
        template=request.template,
        target_language=request.target_language,
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
        template=request.template,
        target_language=request.target_language,
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

@router.post("/dual-stream")
async def translate_dual_models(
    request: MultiTranslationRequest = Body(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Translate text using exactly two specified models with streaming response.
    This endpoint ensures both models use the same job ID for proper session tracking.
    """
    
    
    # Validate exactly 2 models
    if len(request.models) != 2:
        raise HTTPException(
            status_code=400,
            detail="Exactly 2 models must be specified for dual comparison"
        )
    
    # Validate models exist
    for model in request.models:
        if model not in MODEL_PROVIDERS:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported model: {model}. Supported models: {list(MODEL_PROVIDERS.keys())}"
            )
    
    return translate_multi_model(request, db, current_user)

# Comparison voting endpoint  
from pydantic import BaseModel, Field
from typing import List, Optional

class ComparisonVoteRequest(BaseModel):
    translation_output1_id: str = Field(..., description="First translation output ID for comparison")
    translation_output2_id: str = Field(..., description="Second translation output ID for comparison")
    winner_choice: str = Field(..., description="Winner choice: 'output1', 'output2', 'tie', or 'neither'")
    response_time_ms: Optional[int] = Field(None, description="Time taken to make decision in milliseconds")
    comment: Optional[str] = Field(None, description="Optional user comment about the vote decision")

class ComparisonVoteResponse(BaseModel):
    message: str
    vote_id: str
    translation_output_a_id: str
    translation_output_b_id: str
    winner_id: Optional[str]
    is_tie: int
    translation_job_id: str

@router.post("/vote", response_model=ComparisonVoteResponse)
def submit_comparison_vote(
    vote_request: ComparisonVoteRequest = Body(..., description="Submit a comparison vote between two translation outputs"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    redis_client = Depends(get_redis)
):
    """
    Submit a comparison vote between two translation outputs using the improved analytics schema.
    Users compare two translations and select a winner, tie, or neither.
    Each user can only vote once per normalized comparison pair.
    """
    # Validate UUID formats
    try:
        from uuid import UUID
        output1_uuid = UUID(vote_request.translation_output1_id)
        output2_uuid = UUID(vote_request.translation_output2_id)
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid UUID format: {str(e)}"
        )
    
    # Ensure the two translation outputs are different
    if output1_uuid == output2_uuid:
        raise HTTPException(
            status_code=400,
            detail="translation_output1_id and translation_output2_id must be different"
        )
    
    # Validate winner_choice
    valid_choices = ["output1", "output2", "tie", "neither"]
    if vote_request.winner_choice not in valid_choices:
        raise HTTPException(
            status_code=400,
            detail=f"winner_choice must be one of: {valid_choices}"
        )
    
    # Validate that both translation outputs exist and get their job context
    output1 = db.query(TranslationOutput).filter(TranslationOutput.id == output1_uuid).first()
    output2 = db.query(TranslationOutput).filter(TranslationOutput.id == output2_uuid).first()
    
    if not output1:
        raise HTTPException(
            status_code=404,
            detail=f"Translation output with ID {vote_request.translation_output1_id} not found"
        )
    if not output2:
        raise HTTPException(
            status_code=404,
            detail=f"Translation output with ID {vote_request.translation_output2_id} not found"
        )
    
    # Check if outputs are from the same job OR have the same source text
    print(f"Output job IDs: {output1.job_id} vs {output2.job_id}")
    
    # Get the jobs to check source text
    job1 = db.query(TranslationJob).filter(TranslationJob.id == output1.job_id).first()
    job2 = db.query(TranslationJob).filter(TranslationJob.id == output2.job_id).first()
    
    if not job1 or not job2:
        raise HTTPException(
            status_code=404,
            detail="One or both translation jobs not found"
        )
    
    # Allow comparison if same job OR same source text (for cross-session comparisons)
    if output1.job_id != output2.job_id and job1.source_text != job2.source_text:
        raise HTTPException(
            status_code=400,
            detail="Translation outputs must be from the same translation job or have the same source text for valid comparison"
        )
    
    print(f"Source texts match: {job1.source_text == job2.source_text}")
    print(f"Job1 source text: {job1.source_text[:50]}...")
    print(f"Job2 source text: {job2.source_text[:50]}...")
    
    # Determine which job ID to use for the vote record
    # If same job, use that job ID. If different jobs with same source text, use the more recent job
    if output1.job_id == output2.job_id:
        vote_job_id = output1.job_id
    else:
        # Use the job with the later created_at timestamp (more recent)
        vote_job_id = job1.id if job1.created_at >= job2.created_at else job2.id
        print(f"Cross-job comparison: Using job {vote_job_id} (more recent) for vote record")
    
    # Normalize UUID ordering for consistent storage (A < B lexicographically)
    if output1_uuid < output2_uuid:
        output_a_uuid, output_b_uuid = output1_uuid, output2_uuid
        winner_mapping = {"output1": output1_uuid, "output2": output2_uuid}
    else:
        output_a_uuid, output_b_uuid = output2_uuid, output1_uuid  
        winner_mapping = {"output1": output1_uuid, "output2": output2_uuid}
    
    # Determine winner and tie status
    winner_id = None
    is_tie = 0  # Default: clear winner
    
    if vote_request.winner_choice == "output1":
        winner_id = winner_mapping["output1"]
        is_tie = 0
    elif vote_request.winner_choice == "output2":
        winner_id = winner_mapping["output2"] 
        is_tie = 0
    elif vote_request.winner_choice == "tie":
        winner_id = None
        is_tie = 1
    elif vote_request.winner_choice == "neither":
        winner_id = None
        is_tie = 2
    
    # Check if user has already voted for this normalized comparison pair
    existing_vote = db.query(Vote).filter(
        Vote.user_id == current_user.id,
        Vote.translation_output_a_id == output_a_uuid,
        Vote.translation_output_b_id == output_b_uuid
    ).first()
    
    if existing_vote:
        # Update the existing vote instead of creating a new one
        existing_vote.winner_id = winner_id
        existing_vote.is_tie = is_tie
        existing_vote.response_time_ms = vote_request.response_time_ms
        existing_vote.comment = vote_request.comment
        existing_vote.updated_at = datetime.datetime.now(datetime.timezone.utc)
        
        try:
            db.commit()
            db.refresh(existing_vote)
        except Exception as e:
            db.rollback()
            raise HTTPException(
                status_code=500,
                detail=f"Database error while updating vote: {str(e)}"
            )
        
        # Invalidate relevant caches when a vote is updated
        if redis_client:
            from redis_client import CacheKeys
            # Clear arena scores cache (they depend on vote results)
            redis_client.delete_cache(CacheKeys.arena_score())
            # Clear leaderboard cache
            redis_client.delete_cache(CacheKeys.leaderboard())
            # Clear user vote leaderboard cache  
            redis_client.delete_cache(CacheKeys.user_vote_leaderboard())
            # Clear vote statistics cache
            redis_client.delete_cache(CacheKeys.vote_stats())
            # Clear model scores cache
            redis_client.delete_cache(CacheKeys.model_scores())
            # Clear model vote leaderboard cache
            redis_client.delete_cache(CacheKeys.model_vote_leaderboard())
        
        return ComparisonVoteResponse(
            message="Vote updated successfully",
            vote_id=str(existing_vote.id),
            translation_output_a_id=str(output_a_uuid),
            translation_output_b_id=str(output_b_uuid),
            winner_id=str(winner_id) if winner_id else None,
            is_tie=is_tie,
            translation_job_id=str(vote_job_id)
        )
    
    # Create new comparison vote with improved schema
    new_vote = Vote(
        user_id=current_user.id,
        translation_job_id=vote_job_id,  # Use determined job ID (may be different for cross-job comparisons)
        translation_output_a_id=output_a_uuid,
        translation_output_b_id=output_b_uuid,
        winner_id=winner_id,
        is_tie=is_tie,
        response_time_ms=vote_request.response_time_ms,
        comment=vote_request.comment
    )
    
    try:
        db.add(new_vote)
        db.commit()
        db.refresh(new_vote)
    except Exception as e:
        db.rollback()
        if "unique_user_normalized_comparison" in str(e).lower():
            raise HTTPException(
                status_code=409,
                detail="User has already voted for this comparison."
            )
        else:
            raise HTTPException(
                status_code=500,
                detail=f"Database error while recording vote: {str(e)}"
            )
    
    # Invalidate relevant caches when a new vote is submitted
    if redis_client:
        from redis_client import CacheKeys
        # Clear arena scores cache (they depend on vote results)
        redis_client.delete_cache(CacheKeys.arena_score())
        # Clear leaderboard cache
        redis_client.delete_cache(CacheKeys.leaderboard())
        # Clear user vote leaderboard cache  
        redis_client.delete_cache(CacheKeys.user_vote_leaderboard())
        # Clear vote statistics cache
        redis_client.delete_cache(CacheKeys.vote_stats())
        # Clear model scores cache
        redis_client.delete_cache(CacheKeys.model_scores())
        # Clear model vote leaderboard cache
        redis_client.delete_cache(CacheKeys.model_vote_leaderboard())
    
    return ComparisonVoteResponse(
        message="Comparison vote recorded successfully",
        vote_id=str(new_vote.id),
        translation_output_a_id=str(output_a_uuid),
        translation_output_b_id=str(output_b_uuid),
        winner_id=str(winner_id) if winner_id else None,
        is_tie=is_tie,
        translation_job_id=str(vote_job_id)
    )

# Constants for Redis cache management
REDIS_UNAVAILABLE_MESSAGE = "Redis cache is not available"

# Redis cache management endpoints
@router.post("/cache/reset")
def reset_redis_cache(
    redis_client = Depends(get_redis),
    current_user: User = Depends(get_current_active_user)
):
    """
    Reset/clear all Redis cache entries. Requires authentication.
    This will force fresh data to be loaded from the database for all cached endpoints.
    """
    if not redis_client:
        raise HTTPException(
            status_code=503, 
            detail=REDIS_UNAVAILABLE_MESSAGE
        )
    
    try:
        # Clear all cache
        success = redis_client.clear_all_cache()
        
        if success:
            return {
                "message": "Redis cache cleared successfully",
                "status": "success",
                "cleared_by": current_user.email,
                "timestamp": str(datetime.now(timezone.utc))
            }
        else:
            raise HTTPException(
                status_code=500,
                detail="Failed to clear Redis cache"
            )
            
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error clearing Redis cache: {str(e)}"
        )

@router.get("/cache/info")
def get_cache_info(
    redis_client = Depends(get_redis),
    current_user: User = Depends(get_current_active_user)
):
    """
    Get Redis cache information and statistics. Requires authentication.
    """
    if not redis_client:
        raise HTTPException(
            status_code=503, 
            detail=REDIS_UNAVAILABLE_MESSAGE
        )
    
    try:
        cache_info = redis_client.get_cache_info()
        return {
            "cache_info": cache_info,
            "requested_by": current_user.email,
            "timestamp": str(datetime.now(timezone.utc))
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error getting cache info: {str(e)}"
        )

@router.delete("/cache/pattern/{pattern}")
def clear_cache_pattern(
    pattern: str,
    redis_client = Depends(get_redis),
    current_user: User = Depends(get_current_active_user)
):
    """
    Clear cache entries matching a specific pattern. Requires authentication.
    
    Examples:
    - arena:* - Clear all arena-related cache
    - leaderboard:* - Clear all leaderboard cache  
    - stats:* - Clear all statistics cache
    """
    if not redis_client:
        raise HTTPException(
            status_code=503, 
            detail=REDIS_UNAVAILABLE_MESSAGE
        )
    
    try:
        # Validate pattern to prevent dangerous operations
        allowed_patterns = ['arena:*', 'leaderboard:*', 'stats:*', 'scores:*']
        if pattern not in allowed_patterns:
            raise HTTPException(
                status_code=400,
                detail=f"Pattern '{pattern}' not allowed. Allowed patterns: {allowed_patterns}"
            )
        
        deleted_count = redis_client.clear_pattern_cache(pattern)
        
        return {
            "message": f"Cleared {deleted_count} cache entries matching pattern '{pattern}'",
            "pattern": pattern,
            "deleted_count": deleted_count,
            "cleared_by": current_user.email,
            "timestamp": str(datetime.now(timezone.utc))
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error clearing cache pattern: {str(e)}"
        )

# Statistics endpoint for improved comparison voting
@router.get("/vote-stats")
def get_vote_statistics(
    db: Session = Depends(get_db),
    redis_client = Depends(get_redis)
):
    """
    Get voting statistics for the improved comparison voting system.
    Shows win rates, tie rates, and model performance analytics.
    Cached in Redis for 1 day.
    """
    # Try to get from cache first
    if redis_client:
        from redis_client import CacheKeys, CacheExpiry
        cache_key = CacheKeys.vote_stats()
        cached_result = redis_client.get_cache(cache_key)
        if cached_result:
            return cached_result
    
    try:
        from sqlalchemy import func, case
        
        # Get win statistics for each translation output
        win_stats = db.query(
            Vote.winner_id.label('winner_id'),
            func.count(Vote.id).label('wins')
        ).filter(
            Vote.is_tie == 0  # Only count clear wins
        ).group_by(Vote.winner_id).all()
        
        # Get total comparisons each output was involved in
        from sqlalchemy import text
        involvement_stats = db.execute(text("""
            SELECT 
                output_id,
                COUNT(*) as total_comparisons
            FROM (
                SELECT translation_output_a_id as output_id FROM vote
                UNION ALL
                SELECT translation_output_b_id as output_id FROM vote
            ) as all_outputs
            GROUP BY output_id
        """)).fetchall()
        
        # Combine win and involvement data
        stats_with_details = []
        involvement_dict = {str(stat.output_id): stat.total_comparisons for stat in involvement_stats}
        
        for win_stat in win_stats:
            if win_stat.winner_id:
                output = db.query(TranslationOutput).filter(
                    TranslationOutput.id == win_stat.winner_id
                ).first()
                
                if output:
                    model_version = db.query(ModelVersion).filter(
                        ModelVersion.id == output.model_version_id
                    ).first()
                    
                    total_comparisons = involvement_dict.get(str(win_stat.winner_id), 0)
                    win_rate = (win_stat.wins / total_comparisons * 100) if total_comparisons > 0 else 0
                    
                    stats_with_details.append({
                        "translation_output_id": str(win_stat.winner_id),
                        "wins": win_stat.wins,
                        "total_comparisons": total_comparisons,
                        "win_rate_percentage": round(win_rate, 2),
                        "model_version": model_version.version if model_version else "Unknown",
                        "provider": model_version.provider if model_version else "Unknown"
                    })
        
        # Sort by win rate descending
        stats_with_details.sort(key=lambda x: x["win_rate_percentage"], reverse=True)
        
        # Get overall statistics
        total_votes = db.query(Vote).count()
        total_wins = db.query(Vote).filter(Vote.is_tie == 0).count()
        total_ties = db.query(Vote).filter(Vote.is_tie == 1).count()
        total_neither = db.query(Vote).filter(Vote.is_tie == 2).count()
        
        # Get average response time
        avg_response_time = db.query(func.avg(Vote.response_time_ms)).filter(
            Vote.response_time_ms.isnot(None)
        ).scalar()
        
        result = {
            "total_votes": total_votes,
            "total_clear_wins": total_wins,
            "total_ties": total_ties,
            "total_neither": total_neither,
            "average_response_time_ms": round(avg_response_time, 2) if avg_response_time else None,
            "translation_output_stats": stats_with_details
        }
        
        # Cache the result for vote statistics (1 day)
        if redis_client:
            redis_client.set_cache(cache_key, result, CacheExpiry.LEADERBOARD)
        
        return result
        
    except Exception as e:
        return {
            "total_votes": 0,
            "total_clear_wins": 0,
            "total_ties": 0,
            "total_neither": 0,
            "average_response_time_ms": None,
            "translation_output_stats": [],
            "error": f"Could not retrieve statistics: {str(e)}"
        }

@router.get("/user-vote-leaderboard")
def get_user_vote_leaderboard(
    db: Session = Depends(get_db),
    redis_client = Depends(get_redis)
):
    """
    Get user vote leaderboard showing users ranked by their total vote count in descending order.
    Returns users who have voted the most at the top.
    Cached in Redis for 1 day.
    """
    # Try to get from cache first
    if redis_client:
        from redis_client import CacheKeys, CacheExpiry
        cache_key = CacheKeys.user_vote_leaderboard()
        cached_result = redis_client.get_cache(cache_key)
        if cached_result:
            return cached_result
    
    try:
        from sqlalchemy import func, text
        
        # Query to get user vote statistics
        user_vote_stats = db.execute(text("""
            SELECT 
                u.id as user_id,
                u.username,
                u.first_name,
                u.last_name,
                u.email,
                u.picture,
                COUNT(v.id) as total_votes,
                COUNT(CASE WHEN v.is_tie = 0 AND v.winner_id IS NOT NULL THEN 1 END) as decisive_votes,
                COUNT(CASE WHEN v.is_tie = 1 THEN 1 END) as tie_votes,
                COUNT(CASE WHEN v.is_tie = 2 THEN 1 END) as neither_votes,
                AVG(v.response_time_ms) as avg_response_time_ms,
                MIN(v.created_at) as first_vote_date,
                MAX(v.created_at) as last_vote_date
            FROM "user" u
            JOIN vote v ON u.id = v.user_id
            GROUP BY u.id, u.username, u.first_name, u.last_name, u.email, u.picture
            HAVING COUNT(v.id) > 0
            ORDER BY total_votes DESC, decisive_votes DESC
        """)).fetchall()
        
        leaderboard = []
        for i, stat in enumerate(user_vote_stats, 1):
            leaderboard.append({
                "rank": i,
                "user_id": stat.user_id,
                "username": stat.username,
                "first_name": stat.first_name,
                "last_name": stat.last_name,
                "email": stat.email,
                "picture": stat.picture,
                "total_votes": stat.total_votes,
                "decisive_votes": stat.decisive_votes,
                "tie_votes": stat.tie_votes,
                "neither_votes": stat.neither_votes,
                "average_response_time_ms": round(float(stat.avg_response_time_ms), 2) if stat.avg_response_time_ms else None,
                "first_vote_date": stat.first_vote_date.isoformat() if stat.first_vote_date else None,
                "last_vote_date": stat.last_vote_date.isoformat() if stat.last_vote_date else None
            })
        
        # Get overall statistics
        total_users_with_votes = len(leaderboard)
        total_votes_cast = sum(user["total_votes"] for user in leaderboard)
        
        result = {
            "total_users_with_votes": total_users_with_votes,
            "total_votes_cast": total_votes_cast,
            "leaderboard": leaderboard
        }
        
        # Cache the result for user vote leaderboard (1 day)
        if redis_client:
            redis_client.set_cache(cache_key, result, CacheExpiry.LEADERBOARD)
        
        return result
        
    except Exception as e:
      raise HTTPException(status_code=500, detail=f"Could not retrieve user vote leaderboard: {str(e)}")

@router.get("/model-vote-leaderboard")
def get_model_vote_leaderboard(
    db: Session = Depends(get_db),
    redis_client = Depends(get_redis)
):
    """
    Get model performance leaderboard based on voting results with scores.
    Score calculation: 1 point for clear wins + 0.5 points for ties.
    Results are ordered by score in descending order.
    Cached in Redis for 60 minutes.
    """
    # Try to get from cache first
    if redis_client:
        from redis_client import CacheKeys, CacheExpiry
        cache_key = CacheKeys.model_vote_leaderboard()
        cached_result = redis_client.get_cache(cache_key)
        if cached_result:
            return cached_result
    
    try:
        from sqlalchemy import func, text
        
        # Complex SQL query to calculate model scores
        model_scores = db.execute(text("""
            WITH model_wins AS (
                -- Count clear wins for each model
                SELECT 
                    mv.id as model_version_id,
                    mv.version as model_name,
                    mv.provider as provider,
                    COUNT(v.id) as clear_wins
                FROM model_version mv
                JOIN translation_output trans_out ON mv.id = trans_out.model_version_id
                JOIN vote v ON v.winner_id = trans_out.id AND v.is_tie = 0
                GROUP BY mv.id, mv.version, mv.provider
            ),
            model_ties AS (
                -- Count ties for each model (both output_a and output_b positions)
                SELECT 
                    mv.id as model_version_id,
                    mv.version as model_name,
                    mv.provider as provider,
                    COUNT(v.id) as ties
                FROM model_version mv
                JOIN translation_output trans_out ON mv.id = trans_out.model_version_id
                JOIN vote v ON (v.translation_output_a_id = trans_out.id OR v.translation_output_b_id = trans_out.id) 
                             AND v.is_tie = 1
                GROUP BY mv.id, mv.version, mv.provider
            ),
            model_comparisons AS (
                -- Count total comparisons each model was involved in
                SELECT 
                    mv.id as model_version_id,
                    mv.version as model_name,
                    mv.provider as provider,
                    COUNT(v.id) as total_comparisons
                FROM model_version mv
                JOIN translation_output trans_out ON mv.id = trans_out.model_version_id
                JOIN vote v ON (v.translation_output_a_id = trans_out.id OR v.translation_output_b_id = trans_out.id)
                GROUP BY mv.id, mv.version, mv.provider
            )
            SELECT 
                COALESCE(mw.model_version_id, mt.model_version_id, mc.model_version_id) as model_version_id,
                COALESCE(mw.model_name, mt.model_name, mc.model_name) as model_name,
                COALESCE(mw.provider, mt.provider, mc.provider) as provider,
                COALESCE(mw.clear_wins, 0) as clear_wins,
                COALESCE(mt.ties, 0) as ties,
                COALESCE(mc.total_comparisons, 0) as total_comparisons,
                -- Calculate score: 1 point per win + 0.5 points per tie
                (COALESCE(mw.clear_wins, 0) * 1.0 + COALESCE(mt.ties, 0) * 0.5) as score,
                -- Calculate win rate percentage
                CASE 
                    WHEN COALESCE(mc.total_comparisons, 0) > 0 
                    THEN ROUND((COALESCE(mw.clear_wins, 0) * 100.0) / mc.total_comparisons, 2)
                    ELSE 0.0 
                END as win_rate_percentage
            FROM model_wins mw
            FULL OUTER JOIN model_ties mt ON mw.model_version_id = mt.model_version_id
            FULL OUTER JOIN model_comparisons mc ON COALESCE(mw.model_version_id, mt.model_version_id) = mc.model_version_id
            WHERE COALESCE(mc.total_comparisons, 0) > 0
            ORDER BY score DESC, clear_wins DESC, model_name ASC
        """)).fetchall()
        
        leaderboard = []
        for i, stat in enumerate(model_scores, 1):
            leaderboard.append({
                "rank": i,
                "model_name": stat.model_name,
                "provider": stat.provider,
                "score": float(stat.score),
                "clear_wins": stat.clear_wins,
                "ties": stat.ties,
                "total_comparisons": stat.total_comparisons,
                "win_rate_percentage": float(stat.win_rate_percentage)
            })
        
        # Get overall statistics
        total_votes = db.query(Vote).count()
        total_models_with_data = len(leaderboard)
        total_score = sum(model["score"] for model in leaderboard)
        
        result = {
            "total_votes": total_votes,
            "total_models_with_data": total_models_with_data,
            "total_score": round(total_score, 1),
            "leaderboard": leaderboard
        }
        
        # Cache the result for 60 minutes (arena score expiry)
        if redis_client:
            redis_client.set_cache(cache_key, result, CacheExpiry.ARENA_SCORE)
        
        return result
        
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Could not retrieve model vote leaderboard: {str(e)}"
        )

@router.get("/suggest_model", response_model=ModelSuggestionResponse)
def suggest_model_pair(
    source_text: str = Query(None, description="Source text to check for already used models"),
    db: Session = Depends(get_db)
):
    """
    Suggest two models for comparison, excluding models already used with the same input.
    If source_text is provided, filters out models that have already been used with that text.
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
            "source_text": source_text,
            "note": "Insufficient models in MODEL_PROVIDERS"
        }
    
    # If source_text is provided, filter out models already used with this input
    filtered_models = available_models.copy()
    
    used_models = []
    debug_info = []
    
    if source_text and source_text.strip():
        try:
            source_text_clean = source_text.strip()
            debug_info.append(f"Searching for existing translations with source_text: '{source_text_clean[:50]}...'")
            
            # Query existing translation jobs with the same source text
            existing_jobs = db.query(TranslationJob).filter(
                TranslationJob.source_text == source_text_clean
            ).all()
            
            debug_info.append(f"Found {len(existing_jobs)} existing jobs with this source text")
            
            if existing_jobs:
                # Get all model versions used with this source text using a more direct approach
                used_model_versions = []
                
                for job in existing_jobs:
                    # Get all outputs for this job
                    outputs = db.query(TranslationOutput).filter(
                        TranslationOutput.job_id == job.id
                    ).all()
                    
                    for output in outputs:
                        # Get the model version for each output
                        model_version = db.query(ModelVersion).filter(
                            ModelVersion.id == output.model_version_id
                        ).first()
                        
                        if model_version and model_version not in used_model_versions:
                            used_model_versions.append(model_version)
                
                # Extract the version names (model identifiers)
                used_models = [mv.version for mv in used_model_versions]
                
                # Filter out used models from available models
                filtered_models = [model for model in available_models if model not in used_models]
                
                # Additional check: ensure we're actually excluding the right models
                if used_models:
                    for used_model in used_models:
                        if used_model in available_models:
                            debug_info.append(f"Successfully excluding used model: {used_model}")
                        else:
                            debug_info.append(f"WARNING: Used model '{used_model}' not in available models list")
                            
                # Double-check filtering logic
                should_be_filtered = []
                for model in available_models:
                    if model in used_models:
                        should_be_filtered.append(model)
                        
                debug_info.append(f"Models that should be filtered out: {should_be_filtered}")
                debug_info.append(f"Actual filtered result: {filtered_models}")
                
                # Ensure we have the right logic
                manually_filtered = []
                for model in available_models:
                    if model not in used_models:
                        manually_filtered.append(model)
                        
                if manually_filtered != filtered_models:
                    debug_info.append(f"FILTERING MISMATCH! Manual: {manually_filtered}, Auto: {filtered_models}")
                    filtered_models = manually_filtered  # Use the manual result
                
        except Exception as e:
            # If there's an error querying the database, log it but continue with all models
            debug_info.append(f"Error filtering used models: {e}")
            print(f"Error filtering used models: {e}")
    
    # Use filtered models if we have enough, otherwise fall back to all models
    if len(filtered_models) >= 2:
        models_to_use = filtered_models
        debug_info.append(f"Using {len(filtered_models)} unused models: {filtered_models}")
    elif len(filtered_models) == 1:
        # If we have one unused model, pair it with a random used model
        unused_model = filtered_models[0]
        import random
        used_models_available = [m for m in used_models if m in available_models]
        if used_models_available:
            models_to_use = [unused_model] + [random.choice(used_models_available)]
            debug_info.append(f"Pairing 1 unused model ({unused_model}) with 1 used model ({models_to_use[1]})")
        else:
            models_to_use = available_models
            debug_info.append(f"Only 1 unused model but no used models available, using all models")
    else:
        # No unused models available, fall back to all models
        models_to_use = available_models
        debug_info.append(f"No unused models available, using all {len(available_models)} models")
    
    debug_info.append(f"Final models to use: {models_to_use}")
    
    if len(models_to_use) < 2:
        # If we still don't have enough models, use fallback
        return {
            "model_a": "claude-3-5-sonnet-20241022",
            "model_b": "gemini-1.5-pro",
            "selection_method": "fallback",
            "source_text": source_text,
            "used_models": used_models,
            "note": "Insufficient unused models available"
        }
    
    # Generate all possible combinations (A,B) and (B,A) to ensure fairness
    all_combinations = []
    for combo in itertools.combinations(models_to_use, 2):
        # Add both (A,B) and (B,A) to ensure every model can be in either position
        all_combinations.append((combo[0], combo[1]))
        all_combinations.append((combo[1], combo[0]))
    
    # Randomly select one combination from all possibilities
    selected_combination = random.choice(all_combinations)
    
    # Determine selection method based on what models we're using
    if len(filtered_models) >= 2:
        selection_method = "filtered_random"
    elif len(filtered_models) == 1:
        selection_method = "mixed_unused_used"
    else:
        selection_method = "fallback_all_used"
    note_parts = [f"Selected from {len(all_combinations)} possible combinations"]
    
    if source_text and used_models:
        note_parts.append(f"Excluded {len(used_models)} already used models: {', '.join(used_models)}")
    
    # Add debug information to note for troubleshooting
    if debug_info:
        note_parts.extend(debug_info)
    
    return {
        "model_a": selected_combination[0],
        "model_b": selected_combination[1],
        "selection_method": selection_method,
        "source_text": source_text,
        "used_models": used_models,
        "total_combinations": len(all_combinations),
        "note": " | ".join(note_parts)
    }

@router.get("/debug/vote-comparison")
def debug_vote_comparison(
    output1_id: str = Query(..., description="First translation output ID"),
    output2_id: str = Query(..., description="Second translation output ID"),
    db: Session = Depends(get_db)
):
    """
    Debug endpoint to check if two translation outputs can be compared
    """
    try:
        from uuid import UUID
        
        # Validate UUIDs
        try:
            output1_uuid = UUID(output1_id)
            output2_uuid = UUID(output2_id)
        except ValueError:
            return {"error": "Invalid UUID format"}
        
        # Get outputs
        output1 = db.query(TranslationOutput).filter(TranslationOutput.id == output1_uuid).first()
        output2 = db.query(TranslationOutput).filter(TranslationOutput.id == output2_uuid).first()
        
        if not output1 or not output2:
            return {
                "error": "One or both outputs not found",
                "output1_found": output1 is not None,
                "output2_found": output2 is not None
            }
        
        # Get jobs
        job1 = db.query(TranslationJob).filter(TranslationJob.id == output1.job_id).first()
        job2 = db.query(TranslationJob).filter(TranslationJob.id == output2.job_id).first()
        
        if not job1 or not job2:
            return {
                "error": "One or both jobs not found",
                "job1_found": job1 is not None,
                "job2_found": job2 is not None
            }
        
        # Check comparison validity
        same_job = output1.job_id == output2.job_id
        same_source_text = job1.source_text == job2.source_text
        can_compare = same_job or same_source_text
        
        return {
            "output1_id": output1_id,
            "output2_id": output2_id,
            "output1_job_id": str(output1.job_id),
            "output2_job_id": str(output2.job_id),
            "same_job": same_job,
            "same_source_text": same_source_text,
            "can_compare": can_compare,
            "job1_source_text_preview": job1.source_text[:100] + "..." if len(job1.source_text) > 100 else job1.source_text,
            "job2_source_text_preview": job2.source_text[:100] + "..." if len(job2.source_text) > 100 else job2.source_text,
            "job1_model": str(output1.model_version_id),
            "job2_model": str(output2.model_version_id),
            "validation_result": "Valid for comparison" if can_compare else "Invalid for comparison"
        }
        
    except Exception as e:
        return {
            "error": str(e),
            "output1_id": output1_id,
            "output2_id": output2_id
        }

@router.get("/debug/deepseek-config")
def debug_deepseek_config():
    """
    Debug endpoint to check DeepSeek configuration
    """
    return {
        "deepseek_client_configured": deepseek_client is not None,
        "deepseek_api_key_present": bool(os.getenv("DEEPSEEK_API_KEY")),
        "openai_available": OPENAI_AVAILABLE,
        "model_providers": MODEL_PROVIDERS,
        "deepseek_in_providers": "deepseek/deepseek-v3.1" in MODEL_PROVIDERS,
        "deepseek_provider_value": MODEL_PROVIDERS.get("deepseek/deepseek-v3.1", "not found"),
        "client_base_url": "https://api.novita.ai/openai" if deepseek_client else None
    }

@router.get("/debug/source-text-models")
def debug_source_text_models(
    source_text: str = Query(..., description="Source text to debug"),
    db: Session = Depends(get_db)
):
    """
    Debug endpoint to see what models have been used with a specific source text
    """
    try:
        # Query existing translation jobs with the same source text
        existing_jobs = db.query(TranslationJob).filter(
            TranslationJob.source_text == source_text.strip()
        ).all()
        
        debug_data = {
            "source_text": source_text,
            "source_text_length": len(source_text),
            "jobs_found": len(existing_jobs),
            "job_details": [],
            "used_model_versions": [],
            "available_models": list(MODEL_PROVIDERS.keys())
        }
        
        if existing_jobs:
            for job in existing_jobs:
                job_info = {
                    "job_id": str(job.id),
                    "source_text_match": job.source_text == source_text.strip(),
                    "source_text_preview": job.source_text[:100] + "..." if len(job.source_text) > 100 else job.source_text,
                    "outputs": []
                }
                
                # Get outputs for this job
                outputs = db.query(TranslationOutput).filter(
                    TranslationOutput.job_id == job.id
                ).all()
                
                for output in outputs:
                    model_version = db.query(ModelVersion).filter(
                        ModelVersion.id == output.model_version_id
                    ).first()
                    
                    output_info = {
                        "output_id": str(output.id),
                        "model_version_id": str(output.model_version_id),
                        "model_version": model_version.version if model_version else "Unknown",
                        "model_provider": model_version.provider if model_version else "Unknown"
                    }
                    job_info["outputs"].append(output_info)
                    
                    if model_version and model_version.version not in debug_data["used_model_versions"]:
                        debug_data["used_model_versions"].append(model_version.version)
                
                debug_data["job_details"].append(job_info)
        
        # Show what would be filtered
        filtered_models = [model for model in debug_data["available_models"] if model not in debug_data["used_model_versions"]]
        debug_data["filtered_models"] = filtered_models
        debug_data["would_suggest_from"] = filtered_models if len(filtered_models) >= 2 else debug_data["available_models"]
        
        return debug_data
        
    except Exception as e:
        return {
            "error": str(e),
            "source_text": source_text
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