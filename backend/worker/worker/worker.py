from rq import Connection, Worker

from scrapper_shared.config import get_settings
from scrapper_shared.queue import get_redis

settings = get_settings()


def run() -> None:
    redis_conn = get_redis()
    with Connection(redis_conn):
        worker = Worker([settings.rq_queue_name])
        worker.work(with_scheduler=True)


if __name__ == "__main__":
    run()
