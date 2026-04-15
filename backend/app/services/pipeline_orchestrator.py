"""
Pipeline Orchestrator - LangGraph Workflow for DDL-FIBO Mapping

This module defines the LangGraph state machine that orchestrates the entire mapping pipeline:
1. DDL Parsing
2. TTL Indexing
3. Batch Mapping (concurrent)
4. Critic Review (batch)
5. Revision Loop (up to 3 rounds)
6. Report Generation
"""

from typing import Optional
from loguru import logger
from langgraph.graph import StateGraph, END
from sqlalchemy import select

from backend.app.config import settings
from backend.app.database import async_session_factory
from backend.app.services.pipeline_state import PipelineState, PipelinePhase


def route_after_mapping(state: PipelineState) -> str:
    """After mapping_llm_node clears the batch, always return to fetch_batch.

    fetch_batch_node is responsible for deciding whether to continue loading
    more pending tables (-> retrieve_candidates) or move on to critic (-> critic)
    once no pending tables remain.
    """
    return "fetch_batch"


def route_after_fetch_batch(state: PipelineState) -> str:
    """After fetch_batch_node, route based on whether any pending tables were found."""
    if state.get("current_batch"):
        return "retrieve_candidates"
    return "critic"


def route_after_revision_check(state: PipelineState) -> str:
    """Route after revision check: revise or finish."""
    # If revision_round < 3 and there are must_fix issues, continue revision
    if state["revision_round"] < 3:
        return "revision"
    return "report"


async def fetch_batch_node(state: PipelineState) -> PipelineState:
    """Fetch next batch of pending tables from table_registry.

    Queries table_registry for rows with mapping_status='pending', ordered by id,
    and loads up to BATCH_SIZE ids into state['current_batch'].
    When no pending tables remain the batch is set to [] and the pipeline
    transitions to the critic phase via the conditional edge.
    """
    from backend.app.models.table_registry import TableRegistry

    job_id = state['job_id']
    batch_size = settings.BATCH_SIZE

    async with async_session_factory() as db:
        result = await db.execute(
            select(TableRegistry.id)
            .where(
                TableRegistry.mapping_status == 'pending',
                TableRegistry.is_deleted == False,
            )
            .order_by(TableRegistry.id)
            .limit(batch_size)
        )
        batch_ids = [row[0] for row in result.fetchall()]

    state['current_batch'] = batch_ids
    if batch_ids:
        logger.info(f"fetch_batch_node: fetched {len(batch_ids)} tables for job_id={job_id}")
    else:
        logger.info(f"fetch_batch_node: no pending tables, moving to critic for job_id={job_id}")
    return state


async def report_node(state: PipelineState) -> PipelineState:
    """Generate execution report and update job status."""
    logger.info(f"Generating report for job_id={state['job_id']}")
    # TODO: Implement report generation
    return state


class PipelineOrchestrator:
    """LangGraph-based Pipeline Orchestrator."""
    
    def __init__(self):
        self.graph = self._build_graph()
        self.compiled_graph = self.graph.compile()
    
    def _build_graph(self) -> StateGraph:
        """Build the LangGraph state machine."""
        logger.info("Building LangGraph workflow...")
        
        workflow = StateGraph(PipelineState)
        
        # Add nodes (imported from other modules)
        from backend.app.services.ddl_parser import parse_ddl_node
        from backend.app.services.ttl_indexer import index_ttl_node
        from backend.app.services.candidate_retriever import retrieve_candidates_node
        from backend.app.services.mapping_llm import mapping_llm_node, revision_node
        from backend.app.services.critic_agent import critic_node, check_revision_node
        
        workflow.add_node("parse_ddl", parse_ddl_node)
        workflow.add_node("index_ttl", index_ttl_node)
        workflow.add_node("fetch_batch", fetch_batch_node)
        workflow.add_node("retrieve_candidates", retrieve_candidates_node)
        workflow.add_node("mapping_llm", mapping_llm_node)
        workflow.add_node("critic", critic_node)
        workflow.add_node("check_revision", check_revision_node)
        workflow.add_node("revision", revision_node)
        workflow.add_node("report", report_node)
        
        # Define edges
        workflow.set_entry_point("parse_ddl")
        workflow.add_edge("parse_ddl", "index_ttl")
        
        # index_ttl → fetch_batch (conditional: batch found → candidates, empty → critic)
        workflow.add_edge("index_ttl", "fetch_batch")
        workflow.add_conditional_edges(
            "fetch_batch",
            route_after_fetch_batch,
            {
                "retrieve_candidates": "retrieve_candidates",
                "critic": "critic",
            }
        )
        
        # Mapping loop: retrieve_candidates → mapping_llm → fetch_batch (loop)
        workflow.add_edge("retrieve_candidates", "mapping_llm")
        workflow.add_conditional_edges(
            "mapping_llm",
            route_after_mapping,
            {
                "fetch_batch": "fetch_batch",
            }
        )
        
        # Critic → Revision check
        workflow.add_edge("critic", "check_revision")
        
        # Revision loop: check_revision → revision → critic
        workflow.add_conditional_edges(
            "check_revision",
            route_after_revision_check,
            {
                "revision": "revision",
                "report": "report",
            }
        )
        workflow.add_edge("revision", "critic")
        
        # Report → End
        workflow.add_edge("report", END)
        
        logger.info("LangGraph workflow built successfully")
        return workflow
    
    async def execute(self, initial_state: PipelineState) -> dict:
        """Execute the pipeline with given initial state."""
        logger.info(f"Starting pipeline execution for job_id={initial_state['job_id']}")
        
        try:
            result = await self.compiled_graph.ainvoke(initial_state)
            logger.info(f"Pipeline completed for job_id={initial_state['job_id']}")
            return result
        except Exception as e:
            logger.error(f"Pipeline failed for job_id={initial_state['job_id']}: {str(e)}")
            raise
    
    async def execute_from_phase(self, initial_state: PipelineState) -> dict:
        """Execute pipeline from a specific phase (for resume after interruption)."""
        logger.info(f"Resuming pipeline from phase={initial_state['phase']}")
        
        # TODO: Implement phase-based routing for resume
        # For now, always start from beginning
        return await self.execute(initial_state)


# Global orchestrator instance
orchestrator = PipelineOrchestrator()
