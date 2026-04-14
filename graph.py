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

    def export_json(state: AgentState):
        if state.analysis is None or state.study_material is None:
            raise ValueError("Both analysis and study material must exist before export.")

        export_path = export_results(
            output_path=state.output_path,
            input_path=state.input_path,
            analysis=state.analysis,
            study_material=state.study_material,
        )
        return {"exported_output_path": str(export_path)}

    workflow = StateGraph(AgentState)
    workflow.add_node("ingest_notes", ingest_notes)
    workflow.add_node("analyze_notes", analyze_notes)
    workflow.add_node("generate_study_material", generate_study_material)
    workflow.add_node("export_json", export_json)

    workflow.add_edge(START, "ingest_notes")
    workflow.add_edge("ingest_notes", "analyze_notes")
    workflow.add_edge("analyze_notes", "generate_study_material")
    workflow.add_edge("generate_study_material", "export_json")
    workflow.add_edge("export_json", END)

    return workflow.compile()
