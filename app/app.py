from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

from app.api.endpoints.summarizer_router import router as summarizer_router

app = FastAPI(
    title="Vitafy AI Chat API",
    description="""
## Vitafy AI Chat API

AI-powered summarization service for healthcare case notes.

### Features

* **Case Note Summarization** - Generate AI-powered summaries of patient case notes
* **Role-based Summaries** - Tailored summaries based on user roles
* **Flexible Summarization Types** - Support for full and unread note summarization

### Authentication

Currently, no authentication is required for API access.
    """,
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    openapi_tags=[
        {
            "name": "Summarization",
            "description": "Operations for summarizing healthcare case notes using AI",
        },
        {
            "name": "Health",
            "description": "Health check and status endpoints",
        },
    ],
    contact={
        "name": "Vitafy Support",
        "email": "support@vitafy.com",
    },
    license_info={
        "name": "Proprietary",
    },
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(summarizer_router, prefix="/api/v1", tags=["Summarization"])


@app.get(
    "/",
    tags=["Health"],
    summary="Root Endpoint",
    description="Welcome endpoint that confirms the API is running.",
)
async def root():
    """Return a welcome message confirming the API is running."""
    return {"message": "Welcome to Vitafy AI Chat API"}


@app.get(
    "/health",
    tags=["Health"],
    summary="Health Check",
    description="Check if the API service is healthy and responding.",
    responses={
        200: {
            "description": "Service is healthy",
            "content": {
                "application/json": {
                    "example": {"status": "healthy"}
                }
            }
        }
    }
)
async def health_check():
    """Return the health status of the API service."""
    return {"status": "healthy"}
