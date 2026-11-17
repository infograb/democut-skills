#!/usr/bin/env python3
"""창은 도면의 오프셋·폭·높이·턱으로 그린다. 위 끝은 턱+높이.

  python3 test_window_size.py
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
import shots as S  # noqa: E402


def house(height=1200, width=1200, offset=900):
    return {
        "version": 1, "name": "window probe", "type": "oneroom", "units": "mm", "wall": 100,
        "rooms": [
            {"id": "room", "kind": "bedroom", "name": "room", "rect": [0, 0, 3000, 3600]},
            {"id": "entry", "kind": "entrance", "name": "entry", "rect": [3000, 2000, 1000, 1200]},
        ],
        "openings": [
            {"id": "w", "type": "window", "room": "room", "wall": "n",
             "offset": offset, "width": width, "height": height, "sill": 900},
            {"id": "front", "type": "door", "room": "entry", "wall": "s",
             "offset": 0, "width": 900, "to": "outside", "swing": "out", "hinge": "end"},
        ],
        "items": [
            {"id": "bed", "room": "room", "category": "bed", "label": "bed",
             "size": {"w": 1100, "d": 2000, "h": 450},
             "place": {"wall": "n", "offset": 950},
             "owned": True, "look": "a low bed"},
        ],
        "photo": {"concept": "natural", "ratio": "9:16"},
    }


def shot(h):
    ctx, _ = S.P.check(h)
    W, H, _, sw, _ = S.RATIOS["9:16"]
    cam = S.Cam(1500, 3000, 1200, -math.pi / 2, 0.0, 2 * math.atan((sw / 2.0) / S.MAIN_LENS),
                W, H, S.MAIN_LENS, S.HORIZON["9:16"])
    sc = S.Scene(ctx, ctx.rooms["room"], 2300)
    cv = S.see_through(sc, cam, sc.render(cam))
    _vis, _lines, ops, _checks, _board, _avoid, _facts, _thru = S.describe(sc, cam, cv, cv.stats(), h)
    return sc, " ".join(ops)


def main():
    h = house(height=1000, width=1200, offset=900)
    sc, ops = shot(h)
    win = next(m for m in sc.ops.values() if m["op"]["type"] == "window")
    zs = sorted({p[2] for p in win["poly"]})
    assert zs == [900, 1900], zs
    along = sorted({p[0] for p in win["poly"]})
    assert along == [900, 2100], along
    assert "120x100 cm sliding sash" in ops, ops
    assert "sill 90 cm" in ops, ops
    assert "above the bed" in ops, ops
    assert len(ops) <= 4000
    print("ok window-size")


if __name__ == "__main__":
    main()
