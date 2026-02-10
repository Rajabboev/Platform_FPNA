# FP&A Platform - Backend

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Configure environment:
```bash
cp .env.example .env
# Edit .env with your database credentials
```

3. Run the application:
```bash
uvicorn app.main:app --reload
```

4. Access API documentation:
- Swagger UI: http://localhost:8000/api/docs
- ReDoc: http://localhost:8000/api/redoc

## Project Structure

- `app/` - Main application code
  - `api/` - API route handlers
  - `models/` - Database models
  - `schemas/` - Pydantic schemas
  - `services/` - Business logic
  - `utils/` - Utility functions
  - `middleware/` - Custom middleware
- `tests/` - Test files
- `alembic/` - Database migrations
- `scripts/` - Utility scripts
