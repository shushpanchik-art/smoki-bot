"""ROUTERS должен быть непустым списком aiogram-роутеров."""
from aiogram import Router

from handlers import ROUTERS


def test_routers_not_empty():
    assert isinstance(ROUTERS, list)
    assert len(ROUTERS) >= 2


def test_routers_are_router_instances():
    for r in ROUTERS:
        assert isinstance(r, Router), f"{r!r} не Router"


def test_routers_unique():
    assert len(ROUTERS) == len(set(id(r) for r in ROUTERS))
