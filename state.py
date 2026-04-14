from __future__ import annotations

from pydantic import BaseModel

from schemas import LectureAnalysis, StudyMaterial


class AgentState(BaseModel):
    input_path: str
    output_path: str
    raw_text: str = ""
    analysis: LectureAnalysis | None = None
    study_material: StudyMaterial | None = None
    exported_output_path: str | None = None
