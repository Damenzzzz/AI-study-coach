from __future__ import annotations

import os
import re
from pathlib import Path
from textwrap import fill
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
from schemas import LectureAnalysis, QuizQuestion, StudyMaterial, TopicInfo

SUPPORTED_EXTENSIONS = {".txt", ".md", ".pdf"}
STOPWORDS = {
    "a",
    "an",
    "and",
    "for",
    "from",
    "how",
    "in",
    "into",
    "is",
    "of",
    "on",
    "or",
    "the",
    "to",
    "uses",
    "using",
    "with",
}
GENERIC_KEY_TERM_WORDS = {
    "algorithm",
    "between",
    "better",
    "common",
    "contains",
    "data",
    "difference",
    "direction",
    "each",
    "estimate",
    "example",
    "helps",
    "important",
    "lecture",
    "main",
    "model",
    "models",
    "practice",
    "practices",
    "presented",
    "measure",
    "step",
    "subject",
    "simpler",
    "techniques",
    "topic",
    "training",
    "used",
    "updates",
    "expected",
    "functions",
}
ANSWER_LABELS = ("A", "B", "C", "D")


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
        title = f"Study Report: {subject}"
        topic_names = self._extract_topic_names(lecture_text)

        topics = []
        for name in topic_names:
            importance = self._describe_topic(name, lecture_text)
            key_terms = self._extract_key_terms(name, importance)
            topics.append(
                TopicInfo(
                    topic_name=name,
                    importance=importance,
                    key_terms=key_terms,
                )
            )

        return LectureAnalysis(
            title=title,
            subject=subject,
            main_goal=main_goal,
            topics=topics,
        )

    def generate_study_material(
        self, lecture_text: str, analysis: LectureAnalysis
    ) -> StudyMaterial:
        content_sentences = self._content_sentences(lecture_text)
        summary = self._build_summary(content_sentences, analysis.subject)
        key_points = self._build_key_points(analysis, content_sentences)
        quiz = self._build_quiz(analysis)

        return StudyMaterial(
            title=analysis.title,
            subject=analysis.subject,
            main_goal=analysis.main_goal,
            topics=analysis.topics,
            summary=summary,
            key_points=key_points,
            quiz=quiz,
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

        content_sentences = self._content_sentences(lecture_text)
        if content_sentences:
            return content_sentences[0]
        return "Understand the main ideas presented in the lecture."

    def _extract_topic_names(self, lecture_text: str) -> list[str]:
        topic_names: list[str] = []
        list_pattern = re.compile(r"^\s*(?:[-*]|\d+[.)])\s+(.+)$")

        for line in self._non_empty_lines(lecture_text):
            if line.lower().startswith(("goal:", "objective:", "aim:")):
                continue
            match = list_pattern.match(line)
            if match:
                candidate = match.group(1).strip().rstrip(".")
                if candidate and candidate not in topic_names:
                    topic_names.append(candidate)

        if not topic_names:
            subject = self._extract_subject(lecture_text)
            topic_names = [
                f"{subject} foundations",
                f"{subject} workflow",
                f"{subject} evaluation",
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
            if score > best_score or (
                score == best_score and len(sentence) > len(best_sentence)
            ):
                best_sentence = sentence.strip()
                best_score = score

        if best_sentence:
            return best_sentence
        return f"{topic_name} is presented as an important concept in the lecture."

    def _extract_key_terms(self, topic_name: str, importance: str) -> list[str]:
        terms: list[str] = []

        for chunk in re.split(r",| and ", topic_name, flags=re.IGNORECASE):
            cleaned = chunk.strip(" .")
            if cleaned and cleaned.lower() not in STOPWORDS and cleaned not in terms:
                terms.append(cleaned)

        for phrase in re.findall(r"[A-Za-z]+(?:-[A-Za-z]+)+", importance):
            cleaned = phrase.strip()
            if cleaned.lower() not in STOPWORDS and cleaned not in terms:
                terms.append(cleaned)

        for word in re.findall(r"[A-Za-z][A-Za-z\-]+", importance):
            cleaned = word.strip(" .,:;").lower()
            if (
                len(cleaned) >= 6
                and cleaned not in STOPWORDS
                and cleaned not in GENERIC_KEY_TERM_WORDS
                and cleaned not in {term.lower() for term in terms}
            ):
                terms.append(cleaned)

        return terms[:5]

    def _build_summary(self, sentences: list[str], subject: str) -> str:
        if not sentences:
            return (
                f"{subject} is explained through its central ideas, important steps, "
                "and the reasons it matters for revision."
            )

        selected = sentences[:6]
        first_paragraph = " ".join(selected[:3]).strip()
        second_paragraph = " ".join(selected[3:6]).strip()

        paragraphs = [paragraph for paragraph in [first_paragraph, second_paragraph] if paragraph]
        return "\n\n".join(paragraphs)

    def _build_key_points(
        self, analysis: LectureAnalysis, content_sentences: list[str]
    ) -> list[str]:
        key_points = [analysis.main_goal]
        key_points.extend(topic.importance for topic in analysis.topics[:5])

        for sentence in content_sentences:
            if sentence not in key_points:
                key_points.append(sentence)
            if len(key_points) >= 6:
                break

        deduped_points = []
        for point in key_points:
            cleaned = point.strip()
            if cleaned and cleaned not in deduped_points:
                deduped_points.append(cleaned)
        return deduped_points[:6]

    def _build_quiz(self, analysis: LectureAnalysis) -> list[QuizQuestion]:
        quiz_items: list[QuizQuestion] = []
        topic_importances = [topic.importance for topic in analysis.topics]

        quiz_items.append(
            self._make_question(
                question=f"What best describes the main goal of {analysis.subject}?",
                correct_option=analysis.main_goal,
                distractors=[
                    "To remove the need for evaluation and validation.",
                    "To avoid using structured data or labels.",
                    "To replace understanding with memorizing isolated facts.",
                ],
                explanation="The main goal should match the lecture objective, not a side detail.",
                correct_index=0,
            )
        )

        for index, topic in enumerate(analysis.topics[:4], start=1):
            distractors = [item for item in topic_importances if item != topic.importance]
            distractors.extend(
                [
                    "It is mainly used to ignore evidence from the lecture notes.",
                    "It removes the need to compare predictions with expected results.",
                    "It guarantees perfect performance on unseen examples.",
                ]
            )
            quiz_items.append(
                self._make_question(
                    question=f"Which statement best explains {topic.topic_name}?",
                    correct_option=topic.importance,
                    distractors=distractors,
                    explanation=f"The correct option matches the lecture note explanation of {topic.topic_name}.",
                    correct_index=index % 4,
                )
            )

        return quiz_items

    def _make_question(
        self,
        question: str,
        correct_option: str,
        distractors: list[str],
        explanation: str,
        correct_index: int,
    ) -> QuizQuestion:
        unique_distractors = []
        for distractor in distractors:
            cleaned = distractor.strip()
            if cleaned and cleaned != correct_option and cleaned not in unique_distractors:
                unique_distractors.append(cleaned)
            if len(unique_distractors) == 3:
                break

        while len(unique_distractors) < 3:
            unique_distractors.append(
                "It focuses on an idea that is not presented as the main point in the lecture."
            )

        options: list[str] = []
        distractor_index = 0
        for option_index in range(4):
            if option_index == correct_index:
                options.append(correct_option)
            else:
                options.append(unique_distractors[distractor_index])
                distractor_index += 1

        return QuizQuestion(
            question=question,
            options=options,
            correct_answer=ANSWER_LABELS[correct_index],
            explanation=explanation,
        )

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
    study_material: StudyMaterial,
    json_output_path: str | None = None,
) -> tuple[Path, Path | None]:
    report_path = Path(output_path)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(render_markdown_report(study_material), encoding="utf-8")

    exported_json_path: Path | None = None
    if json_output_path:
        exported_json_path = Path(json_output_path)
        exported_json_path.parent.mkdir(parents=True, exist_ok=True)
        exported_json_path.write_text(
            study_material.model_dump_json(indent=2),
            encoding="utf-8",
        )

    return report_path, exported_json_path


def render_markdown_report(study_material: StudyMaterial) -> str:
    sections = [
        f"# {study_material.title}",
        _simple_section("Subject", study_material.subject),
        _simple_section("Main Goal of the Lecture", study_material.main_goal),
        _render_topics(study_material.topics),
        _render_key_terms(study_material.topics),
        _render_summary(study_material.summary),
        _render_key_points(study_material.key_points),
        _render_quiz(study_material.quiz),
        _render_answer_key(study_material.quiz),
    ]
    return "\n\n".join(section for section in sections if section).strip() + "\n"


def _simple_section(title: str, content: str) -> str:
    cleaned = content.strip() if content else "Not available."
    return f"## {title}\n\n{cleaned}"


def _render_topics(topics: list[TopicInfo]) -> str:
    if not topics:
        return "## Key Topics\n\n- No key topics were identified."

    lines = ["## Key Topics", ""]
    for topic in topics:
        lines.append(f"- **{topic.topic_name}** - {topic.importance}")
    return "\n".join(lines)


def _render_key_terms(topics: list[TopicInfo]) -> str:
    lines = ["## Key Terms for Each Topic", ""]
    if not topics:
        lines.append("No key terms were identified.")
        return "\n".join(lines)

    for topic in topics:
        lines.append(f"### {topic.topic_name}")
        if topic.key_terms:
            for term in topic.key_terms:
                lines.append(f"- {term}")
        else:
            lines.append("- No key terms provided.")
        lines.append("")

    return "\n".join(lines).rstrip()


def _render_summary(summary: str) -> str:
    paragraphs = [
        " ".join(paragraph.split())
        for paragraph in re.split(r"\n\s*\n", summary.strip())
        if paragraph.strip()
    ]
    if not paragraphs:
        paragraphs = ["No summary was generated."]

    body = "\n\n".join(fill(paragraph, width=100) for paragraph in paragraphs)
    return f"## Study-Note Summary\n\n{body}"


def _render_key_points(key_points: list[str]) -> str:
    lines = ["## Key Points / Formulas / Important Facts", ""]
    if not key_points:
        lines.append("- No key points were generated.")
        return "\n".join(lines)

    for point in key_points:
        lines.append(f"- {point}")
    return "\n".join(lines)


def _render_quiz(quiz: list[QuizQuestion]) -> str:
    lines = ["## Quiz", ""]
    if not quiz:
        lines.append("No quiz questions were generated.")
        return "\n".join(lines)

    for index, question in enumerate(quiz, start=1):
        lines.append(f"{index}. {question.question}")
        for label, option in zip(ANSWER_LABELS, question.options, strict=True):
            lines.append(f"   {label}. {option}")
        lines.append("")
    return "\n".join(lines).rstrip()


def _render_answer_key(quiz: list[QuizQuestion]) -> str:
    lines = ["## Answer Key", ""]
    if not quiz:
        lines.append("No answers available.")
        return "\n".join(lines)

    for index, question in enumerate(quiz, start=1):
        answer_index = ANSWER_LABELS.index(question.correct_answer)
        answer_text = question.options[answer_index]
        lines.append(f"{index}. **{question.correct_answer}** - {answer_text}")
        if question.explanation:
            lines.append(f"   Explanation: {question.explanation}")
        lines.append("")
    return "\n".join(lines).rstrip()


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
