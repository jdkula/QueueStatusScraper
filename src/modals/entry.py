from datetime import datetime
from enum import Enum
from typing import List, Tuple, Union

import hashlib


class EntryState(Enum):
    WAITING = "waiting"
    IN_PROGRESS = "in_progress"
    SERVED = "served"
    REMOVED = "removed"

class Entry:
    def __init__(
        self,
        id: Union[None, str],
        name: str,
        image_url: str,
        time_in: Union[None, datetime],
        time_out: Union[None, datetime],
        server: Union[None, str],
        status: EntryState,
        questions: List[Tuple[str, str]],
    ) -> None:
        self.id = id
        self.name = name
        self.image_url = image_url
        self.time_in = time_in
        self.time_out = time_out
        self.server = server
        self.status = status
        self.questions = questions

    @property
    def content_hash(self) -> int:
        h = hashlib.sha256()
        h.update(self.name.encode("utf8"))
        for (_, answer) in self.questions:
            h.update(answer.encode("utf8"))

        return h.hexdigest()

    def __iter__(self):
        yield ("id", self.id)
        yield ("name", self.name)
        yield ("image_url", self.image_url)
        yield ("time_in", self.time_in)
        yield ("time_out", self.time_out)
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

