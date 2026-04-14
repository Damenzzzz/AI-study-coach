from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from state import AgentState
from utils import StudyCoachLLM, export_results, read_lecture_notes


def build_study_coach_graph(llm_client: StudyCoachLLM):
    def ingest_notes(state: AgentState) -> dict[str, str]:
        raw_text = read_lecture_notes(state.input_path)
        return {"raw_text": raw_text}

    def analyze_notes(state: AgentState):
        analysis = llm_client.analyze_lecture(state.raw_text)
        return {"analysis": analysis}

    def generate_study_material(state: AgentState):
        if state.analysis is None:
            raise ValueError("Lecture analysis is missing.")

        study_material = llm_client.generate_study_material(
            lecture_text=state.raw_text,
            analysis=state.analysis,
        )
        return {"study_material": study_material}

    def export_report(state: AgentState):
        if state.study_material is None:
            raise ValueError("Study material must exist before export.")

        report_path, json_path = export_results(
            output_path=state.output_path,
            study_material=state.study_material,
            json_output_path=state.json_output_path,
        )
        result = {"exported_output_path": str(report_path)}
        if json_path is not None:
            result["exported_json_path"] = str(json_path)
        return result

    workflow = StateGraph(AgentState)
    workflow.add_node("ingest_notes", ingest_notes)
    workflow.add_node("analyze_notes", analyze_notes)
    workflow.add_node("generate_study_material", generate_study_material)
    workflow.add_node("export_report", export_report)

    workflow.add_edge(START, "ingest_notes")
    workflow.add_edge("ingest_notes", "analyze_notes")
    workflow.add_edge("analyze_notes", "generate_study_material")
    workflow.add_edge("generate_study_material", "export_report")
    workflow.add_edge("export_report", END)

    return workflow.compile()
