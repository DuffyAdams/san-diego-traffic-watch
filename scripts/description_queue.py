"""Inspect durable description work; retry failed jobs after fixing configuration.

python -m scripts.description_queue
python -m scripts.description_queue --retry-failed
"""
import argparse
import json
import time
from backend.config import DB_FILE
from backend.description_jobs import usage_metrics
from backend.sqlite_utils import sqlite_connection


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db', default=DB_FILE)
    parser.add_argument('--retry-failed', action='store_true')
    args = parser.parse_args()
    if args.retry_failed:
        with sqlite_connection(args.db) as conn:
            count = conn.execute("""UPDATE description_jobs SET status='pending', attempts=0,
                due_at=?, lease_token=NULL, lease_until=NULL, last_error=NULL
                WHERE status='failed'""", (time.time(),)).rowcount
        print(f'Requeued {count} failed descriptions.')
    print(json.dumps(usage_metrics(args.db), indent=2))


if __name__ == '__main__':
    main()
