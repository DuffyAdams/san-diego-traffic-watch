"""Repair placeholder descriptions from stored facts; no AI calls are made.

Preview: python -m scripts.backfill_descriptions
Apply:   python -m scripts.backfill_descriptions --apply
"""

import argparse
import sqlite3
from contextlib import closing

from backend.config import DB_FILE
from backend.descriptions import PLACEHOLDERS, source_description


def backfill(db_file, apply=False, batch_size=500):
    repaired = 0
    last_rowid = 0
    placeholders = tuple(sorted(PLACEHOLDERS))
    markers = ",".join("?" for _ in placeholders)
    with closing(sqlite3.connect(db_file, timeout=30)) as conn:
        conn.row_factory = sqlite3.Row
        while True:
            # Hold the write lock only for one bounded batch. Concurrent summaries
            # and source updates cannot change between selection and repair.
            with conn:
                if apply:
                    conn.execute("BEGIN IMMEDIATE")
                rows = conn.execute(
                    f"SELECT rowid AS repair_rowid, * FROM incidents "
                    f"WHERE rowid > ? AND lower(trim(coalesce(description, ''))) "
                    f"IN ({markers}) ORDER BY rowid LIMIT ?",
                    (last_rowid, *placeholders, batch_size),
                ).fetchall()
                if not rows:
                    break
                if apply:
                    conn.executemany(
                        "UPDATE incidents SET description = ? WHERE rowid = ?",
                        [(source_description(dict(row)), row["repair_rowid"]) for row in rows],
                    )
                repaired += len(rows)
                last_rowid = rows[-1]["repair_rowid"]
    return repaired


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=DB_FILE)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    count = backfill(args.db, apply=args.apply)
    print(f"{'Repaired' if args.apply else 'Would repair'} {count} descriptions.")


if __name__ == "__main__":
    main()
