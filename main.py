from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from graph import build_study_coach_graph
from state import AgentState
from utils import create_llm


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate study material from lecture notes with LangGraph."
    )
    parser.add_argument(
        "input_path",
        nargs="?",
        default="sample_input/lecture.txt",
        help="Path to a .txt, .md, or .pdf lecture notes file.",
    )
    parser.add_argument(
        "--output",
        default="sample_output/output.json",
        help="Path for the exported JSON file.",
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
    return parser.parse_args()


def main() -> int:
    load_dotenv()
    args = parse_args()

    try:
        llm_client = create_llm(provider=args.provider, model_name=args.model)
        graph = build_study_coach_graph(llm_client)

        initial_state = AgentState(
            input_path=str(Path(args.input_path)),
            output_path=str(Path(args.output)),
        )
        final_state = AgentState.model_validate(graph.invoke(initial_state))

        print(f"Provider used: {llm_client.provider_name}")
        print(f"Output saved to: {final_state.exported_output_path}")
        if final_state.analysis is not None:
            print(f"Detected subject: {final_state.analysis.subject}")
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
