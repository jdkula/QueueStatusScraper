from datetime import datetime, timedelta


def nowify(dt: datetime) -> datetime:
    now = datetime.now()

    nowified = dt.replace(year=now.year, month=now.month, day=now.day)
    if dt.hour > now.hour or (dt.hour == now.hour and dt.minute > now.minute):
        nowified -= timedelta(days=1)

    return nowified
