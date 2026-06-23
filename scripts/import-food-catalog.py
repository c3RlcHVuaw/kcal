#!/usr/bin/env python
from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from kcal_tracker.database import SessionLocal
from kcal_tracker.services.catalog_import import import_catalog_seed, read_catalog_seed


async def _main() -> None:
    parser = argparse.ArgumentParser(description="Import food catalog seed CSV.")
    parser.add_argument(
        "path",
        nargs="?",
        default="data/food_catalog_seed.csv",
        help="CSV path with seed catalog rows.",
    )
    args = parser.parse_args()

    rows = read_catalog_seed(Path(args.path))
    async with SessionLocal() as session:
        result = await import_catalog_seed(session, rows)
    print(
        "Catalog import completed: "
        f"created={result.created} "
        f"updated={result.updated} "
        f"aliases_created={result.aliases_created} "
        f"skipped={result.skipped}"
    )


if __name__ == "__main__":
    asyncio.run(_main())
