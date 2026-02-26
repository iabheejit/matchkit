# 🤝 MatchKit

**Open-source, white-label cofounder and interest-area matching platform.**

Inspired by the YC Co-Founder Matching System, MatchKit uses AI-powered semantic embeddings and configurable multi-dimensional scoring to create recurring connections between people and profiles around shared interests, geography, size, and preferences to help surface potential cofounders. It delivers automated match digest emails and exposes a full REST API — while remaining fully customizable for multi-use-case, multi-domain deployment.

[![License: Apache%202.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-green.svg)](https://fastapi.tiangolo.com)

---

## ✨ Features

- **AI-Powered Matching** — Semantic similarity across people and profile data via Azure OpenAI embeddings
- **Configurable Scoring** — 5 weighted dimensions defined in YAML (no code changes needed)
- **White-Label Ready** — Brand name, colors, URLs, and email templates are all configurable
- **Email Digests** — Automated weekly/monthly match digests via Mandrill or SendGrid
- **REST API** — Full CRUD for profiles, matches, and scheduling
- **CRM Integration** — Optional two-way sync with any OAuth2-compatible CRM
- **Background Scheduler** — APScheduler for automated match refresh and email delivery
- **PostgreSQL + pgvector** — Production-ready storage with optional vector similarity search

## 🏗️ Architecture

```
matchkit/
├── api/              # FastAPI routes, schemas, auth
├── config/           # Settings + scoring.yml
│   └── examples/     # Domain-specific scoring configs
├── crm/              # Optional CRM integration (OAuth2-compatible)
├── db/               # SQLAlchemy session, repositories
├── email_service/    # Jinja2 templates, Mandrill/SendGrid senders
├── matching/         # Embedding generation, scoring engine, recommendations
├── models/           # Generic profile entities (Organization, Member, Match)
├── scheduler/        # APScheduler jobs and manager
├── tests/            # pytest test suite
└── utils/            # CSV loader, URL helpers, logging
```

## 🚀 Quick Start

### 1. Clone and configure

```bash
git clone https://github.com/yourorg/matchkit.git
cd matchkit
cp .env.example .env
# Edit .env with your settings
```

### 2. Run with Docker Compose

```bash
docker compose up -d
```

The API will be available at `http://localhost:8000`. Check health:

```bash
curl http://localhost:8000/health
```

### 3. Or run locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Start PostgreSQL (with pgvector)
docker run -d --name matchkit-db \
  -e POSTGRES_DB=matchkit \
  -e POSTGRES_PASSWORD=postgres \
  -p 5432:5432 \
  pgvector/pgvector:pg16

# Run the API
uvicorn api.main:app --reload
```

## ⚙️ Configuration

### Environment Variables

All settings are configured via environment variables or a `.env` file. See [`.env.example`](.env.example) for the full list.

| Variable | Description | Default |
|----------|-------------|---------|
| `APP_NAME` | Your platform name | `MatchKit` |
| `APP_TAGLINE` | Tagline shown in emails | `Cofounder & Interest Matching Platform` |
| `SUPPORT_EMAIL` | Support contact in emails | _(empty)_ |
| `PROFILE_BASE_URL` | Base URL for member profiles | _(empty)_ |
| `DATABASE_URL` | PostgreSQL connection string | `postgresql+asyncpg://...localhost.../matchkit` |
| `AZURE_OPENAI_ENDPOINT` | Azure OpenAI endpoint | _(empty — disables embeddings)_ |
| `API_KEY` | API authentication key | `dev-api-key-change-in-production` |
| `SCORING_CONFIG_PATH` | Path to scoring YAML | `config/scoring.yml` |

### Scoring Configuration

The matching engine is fully configurable via `config/scoring.yml`:

```yaml
weights:
  embedding: 0.30      # Semantic similarity
  interest: 0.25       # Interest/domain complementarity
  geographic: 0.20     # Geographic overlap
  size: 0.15           # Profile/company size compatibility
  preference: 0.10     # Preference/tag alignment

interest_pairs:
  - pair: ["Technology", "Education"]
    score: 0.9
  # ... add your domain-specific pairs

size_compatibility:
  - pair: ["Large", "Small"]
    score: 0.9
  # ...
```

See [`config/examples/`](config/examples/) for cofounder-focused and multi-domain scoring examples.

## 🎨 White-Labeling

MatchKit is designed to be white-labeled. To customize for your brand:

1. **Set branding env vars**: `APP_NAME`, `APP_TAGLINE`, `SUPPORT_EMAIL`, `PROFILE_BASE_URL`
2. **Customize scoring**: Edit `config/scoring.yml` with your domain's interest taxonomy
3. **Customize email templates**: Edit `email_service/templates/` (Jinja2 HTML/TXT)
4. **Import your data**: Use the CSV loader or CRM sync

## 📡 API Reference

All endpoints (except `/health`) require an `X-API-Key` header.

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | Health check |
| `GET` | `/api/organizations` | List profiles (paginated) |
| `GET` | `/api/organizations/{id}` | Get profile detail |
| `GET` | `/api/organizations/{id}/matches` | Get matches for a profile |
| `POST` | `/api/organizations/{id}/matches/generate` | Generate fresh matches |
| `PATCH` | `/api/matches/{id}/status` | Update match status |
| `GET` | `/api/scheduler/status` | Scheduler status |
| `POST` | `/api/scheduler/trigger/{job}` | Trigger a job manually |
| `POST` | `/api/email/send-test` | Send a test digest email |
| `GET` | `/api/email/preview/{org_id}` | Preview digest HTML |

## 🧪 Testing

```bash
pip install -e ".[dev]"
pytest
```

## 🤝 Contributing

Contributions are welcome! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## 📄 License

Apache-2.0 — see [LICENSE](LICENSE).
