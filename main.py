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

from dotenv import load_dotenv
from pymongo import MongoClient
from prometheus_client import start_http_server

from src.monitor import QueueStatusMonitor


async def main():
    queue_id = os.environ.get("QUEUE_ID")
    interval = int(os.environ.get("INTERVAL"))
    email = os.environ.get("EMAIL")
    password = os.environ.get("PASSWORD")

    mongo_url = os.environ.get("MONGODB_URL")
    mongo_db = os.environ.get("MONGODB_DB")

    db = MongoClient(mongo_url)[mongo_db]

    credentials = None
    if email and password:
        credentials = (email, password)

    monitor = QueueStatusMonitor(db, queue_id, credentials)
    await monitor.monitor(interval=interval)


if __name__ == "__main__":
    load_dotenv()
    start_http_server(8000)
    asyncio.run(main())
