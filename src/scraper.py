"""
Implements a scraping class that maintains a 
"""
import os
from typing import Optional
from datetime import datetime, timedelta

import requests
import pytz
from bs4 import BeautifulSoup
from requests.models import Response

from src.util import nowify, to_utc
from src.modals import Queue, Server, Chat, Entry, EntryState, QueueState

configured_tz = os.environ.get("TIMEZONE")
localtz = pytz.timezone(configured_tz if configured_tz is not None else "US/Pacific")


class QueueStatusScraper:
    def __init__(self, session: Optional[requests.Session]) -> None:
        self._session = session if session is not None else requests.Session()

    async def login(self, email: str, password: str) -> Response:
        """Logs into QueueStatus using the provided email and password"""

        # Retrieve CSRF token
        res = self._session.get("https://queuestatus.com/")
        bs = BeautifulSoup(res.text, features="html.parser")
        csrf = bs.find("meta", {"name": "csrf-token"})["content"]

        # Login via post
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
        """Given a queue id, scrape the website and pack it into a Queue instance"""

        # Retrieve the queue website and parse it
        res = self._session.get(f"https://queuestatus.com/queues/{queue_id}/queue")
        bs = BeautifulSoup(res.text, features="html.parser")

        # Active servers
        servers = []
        for container in bs.select(
            "div.active-server-container div.server-headshot-container"
        ):
            name = container.span.text.strip()
            pic = container.img["src"].strip()
            servers.append(Server(name, pic))

        # Chat messages
        chat = []
        chat_divs = bs.select("#chat-messages div")
        for i in range(0, len(chat_divs), 3):
            # Chat messages are a flat list of divs in trios 🙄
            (name_el, time_el, message_el) = chat_divs[i : i + 3]

            # Timestamp are in local time in the format MMM DD, 12:MM pm
            timestamp = to_utc(
                localtz.localize(
                    datetime.strptime(time_el.text.strip(), "%b %d, %I:%M %p").replace(
                        year=datetime.now().year
                    )
                )
            )
            if timestamp > datetime.now(pytz.utc):  # Handle case where the year changes over
                timestamp -= timedelta(years=1)

            chat.append(Chat(name_el.text.strip(), message_el.text.strip(), timestamp))

        # Queue state/status
        signup = bs.select_one('a[data-target="#queue_signup"]')
        if signup:
            q_status = QueueState.OPEN
        else:
            q_status = QueueState.CLOSED

        # Each actual queue entry
        entries = []
        for block in bs.select("div.queue-block"):
            signup_time = to_utc(
                localtz.localize(
                    nowify(
                        datetime.strptime(
                            block.select_one('div[title="Signup time"]').text.strip(),
                            "%I:%M %p",
                        )
                    )
                )
            )

            # Grab questions/answers students type in
            questions = []
            for question_block in block.select_one("div.menu-selections").children:
                # Q/A is literally formatted as <b>Question:</b> Answer 🙄🙄🙄
                question = question_block.b.text[:-1].strip()  # Remove colon
                # Remove question from the answer and strip away extra whitespace
                answer = question_block.text[len(question) + 2 :].strip()
                questions.append((question, answer))

            # Default status is waiting -- other indications say otherwise
            status = EntryState.WAITING
            time_out = None
            server = None
            if block.select_one(".in-process-block"):
                # This class only present if we're in progress
                status = EntryState.IN_PROGRESS
            elif block.select_one(".served-block"):
                # This class only present if they've been served
                status = EntryState.SERVED
                time_out = to_utc(
                    localtz.localize(  # Only present once done serving
                        nowify(
                            datetime.strptime(
                                block.select_one(
                                    'div[title="Served time"]'
                                ).text.strip(),
                                "%I:%M %p",
                            )
                        )
                    )
                )

            if status != EntryState.WAITING:
                # Literally just need to search for Server: <XYZ> 🙄🙄
                server = block.find("b", text="Server:").next_sibling.strip()

            # Sometimes (if the block hasn't been completed yet) QueueStatus will expose an internal ID
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
