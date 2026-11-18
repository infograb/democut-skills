#!/usr/bin/env python3
"""원룸·작은 방 창의 기본은 간유리와 바깥 쇠창살. 맑은 유리는 주의.

  python3 test_window_glass.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
import planner as P  # noqa: E402


def codes(house):
    ctx, _ = P.check(house)
    return ctx, {i["code"] for i in ctx.issues}


def opening(rooms, window, htype="oneroom"):
    return {
        "version": 1, "name": "glass", "type": htype, "units": "mm", "wall": 100,
        "rooms": rooms,
        "openings": [
            {"id": "front", "type": "door", "room": rooms[0]["id"], "wall": "s", "offset": 0,
             "width": 900, "to": "outside", "swing": "out", "hinge": "end"},
            window,
        ],
        "items": [],
    }


def main():
    studio = P.shell({
        "type": "oneroom", "name": "studio",
        "rooms": [{"kind": "bedroom", "w": 3200, "d": 4000}],
    })
    w = next(o for o in studio["openings"] if o["type"] == "window" and o["room"] == "room")
    assert (w["glass"], w["bars"]) == ("frosted", "outside"), w
    assert any("간유리" in n for n in studio["meta"]["notes"]), studio["meta"]["notes"]

    small = P.shell({
        "type": "room", "name": "small",
        "rooms": [{"kind": "bedroom", "w": 3200, "d": 4000}],
    })
    sw = next(o for o in small["openings"] if o["type"] == "window")
    assert (sw["glass"], sw["bars"]) == ("frosted", "outside"), sw

    big = P.shell({
        "type": "room", "name": "big",
        "rooms": [{"kind": "living", "w": 6000, "d": 5000}],
    })
    bw = next(o for o in big["openings"] if o["type"] == "window")
    assert "glass" not in bw and "bars" not in bw, bw

    kept = P.shell({
        "type": "room", "name": "kept",
        "rooms": [{"kind": "bedroom", "w": 3000, "d": 3600}],
        "windows": [{"wall": "n", "offset": "center", "width": 1200, "height": 1200,
                     "sill": 900, "glass": "clear", "bars": False}],
    })
    kw = next(o for o in kept["openings"] if o["type"] == "window")
    assert kw["glass"] == "clear" and kw["bars"] is False, kw

    room = {"id": "room", "kind": "bedroom", "name": "방", "rect": [0, 0, 3200, 4000]}
    base = {"id": "w", "type": "window", "room": "room", "wall": "n", "offset": 400,
            "width": 1200, "height": 1200, "sill": 900}
    ctx, got = codes(opening([room], dict(base)))
    op = next(o for o in ctx.ops if o["id"] == "w")
    assert (op["glass"], op["bars"]) == ("frosted", "outside"), op
    assert "window_glass" not in got, got

    ctx, got = codes(opening([room], dict(base, glass="clear")))
    op = next(o for o in ctx.ops if o["id"] == "w")
    assert op["glass"] == "clear", op
    assert "window_glass" in got, got

    ctx, got = codes(opening([room], dict(base, glass="frosted", bars=False)))
    op = next(o for o in ctx.ops if o["id"] == "w")
    assert op["glass"] == "frosted" and op["bars"] is None, op
    assert "window_glass" not in got, got

    living = {"id": "living", "kind": "living", "name": "거실", "rect": [0, 0, 6000, 5000]}
    ctx, got = codes(opening([living], dict(base, id="w", room="living", width=1800), "apartment"))
    op = next(o for o in ctx.ops if o["id"] == "w")
    assert op["glass"] == "clear" and op["bars"] is None, op
    assert "window_glass" not in got, got

    tiny = {"id": "bed", "kind": "bedroom", "name": "침실", "rect": [0, 0, 3000, 4000]}
    ctx, got = codes(opening([tiny], dict(base, id="w", room="bed", glass="clear"), "apartment"))
    assert "window_glass" in got, got
    print("ok window-glass")


if __name__ == "__main__":
    main()
