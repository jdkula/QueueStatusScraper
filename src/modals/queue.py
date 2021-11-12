"""
Represents a full Queue
"""
from typing import List
from enum import Enum

from src.modals.chat import Chat
from src.modals.entry import Entry
from src.modals.server import Server


class QueueState(Enum):
    OPEN = "open"
    CLOSED = "closed"

class Queue:
    def __init__(
        self,
        entries: List[Entry],
        chat: List[Chat],
        servers: List[Server],
        state: QueueState,
    ) -> None:
        self.entries = entries
        self.chat = chat
        self.servers = servers
        self.state = state

    def __iter__(self):
        # Allows this class to be turned into a dictionary -- for MongoDB
        yield ("state", self.state.value)
        yield ("entries", [dict(entry) for entry in self.entries])
        yield ("chat", [dict(chat) for chat in self.chat])
        yield ("servers", [dict(server) for server in self.servers])
