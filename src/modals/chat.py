from datetime import datetime


class Chat:
    def __init__(self, name: str, message: str, timestamp: datetime) -> None:
        self.name = name
        self.message = message
        self.timestamp = timestamp

    def __iter__(self):
        yield ("name", self.name)
        yield ("message", self.message)
        yield ("timestamp", self.timestamp)
