#!/usr/bin/env python3
"""싱크 줄 위 상부장과 쿡탑 위 후드는 기본으로 넣고, 빼면 주의가 난다.

  python3 test_kitchen.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
import planner as P  # noqa: E402


def house(extra=None, kitchen=None):
    h = {
        "version": 1, "name": "kitchen probe", "type": "oneroom", "units": "mm", "wall": 100,
        "rooms": [
            {"id": "cook", "kind": "kitchen", "name": "kitchen", "rect": [0, 0, 2400, 2000]},
            {"id": "entry", "kind": "entrance", "name": "entry", "rect": [0, 2100, 1200, 1200]},
        ],
        "openings": [
            {"id": "front", "type": "door", "room": "entry", "wall": "s",
             "offset": 100, "width": 900, "to": "outside", "swing": "out", "hinge": "end"},
        ],
        "items": [
            {"id": "counter", "room": "cook", "category": "kitchen_counter", "label": "counter",
             "size": {"w": 1800, "d": 600, "h": 850}, "place": {"wall": "n", "offset": 0},
             "owned": True},
            {"id": "sink", "room": "cook", "category": "sink", "label": "sink",
             "size": {"w": 500, "d": 400, "h": 180}, "place": {"x": 200, "y": 40, "facing": "s"},
             "on": "counter", "owned": True},
            {"id": "top", "room": "cook", "category": "appliance", "label": "induction cooktop",
             "size": {"w": 560, "d": 480, "h": 60}, "place": {"x": 900, "y": 40, "facing": "s"},
             "on": "counter", "owned": True},
        ],
    }
    if extra:
        h["items"].extend(extra)
    if kitchen is not None:
        h["kitchen"] = kitchen
    return h


def codes(h):
    ctx, _ = P.check(h)
    return ctx, {i["code"] for i in ctx.issues}


def main():
    h = house()
    ctx, got = codes(h)
    up = next(i for i in h["items"] if i["category"] == "upper_cabinet")
    hood = next(i for i in h["items"] if i["category"] == "hood")
    assert up["over"] == "counter" and up["z"] == 850 + 550 and up["size"]["d"] == 340, up
    assert hood["above"] == "top" and hood["z"] == 850 + 760, hood
    assert "no_upper" not in got and "no_hood" not in got, got
    assert up["id"] in ctx.geo and hood["id"] in ctx.geo
    codes(h)
    assert sum(1 for i in h["items"] if i["category"] == "upper_cabinet") == 1
    assert sum(1 for i in h["items"] if i["category"] == "hood") == 1

    off = house(kitchen={"upper": False, "hood": False})
    _ctx, got = codes(off)
    assert not any(i["category"] == "upper_cabinet" for i in off["items"])
    assert not any(i["category"] == "hood" for i in off["items"])
    assert "no_upper" in got and "no_hood" in got, got

    one = house(extra=[{
        "id": "up", "room": "cook", "category": "upper_cabinet", "label": "up",
        "size": {"w": 1800, "d": 340, "h": 700}, "place": {"wall": "n", "offset": 0},
        "z": 1400, "over": "counter", "owned": True,
    }])
    one["items"][2]["hood"] = False
    _ctx, got = codes(one)
    assert sum(1 for i in one["items"] if i["category"] == "upper_cabinet") == 1
    assert "no_upper" not in got and "no_hood" in got, got
    print("ok kitchen")


if __name__ == "__main__":
    main()
