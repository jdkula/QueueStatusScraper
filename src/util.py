"""
Provides utility functions used throughout the program
"""

from datetime import datetime, timedelta

import pytz

def nowify(dt: datetime) -> datetime:
    """
    Given a datetime with only time information filled out,
    returns a datetime with the date matching today.

    This operation is done using the system's current time zone.
    """
    now = datetime.now()

    nowified = dt.replace(year=now.year, month=now.month, day=now.day)
    if dt.hour > now.hour or (dt.hour == now.hour and dt.minute > now.minute):
        nowified -= timedelta(days=1)

    return nowified

def to_utc(dt: datetime) -> datetime:
    return dt.astimezone(pytz.utc)