"""Mapping LLM - Call LLM to execute table-to-FIBO class mapping."""

import json
import asyncio
from typing import Optional, List, Dict, Any
from loguru import logger
from langchain_openai import ChatOpenAI
from langchain.schema import SystemMessage, HumanMessage
from sqlalchemy import select

from backend.app.config import settings
from backend.app.services.pipeline_state import PipelineState
from backend.app.services.ttl_indexer import search_candidates
from backend.app.prompts.mapping_prompt import (
    MAPPING_SYSTEM_PROMPT,
    build_mapping_prompt,
    MAPPING_OUTPUT_SCHEMA
)
from backend.app.models.table_registry import TableRegistry
from backend.app.models.table_mapping import TableMapping, FieldMapping
from backend.app.models.llm_call_log import LLMCallLog
from backend.app.database import async_session_factory


# Semaphore for concurrency control
mapping_semaphore = asyncio.Semaphore(settings.MAX_CONCURRENCY)

# Constants: DDL preview lengths used in keyword building and prompt construction
DDL_KEYWORD_PREVIEW_LEN = 200   # chars of raw_ddl used for vector search keywords
DDL_COMMENT_PREVIEW_LEN = 100   # chars of raw_ddl used as table comment in prompt

async def mapping_llm_node(state: PipelineState) -> PipelineState:
    """Call LLM to map current table to FIBO class.
    
    This node:
    1. Takes table DDL and candidate FIBO classes
    2. Calls qwen-long model for mapping
    3. Parses JSON response
    4. Inserts into table_mapping and field_mapping
    """
    logger.info(f"[mapping_llm_node] Executing LLM mapping for batch")
    
    job_id = state['job_id']
    current_batch = state.get('current_batch', [])
    
    if not current_batch:
        logger.info("[mapping_llm_node] No tables in batch, skipping")
        return state
    
    # Process tables concurrently with semaphore
    tasks = []
    for table_id in current_batch:
        task = process_single_table(job_id, table_id)
        tasks.append(task)
    
    # Wait for all mappings to complete
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Clear batch after processing
    state['current_batch'] = []
    
    # Check for errors
    errors = [r for r in results if isinstance(r, Exception)]
    if errors:
        logger.error(f"[mapping_llm_node] {len(errors)} tables failed to map")
    
    logger.info(f"[mapping_llm_node] LLM mapping completed: {len(results)} tables processed")
    return state


