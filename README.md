<h1 align="center"> <br> <a href="https://openpecha.org"><img src="https://avatars.githubusercontent.com/u/82142807?s=400&u=19e108a15566f3a1449bafb03b8dd706a72aebcd&v=4" alt="OpenPecha" width="150"></a> <br> </h1> <h1 align="center">Buddhist AI Arena - Backend API</h1>

A robust FastAPI-based backend service for the Buddhist AI Arena evaluation platform, providing authentication, challenge management, model evaluation, and real-time translation services.

## 🚀 Tech Stack

- **Framework:** FastAPI 0.108.0
- **Database:** PostgreSQL with SQLAlchemy 2.0+ & SQLModel
- **Authentication:** Auth0 with JWT tokens
- **Caching:** Redis 5.0+
- **Migrations:** Alembic 1.12+
- **File Storage:** AWS S3 with aioboto3
- **Background Tasks:** Threading with queue-based workers
- **AI Providers:** OpenAI, Anthropic, Google Gemini, DeepSeek
- **Evaluation:** Hugging Face datasets & evaluate library
- **Server:** Uvicorn with auto-reload

## 📋 Prerequisites

- Python 3.9 or higher (3.10+ recommended)
- PostgreSQL 12 or higher
- Redis server (local or remote)
- AWS account with S3 bucket (for file storage)
- Auth0 account and application credentials
- API keys for AI providers (OpenAI, Anthropic, Google, DeepSeek)

## 🔧 Installation

### 1. Clone the repository

```bash
git clone <repository-url>
cd arena/backend
```

### 2. Create and activate virtual environment

**Windows:**

```bash
python -m venv .venv
.venv\Scripts\activate
```

**macOS/Linux:**

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Set up PostgreSQL database

Create a new PostgreSQL database:

```sql
-- Connect to PostgreSQL
psql -U postgres

-- Create database
CREATE DATABASE arena_db;

-- Create user (optional)
CREATE USER arena_user WITH PASSWORD 'your_password';

-- Grant privileges
GRANT ALL PRIVILEGES ON DATABASE arena_db TO arena_user;
```

### 5. Set up Redis

**Option A: Local Redis (Recommended for development)**

**Windows:**

