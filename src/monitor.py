"""
Exposes a class that monitors QueueStatus for changes over time
"""
import asyncio
from datetime import datetime, timedelta, timezone
from enum import Enum, Flag
from typing import Any, Dict, Literal, Optional, Tuple, Union

import requests
from pymongo.collection import ReturnDocument
from pymongo.database import Database
from prometheus_client import Histogram, Counter

from src.modals import Queue, EntryState, QueueState
from src.scraper import QueueStatusScraper
from src.util import localtz


# Type of a Queue object when converted to a dictionary
QueueDict = Dict[Literal["state", "entries", "chat", "servers"], Any]

REQUEST_FAILURE_COUNTER = Counter(
    "request_failures", "Number of times a request failed", labelnames=("queue_id",)
)
REQUEST_SUCCESS_COUNTER = Counter(
    "requests", "Number of times a request succeeded", labelnames=("queue_id",)
)
SCRAPE_LENGTH = Histogram(
    "scrape_length",
    "Times to finish processing one scrape iteration (ms)",
    labelnames=("queue_id",),
)


class EventType(Enum):
    QUEUE_OPEN = "queue_open"
    QUEUE_CLOSE = "queue_close"


class QueueStatusMonitor:
    def __init__(
        self, db: Database, queue_id: str, credentials: Optional[Tuple[str, str]]
    ) -> None:
        """
        Initializes this monitor. Requires a MongoDB database to store information in,
        a queue_id to monitor, and (optionally) credentials to view an elevated
        version of the QueueStatus page.

        Will create the following collections in the mongodb database:
        queue_{queue_id}_entries
        queue_{queue_id}_events
        queue_{queue_id}_full_history
        """
        self._client = requests.Session()
        self._db = db
        self._credentials = credentials
        self._queue_id = queue_id

        self._entries = self._db[f"queue_{queue_id}_entries"]
        self._events = self._db[f"queue_{queue_id}_events"]
        self._full_history = self._db[f"queue_{queue_id}_full_history"]

        self._entries.create_index("content_hash")

    def __process_update(
        self,
        old: Union[Queue, QueueDict],
        new: Union[Queue, QueueDict],
        only_record_deltas=False,
        at: Union[datetime, None] = None,
    ):
        # Use dictionary version so we can re-import from full history
        # without re-loading everything into their modal types.
        if isinstance(old, Queue):
            old = dict(old)
        if isinstance(new, Queue):
            new = dict(new)

        if at is None:
            # Lets us specify a different time upon re-import from full history
            at = datetime.now(timezone.utc)

        new["timestamp"] = at

        # On any change, add full copy to full history
        if not only_record_deltas:
            self._full_history.update_one(
                {
                    "chat": new["chat"],
                    "entries": new["entries"],
                    "state": new["state"],
                    "servers": new["servers"],
                },
                {"$setOnInsert": new},
                upsert=True,
            )

        # Process updates for entries
        for entry in new["entries"]:
            if entry["id"] is None:
                del entry["id"]  # never unset an id

            # most values we want to keep immutable, except for–
            entry_update = {"status": entry["status"], "server": entry["server"]}
            del entry["status"]
            del entry["server"]

            old_entry = self._entries.find_one_and_update(
                {"content_hash": entry["content_hash"]},
                {"$set": entry_update, "$setOnInsert": entry},
                upsert=True,
                return_document=ReturnDocument.BEFORE,
            )

            # Notice and record when a TA takes a student
            if (
                old_entry
                and old_entry["status"] != entry_update["status"]
                and entry_update["status"] == EntryState.IN_PROGRESS.value
            ):
                # only order is waiting -> in_progress -> served
                # just started serving this student
                self._entries.update_one(
                    {"content_hash": entry["content_hash"]},
                    {"$set": {"time_started": at}},
                )

            # lock time_out once we set it
            if entry["time_out"] is not None:
                self._entries.update_one(
                    {"content_hash": entry["content_hash"], "time_out": None},
                    {"$set": {"time_out": entry["time_out"]}},
                )

        # When entries go away, mark ones that went away from in_progress as implicitly served
        hashes = [entry["content_hash"] for entry in new["entries"]]
        self._entries.update_many(
            {
                "status": EntryState.IN_PROGRESS.value,
                "content_hash": {"$nin": hashes},
            },
            {
                "$set": {
                    "status": EntryState.SERVED.value,
                    "implicitly": True,
                    "time_out": at,
                }
            },
        )
        # ...and mark ones that went away from waiting as removed.
        self._entries.update_many(
            {
                "status": EntryState.WAITING.value,
                "content_hash": {"$nin": hashes},
            },
            {"$set": {"status": EntryState.REMOVED.value, "time_out": at}},
        )

        # Note when the queue opens/closes
        if (
            old["state"] == QueueState.CLOSED.value
            and new["state"] == QueueState.OPEN.value
        ):
            self._events.insert_one(
                {"event": EventType.QUEUE_OPEN.value, "timestamp": at}
            )
        elif (
            old["state"] == QueueState.OPEN.value
            and new["state"] == QueueState.CLOSED.value
        ):
            self._events.insert_one(
                {"event": EventType.QUEUE_CLOSE.value, "timestamp": at}
            )

    async def __init_qs(self):
        # Re-logs into QueueStatus
        self._qs = QueueStatusScraper(self._client)
        if self._credentials:
            await self._qs.login(*self._credentials)

    async def __should_reinit(self):
        # Checks if we've been logged out
        res = self._client.get(
            "https://queuestatus.com/users/any/edit",
            allow_redirects=False,
            timeout=5,
        )
        return res.status_code == 302

    async def __update_loop(self, interval: int):
        # Loop forever at a given interval
        last = await self._qs.get_queue(self._queue_id)
        reinit_next = False

        while True:
            try:
                start_time = datetime.now()
                if reinit_next or await self.__should_reinit():
                    print(
                        f"[{datetime.now(localtz)}] Re-logging into QueueStatus... ",
                        flush=True,
                        end="",
                    )
                    await self.__init_qs()
                    print(
                        f"done",
                        flush=True,
                    )
                    reinit_next = False

                print(
                    f"[{datetime.now(localtz)}] Retrieving queue status... ",
                    flush=True,
                    end="",
                )

                queue = await self._qs.get_queue(self._queue_id)
                self.__process_update(last, queue)
                last = queue

                duration = datetime.now() - start_time
                print(
                    f"found with {len(queue.entries)} entries. Queue is {queue.state.name}. Took {duration} to complete.",
                    flush=True,
                )
                REQUEST_SUCCESS_COUNTER.labels(queue_id=self._queue_id).inc()
                SCRAPE_LENGTH.labels(queue_id=self._queue_id).observe(
                    duration.total_seconds()
                )

                await asyncio.sleep(interval)
            except requests.exceptions.ReadTimeout:
                print(
                    "Failed to query QueueStatus in a timely manner, waiting 5 seconds then trying to log in again.",
                    flush=True,
                )
                REQUEST_FAILURE_COUNTER.labels(queue_id=self._queue_id).inc()
                await asyncio.sleep(5)
                reinit_next = True

    async def monitor(self, interval: int = 10):
        """
        Starts monitoring QueueStatus at the given interval
        until externally cancelled (this method does not normally terminate)
        """
        await self.__init_qs()
        await self.__update_loop(interval)

    async def backport_from_full_history(self):
        """
        Clears the events and entries collections and
        re-calculates them by running back the full history log
        """
        self._events.delete_many({})
        self._entries.delete_many({})
        last = None
        n = 0
        print("Backporting queue information from full history...")
        for querydict in self._full_history.find(sort=[("timestamp", 1)]):
            n += 1
            print(f"Processing entry {n}...", flush=True, end="\r")
            if last is None:
                last = querydict

            self.__process_update(
                last, querydict, only_record_deltas=True, at=querydict["timestamp"]
            )
            last = querydict
        print()
        print("Done")