async def process_single_table(job_id: int, table_registry_id: int) -> Dict[str, Any]:
    """Process mapping for a single table.
    
    Execution stages (semaphore ONLY wraps LLM call):
      1. DB query      — no rate-limit, high parallelism allowed
      2. Vector search — no rate-limit, high parallelism allowed
      3. LLM call      — guarded by mapping_semaphore (QPS control)
      4. Save result   — no rate-limit, high parallelism allowed
    """
    # -----------------------------------------------------------------
    # Stage 1 & 2: DB query + vector search (outside semaphore)
    # -----------------------------------------------------------------
    async with async_session_factory() as db:
        table_registry = await db.get(TableRegistry, table_registry_id)
        if not table_registry:
            logger.error(f"Table registry not found: {table_registry_id}")
            return {"error": "Table not found"}

        # Search for candidate classes
        keywords = f"{table_registry.table_name} {table_registry.raw_ddl[:DDL_KEYWORD_PREVIEW_LEN]}"
        candidates = await search_candidates(keywords, limit=settings.CANDIDATE_LIMIT)

        if not candidates:
            logger.warning(f"No candidates found for table: {table_registry.table_name}")
            await mark_unmappable(db, job_id, table_registry)
            return {"status": "unmappable", "reason": "No candidates"}

        # Build prompt (needs table_registry data, must be inside session scope)
        prompt = build_mapping_prompt(
            database_name=table_registry.database_name,
            table_name=table_registry.table_name,
            table_comment=table_registry.raw_ddl[:DDL_COMMENT_PREVIEW_LEN],
            fields=table_registry.parsed_fields,
            candidate_classes=candidates
        )
        # Capture table_name before session closes (used in log messages below)
        table_name_snapshot = table_registry.table_name

    # -----------------------------------------------------------------
    # Stage 3: LLM call — ONLY this block is rate-limited
    # -----------------------------------------------------------------
    llm = get_mapping_llm()
    messages = [
        SystemMessage(content=MAPPING_SYSTEM_PROMPT),
        HumanMessage(content=prompt)
    ]
    start_time = asyncio.get_event_loop().time()

    try:
        async with mapping_semaphore:
            response = await llm.ainvoke(messages)

        response_text = response.content
        latency_ms = int((asyncio.get_event_loop().time() - start_time) * 1000)

        # Parse JSON response
        mapping_result = parse_mapping_response(response_text)

        if not mapping_result:
            async with async_session_factory() as db:
                # Re-fetch registry for save operations
                table_registry = await db.get(TableRegistry, table_registry_id)
                await handle_parse_error(db, job_id, table_registry, response_text)
            return {"status": "parse_error"}

        # -----------------------------------------------------------------
        # uncertainty_exit check (llm-caller principle 6)
        # -----------------------------------------------------------------
        if mapping_result.get("uncertainty_exit"):
            exit_info = mapping_result["uncertainty_exit"]
            logger.warning(
                f"LLM uncertainty for table {table_name_snapshot}: {exit_info.get('reason', 'unknown')}"
            )
            async with async_session_factory() as db:
                table_registry = await db.get(TableRegistry, table_registry_id)
                await handle_uncertainty(db, job_id, table_registry, exit_info)
            return {"status": "uncertainty", "reason": exit_info.get("reason", "")}

        # -----------------------------------------------------------------
        # Stage 4: Save result (outside semaphore)
        # -----------------------------------------------------------------
        async with async_session_factory() as db:
            table_registry = await db.get(TableRegistry, table_registry_id)
            await save_mapping_result(
                db=db,
                job_id=job_id,
                table_registry=table_registry,
                mapping_result=mapping_result,
                model_used=settings.MAPPING_MODEL,
                tokens=response.usage.total_tokens if hasattr(response, 'usage') else 0,
                latency_ms=latency_ms,
            )

        return {"status": "success", "mapping": mapping_result}

    except Exception as e:
        logger.error(f"LLM call failed for table {table_name_snapshot}: {str(e)}")
        # Try fallback model
        async with async_session_factory() as db:
            table_registry = await db.get(TableRegistry, table_registry_id)
            return await try_fallback_mapping(db, job_id, table_registry, prompt, str(e))


async def try_fallback_mapping(db, job_id: int, table_registry: TableRegistry, 
                                prompt: str, original_error: str) -> Dict[str, Any]:
    """Try fallback model if primary mapping model fails."""
    logger.info(f"Trying fallback model for table: {table_registry.table_name}")
    
    try:
        llm = ChatOpenAI(
            model=settings.MAPPING_FALLBACK_MODEL,  # Dedicated fallback config
            openai_api_key=settings.DASHSCOPE_API_KEY,
            openai_api_base=settings.DASHSCOPE_API_BASE,
            temperature=settings.LLM_TEMPERATURE,
            max_tokens=settings.LLM_MAX_TOKENS,
        )
        
        start_time = asyncio.get_event_loop().time()
        
        messages = [
            SystemMessage(content=MAPPING_SYSTEM_PROMPT),
            HumanMessage(content=prompt)
        ]
        
        response = await llm.ainvoke(messages)
        response_text = response.content
        
        latency_ms = int((asyncio.get_event_loop().time() - start_time) * 1000)
        
        mapping_result = parse_mapping_response(response_text)
        
        if mapping_result:
            await save_mapping_result(db, job_id, table_registry, mapping_result,
                                     settings.CRITIC_MODEL, 
                                     response.usage.total_tokens if hasattr(response, 'usage') else 0,
                                     latency_ms, is_fallback=True)
            return {"status": "success_fallback", "mapping": mapping_result}
        else:
            await handle_parse_error(db, job_id, table_registry, response_text, is_fallback=True)
            return {"status": "parse_error_fallback"}
            
    except Exception as e:
        logger.error(f"Fallback also failed: {str(e)}")
        await mark_llm_error(db, job_id, table_registry, f"Original: {original_error}, Fallback: {str(e)}")
        return {"status": "error", "error": str(e)}


