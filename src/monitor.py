import asyncio
from datetime import datetime
from enum import Enum
from typing import Tuple, Union

from pymongo.database import Database

from src.modals import Queue, EntryState, QueueState
from src.scraper import QueueStatus

import requests


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

        self._entries.create_index("content_hash")

    def __process_update(self, old: Queue, new: Queue):
        # On any change, add full copy to full history
        new_d = dict(new)
        new_d["timestamp"] = datetime.now()
        self._full_history.update_one(
            {
                "chat": new_d["chat"],
                "entries": new_d["entries"],
                "state": new_d["state"],
                "servers": new_d["servers"],
            },
            {"$setOnInsert": new_d},
            upsert=True,
        )

        # Process updates for entries
        for entry in new.entries:
            entry_d = dict(entry)
            if entry.id is None:
                del entry_d["id"]  # never unset an id

            # most values we want to keep immutable, except for–
            entry_update = {"status": entry_d["status"], "server": entry_d["server"]}
            del entry_d["status"]
            del entry_d["server"]

            self._entries.update_one(
                {"content_hash": entry.content_hash},
                {"$set": entry_update, "$setOnInsert": entry_d},
                upsert=True,
            )

            # lock time_out once we set it
            if entry.time_out is not None:
                self._entries.update_one(
                    {"content_hash": entry.content_hash, "time_out": None},
                    {"$set": {"time_out": entry_d["time_out"]}},
                )

        # When entries go away, mark ones that went away from in_progress as implicitly served
        hashes = [entry.content_hash for entry in new.entries]
        self._entries.update_many(
            {
                "status": EntryState.IN_PROGRESS.value,
                "content_hash": {"$nin": hashes},
            },
            {"$set": {"status": EntryState.SERVED.value, "implicitly": True}},
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
        if old.state == QueueState.CLOSED and new.state == QueueState.OPEN:
            self._events.insert_one(
                {"event": EventType.QUEUE_OPEN, "timestamp": datetime.now()}
            )
        elif old.state == QueueState.OPEN and new.state == QueueState.CLOSED:
            self._events.insert_one(
                {"event": EventType.QUEUE_CLOSE, "timestamp": datetime.now()}
            )

    async def __init_qs(self):
        self._qs = QueueStatus(self._client)
        if self._credentials:
            await self._qs.login(*self._credentials)
            self._last_login = datetime.now()

    async def __should_reinit(self):
        res = self._client.get("https://queuestatus.com/users/any/edit", allow_redirects=False)
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
