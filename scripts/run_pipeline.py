#!/usr/bin/env python3
"""
Example run script for the Journal Article Writer pipeline.
Usage:
  python scripts/run_pipeline.py                    # full pipeline
  python scripts/run_pipeline.py --skip-trends      # use existing data only
  python scripts/run_pipeline.py --no-pdf            # skip PDF generation
  python scripts/run_pipeline.py --config config/custom.yaml
"""

import argparse
import sys
from pathlib import Path

# Ensure package is on path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from articlewriter.orchestrator import ArticleWriterPipeline
from articlewriter.exceptions import ArticleWriterError


def main():
    parser = argparse.ArgumentParser(description="Journal Article Writer - full pipeline")
    parser.add_argument("--config", "-c", type=str, default=None, help="Path to YAML config")
    parser.add_argument("--skip-trends", action="store_true", help="Skip trend detection; use retrieval only")
    parser.add_argument("--no-pdf", action="store_true", help="Do not generate PDF")
    parser.add_argument("--title", "-t", type=str, default=None, help="Article title (optional)")
    args = parser.parse_args()

    try:
        pipeline = ArticleWriterPipeline(config_path=args.config)
        paths = pipeline.run_full(
            article_title=args.title,
            write_pdf=not args.no_pdf,
            skip_trends=args.skip_trends,
        )
        print("Output files:")
        for name, path in paths.items():
            print(f"  {name}: {path}")
    except ArticleWriterError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