def parse_mapping_response(response_text: str) -> Optional[Dict[str, Any]]:
    """Parse LLM JSON response."""
    try:
        # Try to extract JSON from response
        # LLM might wrap JSON in markdown code blocks
        json_str = response_text
        if "```json" in response_text:
            json_str = response_text.split("```json")[1].split("```")[0]
        elif "```" in response_text:
            json_str = response_text.split("```")[1].split("```")[0]
        
        json_str = json_str.strip()
        result = json.loads(json_str)
        
        # Basic validation:
        # - uncertainty_exit is always valid (LLM signals it cannot map with confidence)
        # - normal mapping must have 'mappable' and 'field_mappings'
        if "uncertainty_exit" in result:
            return result  # Valid uncertainty response
        if "mappable" not in result or "field_mappings" not in result:
            logger.error("Invalid mapping response: missing required fields")
            return None
        
        return result
        
    except json.JSONDecodeError as e:
        logger.error(f"JSON parse error: {str(e)}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error parsing response: {str(e)}")
        return None


async def save_mapping_result(db, job_id: int, table_registry: TableRegistry,
                               mapping_result: Dict, model_used: str, 
                               tokens: int, latency_ms: int, is_fallback: bool = False):
    """Save mapping result to database."""
    # Create table mapping
    table_mapping = TableMapping(
        job_id=job_id,
        database_name=table_registry.database_name,
        table_name=table_registry.table_name,
        fibo_class_uri=mapping_result.get('fibo_class_uri'),
        confidence_level=mapping_result.get('confidence_level', 'UNRESOLVED'),
        mapping_reason=mapping_result.get('mapping_reason', ''),
        mapping_status='mapped' if mapping_result.get('mappable') else 'unmappable',
        review_status='pending',
        model_used=model_used,
    )
    db.add(table_mapping)
    await db.flush()  # Get ID
    
    # Create field mappings
    for field_mapping in mapping_result.get('field_mappings', []):
        field_map = FieldMapping(
            table_mapping_id=table_mapping.id,
            field_name=field_mapping['field_name'],
            fibo_property_uri=field_mapping.get('fibo_property_uri'),
            confidence_level=field_mapping.get('confidence_level', 'UNRESOLVED'),
            mapping_reason=field_mapping.get('mapping_reason', ''),
        )
        db.add(field_map)
    
    # Update table registry status
    table_registry.mapping_status = 'mapped' if mapping_result.get('mappable') else 'unmappable'
    
    # Log LLM call
    llm_log = LLMCallLog(
        job_id=job_id,
        table_mapping_id=table_mapping.id,
        call_type='mapping',
        model_name=model_used,
        prompt_tokens=tokens // 2,  # Approximate
        completion_tokens=tokens // 2,
        latency_ms=latency_ms,
        is_fallback=is_fallback,
    )
    db.add(llm_log)
    
    await db.commit()


async def mark_unmappable(db, job_id: int, table_registry: TableRegistry):
    """Mark table as unmappable."""
    table_mapping = TableMapping(
        job_id=job_id,
        database_name=table_registry.database_name,
        table_name=table_registry.table_name,
        mapping_status='unmappable',
        review_status='approved',  # No need to review
    )
    db.add(table_mapping)
    
    table_registry.mapping_status = 'unmappable'
    await db.commit()