- Download Redis from [Redis Windows](https://github.com/microsoftarchive/redis/releases)
- Run `redis-server.exe`

**macOS:**

```bash
brew install redis
brew services start redis
```

**Linux:**

```bash
sudo apt-get install redis-server
sudo systemctl start redis
```

**Option B: Cloud Redis**

- Use services like Redis Cloud, AWS ElastiCache, or Upstash
- Get the connection URL

### 6. Configure environment variables

Create a `.env` file in the `backend` directory:

```env
# Database Configuration (Required)
DATABASE_URL=postgresql://username:password@localhost:5432/arena_db

# Redis Configuration (Required)
REDIS_URL=redis://localhost:6379/0

# Auth0 Configuration (Required)
AUTH0_DOMAIN=your-domain.auth0.com
AUTH0_CLIENT_ID=your-client-id
AUTH0_AUDIENCE=your-api-audience

# CORS Origins (Required for frontend connection)
ALLOWED_ORIGINS=http://localhost:3000,http://localhost:5173,http://127.0.0.1:3000,http://127.0.0.1:5173

# AI API Keys for Translation (Required for translation features)
OPENAI_API_KEY=sk-your-openai-api-key
ANTHROPIC_API_KEY=sk-ant-your-anthropic-api-key
GOOGLE_API_KEY=your-google-api-key
DEEPSEEK_API_KEY=session_your-novita-ai-session-key

# AWS S3 Configuration (Required for file uploads)
AWS_ACCESS_KEY_ID=your-aws-access-key
AWS_SECRET_ACCESS_KEY=your-aws-secret-key
AWS_BUCKET_NAME=your-bucket-name
AWS_REGION=us-east-1

# System Prompt (Optional - has default)
SYSTEM_PROMPT=You are a professional translation engine. Translate the given text accurately while preserving meaning, tone, and context. Output only the translated text without any additional commentary.

# Model Providers (Required - JSON format)
MODEL_PROVIDERS={"claude-3-5-sonnet-20241022": "anthropic", "claude-3-5-haiku-20241022": "anthropic", "claude-3-opus-20240229": "anthropic", "gemini-1.5-pro": "google", "gemini-1.5-flash": "google", "gpt-4o-mini": "openai", "gpt-4o": "openai", "gpt-4": "openai", "gpt-3.5-turbo": "openai", "deepseek/deepseek-v3.1": "deepseek-v3"}

# Pecha Studio Link (Optional)
STUDIO_LINK=https://studio.pecha.ai
```

### 7. Run database migrations

Initialize and run Alembic migrations to create database tables:

```bash
# Initialize Alembic (only if not already initialized)
alembic init alembic

# Run migrations to create all tables
alembic upgrade head
```

**Note:** If you encounter migration issues, you can reset the database:

```bash
# Downgrade all migrations
alembic downgrade base

# Re-run migrations
alembic upgrade head
```

## 🎯 Running the Application

### Development Mode

Start the development server with auto-reload:

```bash
# Make sure your virtual environment is activated
python main.py

# Or using uvicorn directly
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at:

- **API Base URL:** http://localhost:8000
- **Interactive Docs (Swagger):** http://localhost:8000/docs
- **Alternative Docs (ReDoc):** http://localhost:8000/redoc
- **API Documentation:** http://localhost:8000/documentation

### Production Mode

For production deployment:

```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
```

## 📁 Project Structure

```
backend/
├── alembic/                    # Database migrations
│   ├── versions/              # Migration versions
│   ├── env.py                 # Alembic environment config
│   └── script.py.mako         # Migration template
├── CRUD/                       # CRUD operations
│   ├── model.py               # Model CRUD operations
│   ├── s3_utils.py            # S3 helper functions
│   ├── upload_file_to_s3.py   # File upload logic
│   └── ground_truth_upload_s3.py
├── Evaluation/                 # Evaluation logic
│   └── evaluation.py          # Automatic evaluation system
├── models/                     # SQLAlchemy ORM models
│   ├── user.py                # User model
│   ├── challenge.py           # Challenge model
│   ├── submission.py          # Submission model
│   ├── model.py               # AI Model model
│   ├── result.py              # Result model
│   ├── arena_challenge.py     # Arena challenge model
│   ├── arena_rating.py        # Arena rating model
│   └── ...                    # Other models
├── routers/                    # API route handlers
│   ├── user.py                # User endpoints
│   ├── challenge.py           # Challenge endpoints
│   ├── submission.py          # Submission endpoints
│   ├── arena_challenge.py     # Arena challenge endpoints
│   ├── arena_ranking.py       # Ranking/leaderboard endpoints
│   ├── translate_v2.py        # Translation endpoints
│   ├── template_v2.py         # Template management
│   ├── tools.py               # Utility tools
│   └── ...                    # Other routers
├── schemas/                    # Pydantic schemas
│   ├── user.py                # User schemas
│   ├── challenge.py           # Challenge schemas
│   ├── submission.py          # Submission schemas
│   └── ...                    # Other schemas
├── service/                    # Business logic services
│   └── translate_v2_service.py
├── templates/                  # HTML templates
│   └── documentation.html     # API documentation page
├── samples/                    # Sample JSON files
│   ├── ocr challenge.json
│   └── ocr submission.json
├── commentaries_and_sanskrit/  # Buddhist texts data
│   ├── choejuk.json
│   ├── dorjee_choepa.json
│   └── ...
├── main.py                     # FastAPI application entry point
├── database.py                 # Database configuration
├── auth.py                     # Auth0 JWT authentication
├── redis_client.py             # Redis caching client
├── submission_worker.py        # Background worker for submissions
├── submission_cache.py         # Submission progress caching
├── background_tasks.py         # Background task management
├── requirements.txt            # Python dependencies
├── alembic.ini                 # Alembic configuration
├── .env                        # Environment variables (create this)
└── README.md                   # This file
```

## 🔑 Key Features

### Authentication & Authorization

- **Auth0 Integration:** Secure JWT-based authentication
- **Role-based Access:** Protected endpoints with user verification
- **Automatic Token Validation:** JWT signature verification with Auth0 JWKS

### Challenge Management

- **Create & Manage Challenges:** OCR, translation, and custom evaluation tasks
- **Arena Challenges:** Head-to-head model comparisons
- **Template System:** Reusable challenge templates
- **Category Organization:** Group challenges by type and domain

### Submission Processing

- **Queue-based Workers:** Non-blocking submission processing
- **Progress Tracking:** Real-time submission status via Redis cache
- **Automatic Evaluation:** Integrated evaluation metrics (BLEU, WER, etc.)
- **S3 File Storage:** Secure file upload and management

### Translation Services

- **Multi-provider Support:** OpenAI, Anthropic, Google, DeepSeek
- **Streaming Responses:** Real-time translation output
- **Model Comparison:** Side-by-side translation comparison
- **Custom Templates:** Configurable prompt templates

### Leaderboard & Rankings

- **ELO Rating System:** Arena-style model rankings
- **Score-based Leaderboards:** Performance metrics tracking
- **Vote Counting:** User voting and preferences
- **Real-time Updates:** Live ranking calculations

### Caching & Performance

- **Redis Caching:** Fast data retrieval for frequently accessed data
- **Submission Progress Cache:** Real-time status updates
- **JWKS Caching:** LRU cache for Auth0 public keys
- **Query Optimization:** Efficient database queries

## 📝 Environment Variables Reference

| Variable                  | Required | Default        | Description                      |
| ------------------------- | -------- | -------------- | -------------------------------- |
| `DATABASE_URL`          | Yes      | -              | PostgreSQL connection string     |
| `REDIS_URL`             | Yes      | -              | Redis connection URL             |
| `AUTH0_DOMAIN`          | Yes      | -              | Your Auth0 domain                |
| `AUTH0_CLIENT_ID`       | Yes      | -              | Auth0 application client ID      |
| `AUTH0_AUDIENCE`        | Yes      | -              | Auth0 API audience identifier    |
| `ALLOWED_ORIGINS`       | Yes      | localhost URLs | Comma-separated CORS origins     |
| `OPENAI_API_KEY`        | Yes*     | -              | OpenAI API key for GPT models    |
| `ANTHROPIC_API_KEY`     | Yes*     | -              | Anthropic API key for Claude     |
| `GOOGLE_API_KEY`        | Yes*     | -              | Google API key for Gemini        |
| `DEEPSEEK_API_KEY`      | Yes*     | -              | DeepSeek API key                 |
| `AWS_ACCESS_KEY_ID`     | Yes      | -              | AWS access key for S3            |
| `AWS_SECRET_ACCESS_KEY` | Yes      | -              | AWS secret key for S3            |
| `AWS_BUCKET_NAME`       | Yes      | -              | S3 bucket name for file storage  |
| `AWS_REGION`            | Yes      | `us-east-1`  | AWS region for S3 bucket         |
| `SYSTEM_PROMPT`         | No       | Default prompt | System prompt for translations   |
| `MODEL_PROVIDERS`       | Yes      | -              | JSON mapping models to providers |
| `STUDIO_LINK`           | No       | -              | Link to Pecha Studio             |

**Note:** AI API keys marked with * are required only if you plan to use translation features with those specific providers.

## 🗄️ Database Management

### Creating Migrations

When you modify database models:

```bash
# Generate a new migration
alembic revision --autogenerate -m "Description of changes"

# Review the generated migration file in alembic/versions/

# Apply the migration
alembic upgrade head
```

### Common Migration Commands

```bash
# Check current migration version
alembic current

# View migration history
alembic history

# Upgrade to specific version
alembic upgrade <revision_id>

# Downgrade one version
alembic downgrade -1

# Downgrade to base (clear all tables)
alembic downgrade base
```

### Database Reset (Development Only)

```bash
# WARNING: This will delete all data!
alembic downgrade base
alembic upgrade head
```

## 🔍 API Documentation

### Interactive API Docs

Once the server is running, access the interactive API documentation:

- **Swagger UI:** http://localhost:8000/docs
- **ReDoc:** http://localhost:8000/redoc

### Authentication in API Docs

1. Get an Auth0 access token from your frontend application
2. Click the "Authorize" button in Swagger UI
3. Enter `Bearer <your_token>` in the Auth0Bearer field
4. Click "Authorize" to apply the token to all requests

### Key Endpoints

**Authentication & Users**

- `POST /user` - Create a new user
- `GET /user/{user_id}` - Get user details

**Challenges**

- `GET /challenges` - List all challenges
- `POST /challenge` - Create a challenge (protected)
- `GET /challenge/{challenge_id}` - Get challenge details

**Submissions**

- `POST /submission` - Submit a solution (protected)
- `GET /submission/{submission_id}` - Get submission status
- `GET /submission/{submission_id}/progress` - Get real-time progress

**Arena**

- `GET /arena-challenges` - List arena challenges
- `POST /arena-challenge/{id}/vote` - Vote on model comparison
- `GET /arena-rankings` - Get model rankings

**Translation**

- `POST /translate-v2/chat` - Chat-based translation (streaming)
- `POST /translate-v2/compare` - Compare multiple models
- `GET /templates-v2` - List available templates

**Tools**

- `POST /tools/convert-ewts-to-unicode` - Convert EWTS to Tibetan Unicode

## 🐛 Troubleshooting

### Database Connection Issues

**Problem:** "DATABASE_URL is not set"

- **Solution:** Ensure `.env` file exists with correct `DATABASE_URL`
- Verify PostgreSQL is running: `pg_isready`

**Problem:** "Connection refused to database"

- **Solution:** Check PostgreSQL service status
- Verify connection details (host, port, username, password)
- Test connection: `psql -U username -d arena_db`

### Redis Connection Issues

**Problem:** "REDIS_URL is not set"

- **Solution:** Add `REDIS_URL=redis://localhost:6379/0` to `.env`

**Problem:** "Redis connection failed"

- **Solution:** Ensure Redis server is running
- **Windows:** Check if `redis-server.exe` is running
- **macOS/Linux:** Run `redis-cli ping` (should return "PONG")

### Migration Issues

**Problem:** "alembic.util.exc.CommandError: Target database is not up to date"

- **Solution:** Run `alembic upgrade head`

**Problem:** "Table already exists"

- **Solution:** Reset migrations:
  ```bash
  alembic downgrade base
  alembic upgrade head
  ```

### Authentication Issues

**Problem:** "Invalid token"

- **Solution:** Check Auth0 configuration (domain, audience)
- Verify token is not expired
- Ensure frontend and backend use same Auth0 settings

**Problem:** "Unable to verify token"

- **Solution:** Check internet connection (needs to fetch JWKS)
- Verify `AUTH0_DOMAIN` is correct

### Import Errors

**Problem:** "ModuleNotFoundError"

- **Solution:** Ensure virtual environment is activated
- Reinstall dependencies: `pip install -r requirements.txt`

**Problem:** "ImportError: attempted relative import with no known parent package"

- **Solution:** Run from project root: `python main.py`

## 🚢 Deployment

### Environment Setup

1. **Set all environment variables** in your hosting platform
2. **Use production database** (not local PostgreSQL)
3. **Use production Redis** (managed Redis service recommended)
4. **Update ALLOWED_ORIGINS** with your frontend production URL

### Pre-deployment Checklist

- [ ] All environment variables configured
- [ ] Database migrations run: `alembic upgrade head`
- [ ] Redis connection tested and working
- [ ] S3 bucket configured with proper permissions
- [ ] Auth0 application configured with production URLs
- [ ] AI API keys have sufficient credits
- [ ] CORS origins include production frontend URL

### Deployment Platforms

**Render / Railway / Heroku:**

- Set environment variables in dashboard
- Set build command: `pip install -r requirements.txt`
- Set start command: `uvicorn main:app --host 0.0.0.0 --port $PORT`

**AWS / DigitalOcean / VPS:**

- Use systemd or supervisor to manage the process
- Set up nginx as reverse proxy
- Use gunicorn with uvicorn workers:
  ```bash
  gunicorn main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
  ```

**Docker:**

```dockerfile
FROM python:3.10
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Database Backups

Regular backups are crucial:

```bash
# Backup PostgreSQL database
pg_dump -U username arena_db > backup_$(date +%Y%m%d).sql

# Restore from backup
psql -U username arena_db < backup_20250101.sql
```

## 🧪 Testing

Run the application in development mode and test endpoints:

```bash
# Start server
python main.py

# Test root endpoint
curl http://localhost:8000/

# Test with httpie (install: pip install httpie)
http http://localhost:8000/challenges
```

## 📚 Additional Resources

### How to Get API Keys

**OpenAI:**

1. Sign up at https://platform.openai.com
2. Navigate to API Keys section
3. Create new secret key

**Anthropic:**

1. Sign up at https://console.anthropic.com
2. Go to API Keys
3. Generate new key

**Google Gemini:**

1. Visit https://makersuite.google.com/app/apikey
2. Create API key
3. Enable Gemini API

**AWS S3:**

1. Create AWS account
2. Create IAM user with S3 permissions
3. Generate access keys
4. Create S3 bucket in desired region

## 🤝 Contributing

1. Create a new branch for your feature
2. Make your changes
3. Run migrations if models changed: `alembic revision --autogenerate`
4. Test all endpoints
5. Submit a pull request

## 🆘 Support

For issues and questions:

- Check the troubleshooting section above
- Review API documentation at `/docs`
- Check FastAPI logs for detailed error messages
- Verify all environment variables are set correctly

---

**Note:** This backend requires a PostgreSQL database and Redis server. For frontend setup instructions, see `https://github.com/OpenPecha/openpecha_evalai_frontend/README.md`.
