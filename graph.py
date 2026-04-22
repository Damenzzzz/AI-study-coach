from __future__ import annotations

import logging

from langgraph.graph import END, START, StateGraph

from state import AgentState
from utils import (
    StudyCoachLLM,
    aggregate_chunk_analyses,
    analyze_chunks_parallel,
    build_chunks,
    build_coverage_report,
    export_results,
    read_lecture_document,
)

logger = logging.getLogger(__name__)


def build_study_coach_graph(llm_client: StudyCoachLLM):
    def ingest_notes(state: AgentState):
        logger.info(f"Ingesting lecture notes from: {state.input_path}")
        document = read_lecture_document(state.input_path)
        logger.info(
            f"Successfully ingested document: {document.file_name} "
            f"({document.total_words} words, {document.total_pages} pages)"
        )
        return {"document": document}

    def chunk_notes(state: AgentState):
        if state.document is None:
            raise ValueError("Document must exist before chunking.")
        logger.info(
            f"Chunking document into logical segments (mode: {state.summary_mode.value})"
        )
        chunks = build_chunks(state.document, state.summary_mode)
        logger.info(f"Successfully created {len(chunks)} chunks from document")
        return {"chunks": chunks}

    def analyze_chunks(state: AgentState):
        if state.document is None:
            raise ValueError("Document must exist before chunk analysis.")
        logger.info(f"Starting parallel analysis of {len(state.chunks)} chunks")
        analyses = analyze_chunks_parallel(
            llm_client=llm_client,
            chunks=state.chunks,
            summary_mode=state.summary_mode,
            document_title=state.document.title_hint,
            max_workers=4,
        )
        logger.info(f"Completed analysis of all {len(analyses)} chunks")
        return {"chunk_analyses": analyses}

    def aggregate_analysis(state: AgentState):
        if state.document is None:
            raise ValueError("Document must exist before aggregation.")
        logger.info("Aggregating chunk analyses into full-document analysis")
        analysis = aggregate_chunk_analyses(
            document=state.document,
            chunk_analyses=state.chunk_analyses,
            summary_mode=state.summary_mode,
        )
        logger.info(
            f"Aggregation complete: {len(analysis.topics)} topics, "
            f"{len(analysis.definitions)} definitions"
        )
        coverage = build_coverage_report(
            document=state.document,
            chunks=state.chunks,
            summary_mode=state.summary_mode,
            quiz_count=state.quiz_count,
            output_path=state.output_path,
            json_output_path=state.json_output_path,
        )
        logger.info(
            f"Coverage report generated: {coverage.total_chunks_processed} chunks processed"
        )
        return {"analysis": analysis, "coverage": coverage}

    def generate_study_material(state: AgentState):
        if state.document is None or state.analysis is None:
            raise ValueError(
                "Document analysis must exist before final report generation."
            )
        logger.info(
            f"Generating study material with {state.quiz_count} quiz questions "
            f"(mode: {state.summary_mode.value})"
        )
        study_material = llm_client.generate_study_material(
            document=state.document,
            analysis=state.analysis,
            chunk_analyses=state.chunk_analyses,
            summary_mode=state.summary_mode,
            quiz_count=state.quiz_count,
        )
        logger.info(
            f"Study material generated: {len(study_material.section_notes)} sections, "
            f"{len(study_material.quiz)} quiz questions"
        )
        return {"study_material": study_material}

    def export_report(state: AgentState):
        if state.study_material is None or state.coverage is None:
            raise ValueError("Study material and coverage must exist before export.")
        logger.info(f"Exporting study report to: {state.output_path}")
        report_path, json_path = export_results(
            output_path=state.output_path,
            study_material=state.study_material,
            coverage=state.coverage,
            json_output_path=state.json_output_path,
        )
        logger.info(f"Successfully exported report to: {report_path}")
        if json_path is not None:
            logger.info(f"Successfully exported JSON to: {json_path}")
        result = {"exported_output_path": str(report_path)}
        if json_path is not None:
            result["exported_json_path"] = str(json_path)
        return result

    workflow = StateGraph(AgentState)
    workflow.add_node("ingest_notes", ingest_notes)
    workflow.add_node("chunk_notes", chunk_notes)
    workflow.add_node("analyze_chunks", analyze_chunks)
    workflow.add_node("aggregate_analysis", aggregate_analysis)
    workflow.add_node("generate_study_material", generate_study_material)
    workflow.add_node("export_report", export_report)

    workflow.add_edge(START, "ingest_notes")
    workflow.add_edge("ingest_notes", "chunk_notes")
    workflow.add_edge("chunk_notes", "analyze_chunks")
    workflow.add_edge("analyze_chunks", "aggregate_analysis")
    workflow.add_edge("aggregate_analysis", "generate_study_material")
    workflow.add_edge("generate_study_material", "export_report")
    workflow.add_edge("export_report", END)

    return workflow.compile()
