"""Critic Agent - Review and validate mapping results."""

import json
import asyncio
from typing import Optional, List, Dict, Any
from loguru import logger
from langchain_openai import ChatOpenAI
from langchain.schema import SystemMessage, HumanMessage
from sqlalchemy import select, func, update

from backend.app.config import settings
from backend.app.services.pipeline_state import PipelineState
from backend.app.services.ttl_indexer import get_properties_for_class
from backend.app.prompts.critic_prompt import (
    CRITIC_SYSTEM_PROMPT,
    build_critic_prompt,
    CRITIC_OUTPUT_SCHEMA
)
from backend.app.models.table_registry import TableRegistry
from backend.app.models.table_mapping import TableMapping, FieldMapping
from backend.app.models.ontology_index import OntologyClassIndex
from backend.app.models.mapping_review import MappingReview
from backend.app.models.llm_call_log import LLMCallLog
from backend.app.database import async_session_factory


async def critic_node(state: PipelineState) -> PipelineState:
    """Review mapped tables and validate quality.
    
    This node:
    1. Fetches all table_mapping with review_status='pending'
    2. Validates semantic accuracy, domain/range compliance, over-generalization
    3. Writes review results to mapping_review table
    4. Updates review_status based on severity
    """
    job_id = state['job_id']
    logger.info(f"[critic_node] Starting critic review for job_id={job_id}")
    
    async with async_session_factory() as db:
        # Fetch pending mappings
        result = await db.execute(
            select(TableMapping).where(
                TableMapping.job_id == job_id,
                TableMapping.mapping_status == 'mapped',
                TableMapping.review_status == 'pending'
            )
        )
        pending_mappings = result.scalars().all()
        
        if not pending_mappings:
            logger.info("[critic_node] No pending mappings to review")
            return state
        
        logger.info(f"[critic_node] Found {len(pending_mappings)} pending mappings")
        
        # Process each mapping
        tasks = []
        for mapping in pending_mappings:
            task = review_single_mapping(db, mapping, state['revision_round'])
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Count results
        approved = sum(1 for r in results if r == 'approved')
        needs_revision = sum(1 for r in results if r == 'needs_revision')
        errors = sum(1 for r in results if isinstance(r, Exception))
        
        logger.info(f"[critic_node] Review completed: approved={approved}, needs_revision={needs_revision}, errors={errors}")
    
    return state


async def review_single_mapping(db, table_mapping: TableMapping, review_round: int) -> str:
    """Review a single table mapping.
    
    Returns:
        'approved', 'approved_with_suggestions', 'needs_revision', or 'error'
    """
    try:
        # Get table registry info
        table_registry = await db.execute(
            select(TableRegistry).where(
                TableRegistry.database_name == table_mapping.database_name,
                TableRegistry.table_name == table_mapping.table_name
            )
        )
        table_registry = table_registry.scalar_one_or_none()
        
        if not table_registry:
            logger.error(f"Table registry not found: {table_mapping.database_name}.{table_mapping.table_name}")
            return 'error'
        
        # Get field mappings
        result = await db.execute(
            select(FieldMapping).where(
                FieldMapping.table_mapping_id == table_mapping.id
            )
        )
        field_mappings = result.scalars().all()
        
        # Get mapped class info
        class_result = await db.execute(
            select(OntologyClassIndex).where(
                OntologyClassIndex.class_uri == table_mapping.fibo_class_uri
            )
        )
        class_info = class_result.scalar_one_or_none()
        
        # Get available properties for this class
        available_properties = []
        if table_mapping.fibo_class_uri:
            available_properties = await get_properties_for_class(table_mapping.fibo_class_uri)
        
        # Build prompt
        prompt = build_critic_prompt(
            database_name=table_mapping.database_name,
            table_name=table_mapping.table_name,
            table_comment=table_registry.raw_ddl[:200] if table_registry else '',
            fields=table_registry.parsed_fields if table_registry else [],
            mapped_class_uri=table_mapping.fibo_class_uri or '',
            mapped_class_label_zh=class_info.label_zh if class_info else '',
            mapped_class_comment_zh=class_info.comment_zh if class_info else '',
            field_mappings=[{
                'field_name': fm.field_name,
                'fibo_property_uri': fm.fibo_property_uri,
                'confidence_level': fm.confidence_level,
            } for fm in field_mappings],
            available_properties=available_properties
        )
        
        # Call LLM
        llm = get_critic_llm()
        start_time = asyncio.get_event_loop().time()
        
        messages = [
            SystemMessage(content=CRITIC_SYSTEM_PROMPT),
            HumanMessage(content=prompt)
        ]
        
        response = await llm.ainvoke(messages)
        response_text = response.content
        
        latency_ms = int((asyncio.get_event_loop().time() - start_time) * 1000)
        
        # Parse response
        review_result = parse_critic_response(response_text)
        
        if not review_result:
            logger.error(f"Failed to parse critic response for {table_mapping.table_name}")
            await mark_review_error(db, table_mapping, response_text[:500])
            return 'error'
        
        # Save review results
        await save_review_results(db, table_mapping, review_result, review_round, 
                                  latency_ms, response.usage.total_tokens if hasattr(response, 'usage') else 0)
        
        return review_result.get('overall_status', 'needs_revision')
        
    except Exception as e:
        logger.error(f"Critic review failed for {table_mapping.table_name}: {str(e)}")
        return 'error'


