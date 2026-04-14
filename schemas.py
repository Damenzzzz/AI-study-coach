from __future__ import annotations

from pydantic import BaseModel, Field


class TopicInfo(BaseModel):
    name: str = Field(description="Name of a key topic from the lecture.")
    description: str = Field(description="Short explanation of the topic.")


class LectureAnalysis(BaseModel):
    subject: str = Field(description="Main subject or title of the lecture.")
    main_goal: str = Field(description="Main learning goal of the lecture.")
    key_topics: list[TopicInfo] = Field(
        default_factory=list,
        description="Important topics covered in the lecture.",
    )


class QuizQuestion(BaseModel):
    question: str = Field(description="Revision question for the lecture.")
    answer: str = Field(description="Correct answer or model answer.")


class StudyMaterial(BaseModel):
    summary: str = Field(description="Short summary of the lecture.")
    key_points: list[str] = Field(
        default_factory=list,
        description="List of key revision points.",
    )
    quiz_questions: list[QuizQuestion] = Field(
        default_factory=list,
        description="Quiz questions with answers.",
    )


class StudyCoachOutput(BaseModel):
    input_file: str
    subject: str
    main_goal: str
    key_topics: list[TopicInfo]
    summary: str
    key_points: list[str]
    quiz_questions: list[QuizQuestion]
