# Vitafy AI Chat - Codebase Architecture

## Overview
Vitafy AI Chat is a FastAPI-based healthcare AI service providing two main capabilities:
1. **Case Note Summarization** - AI-powered summaries of patient case notes
2. **Healthcare Advocacy RAG** - Query healthcare policies, plans, and regulations using Retrieval-Augmented Generation

## Folder Structure

```
vitafy-ai-chat/
├── app/                          # Main application package
│   ├── __init__.py
│   ├── app.py                    # FastAPI application entry point
│   │
│   ├── api/                      # API layer - REST endpoints
│   │   ├── __init__.py
│   │   └── endpoints/
│   │       ├── __init__.py
│   │       ├── rag_router.py     # RAG/Advocacy endpoints
│   │       └── summarizer_router.py  # Summarization endpoints
│   │
│   ├── core/                     # Core configuration and infrastructure
│   │   ├── config.py            # RAG settings (LLM, embeddings, chunking)
│   │   ├── indexer.py           # Vector indexing logic
│   │   ├── parser.py            # Document parsing (LlamaParse integration)
│   │   └── storage.py           # Storage backend factory (ChromaDB/Pinecone)
│   │
│   ├── services/                 # Business logic layer
│   │   ├── __init__.py
│   │   ├── advocacy_service.py  # Healthcare advocacy RAG orchestration
│   │   ├── document_service.py  # Document management operations
│   │   ├── ingestion_service.py # Document ingestion and indexing
│   │   └── summarization_service.py  # Case note summarization logic
│   │
│   ├── schemas/                  # Pydantic models for request/response
│   │   ├── __init__.py
│   │   ├── rag_schema.py        # RAG API schemas
│   │   └── summarization_schema.py  # Summarization API schemas
│   │
│   ├── prompts/                  # LLM prompt templates
│   │   ├── __init__.py
│   │   ├── advocacy_prompts.py  # Healthcare advocacy prompts
│   │   └── summarization_prompts.py  # Summarization prompts
│   │
│   └── utils/                    # Utility modules
│       ├── __init__.py
│       ├── exception_handlers.py  # Global exception handling
│       └── logger.py             # Structured logging configuration
│
├── storage/                      # Local storage (gitignored in production)
│   └── raw_uploads/             # Uploaded PDF files
│
├── .github/                      # CI/CD workflows
│   └── workflows/
│       └── build-deploy.yml
│
├── .env.example                  # Environment variable template
├── .gitignore
├── .dockerignore
│
├── Dockerfile                    # Container image definition
├── docker-compose.yml           # Local development setup
│
├── requirements.txt             # Python dependencies
├── swagger.yaml                 # OpenAPI specification
│
├── README.md                    # Project documentation
├── DOCKER.md                    # Docker deployment guide
└── ARCHITECTURE.md             # This file
```

## Architecture Layers

### 1. API Layer (`app/api/endpoints/`)
- **Purpose**: HTTP request handling, validation, and response formatting
- **Pattern**: FastAPI routers with dependency injection
- **Endpoints**:
  - `/api/v2/ai-services/summarize/*` - Summarization endpoints
  - `/api/v2/ai-services/admin/upload` - Document upload
  - `/api/v2/ai-services/query` - RAG query endpoint
  - `/api/v2/ai-services/documents` - Document listing

### 2. Service Layer (`app/services/`)
- **Purpose**: Business logic and orchestration
- **Key Services**:
  - `advocacy_service.py`: RAG query processing, intent classification
  - `ingestion_service.py`: Document parsing, chunking, vector indexing
  - `summarization_service.py`: Case note summarization with role-based prompts
  - `document_service.py`: Document metadata management

### 3. Core Layer (`app/core/`)
- **Purpose**: Infrastructure configuration and abstractions
- **Components**:
  - `config.py`: Global RAG settings (LLM, embeddings, chunking)
  - `storage.py`: Storage backend factory and file operations (supports ChromaDB and Pinecone, handles file uploads and vector store creation)
  - `parser.py`: Document parsing using LlamaParse
  - `indexer.py`: Vector database indexing operations

### 4. Schema Layer (`app/schemas/`)
- **Purpose**: Request/response validation using Pydantic
- **Schemas**:
  - `rag_schema.py`: RAG request/response models
  - `summarization_schema.py`: Summarization request/response models

### 5. Prompt Layer (`app/prompts/`)
- **Purpose**: Centralized LLM prompt templates
- **Templates**:
  - Healthcare advocacy prompts
  - Role-based summarization prompts

## Technology Stack

### Core Framework
- **FastAPI** (0.115.6) - Modern Python web framework
- **Uvicorn** - ASGI server
- **Pydantic** (2.10.4) - Data validation

