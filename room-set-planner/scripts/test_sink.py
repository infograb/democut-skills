#!/usr/bin/env python3
"""개수대는 상판에 자동으로 그리지 않고, 상판 위 품목으로만 둔다.

  python3 test_sink.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
import planner as P  # noqa: E402


def base():
    return {
        "version": 1, "name": "sink probe", "type": "oneroom", "units": "mm", "wall": 100,
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
        ],
    }


def codes(house):
    ctx, _ = P.check(house)
    return ctx, [i["code"] for i in ctx.issues]


def main():
    ctx, got = codes(base())
    assert "no_sink" in got, got
    sym = "".join(P.furniture_symbol(next(i for i in ctx.items if i["id"] == "counter"), ctx.geo["counter"]))
    assert "<rect" not in sym, sym
    assert "<line" in sym

    h = base()
    h["items"].append({
        "id": "sink", "room": "cook", "category": "sink", "label": "sink",
        "size": {"w": 400, "d": 400, "h": 160}, "place": {"x": 80, "y": 40, "facing": "s"},
        "on": "counter", "owned": True,
    })
    ctx, got = codes(h)
    assert "no_sink" not in got, got
    assert "on_fit" not in got and "on_overlap" not in got, got
    sink = next(i for i in ctx.items if i["id"] == "sink")
    sym = "".join(P.furniture_symbol(sink, ctx.geo["sink"]))
    assert "<rect" in sym and "<ellipse" in sym, sym

    hang = base()
    hang["items"].append({
        "id": "sink", "room": "cook", "category": "sink", "label": "sink",
        "size": {"w": 700, "d": 400, "h": 160}, "place": {"x": 0, "y": 250, "facing": "s"},
        "on": "counter", "owned": True,
    })
    _ctx, got = codes(hang)
    assert "on_fit" in got, got

    both = base()
    both["items"] += [
        {"id": "sink", "room": "cook", "category": "sink", "label": "sink",
         "size": {"w": 400, "d": 400, "h": 160}, "place": {"x": 80, "y": 40, "facing": "s"},
         "on": "counter", "owned": True},
        {"id": "top", "room": "cook", "category": "appliance", "label": "cooktop",
         "size": {"w": 300, "d": 300, "h": 60}, "place": {"x": 200, "y": 80, "facing": "s"},
         "on": "counter", "owned": True},
    ]
    _ctx, got = codes(both)
    assert "on_overlap" in got, got

    bowl = base()
    bowl["items"] += [
        {"id": "sink", "room": "cook", "category": "sink", "label": "sink",
         "size": {"w": 400, "d": 400, "h": 160}, "bowl": 200,
         "place": {"x": 80, "y": 40, "facing": "s"}, "on": "counter", "owned": True},
        {"id": "wash", "room": "cook", "category": "washer", "label": "washer",
         "size": {"w": 600, "d": 600, "h": 850}, "place": {"x": 40, "y": 0, "facing": "s"},
         "with": "counter", "owned": True},
    ]
    _ctx, got = codes(bowl)
    assert "sink_bowl" in got, got

    clear = base()
    clear["items"] += [
        {"id": "sink", "room": "cook", "category": "sink", "label": "sink",
         "size": {"w": 400, "d": 400, "h": 160}, "bowl": 180,
         "place": {"x": 80, "y": 40, "facing": "s"}, "on": "counter", "owned": True},
        {"id": "wash", "room": "cook", "category": "washer", "label": "washer",
         "size": {"w": 600, "d": 550, "h": 820}, "place": {"x": 1100, "y": 0, "facing": "s"},
         "with": "counter", "owned": True},
    ]
    _ctx, got = codes(clear)
    assert "sink_bowl" not in got, got
    print("ok sink")


if __name__ == "__main__":
    main()
