"""
Modal class for an active server -- contains their name and profile picture
"""


class Server:
    def __init__(self, name: str, image_url: str) -> None:
        self.name = name
        self.image_url = image_url

    def __iter__(self):
        # Allows this class to be turned into a dictionary -- for MongoDB
        yield ("name", self.name)
        yield ("image_url", self.image_url)
