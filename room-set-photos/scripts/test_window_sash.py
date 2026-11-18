#!/usr/bin/env python3
"""도면이 달리 적지 않은 창은 샷시 미닫이다. 여닫이·들창은 Avoid 에 있다.

  python3 test_window_sash.py
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
import shots as S  # noqa: E402


def house(window):
    return {
        "version": 1, "name": "sash probe", "type": "oneroom", "units": "mm", "wall": 100,
        "rooms": [
            {"id": "room", "kind": "bedroom", "name": "room", "rect": [0, 0, 3000, 3600]},
            {"id": "entry", "kind": "entrance", "name": "entry", "rect": [3000, 2000, 1000, 1200]},
        ],
        "openings": [
            window,
            {"id": "front", "type": "door", "room": "entry", "wall": "s",
             "offset": 0, "width": 900, "to": "outside", "swing": "out", "hinge": "end"},
        ],
        "items": [
            {"id": "bed", "room": "room", "category": "bed", "label": "bed",
             "size": {"w": 1100, "d": 2000, "h": 900}, "place": {"wall": "w", "offset": 200},
             "owned": True, "look": "a low bed"},
        ],
        "photo": {"concept": "natural", "ratio": "9:16"},
    }


def view(window):
    h = house(window)
    ctx, _ = S.P.check(h)
    W, H, _, sw, _ = S.RATIOS["9:16"]
    cam = S.Cam(1500, 3000, 1200, -math.pi / 2, 0.0, 2 * math.atan((sw / 2.0) / S.MAIN_LENS),
                W, H, S.MAIN_LENS, S.HORIZON["9:16"])
    sc = S.Scene(ctx, ctx.rooms["room"], 2300)
    cv = S.see_through(sc, cam, sc.render(cam))
    _vis, _lines, ops, checks, _board, avoid, _facts, _thru = S.describe(sc, cam, cv, cv.stats(), h)
    return " ".join(ops), avoid, checks


def main():
    ops, avoid, checks = view({
        "id": "w", "type": "window", "room": "room", "wall": "n",
        "offset": "center", "width": 1800, "sill": 900,
    })
    assert "sliding sash" in ops, ops
    assert "slid open" not in ops
    assert S._SASH_AVOID in avoid, avoid
    assert any("샷시" in c for c in checks), checks

    ops, avoid, _checks = view({
        "id": "w", "type": "window", "room": "room", "wall": "n",
        "offset": "center", "width": 1800, "sill": 900, "open": True,
    })
    assert "one pane slid open behind the other" in ops, ops
    assert S._SASH_AVOID in avoid

    ops, avoid, checks = view({
        "id": "w", "type": "window", "room": "room", "wall": "n",
        "offset": "center", "width": 1800, "sill": 900, "style": "casement",
    })
    assert "casement" in ops and "sliding sash" not in ops, ops
    assert S._SASH_AVOID not in avoid, avoid
    assert not any("샷시" in c for c in checks)
    # 창 문장에 붙는 말은 짧다
    assert len("sliding sash, one pane slid open behind the other") < 60
    print("ok window-sash")


if __name__ == "__main__":
    main()
