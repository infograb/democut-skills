#!/usr/bin/env python3
"""싱크 볼은 상판 윗면의 개구다. 통으로 그리면 앞면을 가리고 가까운 건조대보다 앞에 선다.

서쪽 벽 상판 1400×600×850. 싱크는 북쪽, 건조대는 그 남쪽(카메라에 더 가깝다).
카메라는 주방 남쪽, 높이 1200, 26mm, 북쪽을 본다.
  python3 test_sink_basin.py
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
import shots as S  # noqa: E402


def house():
    return {
        "version": 1, "name": "sink along counter", "type": "oneroom", "units": "mm", "wall": 100,
        "rooms": [
            {"id": "cook", "kind": "kitchen", "name": "kitchen", "rect": [0, 0, 2000, 2800]},
            {"id": "entry", "kind": "entrance", "name": "entry", "rect": [2100, 1600, 900, 1200]},
        ],
        "openings": [
            {"id": "front", "type": "door", "room": "entry", "wall": "s",
             "offset": 0, "width": 800, "to": "outside", "swing": "out", "hinge": "end"},
        ],
        "items": [
            {"id": "counter", "room": "cook", "category": "kitchen_counter", "label": "counter",
             "size": {"w": 1400, "d": 600, "h": 850}, "place": {"wall": "w", "offset": 0},
             "owned": True, "look": "a white counter"},
            {"id": "sink", "room": "cook", "category": "sink", "label": "sink",
             "size": {"w": 550, "d": 450, "h": 300}, "bowl": 240,
             "place": {"x": 40, "y": 40, "facing": "e"}, "on": "counter",
             "owned": True, "look": "a stainless sink"},
            {"id": "rack", "room": "cook", "category": "other", "label": "dish rack",
             "size": {"w": 450, "d": 200, "h": 300}, "place": {"x": 40, "y": 640, "facing": "e"},
             "on": "counter", "owned": True, "look": "a dish rack"},
        ],
    }


def _inside(x, y, poly):
    n, hit = len(poly), False
    j = n - 1
    for i in range(n):
        xi, yi = poly[i]
        xj, yj = poly[j]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / ((yj - yi) or 1e-9) + xi:
            hit = not hit
        j = i
    return hit


def _proj(cam, pts):
    out = []
    for p in pts:
        q = cam.to_cam(p)
        if q[2] <= S.NEAR:
            return None
        out.append(cam.proj(q))
    return out


def main():
    ctx, _ = S.P.check(house())
    assert ctx.geo["sink"]["rect"][1] < ctx.geo["rack"]["rect"][1], "sink must be north of the rack"
    sc = S.Scene(ctx, ctx.rooms["cook"], 2300)
    boxes = sc.boxes["sink"]
    top = 850
    # 볼 통이 아니다. 개구는 윗면 두께뿐이고 수전은 폭 약 50mm, 높이 300mm.
    basin = [b for b in boxes if b[2] <= top]
    faucet = [b for b in boxes if b[2] > top]
    assert basin and faucet
    assert basin[0][2] - basin[0][1] < 10, basin
    fw = min(faucet[0][0][2] - faucet[0][0][0], faucet[0][0][3] - faucet[0][0][1])
    assert 40 <= fw <= 60, faucet[0][0]
    assert abs((faucet[0][2] - faucet[0][1]) - 300) < 1

    W, H, _, sw, _ = S.RATIOS["9:16"]
    # 상판 한가운데 남쪽, 북쪽을 본다. 건조대가 싱크보다 가깝다.
    cam = S.Cam(300, 2000, 1200, -math.pi / 2, 0.0, 2 * math.atan((sw / 2.0) / S.MAIN_LENS),
                W, H, S.MAIN_LENS, S.HORIZON["9:16"])
    cv = sc.render(cam)
    st = cv.stats()
    sink_id, rack_id, counter_id = sc.iid["sink"], sc.iid["rack"], sc.iid["counter"]
    assert st.get(sink_id) and st[sink_id][0] > 200, st.get(sink_id)
    assert st.get(rack_id) and st[rack_id][0] > 2000, st.get(rack_id)

    cr = ctx.geo["counter"]["rect"]
    top_poly = _proj(cam, [(cr[0], cr[1], top), (cr[2], cr[1], top), (cr[2], cr[3], top), (cr[0], cr[3], top)])
    # 동쪽 앞면. 카메라가 남쪽에서 북쪽을 보므로 이 면이 상판의 정면이다.
    front = _proj(cam, [(cr[2], cr[1], 0), (cr[2], cr[3], 0), (cr[2], cr[3], top), (cr[2], cr[1], top)])
    assert top_poly and front
    sink_n = on_top = on_front = 0
    ids = cv.ids
    for y in range(cv.h):
        row = ids[y * cv.w:(y + 1) * cv.w]
        for x, v in enumerate(row):
            if v != sink_id:
                continue
            sink_n += 1
            if _inside(x + 0.5, y + 0.5, top_poly):
                on_top += 1
            if _inside(x + 0.5, y + 0.5, front):
                on_front += 1
    assert sink_n > 0
    assert on_top / float(sink_n) >= 0.7, (on_top, sink_n)
    assert on_front == 0, on_front

    # 앞면 한가운데는 상판이다. 싱크 통이 덮지 않는다.
    face = (cr[2], (cr[1] + cr[3]) / 2.0, top * 0.45)
    q = cam.to_cam(face)
    u, v = cam.proj(q)
    px, py = int(u), int(v)
    assert 0 <= px < cv.w and 0 <= py < cv.h
    assert cv.ids[py * cv.w + px] == counter_id, cv.ids[py * cv.w + px]

    # 가까운 건조대 앞면은 싱크에 가려지지 않는다.
    rr = ctx.geo["rack"]["rect"]
    rq = cam.to_cam(((rr[0] + rr[2]) / 2.0, (rr[1] + rr[3]) / 2.0, top + 150))
    ru, rv = cam.proj(rq)
    rx, ry = int(ru), int(rv)
    assert cv.ids[ry * cv.w + rx] == rack_id, cv.ids[ry * cv.w + rx]
    print("ok sink-basin", "sink", sink_n, "on top", on_top, "rack", st[rack_id][0])


if __name__ == "__main__":
    main()
