"""ETL API - jobs CRUD, run, history, and FPNA table listing"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import List

from app.database import get_db, engine as app_engine
from app.models.etl_job import ETLJob, ETLRun
from app.models.dwh_connection import DWHConnection
from app.models.user import User
from app.schemas.etl import ETLJobCreate, ETLJobUpdate, ETLJobResponse, ETLRunResponse
from app.utils.dependencies import get_current_active_user
from app.services.etl_service import run_etl_job

router = APIRouter(prefix="/etl", tags=["etl"])


def _job_to_response(j: ETLJob) -> ETLJobResponse:
    return ETLJobResponse(
        id=j.id,
        name=j.name,
        description=j.description,
        source_type=j.source_type,
        source_connection_id=j.source_connection_id,
        source_schema=j.source_schema,
        source_table=j.source_table,
        target_type=j.target_type,
        target_connection_id=j.target_connection_id,
        target_schema=j.target_schema,
        target_table=j.target_table,
        column_mapping=j.column_mapping,
        create_target_if_missing=j.create_target_if_missing,
        load_mode=j.load_mode,
        is_active=j.is_active,
        created_at=j.created_at.isoformat() if j.created_at else None,
    )


def _run_to_response(r: ETLRun) -> ETLRunResponse:
    return ETLRunResponse(
        id=r.id,
        job_id=r.job_id,
        status=r.status,
        rows_extracted=r.rows_extracted or 0,
        rows_loaded=r.rows_loaded or 0,
        error_message=r.error_message,
        started_at=r.started_at.isoformat() if r.started_at else None,
        finished_at=r.finished_at.isoformat() if r.finished_at else None,
    )


@router.get("/fpna-tables")
def list_fpna_tables(
    current_user: User = Depends(get_current_active_user),
):
    """List tables in the FPNA app database (for source/target selection)."""
    with app_engine.connect() as conn:
        result = conn.execute(text("""
            SELECT TABLE_SCHEMA, TABLE_NAME
            FROM INFORMATION_SCHEMA.TABLES
            WHERE TABLE_TYPE = 'BASE TABLE'
            ORDER BY TABLE_SCHEMA, TABLE_NAME
        """))
        rows = result.fetchall()
    return [
        {"schema_name": r[0], "table_name": r[1], "full_name": f"{r[0]}.{r[1]}" if r[0] else r[1]}
        for r in rows
    ]


@router.get("/jobs", response_model=List[ETLJobResponse])
def list_jobs(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """List all ETL jobs."""
    jobs = db.query(ETLJob).order_by(ETLJob.name).all()
    return [_job_to_response(j) for j in jobs]


@router.post("/jobs", response_model=ETLJobResponse, status_code=status.HTTP_201_CREATED)
def create_job(
    payload: ETLJobCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Create a new ETL job."""
    if payload.source_type == "fpna_app" and payload.source_connection_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="fpna_app source cannot have connection_id")
    if payload.target_type == "fpna_app" and payload.target_connection_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="fpna_app target cannot have connection_id")
    if payload.source_type == "dwh_connection" and not payload.source_connection_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="dwh_connection source requires connection_id")
    if payload.target_type == "dwh_connection" and not payload.target_connection_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="dwh_connection target requires connection_id")

    if db.query(ETLJob).filter(ETLJob.name == payload.name).first():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Job name already exists")

    job = ETLJob(
        name=payload.name,
        description=payload.description,
        source_type=payload.source_type,
        source_connection_id=payload.source_connection_id,
        source_schema=payload.source_schema,
        source_table=payload.source_table,
        target_type=payload.target_type,
        target_connection_id=payload.target_connection_id,
        target_schema=payload.target_schema,
        target_table=payload.target_table,
        column_mapping=payload.column_mapping,
        create_target_if_missing=payload.create_target_if_missing,
        load_mode=payload.load_mode,
        created_by_user_id=current_user.id,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return _job_to_response(job)


@router.get("/jobs/{job_id}", response_model=ETLJobResponse)
def get_job(
    job_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Get job by ID."""
    job = db.query(ETLJob).filter(ETLJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return _job_to_response(job)


@router.patch("/jobs/{job_id}", response_model=ETLJobResponse)
def update_job(
    job_id: int,
    payload: ETLJobUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Update job."""
    job = db.query(ETLJob).filter(ETLJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    data = payload.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(job, k, v)
    db.commit()
    db.refresh(job)
    return _job_to_response(job)


@router.delete("/jobs/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_job(
    job_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Delete job."""
    job = db.query(ETLJob).filter(ETLJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    db.delete(job)
    db.commit()
    return None


@router.post("/jobs/{job_id}/run", response_model=ETLRunResponse)
def run_job(
    job_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Run ETL job now. Returns run result (status success/failed, rows, error_message)."""
    job = db.query(ETLJob).filter(ETLJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="ETL job not found. Refresh the job list or create the job again.")
    if not job.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Job is inactive")
    try:
        run = run_etl_job(job, db)
        return _run_to_response(run)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/jobs/{job_id}/runs", response_model=List[ETLRunResponse])
def list_job_runs(
    job_id: int,
    limit: int = 20,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """List run history for a job."""
    job = db.query(ETLJob).filter(ETLJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    runs = db.query(ETLRun).filter(ETLRun.job_id == job_id).order_by(ETLRun.started_at.desc()).limit(limit).all()
    return [_run_to_response(r) for r in runs]
