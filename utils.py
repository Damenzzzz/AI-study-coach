from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from math import ceil
from pathlib import Path
from typing import Protocol, TypeVar

from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from pypdf import PdfReader

from prompts import (
    CHUNK_ANALYSIS_SYSTEM_PROMPT,
    CHUNK_ANALYSIS_USER_PROMPT,
    FINAL_REPORT_SYSTEM_PROMPT,
    FINAL_REPORT_USER_PROMPT,
)
from schemas import (
    ChunkAnalysis,
    CoverageReport,
    DefinitionItem,
    DocumentPage,
    FormulaOrFact,
    LectureAnalysis,
    LectureChunk,
    LectureDocument,
    QuizQuestion,
    SectionNote,
    StudyMaterial,
    StudyRunOutput,
    SummaryMode,
    TopicInfo,
)

SUPPORTED_EXTENSIONS = {".txt", ".md", ".pdf"}
ANSWER_LABELS = ("A", "B", "C", "D")
T = TypeVar("T")
STOPWORDS = {
    "about",
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "because",
    "by",
    "can",
    "clear",
    "common",
    "during",
    "each",
    "for",
    "from",
    "good",
    "how",
    "if",
    "in",
    "into",
    "is",
    "it",
    "its",
    "later",
    "make",
    "more",
    "new",
    "only",
    "of",
    "on",
    "or",
    "out",
    "over",
    "that",
    "the",
    "their",
    "then",
    "this",
    "to",
    "understand",
    "uses",
    "using",
    "used",
    "very",
    "when",
    "where",
    "while",
    "why",
    "will",
    "with",
}
GENERIC_TERMS = {"goal", "goals", "topic", "topics", "section", "lecture", "notes"}
FACT_KEYWORDS = {
    "accuracy",
    "bias",
    "equation",
    "error",
    "f1",
    "formula",
    "gradient",
    "loss",
    "metric",
    "mse",
    "precision",
    "probability",
    "rate",
    "recall",
    "regularization",
    "variance",
}
GENERIC_DISTRACTORS = [
    "It focuses on a narrower point than the lecture actually emphasizes.",
    "It confuses this concept with a different section from the lecture.",
    "It sounds plausible but does not match the explanation given in the notes.",
    "It describes a related idea, but not the correct one for this question.",
    "It reverses the relationship explained in the lecture.",
]


@dataclass(frozen=True)
class ModeSettings:
    chunk_char_limit: int
    target_sections: int
    target_topics: int
    target_definitions: int
    target_facts: int
    target_key_points: int
    overview_paragraphs: int
    chunk_key_points: int


MODE_SETTINGS = {
    SummaryMode.SMALL: ModeSettings(
        chunk_char_limit=2600,
        target_sections=3,
        target_topics=5,
        target_definitions=4,
        target_facts=4,
        target_key_points=6,
        overview_paragraphs=1,
        chunk_key_points=3,
    ),
    SummaryMode.MEDIUM: ModeSettings(
        chunk_char_limit=1800,
        target_sections=6,
        target_topics=8,
        target_definitions=6,
        target_facts=6,
        target_key_points=10,
        overview_paragraphs=2,
        chunk_key_points=4,
    ),
    SummaryMode.LARGE: ModeSettings(
        chunk_char_limit=1200,
        target_sections=14,
        target_topics=14,
        target_definitions=10,
        target_facts=10,
        target_key_points=18,
        overview_paragraphs=4,
        chunk_key_points=5,
    ),
}


