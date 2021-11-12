import asyncio
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, Literal, Tuple, Union
from pymongo.collection import ReturnDocument

from pymongo.database import Database

from src.modals import Queue, EntryState, QueueState
from src.scraper import QueueStatus

import requests

QueueDict = Dict[Literal["state", "entries", "chat", "servers"], Any]


class EventType(Enum):
    QUEUE_OPEN = "queue_open"
    QUEUE_CLOSE = "queue_close"


class QueueStatusMonitor:
    def __init__(
        self, db: Database, queue_id: str, credentials: Union[Tuple[str, str], None]
    ) -> None:
        self._client = requests.Session()
        self._db = db
        self._credentials = credentials
        self._queue_id = queue_id

        self._entries = self._db[f"queue_{queue_id}_entries"]
        self._events = self._db[f"queue_{queue_id}_events"]
        self._full_history = self._db[f"queue_{queue_id}_full_history"]
        self._full_history2 = self._db[f"queue_{queue_id}_full_history2"]

        self._entries.create_index("content_hash")

    def __process_update(
        self,
        old: Union[Queue, QueueDict],
        new: Union[Queue, QueueDict],
        only_record_deltas=False,
        at: Union[datetime, None] = None,
    ):
        # On any change, add full copy to full history
        if isinstance(old, Queue):
            old = dict(old)
        if isinstance(new, Queue):
            new = dict(new)

        if at is None:
            at = datetime.utcnow()

        new["timestamp"] = at
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
        else:
            self._full_history2.update_one(
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

            # Edge detection
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
            {"$set": {"status": EntryState.REMOVED.value}},
        )

        # Edge detection
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
        self._qs = QueueStatus(self._client)
        if self._credentials:
            await self._qs.login(*self._credentials)
            self._last_login = datetime.now()

    async def __should_reinit(self):
        res = self._client.get(
            "https://queuestatus.com/users/any/edit", allow_redirects=False
        )
        return res.status_code == 302

    async def __update_loop(self, interval: int):
        last = await self._qs.get_queue(self._queue_id)

        while True:
            if await self.__should_reinit():
                print(
                    f"[{datetime.now()}] Re-logging into QueueStatus... ",
                    flush=True,
                    end="",
                )
                await self.__init_qs()
                print(
                    f"done",
                    flush=True,
                )

            print(f"[{datetime.now()}] Retrieving queue status... ", flush=True, end="")

            queue = await self._qs.get_queue(self._queue_id)
            self.__process_update(last, queue)
            last = queue

            print(
                f"found with {len(queue.entries)} entries. Queue is {queue.state.name}.",
                flush=True,
            )

            await asyncio.sleep(interval)

    async def monitor(self, interval: int = 10):
        await self.__init_qs()
        await self.__update_loop(interval)

    async def backport_from_full_history(self):
        self._events.delete_many({})
        self._entries.delete_many({})
        self._full_history2.delete_many({})
        last = None
        n = 0
        print("Backporting queue information from full history...")
        for querydict in self._full_history.find(sort=[("timestamp", 1)]):
            n += 1
            print(f"Processing entry {n}...", flush=True, end="\r")
            if last is None:
                last = querydict

            for i in range(len(querydict["entries"])):
                if querydict["entries"][i]["time_in"]:
                    querydict["entries"][i]["time_in"] += timedelta(hours=8)
                if querydict["entries"][i]["time_out"]:
                    querydict["entries"][i]["time_out"] += timedelta(hours=8)

            for i in range(len(querydict["chat"])):
                querydict["chat"][i]["timestamp"] += timedelta(hours=8)

            self.__process_update(
                last, querydict, only_record_deltas=True, at=querydict["timestamp"]
            )
            last = querydict
        print()
        print("Done")
