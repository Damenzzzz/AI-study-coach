from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Protocol

from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from pypdf import PdfReader

from prompts import (
    LECTURE_ANALYSIS_SYSTEM_PROMPT,
    LECTURE_ANALYSIS_USER_PROMPT,
    STUDY_MATERIAL_SYSTEM_PROMPT,
    STUDY_MATERIAL_USER_PROMPT,
)
from schemas import LectureAnalysis, QuizQuestion, StudyCoachOutput, StudyMaterial, TopicInfo

SUPPORTED_EXTENSIONS = {".txt", ".md", ".pdf"}
STOPWORDS = {"a", "an", "and", "for", "in", "of", "on", "or", "the", "to", "with"}


class StudyCoachLLM(Protocol):
    provider_name: str

    def analyze_lecture(self, lecture_text: str) -> LectureAnalysis: ...

    def generate_study_material(
        self, lecture_text: str, analysis: LectureAnalysis
    ) -> StudyMaterial: ...


class OpenAIStudyCoachLLM:
    provider_name = "openai"

    def __init__(self, model_name: str) -> None:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError(
                "OPENAI_API_KEY is not set. Use --provider mock or add the key to your environment."
            )

        chat_model = ChatOpenAI(model=model_name, api_key=api_key, temperature=0)
        analysis_prompt = ChatPromptTemplate.from_messages(
            [
                ("system", LECTURE_ANALYSIS_SYSTEM_PROMPT.strip()),
                ("human", LECTURE_ANALYSIS_USER_PROMPT.strip()),
            ]
        )
        study_prompt = ChatPromptTemplate.from_messages(
            [
                ("system", STUDY_MATERIAL_SYSTEM_PROMPT.strip()),
                ("human", STUDY_MATERIAL_USER_PROMPT.strip()),
            ]
        )

        self._analysis_chain = analysis_prompt | chat_model.with_structured_output(
            LectureAnalysis
        )
        self._study_material_chain = study_prompt | chat_model.with_structured_output(
            StudyMaterial
        )

    def analyze_lecture(self, lecture_text: str) -> LectureAnalysis:
        return self._analysis_chain.invoke({"lecture_text": lecture_text})

    def generate_study_material(
        self, lecture_text: str, analysis: LectureAnalysis
    ) -> StudyMaterial:
        return self._study_material_chain.invoke(
            {
                "lecture_text": lecture_text,
                "analysis_json": analysis.model_dump_json(indent=2),
            }
        )


