import pytest
from datetime import datetime, timedelta

from news_service.src.calendar.engine import EconomicCalendarEngine


@pytest.mark.asyncio
async def test_calendar_fetch_and_bias_prediction():
    engine = EconomicCalendarEngine(providers=[])
    events = await engine.fetch_events(datetime.utcnow() - timedelta(days=1), datetime.utcnow())
    assert isinstance(events, list)
    if events:
        bias = engine.predict_bias(events[0])
        assert "bias" in bias
