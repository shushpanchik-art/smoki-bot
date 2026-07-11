"""Утренние факты: количество рандомно 1..N, а не всегда N."""
import random
from unittest.mock import AsyncMock, patch

import pytest

from services import content


@pytest.mark.asyncio
async def test_morning_facts_random_range():
    """При N=3 length_hint должен получать n из [1..3], встречаются разные."""
    seen = set()
    # утро: MORNING_START <= hour < MORNING_END
    fake_now = type("D", (), {"hour": content.config.MORNING_START})()
    with patch.object(content.db, "get_setting",
                      new=AsyncMock(return_value="3")), \
         patch.object(content.datetime, "datetime") as mdt, \
         patch.object(content.prompts, "facts_rules",
                      side_effect=lambda n: f"N={n}") as mfr:
        mdt.now.return_value = fake_now
        for seed in range(50):
            random.seed(seed)
            await content._default_length_hint()
        # собрать все переданные n
        seen = {call.args[0] for call in mfr.call_args_list}
    assert seen, "facts_rules ни разу не вызван"
    assert seen <= {1, 2, 3}, f"n вне диапазона: {seen}"
    assert len(seen) > 1, f"нет рандома, всегда одно значение: {seen}"


@pytest.mark.asyncio
async def test_morning_facts_min_one():
    """Даже при N=1 не падает и даёт 1."""
    fake_now = type("D", (), {"hour": content.config.MORNING_START})()
    with patch.object(content.db, "get_setting",
                      new=AsyncMock(return_value="1")), \
         patch.object(content.datetime, "datetime") as mdt, \
         patch.object(content.prompts, "facts_rules",
                      side_effect=lambda n: f"N={n}") as mfr:
        mdt.now.return_value = fake_now
        await content._default_length_hint()
        assert mfr.call_args.args[0] == 1
