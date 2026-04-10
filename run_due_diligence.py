#!/usr/bin/env python3
"""
CLI entry point for the AI Due Diligence Pipeline.

Usage examples:
    # Basic run with just a CIM
    python run_due_diligence.py path/to/cim.pdf

    # With deal terms from a JSON file
    python run_due_diligence.py path/to/cim.pdf --deal-terms deal.json

    # With independent industry analysis
    python run_due_diligence.py path/to/cim.pdf --industry-analysis industry.json

    # Resume from a specific step
    python run_due_diligence.py path/to/cim.pdf --start-step 3.1

    # Custom output directory and model
    python run_due_diligence.py path/to/cim.pdf --output ./my_output --model claude-sonnet-4-6
"""

import argparse
import json
import sys
from pathlib import Path

from ai_due_diligence import DueDiligencePipeline


def load_json_file(path: str) -> dict | str:
    """Load and return contents of a JSON file."""
    p = Path(path)
    if not p.exists():
        sys.exit(f"File not found: {path}")
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        sys.exit(f"Invalid JSON in {path}: {e}")


def main():
    parser = argparse.ArgumentParser(
        description="AI Due Diligence Pipeline — 8-phase, 30-prompt IC-grade analysis from a CIM.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
examples:
  %(prog)s cim.pdf
  %(prog)s cim.pdf --deal-terms deal.json
  %(prog)s cim.pdf --start-step 3.1 --output ./resumed_run
""",
    )
    parser.add_argument(
        "cim_path",
        help="Path to the CIM document (PDF, DOCX, or TXT)",
    )
    parser.add_argument(
        "--deal-terms",
        metavar="JSON_FILE",
        help="Path to a JSON file with deal terms (purchase price, leverage, etc.)",
    )
    parser.add_argument(
        "--industry-analysis",
        metavar="JSON_FILE",
        help="Path to a JSON file with independent industry analysis",
    )
    parser.add_argument(
        "--output", "-o",
        metavar="DIR",
        help="Output directory (default: dd_output_<timestamp> next to the CIM)",
    )
    parser.add_argument(
        "--model", "-m",
        default="claude-opus-4-6",
        help="Claude model to use (default: claude-opus-4-6)",
    )
    parser.add_argument(
        "--start-phase",
        type=int,
        default=1,
        choices=range(1, 9),
        metavar="N",
        help="Phase to start from, 1-8 (for resuming interrupted runs)",
    )
    parser.add_argument(
        "--start-step",
        metavar="ID",
        help="Step ID to start from, e.g. '3.1' (more granular than --start-phase)",
    )
    parser.add_argument(
        "--single-step",
        metavar="ID",
        help="Run only a single step by ID, e.g. '1.1' (useful for testing)",
    )

    args = parser.parse_args()

    # Validate CIM path
    if not Path(args.cim_path).exists():
        sys.exit(f"CIM file not found: {args.cim_path}")

    # Load optional inputs
    deal_terms = None
    if args.deal_terms:
        deal_terms = load_json_file(args.deal_terms)

    industry_analysis = None
    if args.industry_analysis:
        data = load_json_file(args.industry_analysis)
        industry_analysis = json.dumps(data, indent=2) if isinstance(data, dict) else str(data)

    # Build pipeline
    pipeline = DueDiligencePipeline(
        cim_path=args.cim_path,
        deal_terms=deal_terms,
        independent_industry_analysis=industry_analysis,
        output_dir=args.output,
        model=args.model,
        start_phase=args.start_phase,
        start_step=args.start_step,
    )

    # Run
    if args.single_step:
        print(f"Running single step: {args.single_step}")
        output = pipeline.run_single_step(args.single_step)
        print(f"\n{'=' * 70}")
        print(output[:2000])
        if len(output) > 2000:
            print(f"\n... ({len(output):,} chars total, see output dir for full text)")
    else:
        pipeline.run()


if __name__ == "__main__":
    main()
