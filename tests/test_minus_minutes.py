from scheduler import _minus_minutes


def test_basic_subtract():
    assert _minus_minutes(12, 0, 15) == (11, 45)


def test_same_hour():
    assert _minus_minutes(12, 30, 15) == (12, 15)


def test_midnight_wrap():
    assert _minus_minutes(0, 10, 15) == (23, 55)


def test_zero_delta():
    assert _minus_minutes(9, 0, 0) == (9, 0)


def test_full_hour_boundary():
    assert _minus_minutes(10, 0, 60) == (9, 0)
