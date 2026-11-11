import argparse
import json
from uuid import uuid4

from core.db import get_session_factory
from core.models import ScraperRun
from scrapers.jobs import SCRAPERS, execute_run, queue_run


def main():
    parser = argparse.ArgumentParser(description="Run permitted public-source scrapers")
    parser.add_argument("channel", choices=SCRAPERS)
    parser.add_argument("--enqueue", action="store_true")
    parser.add_argument("--scheduled-at", help="Future ISO-8601 time with timezone")
    args = parser.parse_args()
    if args.enqueue or args.scheduled_at:
        from datetime import datetime

        run_id = queue_run(
            args.channel,
            datetime.fromisoformat(args.scheduled_at) if args.scheduled_at else None,
        )
    else:
        run_id = uuid4()
        with get_session_factory().begin() as db:
            db.add(ScraperRun(id=run_id, channel=args.channel))
        execute_run(str(run_id))
    print(json.dumps({"run_id": str(run_id)}))


if __name__ == "__main__":
    main()