async def handle_parse_error(db, job_id: int, table_registry: TableRegistry, 
                             raw_response: str, is_fallback: bool = False):
    """Handle JSON parse error."""
    table_mapping = TableMapping(
        job_id=job_id,
        database_name=table_registry.database_name,
        table_name=table_registry.table_name,
        mapping_status='llm_parse_error',
        review_status='manual_review_required',
    )
    db.add(table_mapping)
    await db.flush()
    
    # Log error
    llm_log = LLMCallLog(
        job_id=job_id,
        table_mapping_id=table_mapping.id,
        call_type='mapping',
        model_name=settings.MAPPING_MODEL if not is_fallback else settings.MAPPING_FALLBACK_MODEL,
        is_fallback=is_fallback,
        error_message=f"JSON parse error. Raw response: {raw_response[:500]}",
    )
    db.add(llm_log)
    
    table_registry.mapping_status = 'llm_parse_error'
    await db.commit()


async def handle_uncertainty(db, job_id: int, table_registry: TableRegistry, exit_info: Dict[str, Any]):
    """Handle LLM uncertainty_exit response (llm-caller principle 6)."""
    table_mapping = TableMapping(
        job_id=job_id,
        database_name=table_registry.database_name,
        table_name=table_registry.table_name,
        mapping_status='llm_uncertainty',
        review_status='manual_review_required',
    )
    db.add(table_mapping)
    await db.flush()

    llm_log = LLMCallLog(
        job_id=job_id,
        table_mapping_id=table_mapping.id,
        call_type='mapping',
        model_name=settings.MAPPING_MODEL,
        error_message=f"LLM uncertainty: {exit_info.get('reason', 'unknown')} (confidence={exit_info.get('confidence', 'N/A')})",
    )
    db.add(llm_log)

    table_registry.mapping_status = 'llm_uncertainty'
    await db.commit()


async def mark_llm_error(db, job_id: int, table_registry: TableRegistry, error_message: str):
    """Mark table as failed due to LLM error."""
    table_mapping = TableMapping(
        job_id=job_id,
        database_name=table_registry.database_name,
        table_name=table_registry.table_name,
        mapping_status='llm_parse_error',
        review_status='manual_review_required',
    )
    db.add(table_mapping)
    await db.flush()
    
    llm_log = LLMCallLog(
        job_id=job_id,
        table_mapping_id=table_mapping.id,
        call_type='mapping',
        model_name=settings.MAPPING_MODEL,
        error_message=error_message[:500],
    )
    db.add(llm_log)
    
    table_registry.mapping_status = 'llm_parse_error'
    await db.commit()


async def revision_node(state: PipelineState) -> PipelineState:
    """Call LLM to revise mapping based on critic feedback.
    
    This node:
    1. Takes original mapping + critic reviews
    2. Calls qwen-max for revision
    3. Updates table_mapping and field_mapping
    4. Increments revision_count
    5. Logs revision history
    """
    job_id = state['job_id']
    revision_round = state['revision_round']
    
    logger.info(f"[revision_node] Executing LLM revision for job_id={job_id}, round={revision_round}")
    
    async with async_session_factory() as db:
        # Fetch mappings that need revision
        result = await db.execute(
            select(TableMapping).where(
                TableMapping.job_id == job_id,
                TableMapping.review_status == 'needs_revision',
                TableMapping.revision_count < settings.MAX_REVISION_ROUNDS
            )
        )
        mappings_to_revise = result.scalars().all()
        
        if not mappings_to_revise:
            logger.info("[revision_node] No mappings to revise")
            return state
        
        logger.info(f"[revision_node] Found {len(mappings_to_revise)} mappings to revise")
        
        # Process each mapping
        tasks = []
        for mapping in mappings_to_revise:
            task = revise_single_mapping(db, mapping, revision_round)
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Count results
        revised = sum(1 for r in results if r == 'revised')
        unchanged = sum(1 for r in results if r == 'unchanged')
        errors = sum(1 for r in results if isinstance(r, Exception))
        
        logger.info(f"[revision_node] Revision completed: revised={revised}, unchanged={unchanged}, errors={errors}")
    
    return state


