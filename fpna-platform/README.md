# FP&A Platform

AI-Powered Financial Planning & Analysis Platform

## Features

- Multi-level budget approval workflow
- Role-based access control (RBAC)
- Excel file upload for budget data
- RESTful API with FastAPI
- SQL Server database integration
- JWT authentication

## Quick Start

### Prerequisites

- Python 3.10+
- SQL Server 2017+
- ODBC Driver 17 for SQL Server

### Installation

1. Clone the repository
2. Install dependencies:
```bash
cd backend
pip install -r requirements.txt
```

3. Configure database:
```bash
# Copy and edit .env file
cp backend/.env.example backend/.env
```

4. Initialize database:
```bash
# Run SQL Server scripts
sqlcmd -S localhost -U sa -i backend/scripts/init_database.sql
```

5. Run the application:
```bash
cd backend
uvicorn app.main:app --reload
```

6. Access API docs: http://localhost:8000/api/docs

## Project Structure

```
fpna-platform/
├── backend/           # FastAPI backend
│   ├── app/          # Application code
│   ├── tests/        # Test files
│   └── scripts/      # Utility scripts
├── frontend/         # Frontend (future)
└── README.md
```

## Documentation

See `backend/README.md` for backend-specific documentation.

## License

Proprietary - Westminster International University in Tashkent
