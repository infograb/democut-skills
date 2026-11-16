#!/usr/bin/env python3
"""작은 주방은 방 안 모서리의 초광각으로 찍지 않는다.

1.6 m x 1.9 m 주방, 깊이 60cm 싱크대, 남쪽 벽 전체가 복도로 트여 있다. 이름은 없는 시험 집이다.
  python3 test_wide_stand.py
"""
import math
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
import shots as S  # noqa: E402


def house():
    return {
        "version": 1,
        "name": "probe small kitchen",
        "type": "oneroom",
        "units": "mm",
        "wall": 100,
        "rooms": [
            {"id": "cook", "kind": "kitchen", "name": "kitchen", "rect": [0, 0, 1600, 1900]},
            {"id": "hall", "kind": "hall", "name": "hall", "rect": [0, 2000, 1600, 2400]},
            {"id": "entry", "kind": "entrance", "name": "entry", "rect": [1600, 2000, 900, 1200]},
        ],
        "openings": [
            {"id": "to-hall", "type": "opening", "room": "cook", "wall": "s",
             "offset": 0, "width": 1600, "to": "hall"},
            {"id": "front", "type": "door", "room": "entry", "wall": "s",
             "offset": 0, "width": 900, "to": "outside", "swing": "out", "hinge": "end"},
        ],
        "items": [
            {"id": "counter", "room": "cook", "category": "kitchen_counter", "label": "counter",
             "size": {"w": 1200, "d": 600, "h": 850}, "place": {"wall": "w", "offset": 0},
             "owned": True, "look": "a white counter"},
            {"id": "fridge", "room": "cook", "category": "fridge", "label": "fridge",
             "size": {"w": 480, "d": 500, "h": 850}, "place": {"wall": "w", "offset_end": 0},
             "owned": True, "look": "a white fridge"},
            {"id": "rack", "room": "cook", "category": "other", "label": "dish rack",
             "size": {"w": 450, "d": 200, "h": 300}, "place": {"x": 80, "y": 400, "facing": "e"},
             "on": "counter", "owned": True, "look": "a dish rack"},
        ],
        "photo": {"concept": "natural", "ratio": "9:16"},
    }


def bad_corner(ctx):
    """방 안 모서리, 18mm. 예전 전체 컷이 고르던 자리다."""
    W, H, _, sw, _ = S.RATIOS["9:16"]
    room = ctx.rooms["cook"]
    x0, y0, x1, y1 = S.P.rr(room)
    x, y = x1 - 380, y1 - 380
    yaw = math.atan2(((y0 + y1) / 2) - y, ((x0 + x1) / 2) - x)
    hfov = 2 * math.atan((sw / 2.0) / S.WIDE_LENS)
    cam = S.Cam(x, y, 1200, yaw, 0.0, hfov, W, H, S.WIDE_LENS, S.HORIZON["9:16"])
    sc = S.Scene(ctx, room, 2300)
    cv = S.see_through(sc, cam, sc.render(cam))
    return wide_messages(sc, cam, cv)


def wide_messages(sc, cam, cv):
    return S.wide_faults(sc, cam, cv, cv.stats())


def main():
    h = house()
    ctx, _ = S.P.check(h)
    phys = [i for i in ctx.issues if i["level"] == "error" and i["code"] in S.PHYSICAL]
    assert not phys, phys
    faults = bad_corner(ctx)
    assert faults, "corner + 18mm should be rejected"
    assert any("80" in f or "38" in f or "65" in f or "근접" in f or "물러" in f for f in faults), faults
    out = tempfile.mkdtemp(prefix="wide-stand-")
    data = S.plan(h, out, max_hero=0)
    wides = [s for s in data["shots"] if s["kind"] == "wide" and s.get("for_room") == "cook"]
    assert wides, [(s["id"], s.get("for_room"), s["room"]) for s in data["shots"]]
    shot = wides[0]
    cam = shot["camera"]
    assert cam["lens_mm"] in (S.MAIN_LENS, S.ULTRA_LENS), cam
    assert cam["lens_mm"] == S.MAIN_LENS
    # 1.6 x 1.9 에 깊이 60cm 싱크대가 있으면 방 안에서는 80cm 를 못 지킨다. 복도에서 찍는다.
    assert shot["room"] == "hall", shot
    assert shot.get("for_room") == "cook"
    assert cam["y"] >= 2000, cam
    assert "cook" not in (data.get("unshot") or [])
    print("ok wide-stand", cam["x"], cam["y"], cam["lens_mm"], "faults", len(faults))


if __name__ == "__main__":
    main()
