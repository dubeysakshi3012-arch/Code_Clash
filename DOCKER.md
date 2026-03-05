# CodeClash - Docker Setup

## Development (hot reload)

```bash
cp .env.docker.example .env
# Edit .env: set JWT_SECRET_KEY and SOCKET_SERVER_SECRET

docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build
```

Source is mounted; backend and frontend reload on file changes.

## Production

```bash
cp .env.docker.example .env
# Edit .env: set JWT_SECRET_KEY and SOCKET_SERVER_SECRET

docker compose up --build
```

**Requirements:** Docker and Docker Compose. On Windows, use Docker Desktop.

## What runs

| Service       | Port | URL                    |
|---------------|------|------------------------|
| Frontend      | 3000 | http://localhost:3000  |
| Backend API   | 8000 | http://localhost:8000  |
| Socket server | 3001 | http://localhost:3001  |
| PostgreSQL    | 5433 | localhost:5433         |
| Redis         | 6379 | localhost:6379         |

## Environment variables

Create `.env` in the project root (copy from `.env.docker.example`):

- `JWT_SECRET_KEY` – required, used by backend and socket server
- `SOCKET_SERVER_SECRET` – required, shared secret between backend and socket server
- `GEMINI_API_KEY` – optional, for AI-generated match questions
- `GROQ_API_KEY` – optional, for AI-generated match questions

Do **not** set `DATABASE_URL` in `.env` when using Docker; it is set by `docker-compose.yml` so the backend can reach Postgres by hostname `postgres`.

## Docker socket (code execution)

The backend mounts the host Docker socket so it can run user code. On Linux/Mac this is automatic. On Windows with Docker Desktop it should work. If code execution fails, ensure Docker is running and the backend container has socket access.

## Run in background

```bash
docker compose up -d --build
```

## Stop

```bash
docker compose down
```

## Troubleshooting

- **"could not translate host name 'postgres' to address"** – The backend uses `host.docker.internal` to reach Postgres/Redis (avoids container DNS issues on Docker Desktop for Windows). Ensure nothing else uses port 5432. Run `docker compose down` then `up --build` to recreate containers.
- **Backend exits with code 1** – In dev, the backend retries DB connection until Postgres is reachable. If it still fails, check that `codeclash_postgres` is running: `docker ps`.
- **"Bind for 0.0.0.0:5432 failed: port is already allocated"** – Another app (e.g. local PostgreSQL) is using port 5432. This project uses host port **5433** for Postgres to avoid that conflict; the backend is already configured to use it.
