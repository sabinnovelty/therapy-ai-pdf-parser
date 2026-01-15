# Vitafy AI Chat

AI-powered summarization service for healthcare case notes using FastAPI and LangChain.

## Features

- AI-powered case note summarization
- Support for different summarization styles (advocate, full, short)
- RESTful API with FastAPI
- Docker support for easy deployment

## Prerequisites

- Python 3.12+
- Docker and Docker Compose (for containerized deployment)
- OpenAI API Key

## Quick Start

### Option 1: Using Docker (Recommended)

1. **Clone the repository and navigate to the project directory**

2. **Create your environment file**
   ```bash
   cp .env.example .env
   ```

3. **Add your OpenAI API key to `.env`**
   ```
   OPENAI_API_KEY=your-actual-api-key
   ```

4. **Start the application**
   ```bash
   docker compose up --build
   ```

5. **Access the API**
   - API: http://localhost:8000
   - Swagger Docs: http://localhost:8000/docs
   - Health Check: http://localhost:8000/health

### Option 2: Local Development

1. **Create a virtual environment**
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Create your environment file**
   ```bash
   cp .env.example .env
   # Edit .env and add your OPENAI_API_KEY
   ```

4. **Run the application**
   ```bash
   uvicorn app.app:app --reload
   ```

## API Endpoints

### Health Check
```
GET /health
```

### Summarize Case Notes
```
POST /api/v1/summarize
```

**Request Body:**
```json
{
  "caseId": "case-123",
  "notes": [
    {"note": "Patient called regarding prescription refill..."},
    {"note": "Contacted pharmacy to verify..."}
  ],
  "patientName": "John Doe",
  "assignedTo": "advocate-1",
  "currentCaseStatus": "In Progress",
  "onBehalfOf": "Healthcare Advocate",
  "summarizationType": "full"
}
```

**Response:**
```json
{
  "success": true,
  "caseId": "case-123",
  "summary": "AI-generated summary of the case notes..."
}
```

## Project Structure

```
vitafy-ai-chat/
├── app/
│   ├── api/
│   │   └── endpoints/
│   │       └── summarizer_router.py
│   ├── prompts/
│   │   └── summarization_prompts.py
│   ├── schemas/
│   │   └── summarization_schema.py
│   ├── services/
│   │   └── summarization_service.py
│   └── app.py
├── .env.example
├── .dockerignore
├── .gitignore
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
└── README.md
```

## Development

### Running Tests
```bash
pytest
```

### Code Formatting
```bash
black app/
isort app/
```

## License

Proprietary - All rights reserved.