### AI/ML Stack
- **LlamaIndex** (>=0.10.0) - RAG framework
  - `llama-index-llms-openai` - OpenAI LLM integration
  - `llama-index-embeddings-openai` - OpenAI embeddings
  - `llama-index-vector-stores-chroma` - ChromaDB integration
  - `llama-index-vector-stores-pinecone` - Pinecone integration
- **LangChain** (>=0.3.20) - LLM orchestration
- **OpenAI** (1.59.3) - GPT models and embeddings
- **LlamaParse** (>=0.4.0) - PDF document parsing

### Vector Databases
- **ChromaDB** (>=0.4.0) - Local vector storage (default)
- **Pinecone** (>=3.0.0) - Cloud vector storage (optional)

### Utilities
- **structlog** (>=24.1.0) - Structured logging
- **python-dotenv** - Environment configuration
- **httpx** - HTTP client
- **playwright** - Browser automation (for web scraping if needed)

## Data Flow

### Document Ingestion Flow
```
1. Upload PDF → storage.save_upload()
2. Parse PDF → parser.parse_document() (LlamaParse)
3. Chunk & Embed → ingestion_service.ingest_document_functional()
4. Index → Vector DB (ChromaDB/Pinecone)
5. Metadata → Stored with tenant_id, doc_type, category
```

### RAG Query Flow
```
1. User Query → rag_router.query_advocacy_engine()
2. Intent Classification → advocacy_service (PLAN_RAG vs GENERAL)
3. Vector Search → Retrieve relevant chunks
4. Context Assembly → Combine chunks with query
5. LLM Generation → Generate answer using GPT-4o-mini
6. Response → Return answer with source citations
```

### Summarization Flow
```
1. Case Notes → summarizer_router endpoint
2. Role Detection → Determine user role (doctor, nurse, etc.)
3. Prompt Selection → Load role-specific prompt
4. LLM Generation → Generate summary
5. Response → Return formatted summary
```

## Storage Architecture

### Vector Database Backends
The system supports multiple vector database backends via factory pattern:

1. **ChromaDB** (default)
   - Local persistent storage
   - Path: `./storage/vector_db`
   - Suitable for development and small-scale deployments

2. **Pinecone** (production)
   - Cloud-hosted vector database
   - Requires `PINECONE_API_KEY`
   - Suitable for production and multi-tenant scenarios

3. **Weaviate** (planned)
   - Not yet implemented

### File Storage
- **Upload Directory**: `./storage/raw_uploads/`
- **Tenant Isolation**: Files organized by `tenant_id`
- **Markdown Cache**: `./storage/markdown_cache/` (for parsed documents)

## Configuration

### Environment Variables
- `OPENAI_API_KEY` - Required for LLM and embeddings
- `LLAMA_API_KEY` - Required for PDF parsing
- `PINECONE_API_KEY` - Required if using Pinecone
- `STORAGE_TYPE` - `chroma` (default) or `pinecone`
- `STORAGE_DIR` - Storage directory path (default: `./storage`)
- `PORT` - Server port (default: 8000)

### RAG Configuration
- **LLM Model**: `gpt-4o-mini` (cost-effective)
- **Embedding Model**: `text-embedding-3-small`
- **Chunk Size**: 1024 tokens
- **Chunk Overlap**: 100 tokens
- **Temperature**: 0.1 (deterministic responses)

## API Patterns

### Endpoint Prefix
All endpoints follow the pattern: `/api/v2/ai-services/`

### Authentication
Currently, no authentication is required (as per app.py documentation).

### Error Handling
- Global exception handlers in `app/utils/exception_handlers.py`
- Structured error responses with proper HTTP status codes
- Validation errors handled via Pydantic

## Deployment

### Docker
- **Base Image**: `python:3.12-slim`
- **Port**: 8000 (configurable via `PORT`)
- **Health Check**: `/health` endpoint
- **Volumes**: 
  - `./app` - Application code (dev hot-reload)
  - `./storage` - Persistent storage

### Docker Compose
- Development setup with hot-reload
- Environment variable injection via `.env`
- Volume mounts for development

## Logging

- **Framework**: `structlog` for structured logging
- **Configuration**: `app/utils/logger.py`
- **Modes**: 
  - JSON logs (CloudWatch compatible)
  - Human-readable logs (development)
- **Log Levels**: Configurable via `configure_logger()`

## Future Enhancements

Based on `README-impelmentation4.md`, planned improvements:
1. **Confidence-based Routing** - Self-reflective RAG with confidence scores
2. **Hybrid Ensemble** - Parallel retrieval from Plan RAG + Web Search
3. **Synthesis Prompts** - Handle conflicting medical vs insurance information
4. **Human-in-the-loop** - Escalation for low-confidence queries
