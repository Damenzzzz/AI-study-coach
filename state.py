from __future__ import annotations

from pydantic import BaseModel, Field

from schemas import (
    ChunkAnalysis,
    CoverageReport,
    LectureAnalysis,
    LectureChunk,
    LectureDocument,
    StudyMaterial,
    SummaryMode,
)


class AgentState(BaseModel):
    input_path: str
    output_path: str
    json_output_path: str | None = None
    summary_mode: SummaryMode = SummaryMode.MEDIUM
    quiz_count: int = 5
    document: LectureDocument | None = None
    chunks: list[LectureChunk] = Field(default_factory=list)
    chunk_analyses: list[ChunkAnalysis] = Field(default_factory=list)
    analysis: LectureAnalysis | None = None
    study_material: StudyMaterial | None = None
    coverage: CoverageReport | None = None
    exported_output_path: str | None = None
    exported_json_path: str | None = None
