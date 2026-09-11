import asyncio
import logging

from .config import WorkerConfig
from .worker import PerceptionWorker


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    asyncio.run(PerceptionWorker(WorkerConfig.from_env()).run())


if __name__ == "__main__":
    main()
