# AI Study Coach for Lecture Notes

This project is a mini AI agent system built with LangGraph for Assignment 4. It reads lecture notes from a `.txt`, `.md`, or `.pdf` file, extracts the lecture structure, generates revision material, and exports a polished Markdown study handout.

## Architecture

The project keeps the same simple 4-node LangGraph pipeline:

1. `ingest_notes` reads the source file and converts it into raw text.
2. `analyze_notes` makes LLM call #1 and returns `LectureAnalysis`.
3. `generate_study_material` makes LLM call #2 and returns the final `StudyMaterial`.
4. `export_report` renders `study_report.md` and optionally writes a secondary JSON file.

The graph state is a Pydantic model in `state.py`, and both LLM calls use structured Pydantic outputs from `schemas.py`.

## Clean Schema Design

The final output structure is intentionally simple and easy to explain during defense:

- `TopicInfo`
  - `topic_name`
  - `importance`
  - `key_terms`
- `QuizQuestion`
  - `question`
  - `options`
  - `correct_answer`
  - `explanation`
- `StudyMaterial`
  - `title`
  - `subject`
  - `main_goal`
  - `topics`
  - `summary`
  - `key_points`
  - `quiz`

Validation rules:

- each quiz question must contain exactly 4 options
- `correct_answer` must be one of `A`, `B`, `C`, or `D`
- optional explanation fields are handled safely during Markdown export

## Assignment Checklist

- `3+ LangGraph nodes`: implemented in `graph.py`
- `2+ LLM calls`: implemented in `OpenAIStudyCoachLLM`
- `Pydantic structured outputs`: `LectureAnalysis` and `StudyMaterial`
- `Pydantic graph state`: `AgentState`
- `Separate prompts.py`: all prompts are stored there
- `Runnable main entry point`: `main.py`
- `Sample output file`: `sample_output/study_report.md`
- `README instructions`: this file

## Files

- `main.py` - command-line entry point
- `graph.py` - LangGraph workflow
- `state.py` - Pydantic graph state
- `schemas.py` - Pydantic output models and validation
- `prompts.py` - all prompts as named constants
- `utils.py` - file parsing, LLM setup, Markdown rendering, and export helpers
- `sample_input/lecture.txt` - example lecture notes
- `sample_output/study_report.md` - example Markdown study handout
- `sample_output/study_report.json` - optional technical JSON export

## Setup

1. Create a virtual environment:

```bash
python -m venv .venv
```

2. Activate it:

```bash
.venv\Scripts\activate
```

3. Install dependencies:

```bash
pip install -r requirements.txt
```

4. Optional: create a `.env` file for OpenAI:

```env
OPENAI_API_KEY=your_api_key_here
OPENAI_MODEL=gpt-4o-mini
```

## Run

Default run, which writes the Markdown handout:

```bash
python main.py sample_input/lecture.txt
```

Run with an additional JSON export:

```bash
python main.py sample_input/lecture.txt --json-output sample_output/study_report.json
```

Run explicitly with OpenAI:

```bash
python main.py sample_input/lecture.txt --provider openai --model gpt-4o-mini
```

Run offline with the built-in mock provider:

```bash
python main.py sample_input/lecture.txt --provider mock
```

You can also pass a Markdown or PDF file:

```bash
python main.py notes.md
python main.py lecture.pdf
```

## Output

The main final output is:

- `sample_output/study_report.md`

The report contains:

1. Title
2. Subject
3. Main goal of the lecture
4. Key topics
5. Key terms for each topic
6. Study-note style summary
7. Key points / formulas / important facts
8. Quiz with multiple-choice questions
9. Answer key

Optional secondary output:

- `sample_output/study_report.json`

## Notes

- PDF support is basic but functional through `pypdf`.
- For assignment defense, use `--provider openai` if you want to demonstrate the real structured LLM calls live.
- `--provider mock` keeps the project runnable in environments without an API key.

## Validation

These checks were rerun after the Markdown export update:

```bash
python main.py sample_input/lecture.txt --provider mock --output sample_output/study_report.md --json-output sample_output/study_report.json
python main.py "C:/Users/chebupel777/Downloads/Assignment 4 AIPE.pdf" --provider mock --output sample_output/assignment_report.md
python -m compileall main.py graph.py state.py schemas.py prompts.py utils.py
```
