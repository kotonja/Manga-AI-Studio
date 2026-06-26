from __future__ import annotations

import argparse
import json
from pathlib import Path

from sqlmodel import Session

from manga_api.db import engine
from manga_api.evaluation import MangaEvaluationRunner, scenario_ids
from manga_api.storage import ObjectStorage


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Manga AI Studio evaluation scenarios.")
    parser.add_argument("--scenario", default="all", help=f"Scenario id or 'all'. Choices: {', '.join(scenario_ids())}")
    parser.add_argument("--provider", default="mock", help="Render provider to use. Defaults to mock.")
    parser.add_argument("--quality-mode", default="fast", choices=["fast", "balanced", "high"])
    parser.add_argument("--reports-dir", default=None, help="Directory for latest.json and latest.md.")
    parser.add_argument("--no-write", action="store_true", help="Run without writing eval_reports/latest.*")
    args = parser.parse_args()

    with Session(engine) as session:
        report = MangaEvaluationRunner(
            session,
            ObjectStorage(),
            reports_dir=Path(args.reports_dir) if args.reports_dir else None,
        ).run(
            scenario=args.scenario,
            provider=args.provider,
            quality_mode=args.quality_mode,
            write_reports=not args.no_write,
        )

    print(json.dumps({"run_id": report["run_id"], "metrics": report["metrics"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
