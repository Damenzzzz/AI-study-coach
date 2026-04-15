# AI Study Coach for Lecture Notes

This project is a CLI-based lecture study assistant built with LangGraph for Assignment 4. It reads local lecture files (`.txt`, `.md`, `.pdf`), processes the whole lecture with chunk-based analysis, and produces a polished Markdown study report for revision.

The project keeps the assignment-friendly structure:

- LangGraph `StateGraph`
- Pydantic graph state
- structured Pydantic outputs for LLM calls
- prompts stored in a separate `prompts.py`
- runnable `main.py`
- sample input and sample output files

## What It Does

The system turns lecture notes into a revision handout that includes:

- title
- subject
- main goal
- structured lecture notes / conspect
- key topics
- key terms
- important definitions
- important formulas or facts
- multiple-choice quiz
- answer key

The main visible output is a Markdown file. JSON is still available as an optional secondary technical output.

## Architecture

The workflow keeps the LangGraph + Pydantic design, but now handles long lectures more intelligently.

1. `ingest_notes`
   Reads the selected `.txt`, `.md`, or `.pdf` file and builds a normalized `LectureDocument`.

2. `chunk_notes`
   Splits the lecture into logical chunks based on headings, blocks, pages, and size limits.

3. `analyze_chunks`
   LLM call #1. Each chunk is analyzed separately into a structured `ChunkAnalysis`.

4. `aggregate_analysis`
   Combines chunk analyses into a full-document `LectureAnalysis` and builds a console coverage report.

5. `generate_study_material`
   LLM call #2. Creates the final structured `StudyMaterial` from the whole lecture coverage.

6. `export_report`
   Renders the final Markdown handout and optionally exports JSON.

This keeps the system simple enough to defend in class while still solving the long-document problem.

## Full-Lecture Coverage Strategy

The main project improvement is that the system no longer relies on a single short excerpt.

- the lecture is first parsed into pages and logical blocks
- blocks are grouped into chunks
- each chunk is analyzed separately
- the final report is generated from all chunk analyses, not one fragment
- the quiz is also generated from the whole lecture coverage

This is a simple form of hierarchical summarization:

1. section/chunk analysis
2. full-lecture aggregation
3. final report generation

That makes the output much more reliable for long lecture notes.

## File Parsing

The project works only with local files. No web scraping is used.

Supported inputs:

- `.txt`
- `.md`
- `.pdf`

Parsing behavior:

- `.txt` and `.md`: preserves headings, list items, labels, and paragraph structure
- `.pdf`: uses `pypdf` with page-aware extraction and layout-friendly fallback
- normalized text is split into logical blocks to preserve reading order as much as possible

This is intentionally simple and defendable rather than overengineered.

## Interactive CLI Workflow

If you run `main.py` without an input path, the program starts interactive mode.

### Step 1. File selection

The program scans the `sample_input` folder and shows available files:

```text
Available lecture files:
1. lecture_long.md
2. lecture.txt
Select a file by number:
```

### Step 2. Summary size

The program asks for the summary size:

```text
1. Large
2. Medium
3. Small
```

Behavior:

- `Small`: concise notes with only the most important ideas
- `Medium`: balanced notes with main ideas and useful supporting details
- `Large`: detailed conspect with broad document coverage, more sections, more key points, and more study detail

### Step 3. Output Markdown filename

The program asks:

```text
Enter output markdown filename (without extension):
```

If you enter `conspect`, the output becomes:

```text
sample_output/conspect.md
```

### Step 4. Quiz count

The program asks for the number of quiz questions:

```text
1. 1
2. 5
3. 10
```

Each quiz question:

- is multiple-choice
- has exactly 4 options
- uses answer labels `A`, `B`, `C`, `D`
- has exactly one correct answer
- includes an answer key section at the end

## Summary Modes

The modes are intentionally different in behavior.

### Small

- fewer section notes
- fewer key topics
- fewer key points
- shorter overall report
- keeps only the strongest ideas for fast revision

