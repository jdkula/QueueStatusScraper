from bs4 import BeautifulSoup
from requests.models import Response
from src.util import nowify
from src.modals import Queue, Server, Chat, Entry, EntryState, QueueState
from datetime import datetime
import requests
import pytz

pacific = pytz.timezone("US/Pacific")


class QueueStatus:
    def __init__(self, session: requests.Session) -> None:
        self._session = session

    async def login(self, email: str, password: str) -> Response:
        res = self._session.get("https://queuestatus.com/")
        bs = BeautifulSoup(res.text, features="html.parser")
        csrf = bs.find("meta", {"name": "csrf-token"})["content"]
        return self._session.post(
            "https://queuestatus.com/users/post_login",
            data={"utf8": "✓", "email": email, "password": password, "commit": "Login"},
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "X-CSRF-Token": csrf,
                "X-Requested-With": "XMLHttpRequest",
            },
        )

    async def get_queue(self, queue_id: str) -> Queue:
        res = self._session.get(f"https://queuestatus.com/queues/{queue_id}/queue")
        bs = BeautifulSoup(res.text, features="html.parser")

        # Servers
        servers = []
        for container in bs.select(
            "div.active-server-container div.server-headshot-container"
        ):
            name = container.span.text.strip()
            pic = container.img["src"].strip()
            servers.append(Server(name, pic))

        # Chat
        chat = []
        chat_divs = bs.select("#chat-messages div")
        for i in range(0, len(chat_divs), 3):
            (name_el, time_el, message_el) = chat_divs[i : i + 3]
            timestamp = pacific.localize(
                datetime.strptime(time_el.text.strip(), "%b %d, %I:%M %p").replace(
                    year=datetime.now().year
                )
            )

            chat.append(Chat(name_el.text.strip(), message_el.text.strip(), timestamp))

        # Status
        signup = bs.select_one('a[data-target="#queue_signup"]')
        if signup:
            q_status = QueueState.OPEN
        else:
            q_status = QueueState.CLOSED

        # Entries
        entries = []
        for block in bs.select("div.queue-block"):
            signup_time = pacific.localize(
                nowify(
                    datetime.strptime(
                        block.select_one('div[title="Signup time"]').text.strip(),
                        "%I:%M %p",
                    )
                )
            )
            questions = []
            for question_block in block.select_one("div.menu-selections").children:
                question = question_block.b.text[:-1].strip()
                answer = question_block.text[len(question) + 2 :].strip()
                questions.append((question, answer))

            status = EntryState.WAITING
            time_out = None
            server = None
            if block.select_one(".in-process-block"):
                status = EntryState.IN_PROGRESS
            elif block.select_one(".served-block"):
                status = EntryState.SERVED
                time_out = pacific.localize(
                    nowify(
                        datetime.strptime(
                            block.select_one('div[title="Served time"]').text.strip(),
                            "%I:%M %p",
                        )
                    )
                )

            if status != EntryState.WAITING:
                server = block.find("b", text="Server:").next_sibling.strip()

            id_block = block.find(attrs={"data-queue_entry_id": True})
            id = None
            if id_block:
                id = id_block["data-queue_entry_id"].strip()

            entry = Entry(
                id=id,
                name=block.find("div", {"class": "name"}).text.strip(),
                image_url=block.find("img")["src"].strip(),
                time_in=signup_time,
                time_out=time_out,
                server=server,
                status=status,
                questions=questions,
            )
            entries.append(entry)

        return Queue(entries, chat, servers, q_status)
