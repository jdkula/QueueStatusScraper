class Server:
    def __init__(self, name: str, image_url: str) -> None:
        self.name = name
        self.image_url = image_url

    def __iter__(self):
        yield ("name", self.name)
        yield ("image_url", self.image_url)