class MockStudyCoachLLM:
    provider_name = "mock"

    def analyze_lecture(self, lecture_text: str) -> LectureAnalysis:
        subject = self._extract_subject(lecture_text)
        main_goal = self._extract_goal(lecture_text)
        topic_names = self._extract_topic_names(lecture_text)
        topics = [
            TopicInfo(name=name, description=self._describe_topic(name, lecture_text))
            for name in topic_names
        ]
        return LectureAnalysis(subject=subject, main_goal=main_goal, key_topics=topics)

    def generate_study_material(
        self, lecture_text: str, analysis: LectureAnalysis
    ) -> StudyMaterial:
        sentences = self._content_sentences(lecture_text)
        summary = " ".join(sentences[:4]).strip()
        if not summary:
            summary = (
                f"This lecture introduces {analysis.subject} and explains its core ideas, "
                "main workflow, and revision points."
            )

        key_points = [topic.description for topic in analysis.key_topics[:5]]
        if analysis.main_goal not in key_points:
            key_points.insert(0, analysis.main_goal)
        key_points = list(dict.fromkeys(point for point in key_points if point))[:5]

        while len(key_points) < 3:
            key_points.append(
                f"{analysis.subject} should be revised through its definitions, steps, and examples."
            )

        quiz_questions = [
            QuizQuestion(
                question=f"What is the main goal of the lecture on {analysis.subject}?",
                answer=analysis.main_goal,
            )
        ]
        quiz_questions.extend(
            QuizQuestion(
                question=f"What is {topic.name}?",
                answer=topic.description,
            )
            for topic in analysis.key_topics[:5]
        )

        return StudyMaterial(
            summary=summary,
            key_points=key_points,
            quiz_questions=quiz_questions,
        )

    def _extract_subject(self, lecture_text: str) -> str:
        for line in self._non_empty_lines(lecture_text):
            return re.sub(r"^[#\-\*\d\.\)\s]+", "", line).strip()
        return "Lecture Notes"

    def _extract_goal(self, lecture_text: str) -> str:
        goal_pattern = re.compile(r"^(goal|objective|aim)\s*:\s*(.+)$", re.IGNORECASE)
        for line in self._non_empty_lines(lecture_text):
            match = goal_pattern.match(line)
            if match:
                return match.group(2).strip()

        sentences = self._split_sentences(lecture_text)
        if len(sentences) >= 2:
            return sentences[1]
        if sentences:
            return sentences[0]
        return "Understand the main ideas presented in the lecture."

    def _extract_topic_names(self, lecture_text: str) -> list[str]:
        topic_names: list[str] = []
        list_pattern = re.compile(r"^\s*(?:[-*]|\d+[.)])\s+(.+)$")

        for line in self._non_empty_lines(lecture_text):
            if line.lower().startswith("goal:"):
                continue
            match = list_pattern.match(line)
            if match:
                candidate = match.group(1).strip()
                if candidate and candidate not in topic_names:
                    topic_names.append(candidate)

        if not topic_names:
            subject = self._extract_subject(lecture_text)
            topic_names = [
                f"{subject} definition",
                f"{subject} workflow",
                f"{subject} applications",
            ]

        return topic_names[:5]

    def _describe_topic(self, topic_name: str, lecture_text: str) -> str:
        words = [
            word.lower()
            for word in re.findall(r"[A-Za-z][A-Za-z\-]+", topic_name)
            if word.lower() not in STOPWORDS
        ]
        best_sentence = ""
        best_score = 0

        for sentence in self._content_sentences(lecture_text):
            lowered_sentence = sentence.lower()
            score = sum(word in lowered_sentence for word in words)
            if score > best_score or (score == best_score and len(sentence) > len(best_sentence)):
                best_sentence = sentence.strip()
                best_score = score

        if best_sentence:
            return best_sentence
        return f"{topic_name} is presented as an important concept in the lecture."

    def _content_sentences(self, lecture_text: str) -> list[str]:
        content_blocks = self._content_blocks(lecture_text)
        return self._split_sentences(" ".join(content_blocks))

    def _content_blocks(self, lecture_text: str) -> list[str]:
        list_pattern = re.compile(r"^\s*(?:[-*]|\d+[.)])\s+")
        blocks: list[str] = []

        for raw_block in re.split(r"\n\s*\n", lecture_text):
            lines = [line.strip() for line in raw_block.splitlines() if line.strip()]
            if not lines:
                continue

            cleaned_lines: list[str] = []
            for line in lines:
                lowered = line.lower().rstrip(":")
                if lowered in {"topics"}:
                    continue
                if re.match(r"^(goal|objective|aim)\s*:", line, re.IGNORECASE):
                    continue
                if list_pattern.match(line):
                    continue
                if not re.search(r"[.!?]", line):
                    continue
                cleaned_lines.append(line)

            if cleaned_lines:
                blocks.append(" ".join(cleaned_lines))

        return blocks

    @staticmethod
    def _split_sentences(text: str) -> list[str]:
        return [
            sentence.strip()
            for sentence in re.split(r"(?<=[.!?])\s+", text.replace("\n", " "))
            if sentence.strip()
        ]

    @staticmethod
    def _non_empty_lines(text: str) -> list[str]:
        return [line.strip() for line in text.splitlines() if line.strip()]


def create_llm(provider: str, model_name: str) -> StudyCoachLLM:
    normalized_provider = provider.lower()
    if normalized_provider == "auto":
        if os.getenv("OPENAI_API_KEY"):
            return OpenAIStudyCoachLLM(model_name)
        return MockStudyCoachLLM()
    if normalized_provider == "openai":
        return OpenAIStudyCoachLLM(model_name)
    if normalized_provider == "mock":
        return MockStudyCoachLLM()
    raise ValueError(f"Unsupported provider: {provider}")


def read_lecture_notes(input_path: str) -> str:
    path = Path(input_path)
    if not path.exists():
        raise FileNotFoundError(f"Input file not found: {path}")

    extension = path.suffix.lower()
    if extension not in SUPPORTED_EXTENSIONS:
        raise ValueError(
            f"Unsupported file type: {extension}. Supported types: {', '.join(sorted(SUPPORTED_EXTENSIONS))}"
        )

    if extension in {".txt", ".md"}:
        text = _read_text_file(path)
    else:
        text = _read_pdf_file(path)

    cleaned_text = _normalize_text(text)
    if not cleaned_text:
        raise ValueError(f"No readable content found in {path}")
    return cleaned_text


def export_results(
    output_path: str,
    input_path: str,
    analysis: LectureAnalysis,
    study_material: StudyMaterial,
) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    output_document = StudyCoachOutput(
        input_file=Path(input_path).as_posix(),
        subject=analysis.subject,
        main_goal=analysis.main_goal,
        key_topics=analysis.key_topics,
        summary=study_material.summary,
        key_points=study_material.key_points,
        quiz_questions=study_material.quiz_questions,
    )
    path.write_text(output_document.model_dump_json(indent=2), encoding="utf-8")
    return path


def _read_text_file(path: Path) -> str:
    for encoding in ("utf-8", "utf-8-sig", "cp1251"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    raise ValueError(f"Could not decode text file: {path}")


def _read_pdf_file(path: Path) -> str:
    reader = PdfReader(str(path))
    pages = [page.extract_text() or "" for page in reader.pages]
    return "\n".join(pages)


def _normalize_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()
