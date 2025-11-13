# PR2 Quick Start Guide

This guide will help you get PR2 up and running quickly.

## Prerequisites

- Python 3.11+
- PostgreSQL 14+ with pgvector extension
- Redis 5.0+

## Setup

### 1. Install Dependencies

```bash
# From repo root
pip install -e .
```

This installs all dependencies including PR2 additions:
- SQLAlchemy
- Alembic
- psycopg2-binary
- pgvector
- redis

### 2. Set Up PostgreSQL with pgvector

**Using Docker (easiest):**

```bash
docker run -d \
  --name keyveve-postgres \
  -e POSTGRES_USER=keyveve \
  -e POSTGRES_PASSWORD=keyveve_dev \
  -e POSTGRES_DB=keyveve_dev \
  -p 5432:5432 \
  ankane/pgvector
```

**Or install pgvector locally:**

```bash
# macOS
brew install pgvector

# Ubuntu/Debian
sudo apt-get install postgresql-15-pgvector
```

Then create database:

```bash
createdb keyveve_dev
psql keyveve_dev -c "CREATE EXTENSION vector;"
```

### 3. Set Up Redis

**Using Docker:**

```bash
docker run -d \
  --name keyveve-redis \
  -p 6379:6379 \
  redis:7-alpine
```

**Or install locally:**

```bash
# macOS
brew install redis
brew services start redis

# Ubuntu/Debian
sudo apt-get install redis-server
sudo systemctl start redis
```

### 4. Configure Environment

Create `.env` file in repo root:

```bash
# Database
POSTGRES_URL=postgresql://keyveve:keyveve_dev@localhost:5432/keyveve_dev

# Redis
REDIS_URL=redis://localhost:6379/0

# Optional: Override defaults
# FANOUT_CAP=4
# SOFT_TIMEOUT_S=2.0
# HARD_TIMEOUT_S=4.0
```

### 5. Run Migrations

```bash
# Check current version (should show no version initially)
alembic current

# Upgrade to latest
alembic upgrade head

# Verify
alembic current
# Output: 001 (head)
```

### 6. Seed Demo Data

```bash
python scripts/seed_fixtures.py
```

Output:
```
🌱 Seeding demo data...

Created organization: Demo Organization (org_id=...)
Created user: demo@example.com (user_id=...)
Created destination: Paris, France (dest_id=...)
Created knowledge item (item_id=...)

✅ Seed data created successfully!
```

### 7. Verify Installation

**Check database:**

```bash
psql keyveve_dev -c "SELECT name FROM org;"
```

Should show "Demo Organization".

**Check Redis:**

```bash
redis-cli ping
```

Should return "PONG".

## Run Tests

```bash
# All integration tests
pytest tests/integration/ -v

# Specific test file
pytest tests/integration/test_tenancy.py -v

# With coverage
pytest tests/integration/ --cov=backend/app --cov-report=term-missing
```

Expected output: All tests passing ✅

## Type Check

```bash
mypy backend/app/db backend/app/idempotency backend/app/limits --strict
```

Expected output: Success, no errors

## Common Tasks

### Reset Database

```bash
# Downgrade all migrations
alembic downgrade base

# Drop and recreate database
dropdb keyveve_dev
createdb keyveve_dev
psql keyveve_dev -c "CREATE EXTENSION vector;"

# Upgrade again
alembic upgrade head

# Re-seed
python scripts/seed_fixtures.py
```

### Add New Migration

```bash
# After modifying ORM models, generate migration
alembic revision --autogenerate -m "Add new table"

# Review generated migration in alembic/versions/

# Apply migration
alembic upgrade head
```

### Clear Redis

```bash
redis-cli FLUSHDB
```

### Inspect Tables

```bash
# List all tables
psql keyveve_dev -c "\dt"

# Describe a table
psql keyveve_dev -c "\d user"

# Count rows
psql keyveve_dev -c "SELECT COUNT(*) FROM itinerary;"
```

## Using PR2 Components

### Tenancy Example

```python
from backend.app.db.session import get_session_factory
from backend.app.db.tenancy import scoped_list
from backend.app.db.models import Itinerary

# Get session
factory = get_session_factory()
session = factory()

# Query itineraries for specific org
org_id = "..."  # From auth context
itineraries = scoped_list(
    session,
    Itinerary,
    org_id,
    user_id=user_id,
    limit=10
)

session.close()
```

### Idempotency Example

```python
from backend.app.db.session import get_session_factory
from backend.app.idempotency import get_entry, save_result, mark_completed
import hashlib

factory = get_session_factory()
session = factory()

# Check for existing entry
key = "plan-request-abc123"
existing = get_entry(session, key)

if existing and existing.status == "completed":
    # Return cached response
    return cached_response
else:
    # Create pending entry
    body_hash = hashlib.sha256(request_body.encode()).hexdigest()
    save_result(
        session,
        key=key,
        user_id=user_id,
        org_id=org_id,
        status="pending",
        body_hash=body_hash,
        headers_hash="...",
    )
    session.commit()

    # Process request...

    # Mark completed
    response_hash = hashlib.sha256(response_body.encode()).hexdigest()
    mark_completed(session, key, response_hash, "...")
    session.commit()
```

### Rate Limiting Example

```python
from backend.app.limits import check_rate_limit

# Check if request is allowed
result = check_rate_limit("user-123", "agent")

if not result.allowed:
    # Return 429 Too Many Requests
    raise HTTPException(
        status_code=429,
        detail="Rate limit exceeded",
        headers={"Retry-After": str(result.retry_after_seconds)}
    )

# Process request...
```

### Retention Example

```python
from backend.app.db.session import get_session_factory
from backend.app.db.retention import get_retention_summary, get_stale_agent_runs

factory = get_session_factory()
session = factory()

# Get summary of stale data
summary = get_retention_summary(session)
print(f"Stale agent runs: {summary['agent_runs']}")

# Get stale runs for deletion (later, not in PR2)
stmt = get_stale_agent_runs(session, retention_days=30)
stale_runs = session.execute(stmt).scalars().all()
# Later: delete these runs

session.close()
```

## Troubleshooting

### "No module named 'pgvector'"

```bash
pip install pgvector
```

### "relation does not exist"

Run migrations:

```bash
alembic upgrade head
```

### "could not connect to server"

Check PostgreSQL is running:

```bash
# Docker
docker ps | grep postgres

# Local
pg_isready
```

### "Connection refused" (Redis)

Check Redis is running:

```bash
# Docker
docker ps | grep redis

# Local
redis-cli ping
```

### Type errors from mypy

Ensure you're using Python 3.11+:

```bash
python --version
```

Install type stubs:

```bash
pip install types-python-dateutil
```

## What's Next?

After completing PR2 setup:

1. **Explore the database** using `psql` or a GUI tool
2. **Run tests** to verify everything works
3. **Review ORM models** in `backend/app/db/models/`
4. **Try the examples** above
5. **Read PR2_README.md** for detailed documentation

PR2 is library-only. PR3 will add FastAPI routes that use these components.

## Support

- **Documentation:** See `Docs/PR2_README.md` and `Docs/PR2_SUMMARY.md`
- **SPEC:** See `Docs/SPEC.md` for full system specification
- **Tests:** See `tests/integration/` for usage examples