async def revise_single_mapping(db, table_mapping: TableMapping, revision_round: int) -> str:
    """Revise a single table mapping based on critic feedback.
    
    Returns:
        'revised', 'unchanged', or 'error'
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
        
        # Get current field mappings
        result = await db.execute(
            select(FieldMapping).where(
                FieldMapping.table_mapping_id == table_mapping.id
            )
        )
        field_mappings = result.scalars().all()
        
        # Get must_fix issues
        from backend.app.models.mapping_review import MappingReview
        result = await db.execute(
            select(MappingReview).where(
                MappingReview.table_mapping_id == table_mapping.id,
                MappingReview.is_must_fix == True,
                MappingReview.is_resolved == False
            )
        )
        must_fix_issues = result.scalars().all()
        
        if not must_fix_issues:
            logger.info(f"No must_fix issues for {table_mapping.table_name}, skipping revision")
            return 'unchanged'
        
        # Build current mapping dict
        current_mapping = {
            'fibo_class_uri': table_mapping.fibo_class_uri,
            'confidence_level': table_mapping.confidence_level,
            'mapping_reason': table_mapping.mapping_reason,
            'field_mappings': [
                {
                    'field_name': fm.field_name,
                    'fibo_property_uri': fm.fibo_property_uri,
                    'confidence_level': fm.confidence_level,
                    'mapping_reason': fm.mapping_reason,
                }
                for fm in field_mappings
            ]
        }
        
        # Format issues for prompt
        issues_list = [
            {
                'scope': 'table' if not issue.field_mapping_id else 'field',
                'field_name': None,  # TODO: Get field name if field-level
                'issue_type': issue.issue_type,
                'severity': issue.severity,
                'issue_description': issue.issue_description,
                'suggested_fix': issue.suggested_fix,
            }
            for issue in must_fix_issues
        ]
        
        # Search for alternative candidates
        keywords = f"{table_mapping.table_name} {table_registry.raw_ddl[:200]}"
        from backend.app.services.ttl_indexer import search_candidates
        candidate_classes = await search_candidates(keywords, limit=10)
        
        # Build revision prompt
        from backend.app.prompts.revision_prompt import build_revision_prompt
        prompt = build_revision_prompt(
            database_name=table_mapping.database_name,
            table_name=table_mapping.table_name,
            table_comment=table_registry.raw_ddl[:200],
            fields=table_registry.parsed_fields,
            current_mapping=current_mapping,
            must_fix_issues=issues_list,
            candidate_classes=candidate_classes
        )
        
        # Call LLM (qwen-max for revision)
        llm = ChatOpenAI(
            model=settings.REVISION_MODEL,
            openai_api_key=settings.DASHSCOPE_API_KEY,
            openai_api_base=settings.DASHSCOPE_API_BASE,
            temperature=settings.LLM_TEMPERATURE,
            max_tokens=settings.LLM_MAX_TOKENS,
        )
        
        start_time = asyncio.get_event_loop().time()
        
        from backend.app.prompts.revision_prompt import REVISION_SYSTEM_PROMPT
        messages = [
            SystemMessage(content=REVISION_SYSTEM_PROMPT),
            HumanMessage(content=prompt)
        ]
        
        response = await llm.ainvoke(messages)
        response_text = response.content
        
        latency_ms = int((asyncio.get_event_loop().time() - start_time) * 1000)
        
        # Parse revision response
        revision_result = parse_revision_response(response_text)
        
        if not revision_result:
            logger.error(f"Failed to parse revision response for {table_mapping.table_name}")
            return 'error'
        
        # Save revision results
        await save_revision_result(
            db, table_mapping, field_mappings, revision_result,
            revision_round, latency_ms,
            response.usage.total_tokens if hasattr(response, 'usage') else 0,
            must_fix_issues
        )
        
        return 'revised' if revision_result.get('revised') else 'unchanged'
        
    except Exception as e:
        logger.error(f"Revision failed for {table_mapping.table_name}: {str(e)}")
        return 'error'


def parse_revision_response(response_text: str) -> Optional[Dict[str, Any]]:
    """Parse revision JSON response."""
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
        if "revised" not in result or "field_mappings" not in result:
            logger.error("Invalid revision response: missing required fields")
            return None
        
        return result
        
    except json.JSONDecodeError as e:
        logger.error(f"JSON parse error in revision response: {str(e)}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error parsing revision response: {str(e)}")
        return None


async def save_revision_result(
    db, table_mapping: TableMapping, field_mappings: List[FieldMapping],
    revision_result: Dict, revision_round: int, latency_ms: int,
    tokens: int, resolved_issues: List
):
    """Save revision result to database."""
    from backend.app.models.mapping_review import MappingRevisionLog
    
    # Record previous state
    prev_class_uri = table_mapping.fibo_class_uri
    prev_confidence = table_mapping.confidence_level
    
    # Update table mapping if revised
    if revision_result.get('revised'):
        table_mapping.fibo_class_uri = revision_result.get('fibo_class_uri', table_mapping.fibo_class_uri)
        table_mapping.confidence_level = revision_result.get('confidence_level', table_mapping.confidence_level)
        table_mapping.mapping_reason = revision_result.get('mapping_reason', table_mapping.mapping_reason)
        table_mapping.revision_count += 1
        table_mapping.review_status = 'pending'  # Reset for re-review
    
    # Update field mappings
    field_changes = []
    for revised_fm in revision_result.get('field_mappings', []):
        field_name = revised_fm['field_name']
        
        # Find matching field mapping
        for fm in field_mappings:
            if fm.field_name == field_name:
                if revised_fm.get('is_revised'):
                    # Record change
                    field_changes.append({
                        'field_name': field_name,
                        'prev_property_uri': fm.fibo_property_uri,
                        'new_property_uri': revised_fm.get('fibo_property_uri'),
                        'prev_confidence': fm.confidence_level,
                        'new_confidence': revised_fm.get('confidence_level'),
                        'revision_note': revised_fm.get('revision_note'),
                    })
                    
                    # Update field mapping
                    fm.fibo_property_uri = revised_fm.get('fibo_property_uri', fm.fibo_property_uri)
                    fm.confidence_level = revised_fm.get('confidence_level', fm.confidence_level)
                    fm.mapping_reason = revised_fm.get('mapping_reason', fm.mapping_reason)
                break
    
    # Mark resolved issues
    for issue in resolved_issues:
        issue.is_resolved = True
    
    # Log revision history
    revision_log = MappingRevisionLog(
        table_mapping_id=table_mapping.id,
        revision_round=revision_round,
        model_used=settings.REVISION_MODEL,
        prompt_tokens=tokens // 2,
        completion_tokens=tokens // 2,
        prev_fibo_class_uri=prev_class_uri,
        prev_confidence=prev_confidence,
        new_fibo_class_uri=table_mapping.fibo_class_uri,
        new_confidence=table_mapping.confidence_level,
        field_changes=field_changes if field_changes else None,
        resolved_review_ids=[issue.id for issue in resolved_issues],
    )
    db.add(revision_log)
    
    # Log LLM call
    llm_log = LLMCallLog(
        job_id=table_mapping.job_id,
        table_mapping_id=table_mapping.id,
        call_type='revision',
        model_name=settings.REVISION_MODEL,
        prompt_tokens=tokens // 2,
        completion_tokens=tokens // 2,
        latency_ms=latency_ms,
    )
    db.add(llm_log)
    
    await db.commit()
    
    logger.info(f"Revision saved for {table_mapping.table_name}: " +
                f"class_changed={prev_class_uri != table_mapping.fibo_class_uri}, " +
                f"fields_changed={len(field_changes)}")


def get_mapping_llm() -> ChatOpenAI:
    """Get LLM instance for mapping (qwen-long)."""
    return ChatOpenAI(
        model=settings.MAPPING_MODEL,
        openai_api_key=settings.DASHSCOPE_API_KEY,
        openai_api_base=settings.DASHSCOPE_API_BASE,
        temperature=settings.LLM_TEMPERATURE,
        max_tokens=settings.LLM_MAX_TOKENS,
        request_timeout=settings.LLM_TIMEOUT,
        max_retries=settings.LLM_MAX_RETRIES,
    )
