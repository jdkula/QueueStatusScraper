import os
import asyncio
from src.monitor import QueueStatusMonitor
from dotenv import load_dotenv

from pymongo import MongoClient


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
    asyncio.run(main())
