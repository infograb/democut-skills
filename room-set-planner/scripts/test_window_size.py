#!/usr/bin/env python3
"""원룸 창 기본은 1200×1200, 턱 900. 1500 초과·높이 없음은 주의.

  python3 test_window_size.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
import planner as P  # noqa: E402


def codes(house):
    ctx, _ = P.check(house)
    return ctx, {i["code"] for i in ctx.issues}


def main():
    house = P.shell({
        "type": "oneroom", "name": "studio",
        "rooms": [{"kind": "bedroom", "w": 3200, "d": 4000}],
    })
    wins = [o for o in house["openings"] if o["type"] == "window" and o["room"] == "room"]
    assert len(wins) == 1, wins
    w = wins[0]
    assert (w["width"], w["height"], w["sill"]) == (1200, 1200, 900), w
    assert w["offset"] == (3200 - 1200) / 2, w

    wide = {
        "version": 1, "name": "studio", "type": "oneroom", "units": "mm", "wall": 100,
        "rooms": [
            {"id": "room", "kind": "bedroom", "name": "방", "rect": [0, 0, 3200, 4000]},
            {"id": "entry", "kind": "entrance", "name": "현관", "rect": [0, 4100, 1000, 1200]},
        ],
        "openings": [
            {"id": "front", "type": "door", "room": "entry", "wall": "s", "offset": 0, "width": 900,
             "to": "outside", "swing": "out", "hinge": "end"},
            {"id": "w", "type": "window", "room": "room", "wall": "n", "offset": 200, "width": 1800, "sill": 900},
        ],
        "items": [],
    }
    ctx, got = codes(wide)
    op = next(o for o in ctx.ops if o["id"] == "w")
    assert op["height"] == 1200 and op["sill"] == 900, op
    assert "window_wide" in got and "window_height" in got, got

    given = dict(wide)
    given["openings"] = [
        wide["openings"][0],
        {"id": "w", "type": "window", "room": "room", "wall": "n", "offset": 400,
         "width": 1200, "height": 1100, "sill": 900},
    ]
    ctx, got = codes(given)
    op = next(o for o in ctx.ops if o["id"] == "w")
    assert op["height"] == 1100, op
    assert "window_wide" not in got and "window_height" not in got, got

    big = {
        "version": 1, "name": "apt", "type": "apartment", "units": "mm", "wall": 100,
        "rooms": [
            {"id": "living", "kind": "living", "name": "거실", "rect": [0, 0, 6000, 5000]},
            {"id": "entry", "kind": "entrance", "name": "현관", "rect": [0, 5100, 1400, 1500]},
        ],
        "openings": [
            {"id": "front", "type": "door", "room": "entry", "wall": "s", "offset": 0, "width": 900,
             "to": "outside", "swing": "out", "hinge": "end"},
            {"id": "w", "type": "window", "room": "living", "wall": "n", "offset": 800, "width": 1800, "sill": 0},
        ],
        "items": [],
    }
    ctx, got = codes(big)
    op = next(o for o in ctx.ops if o["id"] == "w")
    assert op["height"] == 1200, op
    assert "window_wide" not in got and "window_height" not in got, got
    print("ok window-size")


if __name__ == "__main__":
    main()
