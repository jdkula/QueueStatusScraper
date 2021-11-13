"""
Queue Status Scraper Tool
==========================
Periodically scrapes a QueueStatus queue and saves
information to a MongoDB database.

Configured using the following environment variables:
    MONGODB_URL -- MongoDB connection URI
    MONGODB_DB  -- MongoDB database name
    EMAIL       -- QueueStatus email address
    PASSWORD    -- QueueStatus password
    QUEUE_ID    -- The ID of the queue to scrape
    INTERVAL    -- How often to scrape in seconds
    TIMEZONE    -- Which timezone QueueStatus is using
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

    mongo_url = os.environ.get("MONGODB_URL")
    mongo_db = os.environ.get("MONGODB_DB")

    db = MongoClient(mongo_url)[mongo_db]

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
