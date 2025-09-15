from fastapi import FastAPI, HTTPException
from fastapi.security import HTTPBearer
from fastapi.openapi.utils import get_openapi
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, FileResponse
from fastapi import Request
from database import create_table
from submission_cache import start_cache_cleanup
from submission_worker import start_submission_workers
import uvicorn

from dotenv import load_dotenv
import os
from fastapi.middleware.cors import CORSMiddleware

# Load environment variables BEFORE importing routers
load_dotenv()

# Import routers AFTER loading environment variables
from routers import user, challenge, submission, result, category, model, file_upload, translation, tools, reports

# Templates setup
templates = Jinja2Templates(directory="templates")

# Auth0 configuration
AUTH0_DOMAIN = os.getenv("AUTH0_DOMAIN")
AUTH0_CLIENT_ID = os.getenv("AUTH0_CLIENT_ID")
AUTH0_AUDIENCE = os.getenv("AUTH0_AUDIENCE")




# HTTP Bearer scheme for API endpoints
security = HTTPBearer()

app = FastAPI(
    title="OpenPecha EvalAI API",
    description="API for OpenPecha evaluation challenges with Auth0 JWT authentication",
    version="1.0.0",
    docs_url="/docs",  # Enable default docs
    redoc_url="/redoc",  # Enable default redoc
    openapi_url="/openapi.json"
)

@app.on_event("startup")
async def startup_event():
    """Initialize submission processing system when FastAPI starts"""
    start_cache_cleanup()  # Start cache cleanup task
    start_submission_workers()  # Start worker threads

def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    
    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
        openapi_version="3.0.3"
    )
    
    # Ensure openapi version is set
    openapi_schema["openapi"] = "3.0.3"
    
    # Initialize components if not present
    if "components" not in openapi_schema:
        openapi_schema["components"] = {}
    if "securitySchemes" not in openapi_schema["components"]:
        openapi_schema["components"]["securitySchemes"] = {}
    
    # Replace HTTPBearer scheme with Auth0Bearer for better naming
    if "HTTPBearer" in openapi_schema["components"]["securitySchemes"]:
        openapi_schema["components"]["securitySchemes"]["Auth0Bearer"] = openapi_schema["components"]["securitySchemes"]["HTTPBearer"]
        del openapi_schema["components"]["securitySchemes"]["HTTPBearer"]
        
        # Update the description
        openapi_schema["components"]["securitySchemes"]["Auth0Bearer"]["description"] = "Auth0 JWT Token - Use your Auth0 access token"
        openapi_schema["components"]["securitySchemes"]["Auth0Bearer"]["bearerFormat"] = "JWT"
        
        # Update security references in paths to use Auth0Bearer instead of HTTPBearer
        if "paths" in openapi_schema:
            for path, path_item in openapi_schema["paths"].items():
                for method, operation in path_item.items():
                    if isinstance(operation, dict) and "security" in operation:
                        for security_req in operation["security"]:
                            if "HTTPBearer" in security_req:
                                security_req["Auth0Bearer"] = security_req.pop("HTTPBearer")
    
    app.openapi_schema = openapi_schema
    return app.openapi_schema

app.openapi = custom_openapi


create_table()

# CORS configuration
allowed_origins = os.getenv(
    "ALLOWED_ORIGINS", 
    "http://localhost:3000,http://localhost:5173,http://127.0.0.1:3000,http://127.0.0.1:5173"
)
origins = [origin.strip() for origin in allowed_origins.split(",")]

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)







@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Welcome to OpenPecha EvalAI API", 
        "status": "success",
        "documentation": "/documentation",
        "api_docs": "/docs"
    }


@app.get("/documentation", response_class=HTMLResponse)
async def documentation(request: Request):
    """API Documentation with examples and specifications"""
    return templates.TemplateResponse("documentation.html", {"request": request})


@app.get("/documentation/samples/{filename}")
async def download_sample(filename: str):
    """Download sample JSON files"""
    allowed_files = ["ocr challenge.json", "ocr submission.json"]
    
    if filename not in allowed_files:
        raise HTTPException(status_code=404, detail="File not found")
    
    file_path = f"samples/{filename}"
    
    try:
        return FileResponse(
            path=file_path,
            filename=filename,
            media_type="application/json"
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Sample file not found")








app.include_router(user.router)
app.include_router(category.router)
app.include_router(model.router)
app.include_router(challenge.router)
app.include_router(submission.router)
app.include_router(result.router)
app.include_router(translation.router)
app.include_router(tools.router)
app.include_router(reports.router)
app.include_router(file_upload.router) # for testing. you can comment out.


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )