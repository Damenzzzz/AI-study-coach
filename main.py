from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from graph import build_study_coach_graph
from schemas import SummaryMode
from state import AgentState
from utils import create_llm, list_input_files


# Configure logging
def setup_logging(verbose: bool = False) -> logging.Logger:
    """Configure logging for the application."""
    log_level = logging.DEBUG if verbose else logging.INFO

    # Create logger
    logger = logging.getLogger()
    logger.setLevel(log_level)

    # Remove existing handlers
    logger.handlers = []

    # Create console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)

    # Create formatter
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    console_handler.setFormatter(formatter)

    # Add handler to logger
    logger.addHandler(console_handler)

    return logger


logger = logging.getLogger(__name__)

SUMMARY_MODE_CHOICES = {
    "1": SummaryMode.LARGE,
    "2": SummaryMode.MEDIUM,
    "3": SummaryMode.SMALL,
}
QUIZ_COUNT_CHOICES = {"1": 1, "2": 5, "3": 10}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate a study report from lecture notes with LangGraph."
    )
    parser.add_argument(
        "input_path",
        nargs="?",
        default=None,
        help="Path to a .txt, .md, or .pdf lecture notes file. If omitted, interactive mode is used.",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Path for the exported Markdown study report.",
    )
    parser.add_argument(
        "--json-output",
        default=None,
        help="Optional path for a secondary JSON export.",
    )
    parser.add_argument(
        "--provider",
        choices=["auto", "openai", "mock"],
        default="auto",
        help="LLM provider. 'auto' uses OpenAI when OPENAI_API_KEY exists, otherwise mock mode.",
    )
    parser.add_argument(
        "--model",
        default=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        help="OpenAI model name used when provider=openai or auto resolves to OpenAI.",
    )
    parser.add_argument(
        "--mode",
        choices=[mode.value for mode in SummaryMode],
        default=None,
        help="Summary size mode: small, medium, or large.",
    )
    parser.add_argument(
        "--quiz-count",
        choices=[1, 5, 10],
        type=int,
        default=None,
        help="Number of quiz questions.",
    )
    parser.add_argument(
        "--input-dir",
        default="sample_input",
        help="Folder scanned during interactive mode.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose debug logging.",
    )
    return parser.parse_args()


def _prompt_choice(prompt: str, valid_choices: dict[str, object]) -> object:
    while True:
        answer = input(prompt).strip()
        if answer in valid_choices:
            return valid_choices[answer]
        print("Invalid choice. Please try again.")


def _prompt_output_name() -> str:
    while True:
        raw_name = input("Enter output markdown filename (without extension): ").strip()
        cleaned_name = raw_name.replace(".md", "").strip().strip(".")
        cleaned_name = "".join(
            character for character in cleaned_name if character not in '<>:"/\\|?*'
        )
        if cleaned_name:
            return cleaned_name
        print("Filename cannot be empty. Please try again.")


def _collect_interactive_config(args: argparse.Namespace) -> dict[str, object]:
    logger.info("Starting interactive mode")
    input_dir = Path(args.input_dir)

    try:
        available_files = list_input_files(input_dir)
    except Exception as e:
        logger.error(f"Failed to list input files from {input_dir}: {str(e)}")
        raise

    if not available_files:
        error_msg = f"No supported files were found in {input_dir}"
        logger.error(error_msg)
        raise FileNotFoundError(error_msg)

    print("Available lecture files:")
    file_choices: dict[str, Path] = {}
    for index, file_path in enumerate(available_files, start=1):
        print(f"{index}. {file_path.name}")
        file_choices[str(index)] = file_path

    logger.debug(f"Found {len(available_files)} available input files")
    selected_file = _prompt_choice("Select a file by number: ", file_choices)

    print("\nSelect summary size:")
    print("1. Large")
    print("2. Medium")
    print("3. Small")
    summary_mode = _prompt_choice("Choose summary size: ", SUMMARY_MODE_CHOICES)
    logger.debug(f"Selected summary mode: {summary_mode}")

    output_name = _prompt_output_name()

    print("\nSelect number of quiz questions:")
    print("1. 1")
    print("2. 5")
    print("3. 10")
    quiz_count = _prompt_choice("Choose quiz count: ", QUIZ_COUNT_CHOICES)
    logger.debug(f"Selected quiz count: {quiz_count}")

    return {
        "input_path": str(selected_file),
        "output_path": str(Path("sample_output") / f"{output_name}.md"),
        "summary_mode": summary_mode,
        "quiz_count": quiz_count,
        "json_output_path": args.json_output,
    }


def _collect_non_interactive_config(args: argparse.Namespace) -> dict[str, object]:
    logger.info(f"Starting non-interactive mode with input: {args.input_path}")

    # Validate input file exists
    input_path = Path(args.input_path)
    if not input_path.exists():
        error_msg = f"Input file not found: {args.input_path}"
        logger.error(error_msg)
        raise FileNotFoundError(error_msg)

    if not input_path.is_file():
        error_msg = f"Input path is not a file: {args.input_path}"
        logger.error(error_msg)
        raise ValueError(error_msg)

    logger.info(
        f"Input file validated: {input_path.name} ({input_path.stat().st_size} bytes)"
    )

    summary_mode = SummaryMode(args.mode) if args.mode else SummaryMode.MEDIUM
    output_path = args.output or str(Path("sample_output") / "study_report.md")
    quiz_count = args.quiz_count if args.quiz_count is not None else 5

    logger.debug(
        f"Config: mode={summary_mode}, quiz_count={quiz_count}, output={output_path}"
    )

    return {
        "input_path": str(input_path),
        "output_path": str(Path(output_path)),
        "summary_mode": summary_mode,
        "quiz_count": quiz_count,
        "json_output_path": (
            str(Path(args.json_output)) if args.json_output is not None else None
        ),
    }


def _print_coverage_report(final_state: AgentState) -> None:
    if final_state.coverage is None:
        return

    coverage = final_state.coverage
    print("\nCoverage Report")
    print(f"- source file: {coverage.source_file}")
    print(f"- total pages read: {coverage.total_pages_read}")
    print(f"- total words read: {coverage.total_words_read}")
    print(f"- total chunks processed: {coverage.total_chunks_processed}")
    print(f"- selected summary mode: {coverage.selected_summary_mode.value}")
    print(f"- selected quiz count: {coverage.selected_quiz_count}")
    print(f"- output markdown path: {final_state.exported_output_path}")
    if final_state.exported_json_path is not None:
        print(f"- output json path: {final_state.exported_json_path}")


def main() -> int:
    load_dotenv()
    args = parse_args()

    # Setup logging
    setup_logging(verbose=args.verbose)
    logger.info("=" * 80)
    logger.info("Starting AI Study Coach")
    logger.info(f"Provider: {args.provider}, Model: {args.model}")
    logger.info("=" * 80)

    try:
        logger.info("Collecting configuration")
        if args.input_path is None:
            config = _collect_interactive_config(args)
        else:
            config = _collect_non_interactive_config(args)

        logger.info("Building LLM client")
        llm_client = create_llm(provider=args.provider, model_name=args.model)
        logger.info(f"LLM client created: {llm_client.provider_name}")

        logger.info("Building study coach graph")
        graph = build_study_coach_graph(llm_client)

        logger.info("Initializing graph execution")
        initial_state = AgentState(
            input_path=config["input_path"],
            output_path=config["output_path"],
            json_output_path=config["json_output_path"],
            summary_mode=config["summary_mode"],
            quiz_count=config["quiz_count"],
        )

        logger.info("Starting graph execution pipeline")
        final_state = AgentState.model_validate(graph.invoke(initial_state))

        logger.info("=" * 80)
        logger.info("Pipeline completed successfully")
        logger.info("=" * 80)

        print(f"\nProvider used: {llm_client.provider_name}")
        print(f"Markdown report saved to: {final_state.exported_output_path}")
        if final_state.exported_json_path is not None:
            print(f"JSON export saved to: {final_state.exported_json_path}")
        if final_state.study_material is not None:
            print(f"Detected subject: {final_state.study_material.subject}")
        _print_coverage_report(final_state)

        logger.info("Execution completed successfully")
        return 0

    except FileNotFoundError as e:
        logger.error(f"File not found: {str(e)}")
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except ValueError as e:
        logger.error(f"Validation error: {str(e)}")
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        logger.warning("Process interrupted by user")
        print("\nProcess interrupted by user", file=sys.stderr)
        return 130
    except Exception as e:
        logger.exception(f"Unexpected error occurred: {str(e)}")
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
