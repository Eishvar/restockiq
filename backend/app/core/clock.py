"""Time helpers. The app works in Asia/Kuala_Lumpur; timestamps are stored as naive local time."""
from datetime import datetime
from zoneinfo import ZoneInfo

KL = ZoneInfo("Asia/Kuala_Lumpur")


def now_kl() -> datetime:
    return datetime.now(KL).replace(tzinfo=None)
