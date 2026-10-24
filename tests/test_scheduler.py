from datetime import datetime
from zoneinfo import ZoneInfo

from automation.scheduler_ingest import due

KST = ZoneInfo("Asia/Seoul")


def test_ingest_runs_at_eight_in_the_morning_and_evening():
    morning = datetime(2026, 10, 19, 8, 0, tzinfo=KST)
    evening = datetime(2026, 10, 19, 20, 0, tzinfo=KST)
    assert due(morning, None)
    assert not due(morning, (morning.date(), 8))
    assert due(evening, (morning.date(), 8))
    assert not due(datetime(2026, 10, 19, 8, 1, tzinfo=KST), None)
    assert not due(datetime(2026, 10, 19, 12, 0, tzinfo=KST), None)