### Medium

- balanced report length
- keeps main ideas plus supporting detail
- suitable for normal revision sessions

### Large

- more chunks preserved in the final structure
- more section notes
- more key points
- broader document coverage
- feels like a study conspect rather than a short summary

## Coverage Report in Console

After processing, the CLI prints a coverage report such as:

```text
Coverage Report
- source file: lecture_long.md
- total pages read: 1
- total words read: 1189
- total chunks processed: 13
- selected summary mode: large
- selected quiz count: 10
- output markdown path: sample_output\study_report.md
```

This makes it easy to demonstrate that the tool processed the whole lecture rather than a tiny excerpt.

## Project Files

- `main.py` - CLI entry point and interactive workflow
- `graph.py` - LangGraph pipeline
- `state.py` - Pydantic graph state
- `schemas.py` - typed Pydantic models and validation
- `prompts.py` - all prompts as named constants
- `utils.py` - parsing, chunking, LLM helpers, Markdown export, coverage helpers
- `sample_input/lecture.txt` - short example input
- `sample_input/lecture_long.md` - long example input for chunking and full coverage
- `sample_output/study_report.md` - sample Markdown report
- `sample_output/study_report.json` - optional technical JSON export

## Setup

Create and activate a virtual environment:

```bash
python -m venv .venv
.venv\Scripts\activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Optional environment variables for real OpenAI calls:

```env
OPENAI_API_KEY=your_api_key_here
OPENAI_MODEL=gpt-4o-mini
```

## Run

### Interactive mode

```bash
python main.py --provider mock
```

### Interactive mode with OpenAI

```bash
python main.py --provider openai --model gpt-4o-mini
```

### Non-interactive mode

```bash
python main.py sample_input/lecture_long.md --provider mock --mode large --quiz-count 10 --output sample_output/study_report.md
```

### With optional JSON output

```bash
python main.py sample_input/lecture_long.md --provider mock --mode large --quiz-count 10 --output sample_output/study_report.md --json-output sample_output/study_report.json
```

### With a PDF file

```bash
python main.py lecture.pdf --provider mock --mode medium --quiz-count 5 --output sample_output/lecture_report.md
```

## Output Format

The main visible output is a polished Markdown report:

- `study_report.md`

Optional secondary output:

- `study_report.json`

The Markdown report is generated from structured Pydantic data, not from raw free-text dumping.

## Validation and Reliability

Validation included in the project:

- graph state is a Pydantic model
- quiz options must contain exactly 4 entries
- quiz options must be distinct
- `correct_answer` must be `A`, `B`, `C`, or `D`
- Markdown rendering handles optional explanation fields safely

## Assignment Requirement Mapping

- `Use LangGraph StateGraph` -> implemented in `graph.py`
- `At least 3 nodes` -> implemented with 6 nodes
- `At least 2 LLM calls` -> chunk analysis + final report generation
- `Use Pydantic structured outputs` -> `ChunkAnalysis`, `LectureAnalysis`, `StudyMaterial`, `QuizQuestion`, etc.
- `Use a Pydantic model for graph state` -> `AgentState`
- `Keep prompts in prompts.py` -> satisfied
- `Produce a sample output file` -> `sample_output/study_report.md`
- `Include README with short explanation and run instructions` -> this file

## Validation Commands Used

The project was validated with commands such as:

```bash
python -m compileall main.py graph.py state.py schemas.py prompts.py utils.py
python main.py sample_input/lecture_long.md --provider mock --mode large --quiz-count 10 --output sample_output/study_report.md --json-output sample_output/study_report.json
python main.py sample_input/lecture_long.md --provider mock --mode medium --quiz-count 5 --output sample_output/validation_medium.md
python main.py sample_input/lecture_long.md --provider mock --mode small --quiz-count 1 --output sample_output/validation_small.md
```

An interactive flow was also tested successfully by selecting a file from `sample_input`, choosing a summary size, entering a custom output name, and generating a custom Markdown file.
