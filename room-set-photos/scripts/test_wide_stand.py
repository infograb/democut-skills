#!/usr/bin/env python3
"""작은 주방은 방 안 모서리의 초광각으로 찍지 않고, 문간 너머 방을 빈 판으로 두지 않는다.

1.6 m x 1.9 m 주방. 남쪽은 복도로, 북쪽은 침실로 벽 전체가 트여 있다. 이름은 없는 시험 집이다.
  python3 test_wide_stand.py
"""
import math
import os
import struct
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
            {"id": "bed", "kind": "bedroom", "name": "bedroom", "rect": [0, 0, 1600, 2100]},
            {"id": "cook", "kind": "kitchen", "name": "kitchen", "rect": [0, 2200, 1600, 1900]},
            {"id": "hall", "kind": "hall", "name": "hall", "rect": [0, 4200, 1600, 2400]},
            {"id": "entry", "kind": "entrance", "name": "entry", "rect": [1700, 4200, 900, 1200]},
        ],
        "openings": [
            {"id": "to-hall", "type": "opening", "room": "cook", "wall": "s",
             "offset": 0, "width": 1600, "to": "hall"},
            {"id": "to-bed", "type": "opening", "room": "cook", "wall": "n",
             "offset": 0, "width": 1600, "to": "bed"},
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
            {"id": "wardrobe", "room": "bed", "category": "wardrobe", "label": "wardrobe",
             "size": {"w": 800, "d": 500, "h": 1800}, "place": {"wall": "w", "offset_end": 0},
             "owned": True, "look": "a wood wardrobe"},
        ],
        "photo": {"concept": "natural", "ratio": "9:16"},
    }


def png_size(path):
    with open(path, "rb") as f:
        sig = f.read(8)
        assert sig == b"\x89PNG\r\n\x1a\n"
        _ln = struct.unpack(">I", f.read(4))[0]
        assert f.read(4) == b"IHDR"
        return struct.unpack(">II", f.read(8))


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
    # 문간을 채우기 전에 렌더하면 빈 회색이 남고, 채우면 침실 옷장까지 보인다.
    W, H, _, sw, _ = S.RATIOS["9:16"]
    cook = ctx.rooms["cook"]
    x0, y0, x1, y1 = S.P.rr(cook)
    cam_x, cam_y = (x0 + x1) / 2.0, y1 + 800
    yaw = math.atan2(((y0 + y1) / 2) - cam_y, ((x0 + x1) / 2) - cam_x)
    hfov = 2 * math.atan((sw / 2.0) / S.MAIN_LENS)
    cam = S.Cam(cam_x, cam_y, 1200, yaw, 0.0, hfov, W, H, S.MAIN_LENS, S.HORIZON["9:16"])
    bare = S.Scene(ctx, cook, 2300).render(cam)
    assert S.void_faults(bare), "unfilled opening should be an error"
    filled = S.see_through(S.Scene(ctx, ctx.rooms["hall"], 2300), cam, S.Scene(ctx, ctx.rooms["hall"], 2300).render(cam))
    assert not S.void_faults(filled), S.void_faults(filled)
    assert any(it["id"] == "wardrobe" for _sc, it, _oid in filled.through.values())
    out = tempfile.mkdtemp(prefix="wide-stand-")
    data = S.plan(h, out, max_hero=0)
    wides = [s for s in data["shots"] if s["kind"] == "wide" and s.get("for_room") == "cook"]
    assert wides, [(s["id"], s.get("for_room"), s["room"]) for s in data["shots"]]
    shot = wides[0]
    camj = shot["camera"]
    assert camj["lens_mm"] == S.MAIN_LENS
    # 1.6 x 1.9 에 깊이 60cm 싱크대가 있으면 방 안에서는 80cm 를 못 지킨다. 복도에서 찍는다.
    assert shot["room"] == "hall", shot["room"]
    assert shot.get("for_room") == "cook"
    assert camj["y"] >= 4200, camj
    assert "cook" not in (data.get("unshot") or [])
    assert "wardrobe" in shot["prompt"]
    refs = [r["file"] for r in shot["refs"] if r["role"] == "sketch"]
    assert refs == ["sketch/{}.png".format(shot["id"])]
    clean, legend = os.path.join(out, refs[0]), os.path.join(out, "sketch", shot["id"] + "-legend.png")
    cw, ch = png_size(clean)
    lw, lh = png_size(legend)
    assert (cw, ch) == (W, H)
    assert lw > cw and lh >= ch
    print("ok wide-stand", camj["x"], camj["y"], camj["lens_mm"], "legend", lw, lh)


if __name__ == "__main__":
    main()
