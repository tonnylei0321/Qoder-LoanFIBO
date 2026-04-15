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

from backend.app.services.pipeline_state import PipelineState, PipelinePhase


def route_after_mapping(state: PipelineState) -> str:
    """Route after mapping node: continue batch or move to critic."""
    # If there are more tables in the batch, continue
    if state.get("current_batch"):
        return "continue"
    return "critic"


def route_after_revision_check(state: PipelineState) -> str:
    """Route after revision check: revise or finish."""
    # If revision_round < 3 and there are must_fix issues, continue revision
    if state["revision_round"] < 3:
        return "revision"
    return "report"


async def fetch_batch_node(state: PipelineState) -> PipelineState:
    """Fetch next batch of pending tables from table_registry."""
    logger.info(f"Fetching batch for job_id={state['job_id']}")
    # TODO: Implement batch fetching logic
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
        workflow.add_edge("index_ttl", "fetch_batch")
        
        # Mapping loop: fetch_batch → retrieve_candidates → mapping_llm → fetch_batch
        workflow.add_edge("retrieve_candidates", "mapping_llm")
        workflow.add_conditional_edges(
            "mapping_llm",
            route_after_mapping,
            {
                "continue": "fetch_batch",
                "critic": "critic",
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
