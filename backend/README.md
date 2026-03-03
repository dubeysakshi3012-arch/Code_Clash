# CodeClash Backend API

Production-grade MVP backend for CodeClash platform - Assessment-based onboarding with ELO progression and AI-driven adaptive learning.

## Tech Stack

- **Framework**: FastAPI (Python)
- **Database**: PostgreSQL
- **ORM**: SQLAlchemy
- **Migrations**: Alembic
- **Cache**: Redis
- **Auth**: JWT (access + refresh tokens)
- **Code Execution**: Docker-based judge (skeleton)

## Project Structure

```
backend/
├── app/
│   ├── main.py                 # FastAPI application entry point
│   ├── core/                   # Core configuration and utilities
│   │   ├── config.py          # Environment-based settings
│   │   ├── security.py        # Password hashing
│   │   └── jwt.py             # JWT token management
│   ├── db/                     # Database configuration
│   │   ├── base.py            # SQLAlchemy base
│   │   ├── session.py         # Database session management
│   │   └── models/            # Database models
│   ├── api/v1/                # API routes
│   │   ├── auth.py            # Authentication endpoints
│   │   ├── assessment.py     # Assessment endpoints
│   │   └── health.py          # Health check
│   ├── services/              # Business logic
│   │   ├── auth_service.py
│   │   ├── assessment_service.py
│   │   ├── elo_service.py
│   │   ├── ai_service.py      # AI integration (placeholder)
│   │   └── judge_service.py   # Code execution (placeholder)
│   ├── schemas/               # Pydantic schemas
│   └── utils/                 # Utility functions
├── alembic/                   # Database migrations
├── docker/                    # Docker judge configurations
└── requirements.txt          # Python dependencies
```

## Setup Instructions

### Prerequisites

- Python 3.11+
- PostgreSQL 15+
- Redis (optional)
- Docker (for code execution judge)

### Installation

1. **Clone and navigate to backend directory**
   ```bash
   cd backend
   ```

2. **Create virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables**
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

5. **Start PostgreSQL and Redis (using Docker Compose)**
   ```bash
   docker-compose up -d
   ```

6. **Run database migrations**
   ```bash
   alembic upgrade head
   ```

7. **Run the application**
   ```bash
   uvicorn app.main:app --reload
   ```

The API will be available at `http://localhost:8000`
- API Documentation: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

### Socket server (PvP matchmaking)

Run the Node.js Socket.io server alongside the API for real-time matchmaking:

1. From the project root: `cd socket-server`
2. `npm install` then `cp .env.example .env`
3. Set `JWT_SECRET_KEY` (same as backend), `SOCKET_SERVER_SECRET` (same as backend `SOCKET_SERVER_SECRET`), and `API_URL=http://localhost:8000`
4. Run: `npm start` (listens on port 3001 by default)

Frontend: set `NEXT_PUBLIC_SOCKET_URL=http://localhost:3001` so the client can connect for Find Match.

## Environment Variables

See `.env.example` for all required environment variables:

- `DATABASE_URL`: PostgreSQL connection string
- `JWT_SECRET_KEY`: Secret key for JWT token signing
- `REDIS_URL`: Redis connection URL (optional)
- `OPENAI_API_KEY`: OpenAI API key (optional)
- `GEMINI_API_KEY`: Google Gemini API key (optional, for match question generation)
- `SOCKET_SERVER_URL`: Socket.io server URL (optional, default `http://localhost:3001`)
- `SOCKET_SERVER_SECRET`: Shared secret for Socket server to call match-creation API

## API Endpoints

### Authentication
- `POST /api/v1/auth/register` - User registration
- `POST /api/v1/auth/login` - User login
- `POST /api/v1/auth/refresh` - Refresh access token
- `GET /api/v1/auth/me` - Get current user (protected)

### Assessment
- `POST /api/v1/assessment/start` - Start new assessment
- `GET /api/v1/assessment/{id}/questions` - Get assessment questions
- `POST /api/v1/assessment/{id}/submit` - Submit answer
- `POST /api/v1/assessment/{id}/complete` - Complete assessment

### Matches (PvP)
- `GET /api/v1/matches` - List my matches (protected)
- `GET /api/v1/matches/{id}` - Match detail (participants only)
- `POST /api/v1/matches/{id}/submit` - Submit answer in a match (protected)
- `POST /api/v1/matches/create` - Internal: create match (Socket server only, `X-Socket-Secret`)

### Health
- `GET /api/v1/health` - Health check

## Database Migrations

Create a new migration:
```bash
alembic revision --autogenerate -m "description"
```

Apply migrations:
```bash
alembic upgrade head
```

Rollback migration:
```bash
alembic downgrade -1
```

## Development

### Code Quality
- Format code: `black app/`
- Lint code: `ruff check app/`

### Testing
```bash
pytest
```

## Architecture Notes

- **Clean Architecture**: Separation of concerns with services handling business logic
- **Dependency Injection**: FastAPI's Depends() for database sessions and auth
- **Type Safety**: Type hints throughout, Pydantic for validation
- **Extensibility**: Placeholders for AI and Docker judge with clear TODOs

## TODO / Future Enhancements

- [ ] Implement OpenAI API integration for question generation (Gemini implemented for matches)
- [ ] Add Redis caching for frequently accessed data
- [ ] Add comprehensive test coverage
- [ ] Add structured logging and monitoring
- Rate limiting is implemented (auth, submission, match create).

## License

MIT
