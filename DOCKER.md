# Docker Setup Instructions

This document provides instructions for building and running the Vitafy AI Chat API using Docker.

## Prerequisites

1. **Docker** (version 20.10 or higher)
2. **Docker Compose** (version 2.0 or higher)
3. **Environment Variables** - Create a `.env` file with required API keys

## Required Environment Variables

Create a `.env` file in the project root with the following variables:

```bash
# OpenAI API (for summarization)
OPENAI_API_KEY=your_openai_api_key_here

# RAG System API Keys
LLAMA_CLOUD_API_KEY=your_llama_cloud_api_key_here
GEMINI_API_KEY=your_gemini_api_key_here
VOYAGE_API_KEY=your_voyage_api_key_here

# Server Configuration
PORT=8000
```

### Getting API Keys

- **OpenAI API Key**: Get from [OpenAI Platform](https://platform.openai.com/api-keys)
- **Llama Cloud API Key**: Get from [LlamaCloud](https://cloud.llamaindex.ai/)
- **Gemini API Key**: Get from [Google AI Studio](https://makersuite.google.com/app/apikey)
- **Voyage API Key**: Get from [Voyage AI](https://www.voyageai.com/)

## Quick Start

### 1. Build and Run with Docker Compose

```bash
# Build and start the container
docker-compose up --build

# Or run in detached mode
docker-compose up -d --build
```

The API will be available at `http://localhost:8000`

### 2. View Logs

```bash
# View logs
docker-compose logs -f

# View logs for specific service
docker-compose logs -f vitafy-ai-chat
```

### 3. Stop the Container

```bash
# Stop containers
docker-compose down

# Stop and remove volumes (WARNING: This deletes vector DB data)
docker-compose down -v
```

## Building Docker Image Manually

### Build the Image

```bash
docker build -t vitafy-ai-chat:latest .
```

### Run the Container

```bash
docker run -d \
  --name vitafy-ai-chat \
  -p 8000:8000 \
  --env-file .env \
  -v $(pwd)/storage:/app/storage \
  vitafy-ai-chat:latest
```

## Docker Compose Configuration

The `docker-compose.yml` includes:

- **Port Mapping**: Maps container port 8000 to host port 8000
- **Volume Mounts**:
  - `./app:/app/app` - Hot-reload for development
  - `./storage:/app/storage` - Persists vector database and uploaded files
- **Environment Variables**: Loads from `.env` file
- **Health Check**: Monitors container health every 30 seconds
- **Auto-restart**: Container restarts automatically unless stopped

## Storage Persistence

The application creates the following directories in `./storage`:

- `storage/raw_uploads/` - Uploaded PDF files organized by tenant
- `storage/vector_db/` - ChromaDB vector database (persisted)
- `storage/markdown_cache/` - Cached parsed markdown files

**Important**: The `./storage` directory is mounted as a volume to persist data between container restarts.

## Health Check

The container includes a health check endpoint:

```bash
# Check health status
curl http://localhost:8000/health

# Expected response
{"status": "healthy"}
```

## API Documentation

Once the container is running, access:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **OpenAPI JSON**: http://localhost:8000/openapi.json

## Troubleshooting

### Container Fails to Start

1. **Check logs**:
   ```bash
   docker-compose logs vitafy-ai-chat
   ```

2. **Verify environment variables**:
   ```bash
   docker-compose config
   ```

3. **Check if port is already in use**:
   ```bash
   lsof -i :8000
   ```

### Module Not Found Errors

If you see `ModuleNotFoundError`, ensure:

1. Requirements are installed during build:
   ```bash
   docker-compose build --no-cache
   ```

2. Check `requirements.txt` includes all dependencies

### Vector Database Issues

If the vector database is corrupted:

1. Stop the container:
   ```bash
   docker-compose down
   ```

2. Remove the vector database:
   ```bash
   rm -rf ./storage/vector_db/*
   ```

3. Restart the container:
   ```bash
   docker-compose up -d
   ```

### Permission Issues

If you encounter permission errors with storage:

```bash
# Fix permissions
sudo chown -R $USER:$USER ./storage
chmod -R 755 ./storage
```

## Development Mode

For development with hot-reload:

```bash
# Already configured in docker-compose.yml
docker-compose up
```

Changes to files in `./app` will automatically reload the server.

## Production Deployment

For production, consider:

1. **Remove hot-reload**: Remove `--reload` flag from command
2. **Use specific image tags**: Don't use `latest` tag
3. **Set up proper secrets management**: Use Docker secrets or external secret managers
4. **Configure CORS**: Update CORS settings in `app.py`
5. **Use reverse proxy**: Set up nginx or similar
6. **Enable HTTPS**: Configure SSL/TLS certificates
7. **Resource limits**: Add memory and CPU limits to docker-compose.yml

Example production docker-compose.yml additions:

```yaml
services:
  vitafy-ai-chat:
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 4G
        reservations:
          cpus: '1'
          memory: 2G
```

## Cleaning Up

```bash
# Stop and remove containers
docker-compose down

# Remove containers, volumes, and images
docker-compose down -v --rmi all

# Remove all unused Docker resources
docker system prune -a
```