def parse_critic_response(response_text: str) -> Optional[Dict[str, Any]]:
    """Parse critic JSON response."""
    try:
        # Extract JSON from markdown code blocks if present
        json_str = response_text
        if "```json" in response_text:
            json_str = response_text.split("```json")[1].split("```")[0]
        elif "```" in response_text:
            json_str = response_text.split("```")[1].split("```")[0]
        
        json_str = json_str.strip()
        result = json.loads(json_str)
        
        # Basic validation
        if "issues" not in result or "overall_status" not in result:
            logger.error("Invalid critic response: missing required fields")
            return None
        
        return result
        
    except json.JSONDecodeError as e:
        logger.error(f"JSON parse error in critic response: {str(e)}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error parsing critic response: {str(e)}")
        return None


async def save_review_results(db, table_mapping: TableMapping, review_result: Dict, 
                               review_round: int, latency_ms: int, tokens: int):
    """Save review results to database."""
    issues = review_result.get('issues', [])
    overall_status = review_result.get('overall_status', 'needs_revision')
    
    # Create review records for each issue
    for issue in issues:
        review = MappingReview(
            table_mapping_id=table_mapping.id,
            field_mapping_id=None,  # TODO: Link to field if scope=field
            review_round=review_round,
            issue_type=issue['issue_type'],
            severity=issue['severity'],
            is_must_fix=issue['is_must_fix'],
            issue_description=issue['issue_description'],
            suggested_fix=issue.get('suggested_fix'),
        )
        db.add(review)
    
    # Update table mapping review status
    table_mapping.review_status = overall_status
    
    # Log LLM call
    llm_log = LLMCallLog(
        job_id=table_mapping.job_id,
        table_mapping_id=table_mapping.id,
        call_type='critic',
        model_name=settings.CRITIC_MODEL,
        prompt_tokens=tokens // 2,
        completion_tokens=tokens // 2,
        latency_ms=latency_ms,
    )
    db.add(llm_log)
    
    await db.commit()


async def mark_review_error(db, table_mapping: TableMapping, error_message: str):
    """Mark review as failed."""
    table_mapping.review_status = 'manual_review_required'
    
    llm_log = LLMCallLog(
        job_id=table_mapping.job_id,
        table_mapping_id=table_mapping.id,
        call_type='critic',
        model_name=settings.CRITIC_MODEL,
        error_message=error_message[:500],
    )
    db.add(llm_log)
    
    await db.commit()


async def check_revision_node(state: PipelineState) -> PipelineState:
    """Check if revision is needed.
    
    This node:
    1. Checks for must_fix issues (P0/P1)
    2. Checks revision_count < 3
    3. Routes to revision_node or report_node
    """
    job_id = state['job_id']
    revision_round = state['revision_round']
    
    logger.info(f"[check_revision_node] Checking revision for job_id={job_id}, round={revision_round}")
    
    # Check if max revisions reached
    if revision_round >= settings.MAX_REVISION_ROUNDS:
        logger.info(f"[check_revision_node] Max revisions ({settings.MAX_REVISION_ROUNDS}) reached")
        # Mark remaining needs_revision as manual_review_required
        await mark_exceeded_revisions(job_id)
        return state
    
    async with async_session_factory() as db:
        # Count must_fix issues
        result = await db.execute(
            select(func.count(MappingReview.id)).where(
                MappingReview.table_mapping_id.in_(
                    select(TableMapping.id).where(
                        TableMapping.job_id == job_id,
                        TableMapping.review_status == 'needs_revision'
                    )
                ),
                MappingReview.is_must_fix == True,
                MappingReview.is_resolved == False
            )
        )
        must_fix_count = result.scalar()
        
        logger.info(f"[check_revision_node] Found {must_fix_count} unresolved must_fix issues")
        
        if must_fix_count == 0:
            logger.info("[check_revision_node] No must_fix issues, proceeding to report")
        else:
            logger.info(f"[check_revision_node] {must_fix_count} must_fix issues need revision")
    
    # Increment revision round
    state['revision_round'] = revision_round + 1
    
    return state


async def mark_exceeded_revisions(job_id: int):
    """Mark tables that exceeded max revisions as manual review required."""
    async with async_session_factory() as db:
        await db.execute(
            update(TableMapping).where(
                TableMapping.job_id == job_id,
                TableMapping.review_status == 'needs_revision',
                TableMapping.revision_count >= settings.MAX_REVISION_ROUNDS
            ).values(
                review_status='manual_review_required'
            )
        )
        await db.commit()


def get_critic_llm() -> ChatOpenAI:
    """Get LLM instance for critic (qwen-max)."""
    return ChatOpenAI(
        model=settings.CRITIC_MODEL,
        openai_api_key=settings.DASHSCOPE_API_KEY,
        openai_api_base=settings.DASHSCOPE_API_BASE,
        temperature=settings.LLM_TEMPERATURE,
        max_tokens=settings.LLM_MAX_TOKENS,
        request_timeout=settings.LLM_TIMEOUT,
        max_retries=settings.LLM_MAX_RETRIES,
    )
