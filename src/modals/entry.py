"""
Modal class for an entry in the queue
"""
from datetime import datetime
from enum import Enum
from typing import List, Optional, Tuple, Union

import hashlib


class EntryState(Enum):
    WAITING = "waiting"
    IN_PROGRESS = "in_progress"
    SERVED = "served"
    REMOVED = "removed"


class Entry:
    def __init__(
        self,
        id: Optional[str],
        name: str,
        image_url: str,
        time_in: datetime,
        time_out: Optional[datetime],
        server: Optional[str],
        status: EntryState,
        questions: List[Tuple[str, str]],
    ) -> None:
        self.id = id
        self.name = name
        self.image_url = image_url
        self.time_in = time_in
        self.time_out = time_out
        self.time_started = None  # QueueStatus doesn't give this information :(
        self.server = server
        self.status = status
        self.questions = questions

    @property
    def content_hash(self) -> str:
        """
        Returns a sha256 hash of:
            * the name and
            * the answer to each question and,
            * the sign-up *time*.

        QueueStatus doesn't give a great unique ID so this will have to do.
        """
        h = hashlib.sha256()
        h.update(self.name.encode("utf8"))
        for (_, answer) in self.questions:
            h.update(answer.encode("utf8"))

        # Only by time, since that's all we're technically given.
        h.update(self.time_in.strftime("%I:%M %p").encode("utf8"))

        return h.hexdigest()

    def __iter__(self):
        # Allows this class to be turned into a dictionary -- for MongoDB
        yield ("id", self.id)
        yield ("name", self.name)
        yield ("image_url", self.image_url)
        yield ("time_in", self.time_in)
        yield ("time_out", self.time_out)
        yield ("time_started", self.time_started)
        yield ("server", self.server)
        yield ("status", self.status.value)
        yield (
            "questions",
            [
                {"question": question, "answer": answer}
                for (question, answer) in self.questions
            ],
        )
        yield ("content_hash", self.content_hash)
