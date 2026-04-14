from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator


class TopicInfo(BaseModel):
    topic_name: str = Field(description="Name of a key lecture topic.")
    importance: str = Field(
        description="Why this topic matters in the lecture, written as one concise sentence."
    )
    key_terms: list[str] = Field(
        default_factory=list,
        description="Important key terms or phrases connected to the topic.",
    )

    @field_validator("key_terms")
    @classmethod
    def validate_key_terms(cls, value: list[str]) -> list[str]:
        cleaned_terms = []
        for term in value:
            cleaned = term.strip()
            if cleaned and cleaned not in cleaned_terms:
                cleaned_terms.append(cleaned)
        return cleaned_terms[:6]


class LectureAnalysis(BaseModel):
    title: str = Field(description="A clean title for the study handout.")
    subject: str = Field(description="Main subject of the lecture.")
    main_goal: str = Field(description="Main learning goal of the lecture.")
    topics: list[TopicInfo] = Field(
        default_factory=list,
        description="Main lecture topics with importance and key terms.",
    )


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

    @field_validator("options")
    @classmethod
    def validate_options(cls, value: list[str]) -> list[str]:
        cleaned_options = [option.strip() for option in value if option.strip()]
        if len(cleaned_options) != 4:
            raise ValueError("Each quiz question must contain exactly 4 non-empty options.")
        return cleaned_options


class StudyMaterial(BaseModel):
    title: str = Field(description="Title of the final study report.")
    subject: str = Field(description="Main subject of the lecture.")
    main_goal: str = Field(description="Main goal of the lecture.")
    topics: list[TopicInfo] = Field(
        default_factory=list,
        description="Topics to include in the report.",
    )
    summary: str = Field(
        description="Study-note style summary written as short readable paragraphs."
    )
    key_points: list[str] = Field(
        default_factory=list,
        description="Important facts, formulas, or revision points.",
    )
    quiz: list[QuizQuestion] = Field(
        default_factory=list,
        description="Multiple-choice revision quiz.",
    )

    @field_validator("key_points")
    @classmethod
    def validate_key_points(cls, value: list[str]) -> list[str]:
        cleaned_points = []
        for point in value:
            cleaned = point.strip()
            if cleaned and cleaned not in cleaned_points:
                cleaned_points.append(cleaned)
        return cleaned_points[:8]
