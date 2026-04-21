#!/usr/bin/env python3
"""
Execute full Pipeline for the 50 BIPV5 tables.
This script runs the complete 9-node LangGraph pipeline end-to-end.
"""

import asyncio
import sys
from datetime import datetime

# Add backend to path
sys.path.insert(0, '/Users/leitao/Documents/trae_projects/Qoder-LoanFIBO')

from backend.app.services.pipeline_orchestrator import PipelineOrchestrator
from backend.app.services.pipeline_state import PipelineState, PipelinePhase
from backend.app.database import async_session_factory
from backend.app.models.mapping_job import MappingJob
from backend.app.models.table_registry import TableRegistry
from sqlalchemy import select, func
from loguru import logger


async def create_job() -> int:
    """Create a new mapping job for the 50 BIPV5 tables."""
    async with async_session_factory() as db:
        # Get total pending tables
        result = await db.execute(
            select(func.count()).select_from(TableRegistry)
            .where(
                TableRegistry.mapping_status == 'pending',
                TableRegistry.is_deleted == False
            )
        )
        total_tables = result.scalar()
        
        # Get unique database names
        result = await db.execute(
            select(TableRegistry.database_name).distinct()
            .where(TableRegistry.is_deleted == False)
        )
        databases = [row[0] for row in result.fetchall()]
        
        job = MappingJob(
            job_name=f"BIPV5_Full_Pipeline_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            scope_databases=databases,
            status='running',
            phase=PipelinePhase.PARSE_DDL,
            total_tables=total_tables,
            processed_tables=0,
        )
        db.add(job)
        await db.commit()
        await db.refresh(job)
        
        logger.info(f"Created job {job.id} for {total_tables} tables across {len(databases)} databases")
        return job.id


async def run_pipeline(job_id: int):
    """Run the complete pipeline."""
    logger.info(f"=" * 60)
    logger.info(f"Starting FULL PIPELINE execution for job_id={job_id}")
    logger.info(f"=" * 60)
    
    # Initialize state
    initial_state: PipelineState = {
        'job_id': job_id,
        'phase': PipelinePhase.PARSE_DDL.value,
        'current_batch': [],
        'revision_round': 0,
        'stop_requested': False,
        'logs': [],
    }
    
    # Create orchestrator and execute
    orchestrator = PipelineOrchestrator()
    
    try:
        result = await orchestrator.execute(initial_state)
        logger.info(f"=" * 60)
        logger.info(f"Pipeline completed successfully!")
        logger.info(f"Final phase: {result.get('phase')}")
        logger.info(f"Revision rounds: {result.get('revision_round', 0)}")
        logger.info(f"=" * 60)
        return result
    except Exception as e:
        logger.error(f"Pipeline failed: {str(e)}")
        raise


async def update_job_status(job_id: int, status: str):
    """Update job status after completion."""
    async with async_session_factory() as db:
        result = await db.execute(
            select(MappingJob).where(MappingJob.id == job_id)
        )
        job = result.scalar_one_or_none()
        if job:
            job.status = status
            if status == 'completed':
                job.phase = PipelinePhase.DONE.value
                job.completed_at = datetime.now()
            await db.commit()
            logger.info(f"Updated job {job_id} status to {status}")


async def print_final_stats():
    """Print final statistics."""
    async with async_session_factory() as db:
        # Table registry stats
        result = await db.execute(
            select(TableRegistry.mapping_status, func.count())
            .where(TableRegistry.is_deleted == False)
            .group_by(TableRegistry.mapping_status)
        )
        print("\n" + "=" * 60)
        print("FINAL STATISTICS")
        print("=" * 60)
        print("\nTable Registry Status:")
        for status, count in result.fetchall():
            print(f"  - {status}: {count}")
        
        # Table mapping count
        from backend.app.models.table_mapping import TableMapping
        result = await db.execute(
            select(func.count()).select_from(TableMapping)
            .where(TableMapping.is_deleted == False)
        )
        mapping_count = result.scalar()
        print(f"\nTable Mappings created: {mapping_count}")
        
        # Field mapping count
        from backend.app.models.table_mapping import FieldMapping
        result = await db.execute(
            select(func.count()).select_from(FieldMapping)
            .where(FieldMapping.is_deleted == False)
        )
        field_count = result.scalar()
        print(f"Field Mappings created: {field_count}")
        print("=" * 60)


async def main():
    """Main entry point."""
    logger.info("Starting full pipeline execution...")
    
    # Create job
    job_id = await create_job()
    
    try:
        # Run pipeline
        result = await run_pipeline(job_id)
        
        # Update job status
        await update_job_status(job_id, 'completed')
        
        # Print stats
        await print_final_stats()
        
        logger.info("\n✅ Full pipeline execution completed!")
        
    except Exception as e:
        logger.error(f"\n❌ Pipeline execution failed: {e}")
        await update_job_status(job_id, 'failed')
        raise


if __name__ == "__main__":
    asyncio.run(main())
