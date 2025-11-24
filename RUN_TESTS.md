# Running Tests Guide

## Quick Start

All tests should be run with the virtual environment activated.

### 1. Activate Virtual Environment (Required)
```bash
source venv/bin/activate
```

### 2. Run Tests

#### Run All Fixed Tests (Confirmed Passing)
```bash
# Selector tests (11 tests)
python -m pytest tests/unit/test_selector.py -v

# PR6 Happy Path tests (7 tests) 
python -m pytest tests/eval/test_pr6_happy_path.py -v

# Budget verification (1 test)
python -m pytest tests/unit/test_budget_verification.py -v

# Run all three together (19 tests - all passing)
python -m pytest tests/unit/test_selector.py tests/eval/test_pr6_happy_path.py tests/unit/test_budget_verification.py -v
```

#### Run Full Test Suite (Some tests may require additional setup)
```bash
python -m pytest -v
```

#### Run Specific Test Categories
```bash
# Unit tests only
python -m pytest tests/unit/ -v

# Integration tests only (requires PostgreSQL + other services)
python -m pytest tests/integration/ -v

# Evaluation tests only
python -m pytest tests/eval/ -v
```

### 3. Deactivate Virtual Environment (When Done)
```bash
deactivate
```

## Prerequisites for Integration Tests

Some integration tests require external services to be running:

### PostgreSQL Database
```bash
# Set test database URL
export TEST_POSTGRES_URL="postgresql://user:password@localhost:5432/keyveve_test"

# Create test database
createdb keyveve_test

# Run migrations
alembic upgrade head
```

### Environment Variables
```bash
# JWT Keys (required for auth tests)
export JWT_PRIVATE_KEY_PEM="<your-private-key>"
export JWT_PUBLIC_KEY_PEM="<your-public-key>"

# Or copy from .env file
source .env
```

### Redis (for rate limiting tests)
```bash
# Start Redis
redis-server

# Or with Docker
docker run -d -p 6379:6379 redis:latest
```

## Test Results Summary

### ✅ Confirmed Passing (19 tests)
- `tests/unit/test_selector.py` - All 11 tests passing
- `tests/eval/test_pr6_happy_path.py` - All 7 tests passing  
- `tests/unit/test_budget_verification.py` - 1 test passing

### 🔧 Requires Setup (Integration Tests)
Most integration tests will pass once PostgreSQL and environment variables are configured:
- `tests/integration/test_destinations_api.py`
- `tests/integration/test_knowledge_api.py`
- `tests/integration/test_plan_edit.py`
- And others...

## Troubleshooting

### "ModuleNotFoundError: No module named 'X'"
**Solution**: Make sure virtual environment is activated
```bash
source venv/bin/activate
```

### "Connection refused" or Database Errors
**Solution**: Ensure PostgreSQL is running and test database exists
```bash
# Check if PostgreSQL is running
pg_isready

# Create test database if it doesn't exist
createdb keyveve_test
```

### Auth/JWT Errors  
**Solution**: Ensure JWT keys are configured in environment
```bash
# Generate new keys if needed
./scripts/generate-jwt-keys.sh

# Export to environment
source .env
```

## CI/CD Note

For automated testing in CI/CD, ensure:
1. Virtual environment is created and activated
2. All dependencies are installed
3. PostgreSQL service is available
4. Environment variables are set
5. Test database is created and migrated

Example CI command:
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
export TEST_POSTGRES_URL="postgresql://user:password@localhost:5432/keyveve_test"
createdb keyveve_test
alembic upgrade head
python -m pytest -v
```
