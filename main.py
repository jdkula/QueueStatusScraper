"""
Queue Status Scraper Tool
==========================
Periodically scrapes a QueueStatus queue and saves
information to a MongoDB database.
"""
import os
import asyncio
from datetime import datetime

from dotenv import load_dotenv
from pymongo import MongoClient
from prometheus_client import start_http_server

from src.monitor import QueueStatusMonitor
from src.util import localtz


async def main():
    interval = int(os.environ.get("INTERVAL"))
    email = os.environ.get("EMAIL")
    password = os.environ.get("PASSWORD")

    mongo_uri = os.environ.get("MONGODB_URI")
    dbname = os.environ.get("MONGODB_DBNAME")

    db = MongoClient(mongo_uri)[dbname]

    credentials = None
    if email and password:
        credentials = (email, password)

    queue_ids = os.environ.get("QUEUE_IDS")
    if not queue_ids:
        queue_ids = os.environ.get("QUEUE_ID")

    jobs = []

    queue_ids = [id.strip() for id in queue_ids.split(",")]
    for queue_id in queue_ids:
        print(f"[{datetime.now(localtz)}] Starting monitor for queue id {queue_id}")
        monitor = QueueStatusMonitor(db, queue_id, credentials)
        jobs.append(monitor.monitor(interval=interval))

        # Interleave the monitors so they don't all make requests at once.
        await asyncio.sleep(interval / len(queue_ids))

    await asyncio.gather(*jobs)


if __name__ == "__main__":
    load_dotenv()
    start_http_server(8000)
    asyncio.run(main())
