"""RQ worker entrypoint."""

import os

from rq import Connection, Worker

from app.config import JOB_QUEUE_NAME, REDIS_URL


def main() -> None:
    if not REDIS_URL:
        raise RuntimeError("REDIS_URL is not set")
    import redis

    conn = redis.from_url(REDIS_URL)
    with Connection(conn):
        worker = Worker([JOB_QUEUE_NAME])
        worker.work()


if __name__ == "__main__":
    main()