class StudyCoachLLM(Protocol):
    provider_name: str

    def analyze_chunk(
        self, chunk: LectureChunk, summary_mode: SummaryMode, document_title: str
    ) -> ChunkAnalysis: ...

    def generate_study_material(
        self,
        document: LectureDocument,
        analysis: LectureAnalysis,
        chunk_analyses: list[ChunkAnalysis],
        summary_mode: SummaryMode,
        quiz_count: int,
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
        chunk_prompt = ChatPromptTemplate.from_messages(
            [
                ("system", CHUNK_ANALYSIS_SYSTEM_PROMPT.strip()),
                ("human", CHUNK_ANALYSIS_USER_PROMPT.strip()),
            ]
        )
        final_prompt = ChatPromptTemplate.from_messages(
            [
                ("system", FINAL_REPORT_SYSTEM_PROMPT.strip()),
                ("human", FINAL_REPORT_USER_PROMPT.strip()),
            ]
        )

        self._chunk_chain = chunk_prompt | chat_model.with_structured_output(ChunkAnalysis)
        self._final_chain = final_prompt | chat_model.with_structured_output(StudyMaterial)

    def analyze_chunk(
        self, chunk: LectureChunk, summary_mode: SummaryMode, document_title: str
    ) -> ChunkAnalysis:
        result = self._chunk_chain.invoke(
            {
                "document_title": document_title,
                "summary_mode": summary_mode.value,
                "mode_instructions": build_mode_instructions(summary_mode),
                "chunk_id": chunk.chunk_id,
                "source_span": format_source_span(chunk.start_page, chunk.end_page),
                "title_hint": chunk.title_hint,
                "chunk_text": chunk.text,
            }
        )
        return result.model_copy(
            update={
                "chunk_id": chunk.chunk_id,
                "source_span": format_source_span(chunk.start_page, chunk.end_page),
            }
        )

    def generate_study_material(
        self,
        document: LectureDocument,
        analysis: LectureAnalysis,
        chunk_analyses: list[ChunkAnalysis],
        summary_mode: SummaryMode,
        quiz_count: int,
    ) -> StudyMaterial:
        return self._final_chain.invoke(
            {
                "summary_mode": summary_mode.value,
                "mode_instructions": build_mode_instructions(summary_mode),
                "quiz_count": quiz_count,
                "document_metadata_json": _serialize_document_context(document),
                "analysis_json": analysis.model_dump_json(indent=2),
                "chunk_analyses_json": _serialize_chunk_analyses(chunk_analyses),
            }
        )


class MockStudyCoachLLM:
    provider_name = "mock"

    def analyze_chunk(
        self, chunk: LectureChunk, summary_mode: SummaryMode, document_title: str
    ) -> ChunkAnalysis:
        settings = get_mode_settings(summary_mode)
        content_blocks = _extract_content_blocks(chunk.text)
        content_text = "\n\n".join(content_blocks).strip() or chunk.text
        sentences = _split_sentences(content_text)
        section_title = _clean_heading(chunk.title_hint) or _guess_chunk_title(
            chunk.text, fallback=f"Chunk {chunk.chunk_id}"
        )
        subject_focus = section_title if section_title else document_title
        main_idea = _combine_sentences(sentences[:2]) or (
            f"{subject_focus} is an important part of {document_title}."
        )
        definitions = _extract_definitions(
            content_text, limit=max(2, settings.chunk_key_points - 1)
        )
        formulas_or_facts = _extract_formulas_or_facts(
            content_text, limit=settings.chunk_key_points
        )
        key_points = _extract_key_points_from_text(
            content_text, limit=settings.chunk_key_points
        )
        topics = _extract_topics_from_chunk(
            text=chunk.text,
            title_hint=section_title,
            fallback_subject=document_title,
            limit=max(1, min(3, settings.chunk_key_points)),
        )

        return ChunkAnalysis(
            chunk_id=chunk.chunk_id,
            source_span=format_source_span(chunk.start_page, chunk.end_page),
            section_title=section_title,
            subject_focus=subject_focus,
            main_idea=main_idea,
            topics=topics,
            definitions=definitions,
            formulas_or_facts=formulas_or_facts,
            key_points=key_points,
        )

    def generate_study_material(
        self,
        document: LectureDocument,
        analysis: LectureAnalysis,
        chunk_analyses: list[ChunkAnalysis],
        summary_mode: SummaryMode,
        quiz_count: int,
    ) -> StudyMaterial:
        settings = get_mode_settings(summary_mode)
        section_notes = _build_section_notes(chunk_analyses, settings.target_sections)
        topics = analysis.topics[: settings.target_topics]
        definitions = analysis.definitions[: settings.target_definitions]
        formulas_or_facts = analysis.formulas_or_facts[: settings.target_facts]
        key_points = _build_final_key_points(
            main_goal=analysis.main_goal,
            section_notes=section_notes,
            formulas_or_facts=formulas_or_facts,
            limit=settings.target_key_points,
        )
        overview = _build_overview(
            subject=analysis.subject,
            main_goal=analysis.main_goal,
            section_notes=section_notes,
            paragraph_count=settings.overview_paragraphs,
        )
        quiz = _build_quiz(
            analysis=analysis,
            chunk_analyses=chunk_analyses,
            definitions=definitions,
            formulas_or_facts=formulas_or_facts,
            quiz_count=quiz_count,
        )

        return StudyMaterial(
            title=analysis.title,
            subject=analysis.subject,
            main_goal=analysis.main_goal,
            overview=overview,
            section_notes=section_notes,
            topics=topics,
            definitions=definitions,
            formulas_or_facts=formulas_or_facts,
            key_points=key_points,
            quiz=quiz,
        )


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


def get_mode_settings(summary_mode: SummaryMode) -> ModeSettings:
    return MODE_SETTINGS[summary_mode]


def build_mode_instructions(summary_mode: SummaryMode) -> str:
    if summary_mode == SummaryMode.SMALL:
        return (
            "Create concise notes focused on only the most important ideas. "
            "Keep section notes compact, reduce secondary detail, and emphasize the main concepts, core definitions, and only the strongest takeaways."
        )
    if summary_mode == SummaryMode.MEDIUM:
        return (
            "Create balanced notes that cover the main ideas plus useful supporting details. "
            "Keep section explanations clear and practical for revision, with the main supporting examples, definitions, and key facts."
        )
    return (
        "Create detailed lecture notes that cover the whole document broadly. "
        "Preserve important sections, definitions, formulas, explanations, and section-by-section detail. "
        "Large mode should feel like a real study conspect, not a short summary."
    )


def list_input_files(directory: Path) -> list[Path]:
    if not directory.exists():
        return []
    return sorted(
        [path for path in directory.iterdir() if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS],
        key=lambda path: (path.suffix.lower(), path.name.lower()),
    )


def read_lecture_document(input_path: str) -> LectureDocument:
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
        normalized = _normalize_extracted_text(text)
        page = DocumentPage(
            page_number=1,
            text=normalized,
            block_count=len(_split_blocks(normalized)),
            word_count=_count_words(normalized),
        )
        pages = [page]
        total_pages = 1
    else:
        reader = PdfReader(str(path))
        pages = []
        for page_number, page in enumerate(reader.pages, start=1):
            extracted = _extract_pdf_page_text(page)
            normalized = _normalize_extracted_text(extracted)
            pages.append(
                DocumentPage(
                    page_number=page_number,
                    text=normalized,
                    block_count=len(_split_blocks(normalized)),
                    word_count=_count_words(normalized),
                )
            )
        total_pages = len(reader.pages)

    raw_text = "\n\n".join(page.text for page in pages if page.text.strip())
    title_hint = _detect_title_hint(pages, fallback=path.stem.replace("_", " ").replace("-", " "))
    goal_hint = _detect_goal_hint(raw_text)
    total_words = sum(page.word_count for page in pages)

    if not raw_text.strip():
        raise ValueError(f"No readable content found in {path}")

    return LectureDocument(
        source_path=str(path),
        file_name=path.name,
        title_hint=title_hint,
        goal_hint=goal_hint,
        pages=pages,
        raw_text=raw_text,
        total_pages=total_pages,
        total_words=total_words,
    )


def build_chunks(document: LectureDocument, summary_mode: SummaryMode) -> list[LectureChunk]:
    settings = get_mode_settings(summary_mode)
    blocks: list[tuple[int, str]] = []
    for page in document.pages:
        for block in _split_blocks(page.text):
            if block.strip():
                blocks.append((page.page_number, block.strip()))

    if not blocks:
        return [
            LectureChunk(
                chunk_id=1,
                title_hint=document.title_hint,
                start_page=1,
                end_page=document.total_pages,
                text=document.raw_text,
                word_count=document.total_words,
                char_count=len(document.raw_text),
            )
        ]

    chunks: list[LectureChunk] = []
    current_blocks: list[str] = []
    current_pages: list[int] = []
    current_title = document.title_hint
    chunk_id = 1

    def flush_chunk() -> None:
        nonlocal chunk_id, current_blocks, current_pages, current_title
        if not current_blocks:
            return
        chunk_text = "\n\n".join(current_blocks).strip()
        title_hint = _guess_chunk_title(chunk_text, fallback=current_title or document.title_hint)
        chunks.append(
            LectureChunk(
                chunk_id=chunk_id,
                title_hint=title_hint,
                start_page=min(current_pages),
                end_page=max(current_pages),
                text=chunk_text,
                word_count=_count_words(chunk_text),
                char_count=len(chunk_text),
            )
        )
        chunk_id += 1
        current_blocks = []
        current_pages = []
        current_title = document.title_hint

    for page_number, block in blocks:
        heading_like = _is_heading_block(block)
        prospective_size = len("\n\n".join(current_blocks + [block]))

        if heading_like and current_blocks:
            flush_chunk()
            current_title = _clean_heading(block)

        if current_blocks and prospective_size > settings.chunk_char_limit:
            flush_chunk()

        if heading_like:
            current_title = _clean_heading(block)

        current_blocks.append(block)
        current_pages.append(page_number)

    flush_chunk()
    return chunks


def aggregate_chunk_analyses(
    document: LectureDocument,
    chunk_analyses: list[ChunkAnalysis],
    summary_mode: SummaryMode,
) -> LectureAnalysis:
    settings = get_mode_settings(summary_mode)
    topics = _merge_topics(chunk_analyses, limit=settings.target_topics)
    definitions = _merge_definitions(chunk_analyses, limit=settings.target_definitions)
    formulas_or_facts = _merge_formulas_or_facts(chunk_analyses, limit=settings.target_facts)
    coverage_summary = _dedupe_text(
        [analysis.main_idea for analysis in chunk_analyses if analysis.main_idea]
    )[: max(settings.target_sections, 4)]
    section_titles = _dedupe_text(
        [analysis.section_title for analysis in chunk_analyses if analysis.section_title]
    )[: max(settings.target_sections, 4)]
    subject = document.title_hint.strip() or "Lecture Notes"
    main_goal = document.goal_hint or (
        coverage_summary[0] if coverage_summary else f"Understand the main ideas of {subject}."
    )

    filtered_topics = [
        topic
        for topic in topics
        if topic.topic_name.lower() != subject.lower() or len(topics) == 1
    ]
    if filtered_topics:
        topics = filtered_topics

    if not topics:
        topics = [
            TopicInfo(
                topic_name=title,
                importance=summary,
                key_terms=_extract_key_terms_from_text(f"{title}. {summary}", limit=5),
            )
            for title, summary in zip(section_titles, coverage_summary, strict=False)
        ][: settings.target_topics]

    return LectureAnalysis(
        title=f"Study Report: {subject}",
        subject=subject,
        main_goal=main_goal,
        topics=topics,
        definitions=definitions,
        formulas_or_facts=formulas_or_facts,
        coverage_summary=coverage_summary,
        section_titles=section_titles,
    )


def build_coverage_report(
    document: LectureDocument,
    chunks: list[LectureChunk],
    summary_mode: SummaryMode,
    quiz_count: int,
    output_path: str,
    json_output_path: str | None = None,
) -> CoverageReport:
    return CoverageReport(
        source_file=document.file_name,
        total_pages_read=document.total_pages,
        total_words_read=document.total_words,
        total_chunks_processed=len(chunks),
        selected_summary_mode=summary_mode,
        selected_quiz_count=quiz_count,
        output_markdown_path=output_path,
        output_json_path=json_output_path,
    )


def _extract_topics_from_chunk(
    text: str,
    title_hint: str,
    fallback_subject: str,
    limit: int,
) -> list[TopicInfo]:
    candidates: list[str] = []
    normalized_title = _clean_heading(title_hint)
    content_text = "\n\n".join(_extract_content_blocks(text)).strip() or text
    if normalized_title and normalized_title.lower() != fallback_subject.lower():
        candidates.append(normalized_title)

    for block in _split_blocks(text):
        if _is_heading_block(block):
            candidate = _clean_heading(block)
            if candidate and candidate.lower() != fallback_subject.lower() and candidate not in candidates:
                candidates.append(candidate)
        elif _is_list_item(block):
            candidate = _clean_list_item(block)
            if (
                2 <= len(candidate.split()) <= 8
                and not re.search(r"[.!?]$", candidate)
                and candidate not in candidates
            ):
                candidates.append(candidate)
        if len(candidates) >= limit:
            break

    if normalized_title and normalized_title.lower() == fallback_subject.lower() and normalized_title not in candidates:
        candidates.append(normalized_title)

    if not candidates:
        for sentence in _split_sentences(content_text):
            prefix_match = re.match(
                r"^([A-Z][A-Za-z0-9\-]*(?:\s+[A-Z]?[A-Za-z0-9\-]+){0,3})\s+(is|are|refers to|describes)",
                sentence,
            )
            if prefix_match:
                candidate = prefix_match.group(1).strip()
                if _is_valid_term(candidate) and candidate not in candidates:
                    candidates.append(candidate)
            if len(candidates) >= limit:
                break

    if not candidates:
        candidates.append(fallback_subject)

    topics: list[TopicInfo] = []
    for candidate in candidates[:limit]:
        importance = _best_sentence_for_phrase(candidate, content_text)
        if not importance or importance == candidate:
            importance = f"{candidate} is one of the important ideas developed in this section."
        topics.append(
            TopicInfo(
                topic_name=candidate,
                importance=importance,
                key_terms=_extract_key_terms_from_text(f"{candidate}. {importance}", limit=6),
            )
        )
    return topics


def _best_sentence_for_phrase(phrase: str, text: str) -> str:
    phrase_words = [word.lower() for word in re.findall(r"[A-Za-z][A-Za-z\-]+", phrase)]
    best_sentence = ""
    best_score = -1
    for sentence in _split_sentences(text):
        lowered = sentence.lower()
        score = sum(word in lowered for word in phrase_words)
        if score > best_score or (score == best_score and len(sentence) > len(best_sentence)):
            best_sentence = sentence
            best_score = score
    return best_sentence.strip() or f"{phrase} is one of the important ideas in this section."


def _extract_key_terms_from_text(text: str, limit: int) -> list[str]:
    terms: list[str] = []
    for word in re.findall(r"[A-Za-z][A-Za-z\-]+", text):
        cleaned = word.strip().lower()
        if len(cleaned) < 4 or cleaned in STOPWORDS or cleaned in GENERIC_TERMS:
            continue
        if cleaned not in terms:
            terms.append(cleaned)
        if len(terms) >= limit:
            break
    return [term.title() if " " not in term else term for term in terms[:limit]]


def _extract_definitions(text: str, limit: int) -> list[DefinitionItem]:
    definitions: list[DefinitionItem] = []
    for block in _split_blocks(text):
        candidate = _extract_definition_candidate(block)
        if not candidate:
            continue
        term, definition = candidate
        if not any(item.term.lower() == term.lower() for item in definitions):
            definitions.append(DefinitionItem(term=term, definition=definition))
        if len(definitions) >= limit:
            return definitions

    for sentence in _split_sentences(text):
        candidate = _extract_definition_candidate(sentence)
        if not candidate:
            continue
        term, definition = candidate
        if not any(item.term.lower() == term.lower() for item in definitions):
            definitions.append(DefinitionItem(term=term, definition=definition))
        if len(definitions) >= limit:
            break
    return definitions


def _extract_formulas_or_facts(text: str, limit: int) -> list[FormulaOrFact]:
    items: list[FormulaOrFact] = []
    for block in _split_blocks(text):
        statement = _extract_fact_candidate(block)
        if not statement:
            continue
        if not any(item.statement == statement for item in items):
            items.append(FormulaOrFact(statement=statement, explanation=None))
        if len(items) >= limit:
            return items

    for sentence in _split_sentences(text):
        statement = _extract_fact_candidate(sentence)
        if not statement:
            continue
        if not any(item.statement == statement for item in items):
            items.append(FormulaOrFact(statement=statement, explanation=None))
        if len(items) >= limit:
            break
    return items


def _extract_key_points_from_text(text: str, limit: int) -> list[str]:
    points: list[str] = []
    for block in _split_blocks(text):
        if _is_heading_block(block):
            continue
        cleaned = _clean_list_item(block) if _is_list_item(block) else _normalize_inline_text(block)
        if cleaned and not _is_noise_point(cleaned) and cleaned not in points:
            points.append(cleaned)
        if len(points) >= limit:
            return points

    for sentence in _split_sentences(text):
        cleaned = sentence.strip()
        if cleaned and not _is_noise_point(cleaned) and cleaned not in points:
            points.append(cleaned)
        if len(points) >= limit:
            break
    return points


def _merge_topics(chunk_analyses: list[ChunkAnalysis], limit: int) -> list[TopicInfo]:
    merged: dict[str, TopicInfo] = {}
    order: list[str] = []
    for analysis in chunk_analyses:
        for topic in analysis.topics:
            key = topic.topic_name.lower()
            if key not in merged:
                merged[key] = TopicInfo(
                    topic_name=topic.topic_name,
                    importance=topic.importance,
                    key_terms=topic.key_terms,
                )
                order.append(key)
            else:
                existing = merged[key]
                importance = (
                    topic.importance
                    if len(topic.importance) > len(existing.importance)
                    else existing.importance
                )
                key_terms = _dedupe_text(existing.key_terms + topic.key_terms)[:8]
                merged[key] = TopicInfo(
                    topic_name=existing.topic_name,
                    importance=importance,
                    key_terms=key_terms,
                )
    return [merged[key] for key in order[:limit]]


def _merge_definitions(chunk_analyses: list[ChunkAnalysis], limit: int) -> list[DefinitionItem]:
    merged: dict[str, DefinitionItem] = {}
    order: list[str] = []
    for analysis in chunk_analyses:
        for item in analysis.definitions:
            key = item.term.lower()
            if key not in merged:
                merged[key] = item
                order.append(key)
            elif len(item.definition) > len(merged[key].definition):
                merged[key] = item
    return [merged[key] for key in order[:limit]]


def _merge_formulas_or_facts(
    chunk_analyses: list[ChunkAnalysis], limit: int
) -> list[FormulaOrFact]:
    merged: dict[str, FormulaOrFact] = {}
    order: list[str] = []
    for analysis in chunk_analyses:
        for item in analysis.formulas_or_facts:
            key = item.statement.lower()
            if any(key in existing_key or existing_key in key for existing_key in merged):
                continue
            if key not in merged:
                merged[key] = item
                order.append(key)
    return [merged[key] for key in order[:limit]]


def export_results(
    output_path: str,
    study_material: StudyMaterial,
    coverage: CoverageReport,
    json_output_path: str | None = None,
) -> tuple[Path, Path | None]:
    report_path = Path(output_path)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(render_markdown_report(study_material), encoding="utf-8")

    exported_json_path: Path | None = None
    if json_output_path:
        exported_json_path = Path(json_output_path)
        exported_json_path.parent.mkdir(parents=True, exist_ok=True)
        run_output = StudyRunOutput(coverage=coverage, study_material=study_material)
        exported_json_path.write_text(run_output.model_dump_json(indent=2), encoding="utf-8")

    return report_path, exported_json_path


def render_markdown_report(study_material: StudyMaterial) -> str:
    sections = [
        f"# {study_material.title}",
        _simple_section("Subject", study_material.subject),
        _simple_section("Main Goal", study_material.main_goal),
        _render_conspect(study_material.overview, study_material.section_notes),
        _render_topics(study_material.topics),
        _render_key_terms(study_material.topics),
        _render_definitions(study_material.definitions),
        _render_formulas_or_facts(study_material.formulas_or_facts),
        _render_key_points(study_material.key_points),
        _render_quiz(study_material.quiz),
        _render_answer_key(study_material.quiz),
    ]
    return "\n\n".join(section for section in sections if section).strip() + "\n"


def format_source_span(start_page: int, end_page: int) -> str:
    if start_page == end_page:
        return f"Page {start_page}"
    return f"Pages {start_page}-{end_page}"


def _serialize_chunk_analyses(chunk_analyses: list[ChunkAnalysis]) -> str:
    serialized = [analysis.model_dump(mode="json") for analysis in chunk_analyses]
    return json.dumps(serialized, indent=2, ensure_ascii=False)


def _serialize_document_context(document: LectureDocument) -> str:
    payload = {
        "file_name": document.file_name,
        "title_hint": document.title_hint,
        "goal_hint": document.goal_hint,
        "total_pages": document.total_pages,
        "total_words": document.total_words,
        "page_summaries": [
            {
                "page_number": page.page_number,
                "block_count": page.block_count,
                "word_count": page.word_count,
            }
            for page in document.pages
        ],
    }
    return json.dumps(payload, indent=2, ensure_ascii=False)


def _simple_section(title: str, content: str) -> str:
    cleaned = _normalize_inline_text(content) if content else "Not available."
    return f"## {title}\n\n{cleaned}"


def _render_conspect(overview: str, section_notes: list[SectionNote]) -> str:
    lines = ["## Structured Lecture Notes / Conspect", ""]
    overview_text = overview.strip() if overview else "No overview was generated."
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n", overview_text) if part.strip()]
    if paragraphs:
        lines.append("### Lecture Overview")
        lines.append("")
    for paragraph in paragraphs:
        lines.append(_normalize_inline_text(paragraph))
        lines.append("")

    if section_notes:
        for section in section_notes:
            lines.append(f"### {section.section_title} ({section.source_span})")
            lines.append("")
            lines.append(_normalize_inline_text(section.section_summary))
            lines.append("")
            for point in section.important_points:
                lines.append(f"- {point}")
            lines.append("")

    return "\n".join(lines).rstrip()


def _render_topics(topics: list[TopicInfo]) -> str:
    lines = ["## Key Topics", ""]
    if not topics:
        lines.append("- No key topics were identified.")
        return "\n".join(lines)

    for topic in topics:
        importance = _trim_topic_importance(topic.topic_name, topic.importance)
        lines.append(f"- **{topic.topic_name}** - {importance}")
    return "\n".join(lines)


def _render_key_terms(topics: list[TopicInfo]) -> str:
    lines = ["## Key Terms", ""]
    if not topics:
        lines.append("No key terms were identified.")
        return "\n".join(lines)

    for topic in topics:
        lines.append(f"### {topic.topic_name}")
        lines.append("")
        if topic.key_terms:
            for term in topic.key_terms:
                lines.append(f"- {term}")
        else:
            lines.append("- No key terms provided.")
        lines.append("")
    return "\n".join(lines).rstrip()


def _render_definitions(definitions: list[DefinitionItem]) -> str:
    lines = ["## Important Definitions", ""]
    if not definitions:
        lines.append("- No important definitions were explicitly detected.")
        return "\n".join(lines)

    for item in definitions:
        lines.append(f"- **{item.term}**: {_trim_definition_text(item.term, item.definition)}")
    return "\n".join(lines)


def _render_formulas_or_facts(formulas_or_facts: list[FormulaOrFact]) -> str:
    lines = ["## Important Formulas or Facts", ""]
    if not formulas_or_facts:
        lines.append("- No formulas or major facts were explicitly detected.")
        return "\n".join(lines)

    for item in formulas_or_facts:
        if item.explanation:
            lines.append(f"- **{item.statement}**: {item.explanation}")
        else:
            lines.append(f"- {item.statement}")
    return "\n".join(lines)


def _render_key_points(key_points: list[str]) -> str:
    lines = ["## Key Points / Major Takeaways", ""]
    if not key_points:
        lines.append("- No key points were generated.")
        return "\n".join(lines)

    for point in key_points:
        lines.append(f"- {_compact_sentence(point)}")
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


def _extract_pdf_page_text(page) -> str:
    try:
        text = page.extract_text(extraction_mode="layout") or ""
    except TypeError:
        text = page.extract_text() or ""
    except Exception:
        text = page.extract_text() or ""

    if not text.strip():
        text = page.extract_text() or ""
    return text


def _normalize_extracted_text(text: str) -> str:
    text = text.replace("\x00", " ")
    text = re.sub(r"(\w)-\s*\n\s*(\w)", r"\1\2", text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    blocks: list[str] = []
    paragraph_lines: list[str] = []

    def flush_paragraph() -> None:
        nonlocal paragraph_lines
        if not paragraph_lines:
            return
        paragraph = " ".join(paragraph_lines)
        blocks.append(_normalize_inline_text(paragraph))
        paragraph_lines = []

    for raw_line in text.split("\n"):
        line = _normalize_inline_text(raw_line)
        if not line:
            flush_paragraph()
            continue

        if _is_structural_line(line):
            flush_paragraph()
            blocks.append(_normalize_structural_line(line))
            continue

        if paragraph_lines and _should_break_paragraph(paragraph_lines[-1], line):
            flush_paragraph()

        paragraph_lines.append(line)

    flush_paragraph()
    return "\n\n".join(block for block in blocks if block).strip()


def _split_blocks(text: str) -> list[str]:
    return [block.strip() for block in re.split(r"\n\s*\n", text) if block.strip()]


def _count_words(text: str) -> int:
    return len(re.findall(r"\b[\w\-]+\b", text))


def _detect_title_hint(pages: list[DocumentPage], fallback: str) -> str:
    for page in pages[:2]:
        for block in _split_blocks(page.text):
            cleaned = _clean_heading(block)
            if cleaned and len(cleaned) <= 120:
                return cleaned
    return fallback.strip() or "Lecture Notes"


def _detect_goal_hint(raw_text: str) -> str | None:
    goal_pattern = re.compile(
        r"^(goal|objective|aim|learning goal|learning objective)\s*:\s*(.+)$",
        re.IGNORECASE | re.MULTILINE,
    )
    match = goal_pattern.search(raw_text)
    if match:
        return match.group(2).strip()
    return None


def _is_heading_block(block: str) -> bool:
    stripped = block.strip()
    if not stripped:
        return False
    if stripped.startswith("#"):
        return True
    if _is_list_item(stripped) or _is_label_line(stripped) or _looks_like_formula(stripped):
        return False

    plain = _clean_heading(stripped)
    if not plain or len(plain) > 80 or re.search(r"[.!?;:]$", plain):
        return False

    words = plain.split()
    if not 1 <= len(words) <= 10:
        return False

    title_case_words = sum(1 for word in words if word[:1].isupper())
    if plain.isupper():
        return True
    return title_case_words >= max(1, len(words) - 1)


def _clean_heading(block: str) -> str:
    cleaned = re.sub(r"^#+\s*", "", block).strip()
    cleaned = re.sub(r"^(?:[-*•]\s+|\d+[.)]\s+)", "", cleaned).strip()
    return _normalize_inline_text(cleaned)


def _guess_chunk_title(text: str, fallback: str) -> str:
    for block in _split_blocks(text):
        cleaned = _clean_heading(block)
        if _is_heading_block(block) and cleaned and len(cleaned) <= 80:
            return cleaned
    for block in _split_blocks(text):
        if _is_list_item(block):
            cleaned = _clean_list_item(block)
            if cleaned and len(cleaned) <= 80:
                return cleaned
    sentences = _split_sentences(text)
    if sentences:
        return sentences[0][:80].rstrip(".")
    return fallback


def _split_sentences(text: str) -> list[str]:
    normalized_text = re.sub(r"\s+", " ", text.replace("\n", " ")).strip()
    return [
        _normalize_inline_text(sentence)
        for sentence in re.split(r"(?<=[.!?])\s+", normalized_text)
        if sentence.strip()
    ]


def _combine_sentences(sentences: list[str]) -> str:
    cleaned = [sentence.strip() for sentence in sentences if sentence.strip()]
    return " ".join(cleaned).strip()


def _normalize_inline_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _is_list_item(line: str) -> bool:
    return bool(re.match(r"^(?:[-*•]\s+|\d+[.)]\s+|[A-D][.)]\s+)", line.strip()))


def _clean_list_item(line: str) -> str:
    return _normalize_inline_text(re.sub(r"^(?:[-*•]\s+|\d+[.)]\s+|[A-D][.)]\s+)", "", line.strip()))


def _is_label_line(line: str) -> bool:
    return bool(
        re.match(
            r"^(goal|objective|aim|learning goal|learning objective|summary|overview|definition|definitions|topic|topics|key points?)\s*:",
            line.strip(),
            re.IGNORECASE,
        )
    )


def _looks_like_formula(line: str) -> bool:
    return "=" in line and len(line) <= 160


def _looks_like_heading_line(line: str) -> bool:
    plain = _clean_heading(line)
    if not plain or len(plain) > 80 or re.search(r"[.!?;:]$", plain):
        return False

    words = plain.split()
    if not 1 <= len(words) <= 10:
        return False

    if plain.isupper():
        return True

    title_case_words = sum(1 for word in words if word[:1].isupper())
    return title_case_words >= max(1, len(words) - 1)


def _is_structural_line(line: str) -> bool:
    stripped = line.strip()
    return (
        stripped.startswith("#")
        or _is_list_item(stripped)
        or _is_label_line(stripped)
        or _looks_like_formula(stripped)
        or _looks_like_heading_line(stripped)
    )


def _normalize_structural_line(line: str) -> str:
    stripped = line.strip()
    if stripped.startswith("#"):
        heading = _clean_heading(stripped)
        return f"# {heading}" if heading else stripped
    if _is_list_item(stripped):
        return f"- {_clean_list_item(stripped)}"
    return _normalize_inline_text(stripped)


def _should_break_paragraph(previous_line: str, next_line: str) -> bool:
    combined_length = len(previous_line) + len(next_line)
    if combined_length > 420:
        return True
    if re.search(r"[.!?]$", previous_line) and _looks_like_heading_line(next_line):
        return True
    return False


def _extract_definition_candidate(text: str) -> tuple[str, str] | None:
    cleaned = _normalize_inline_text(text)
    if not cleaned or _is_heading_block(cleaned):
        return None

    colon_match = re.match(r"^([A-Z][A-Za-z0-9()\/\-]*(?:\s+[A-Za-z0-9()\/\-]+){0,5})\s*:\s*(.+)$", cleaned)
    if colon_match:
        term = colon_match.group(1).strip()
        definition = cleaned
        if _is_valid_term(term):
            return term, definition

    sentence_match = re.match(
        r"^([A-Z][A-Za-z0-9()\/\-]*(?:\s+[A-Za-z0-9()\/\-]+){0,5})\s+(is|are|refers to|means)\s+(.+)$",
        cleaned,
    )
    if not sentence_match:
        return None

    term = sentence_match.group(1).strip()
    if not _is_valid_term(term):
        return None
    return term, cleaned


def _extract_fact_candidate(text: str) -> str | None:
    cleaned = _clean_list_item(text) if _is_list_item(text) else _normalize_inline_text(text)
    if not cleaned or _is_heading_block(cleaned):
        return None

    lowered = cleaned.lower()
    if "=" in cleaned:
        return _strip_fact_prefix(cleaned)
    if any(keyword in lowered for keyword in FACT_KEYWORDS):
        return _strip_fact_prefix(cleaned)
    if re.search(r"\b\d+(?:\.\d+)?%?\b", cleaned) and len(cleaned.split()) >= 5:
        return _strip_fact_prefix(cleaned)
    return None


def _is_valid_term(term: str) -> bool:
    if not term or len(term.split()) > 6:
        return False
    lowered = term.lower()
    if lowered in STOPWORDS:
        return False
    if lowered in {
        "learning goal",
        "important fact",
        "important rule",
        "definition",
        "definitions",
        "formula",
        "formulas",
        "examples",
        "the key idea",
    }:
        return False
    if lowered.startswith(("if ", "examples", "important rule", "important fact", "the key idea")):
        return False
    first_word = lowered.split()[0]
    if first_word in {"a", "an", "the", "this", "that", "these", "those", "if", "here", "even"}:
        return False
    return bool(re.search(r"[A-Za-z]", term))


def _extract_content_blocks(text: str) -> list[str]:
    blocks: list[str] = []
    for block in _split_blocks(text):
        cleaned = _normalize_inline_text(block)
        if not cleaned or _is_heading_block(cleaned):
            continue
        if re.match(r"^[A-Za-z][A-Za-z\s]+:\s*$", cleaned):
            continue
        blocks.append(_clean_list_item(cleaned) if _is_list_item(cleaned) else cleaned)
    return blocks


def _strip_fact_prefix(text: str) -> str:
    return re.sub(r"^(formula|important fact|fact|rule|definition)\s*:\s*", "", text, flags=re.IGNORECASE)


def _is_noise_point(text: str) -> bool:
    cleaned = _normalize_inline_text(text)
    if not cleaned:
        return True
    if re.match(r"^[A-Za-z][A-Za-z\s]+:\s*$", cleaned):
        return True
    return cleaned.lower() in {"examples", "example", "formula", "definition", "important fact"}


def _build_section_notes(
    chunk_analyses: list[ChunkAnalysis], target_sections: int
) -> list[SectionNote]:
    if not chunk_analyses:
        return []

    sections: list[SectionNote] = []
    for group in _partition_evenly(chunk_analyses, min(target_sections, len(chunk_analyses))):
        first = group[0]
        last = group[-1]
        title = first.section_title
        if len(group) > 1 and first.section_title != last.section_title:
            title = f"{first.section_title} to {last.section_title}"
        summary_sentences = _dedupe_text(
            [_compact_sentence(analysis.main_idea) for analysis in group if analysis.main_idea]
        )[:3]
        section_summary = " ".join(summary_sentences)
        raw_points = [point for analysis in group for point in analysis.key_points]
        important_points = _dedupe_text(
            [
                point
                for point in raw_points
                if not _is_noise_point(point)
                and _compact_sentence(point) not in {
                    _compact_sentence(summary) for summary in summary_sentences
                }
            ]
        )[:5]
        sections.append(
            SectionNote(
                section_title=title,
                source_span=_merge_source_spans(first.source_span, last.source_span),
                section_summary=section_summary or first.main_idea,
                important_points=important_points,
            )
        )

    return sections


def _merge_source_spans(start_span: str, end_span: str) -> str:
    page_numbers = [int(number) for number in re.findall(r"\d+", f"{start_span} {end_span}")]
    if not page_numbers:
        return start_span
    return format_source_span(min(page_numbers), max(page_numbers))


def _build_final_key_points(
    main_goal: str,
    section_notes: list[SectionNote],
    formulas_or_facts: list[FormulaOrFact],
    limit: int,
) -> list[str]:
    points = [_compact_sentence(main_goal)]
    for section in section_notes:
        points.extend(_compact_sentence(point) for point in section.important_points[:2])
    points.extend(_compact_sentence(item.statement) for item in formulas_or_facts[: max(2, limit // 4)])
    return _dedupe_text(points)[:limit]


def _build_overview(
    subject: str,
    main_goal: str,
    section_notes: list[SectionNote],
    paragraph_count: int,
) -> str:
    if not section_notes:
        return f"{subject} is covered with emphasis on the main learning goal: {main_goal}"

    groups = _group_list(section_notes, max(1, paragraph_count))
    paragraphs = []
    for group in groups:
        titles = ", ".join(section.section_title for section in group)
        summary_text = " ".join(
            _compact_sentence(section.section_summary) for section in group if section.section_summary
        )
        paragraph = f"{titles}: {summary_text}".strip(": ")
        paragraphs.append(paragraph)
    return "\n\n".join(paragraphs[:paragraph_count])


def _build_quiz(
    analysis: LectureAnalysis,
    chunk_analyses: list[ChunkAnalysis],
    definitions: list[DefinitionItem],
    formulas_or_facts: list[FormulaOrFact],
    quiz_count: int,
) -> list[QuizQuestion]:
    questions: list[QuizQuestion] = []
    question_texts: set[str] = set()
    main_ideas = [chunk.main_idea for chunk in chunk_analyses if chunk.main_idea]
    topic_explanations = [topic.importance for topic in analysis.topics if topic.importance]

    def add_question(question: QuizQuestion) -> None:
        if question.question not in question_texts and len(questions) < quiz_count:
            questions.append(question)
            question_texts.add(question.question)

    add_question(
        _make_question(
            question=f"What best describes the main goal of {analysis.subject}?",
            correct_option=analysis.main_goal,
            distractor_pool=main_ideas
            + topic_explanations
            + [
                "It focuses only on a minor detail from one isolated section.",
                "It ignores the full-document structure of the lecture.",
            ],
            explanation="The correct answer reflects the overall goal developed across the full lecture.",
            correct_index=0,
        )
    )

    if quiz_count == 1:
        return questions[:1]

    section_quota = min(len(chunk_analyses), max(2, quiz_count // 2))
    definition_quota = min(len(definitions), max(1, (quiz_count - 1 - section_quota) // 2))
    fact_quota = min(
        len(formulas_or_facts),
        max(1, quiz_count - 1 - section_quota - definition_quota),
    )

    section_targets = _sample_evenly(chunk_analyses, section_quota)
    for index, chunk in enumerate(section_targets, start=1):
        add_question(
            _make_question(
                question=f"Which statement best captures the section on {chunk.section_title}?",
                correct_option=chunk.main_idea,
                distractor_pool=[
                    other.main_idea
                    for other in chunk_analyses
                    if other.chunk_id != chunk.chunk_id and other.main_idea
                ]
                + topic_explanations,
                explanation="The correct answer summarizes the main idea from that section of the lecture.",
                correct_index=index % 4,
            )
        )

    definition_targets = _sample_evenly(definitions, definition_quota)
    for index, definition in enumerate(definition_targets, start=1):
        add_question(
            _make_question(
                question=f"Which option best defines {definition.term}?",
                correct_option=definition.definition,
                distractor_pool=[
                    other.definition
                    for other in definitions
                    if other.term.lower() != definition.term.lower()
                ]
                + main_ideas,
                explanation=f"The correct answer matches the definition of {definition.term} presented in the notes.",
                correct_index=(index + 1) % 4,
            )
        )

    fact_targets = _sample_evenly(formulas_or_facts, fact_quota)
    for index, item in enumerate(fact_targets, start=1):
        add_question(
            _make_question(
                question="Which option matches an important formula or factual statement from the lecture?",
                correct_option=item.statement,
                distractor_pool=[
                    other.statement
                    for other in formulas_or_facts
                    if other.statement != item.statement
                ]
                + main_ideas,
                explanation="The correct answer is a formula or factual statement explicitly highlighted in the lecture.",
                correct_index=(index + 2) % 4,
            )
        )

    topic_targets = _sample_evenly(analysis.topics, min(len(analysis.topics), quiz_count))
    for index, topic in enumerate(topic_targets, start=1):
        add_question(
            _make_question(
                question=f"Why is {topic.topic_name} important in this lecture?",
                correct_option=topic.importance,
                distractor_pool=[
                    other.importance
                    for other in analysis.topics
                    if other.topic_name != topic.topic_name and other.importance
                ]
                + main_ideas,
                explanation=f"The correct answer explains the role of {topic.topic_name} in the overall lecture.",
                correct_index=(index + 3) % 4,
            )
        )

    return questions[:quiz_count]


def _make_question(
    question: str,
    correct_option: str,
    distractor_pool: list[str],
    explanation: str,
    correct_index: int,
) -> QuizQuestion:
    correct_option = _normalize_inline_text(correct_option)
    distractors: list[str] = []
    for candidate in distractor_pool:
        cleaned = _normalize_inline_text(candidate)
        if (
            cleaned
            and cleaned != correct_option
            and cleaned not in distractors
            and cleaned.lower() != correct_option.lower()
        ):
            distractors.append(cleaned)
        if len(distractors) == 3:
            break

    for fallback in GENERIC_DISTRACTORS:
        if len(distractors) == 3:
            break
        if fallback not in distractors and fallback.lower() != correct_option.lower():
            distractors.append(fallback)

    options: list[str] = []
    distractor_index = 0
    for index in range(4):
        if index == correct_index:
            options.append(correct_option)
        else:
            options.append(distractors[distractor_index])
            distractor_index += 1

    return QuizQuestion(
        question=question,
        options=options,
        correct_answer=ANSWER_LABELS[correct_index],
        explanation=explanation,
    )


def _sample_evenly(items: list[T], target_count: int) -> list[T]:
    if not items or target_count <= 0:
        return []
    if len(items) <= target_count:
        return items
    if target_count == 1:
        return [items[len(items) // 2]]

    selected_indices = {
        round(index * (len(items) - 1) / (target_count - 1))
        for index in range(target_count)
    }
    return [item for index, item in enumerate(items) if index in selected_indices]


def _group_list(items: list[SectionNote], group_count: int) -> list[list[SectionNote]]:
    return _partition_evenly(items, group_count)


def _partition_evenly(items: list[T], group_count: int) -> list[list[T]]:
    if not items or group_count <= 0:
        return []

    actual_groups = min(group_count, len(items))
    base_size, remainder = divmod(len(items), actual_groups)
    groups: list[list[T]] = []
    start_index = 0
    for group_index in range(actual_groups):
        size = base_size + (1 if group_index < remainder else 0)
        groups.append(items[start_index : start_index + size])
        start_index += size
    return groups


def _dedupe_text(items: list[str]) -> list[str]:
    deduped: list[str] = []
    for item in items:
        cleaned = item.strip()
        if cleaned and cleaned not in deduped:
            deduped.append(cleaned)
    return deduped


def _compact_sentence(text: str, max_length: int = 220) -> str:
    cleaned = _normalize_inline_text(text)
    if len(cleaned) <= max_length:
        return cleaned

    sentences = _split_sentences(cleaned)
    if sentences:
        first = sentences[0]
        if len(first) <= max_length:
            return first
    return cleaned[: max_length - 3].rstrip(" ,;:") + "..."


def _trim_topic_importance(topic_name: str, importance: str) -> str:
    normalized_topic = _normalize_inline_text(topic_name)
    normalized_importance = _normalize_inline_text(re.sub(r"^#+\s*", "", importance))
    pattern = re.compile(rf"^{re.escape(normalized_topic)}[\s:,-]*", re.IGNORECASE)
    trimmed = pattern.sub("", normalized_importance).strip()
    return trimmed or normalized_importance


def _trim_definition_text(term: str, definition: str) -> str:
    normalized = _normalize_inline_text(re.sub(r"^#+\s*", "", definition))
    pattern = re.compile(rf"^(?:{re.escape(term)}|definition|important fact)\s*:\s*", re.IGNORECASE)
    trimmed = pattern.sub("", normalized).strip()
    return trimmed or normalized
