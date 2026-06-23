#!/usr/bin/env python
from __future__ import annotations

import argparse
import asyncio
import csv
import sys

from kcal_tracker.database import SessionLocal
from kcal_tracker.services.catalog_gaps import catalog_gap_report


def main() -> None:
    parser = argparse.ArgumentParser(description="Show catalog gaps from quality events.")
    parser.add_argument("--days", type=int, default=14, help="How many recent days to scan.")
    parser.add_argument("--limit", type=int, default=20, help="Maximum rows to print.")
    parser.add_argument(
        "--format",
        choices=("text", "csv"),
        default="text",
        help="Output format.",
    )
    args = parser.parse_args()
    asyncio.run(_run(days=max(1, args.days), limit=max(1, args.limit), output_format=args.format))


async def _run(*, days: int, limit: int, output_format: str) -> None:
    async with SessionLocal() as session:
        gaps = await catalog_gap_report(session, days=days, limit=limit)

    if output_format == "csv":
        writer = csv.writer(sys.stdout)
        writer.writerow(
            [
                "label",
                "count",
                "score",
                "ready_count",
                "already_known",
                "event_types",
                "sample_query",
                "product_add_command",
            ]
        )
        for gap in gaps:
            writer.writerow(
                [
                    gap.label,
                    gap.count,
                    gap.score,
                    gap.ready_count,
                    int(gap.already_known),
                    "|".join(gap.event_types),
                    gap.sample_query or "",
                    gap.product_add_command or "",
                ]
            )
        return

    print(f"Catalog gaps for {days} days")
    if not gaps:
        print("No catalog gaps found.")
        return
    for index, gap in enumerate(gaps, start=1):
        known = "known" if gap.already_known else "missing"
        ready = f", ready={gap.ready_count}" if gap.ready_count else ""
        print(f"{index}. {gap.label}: count={gap.count}, score={gap.score}, {known}{ready}")
        if gap.sample_query:
            print(f"   query: {gap.sample_query}")
        if gap.product_add_command:
            print(f"   {gap.product_add_command}")


if __name__ == "__main__":
    main()
