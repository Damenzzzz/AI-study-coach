from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class SummaryMode(StrEnum):
    SMALL = "small"
    MEDIUM = "medium"
    LARGE = "large"


class DocumentPage(BaseModel):
    page_number: int = Field(description="1-based page number in the source document.")
    text: str = Field(description="Normalized text extracted from the page.")
    block_count: int = Field(default=0, description="Number of logical text blocks found on the page.")
    word_count: int = Field(default=0, description="Approximate number of words on the page.")


class LectureDocument(BaseModel):
    source_path: str
    file_name: str
    title_hint: str
    goal_hint: str | None = None
    pages: list[DocumentPage] = Field(default_factory=list)
    raw_text: str
    total_pages: int
    total_words: int


class LectureChunk(BaseModel):
    chunk_id: int
    title_hint: str
    start_page: int
    end_page: int
    text: str
    word_count: int
    char_count: int


class TopicInfo(BaseModel):
    topic_name: str = Field(description="Name of a key lecture topic.")
    importance: str = Field(description="Why this topic matters in the lecture.")
    key_terms: list[str] = Field(
        default_factory=list,
        description="Important key terms or phrases connected to the topic.",
    )

    @field_validator("key_terms")
    @classmethod
    def validate_key_terms(cls, value: list[str]) -> list[str]:
        cleaned_terms: list[str] = []
        for term in value:
            cleaned = term.strip()
            if cleaned and cleaned not in cleaned_terms:
                cleaned_terms.append(cleaned)
        return cleaned_terms[:8]


class DefinitionItem(BaseModel):
    term: str
    definition: str


class FormulaOrFact(BaseModel):
    statement: str
    explanation: str | None = None


class ChunkAnalysis(BaseModel):
    chunk_id: int
    source_span: str
    section_title: str
    subject_focus: str
    main_idea: str
    topics: list[TopicInfo] = Field(default_factory=list)
    definitions: list[DefinitionItem] = Field(default_factory=list)
    formulas_or_facts: list[FormulaOrFact] = Field(default_factory=list)
    key_points: list[str] = Field(default_factory=list)

    @field_validator("key_points")
    @classmethod
    def validate_key_points(cls, value: list[str]) -> list[str]:
        cleaned_points: list[str] = []
        for point in value:
            cleaned = point.strip()
            if cleaned and cleaned not in cleaned_points:
                cleaned_points.append(cleaned)
        return cleaned_points[:8]


class LectureAnalysis(BaseModel):
    title: str
    subject: str
    main_goal: str
    topics: list[TopicInfo] = Field(default_factory=list)
    definitions: list[DefinitionItem] = Field(default_factory=list)
    formulas_or_facts: list[FormulaOrFact] = Field(default_factory=list)
    coverage_summary: list[str] = Field(default_factory=list)
    section_titles: list[str] = Field(default_factory=list)


class SectionNote(BaseModel):
    section_title: str
    source_span: str
    section_summary: str
    important_points: list[str] = Field(default_factory=list)

    @field_validator("important_points")
    @classmethod
    def validate_important_points(cls, value: list[str]) -> list[str]:
        cleaned_points: list[str] = []
        for point in value:
            cleaned = point.strip()
            if cleaned and cleaned not in cleaned_points:
                cleaned_points.append(cleaned)
        return cleaned_points[:8]


class QuizQuestion(BaseModel):
    question: str = Field(description="Multiple-choice revision question.")
    options: list[str] = Field(
        description="Exactly four answer options ordered for A, B, C, and D."
    )
    correct_answer: Literal["A", "B", "C", "D"] = Field(
        description="Correct answer label."
    )
    explanation: str | None = Field(
        default=None,
        description="Short explanation of why the correct answer is right.",
    )

    @field_validator("correct_answer", mode="before")
    @classmethod
    def normalize_correct_answer(cls, value: str) -> str:
        return value.strip().upper()

    @field_validator("options")
    @classmethod
    def validate_options(cls, value: list[str]) -> list[str]:
        cleaned_options = [option.strip() for option in value if option.strip()]
        if len(cleaned_options) != 4:
            raise ValueError("Each quiz question must contain exactly 4 non-empty options.")
        if len({option.lower() for option in cleaned_options}) != 4:
            raise ValueError("Quiz options must be distinct.")
        return cleaned_options


class StudyMaterial(BaseModel):
    title: str
    subject: str
    main_goal: str
    overview: str = Field(
        description="A structured overview or conspect of the lecture."
    )
    section_notes: list[SectionNote] = Field(default_factory=list)
    topics: list[TopicInfo] = Field(default_factory=list)
    definitions: list[DefinitionItem] = Field(default_factory=list)
    formulas_or_facts: list[FormulaOrFact] = Field(default_factory=list)
    key_points: list[str] = Field(default_factory=list)
    quiz: list[QuizQuestion] = Field(default_factory=list)

    @field_validator("key_points")
    @classmethod
    def validate_key_points(cls, value: list[str]) -> list[str]:
        cleaned_points: list[str] = []
        for point in value:
            cleaned = point.strip()
            if cleaned and cleaned not in cleaned_points:
                cleaned_points.append(cleaned)
        return cleaned_points[:16]


class CoverageReport(BaseModel):
    source_file: str
    total_pages_read: int
    total_words_read: int
    total_chunks_processed: int
    selected_summary_mode: SummaryMode
    selected_quiz_count: int
    output_markdown_path: str | None = None
    output_json_path: str | None = None


class StudyRunOutput(BaseModel):
    coverage: CoverageReport
    study_material: StudyMaterial
