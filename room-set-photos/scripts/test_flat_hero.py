#!/usr/bin/env python3
"""납작한 상판 위 물건은 키로 배율을 재지 않고, 자동 제품 컷 하나의 실패가 나머지 컷을 막지 않는다.

  python3 test_flat_hero.py
"""
import math
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
import shots as S  # noqa: E402


def _flat_house():
    return {
        "version": 1, "name": "flat cooktop", "type": "oneroom", "units": "mm", "wall": 100,
        "rooms": [
            {"id": "cook", "kind": "kitchen", "name": "kitchen", "rect": [0, 0, 2400, 2400]},
            {"id": "entry", "kind": "entrance", "name": "entry", "rect": [2500, 600, 1200, 1400]},
        ],
        "openings": [
            {"id": "front", "type": "door", "room": "entry", "wall": "s",
             "offset": 100, "width": 900, "to": "outside", "swing": "out", "hinge": "end"},
        ],
        "items": [
            {"id": "counter", "room": "cook", "category": "kitchen_counter", "label": "counter",
             "size": {"w": 1400, "d": 600, "h": 850}, "place": {"wall": "w", "offset": 0},
             "owned": True, "look": "a white counter"},
            {"id": "top", "room": "cook", "category": "appliance", "label": "induction cooktop",
             "size": {"w": 560, "d": 480, "h": 60}, "place": {"x": 40, "y": 200, "facing": "e"},
             "on": "counter", "owned": True, "look": "a black induction cooktop"},
            {"id": "pot", "room": "cook", "category": "other", "label": "pot",
             "size": {"w": 220, "d": 220, "h": 200}, "place": {"x": 80, "y": 900, "facing": "e"},
             "on": "counter", "owned": True, "look": "a steel pot"},
        ],
    }


def _ratio_by_height(sc, cam, cv, st):
    """예전 검사: 화면 높이 / 키. 납작한 물건은 여기서 1.75 를 넘을 수 있다."""
    rows = []
    for it in sc.items:
        s = st.get(sc.iid[it["id"]])
        if not s or s[0] < 30:
            continue
        ih = S.item_height(it, sc.ctx.geo[it["id"]])
        if ih < 50:
            continue
        ph = s[6] - s[5] + 1
        dist = S._gap_point(cam.x, cam.y, sc.ctx.geo[it["id"]]["rect"])
        rows.append((ph / float(ih), dist, it["id"]))
    if len(rows) < 2:
        return None
    near = min(r[1] for r in rows)
    cohort = [r for r in rows if r[1] <= near * 1.6]
    if len(cohort) < 2:
        return None
    med = sorted(r[0] for r in cohort)[len(cohort) // 2] or 1
    worst = max(cohort, key=lambda r: r[0])
    return worst[2], worst[0] / med


def check_flat_exempt():
    ctx, _ = S.P.check(_flat_house())
    sc = S.Scene(ctx, ctx.rooms["cook"], 2300)
    W, H, _, sw, _ = S.RATIOS["9:16"]
    # 상판 정면에서 쿡탑을 본다. 60mm 높이에 화면 높이를 나누면 같은 거리의 상판보다 커 보인다.
    cam = S.Cam(1300, 480, 1100, math.pi, math.radians(-12),
                2 * math.atan((sw / 2.0) / S.HERO_LENS), W, H, S.HERO_LENS, 0.5)
    cv = sc.render(cam)
    st = cv.stats()
    old = _ratio_by_height(sc, cam, cv, st)
    assert old and old[0] == "top" and old[1] > 1.75, old
    assert not S.scale_faults(sc, cam, cv, st), S.scale_faults(sc, cam, cv, st)


def check_auto_hero_continues():
    h = {
        "version": 1, "name": "drop hero", "type": "oneroom", "units": "mm", "wall": 100,
        "rooms": [
            {"id": "booth", "kind": "kitchen", "name": "booth", "rect": [0, 0, 2400, 2400]},
            {"id": "entry", "kind": "entrance", "name": "entry", "rect": [2500, 400, 1800, 1800]},
        ],
        "openings": [
            {"id": "front", "type": "door", "room": "entry", "wall": "s",
             "offset": 300, "width": 900, "to": "outside", "swing": "out", "hinge": "end"},
        ],
        "items": [
            {"id": "counter", "room": "booth", "category": "kitchen_counter", "label": "counter",
             "size": {"w": 1200, "d": 600, "h": 850}, "place": {"wall": "n", "offset": 0},
             "owned": True, "look": "a counter"},
            {"id": "bad", "room": "booth", "category": "appliance", "label": "bad unit",
             "size": {"w": 400, "d": 400, "h": 200}, "place": {"x": 100, "y": 80, "facing": "s"},
             "on": "counter", "look": "a small unit",
             "product": {"url": "https://example.com/unit", "dims_source": "user", "verified": True}},
            {"id": "shoe", "room": "entry", "category": "shoe_cabinet", "label": "shoes",
             "size": {"w": 800, "d": 300, "h": 1000}, "place": {"wall": "n", "offset": 200},
             "owned": True, "look": "a shoe cabinet"},
        ],
        "photo": {"concept": "natural", "ratio": "9:16"},
    }
    real = S.item_boxes

    def boxes(ctx, it):
        if it["id"] == "bad":
            return [(ctx.geo["bad"]["rect"], 0, 2000)]
        return real(ctx, it)

    S.item_boxes = boxes
    try:
        data = S.plan(h, tempfile.mkdtemp(prefix="flat-hero-"), max_hero=4)
    finally:
        S.item_boxes = real
    ids = [s["id"] for s in data["shots"]]
    assert not any(i.startswith("hero-") for i in ids), ids
    assert any(s["room"] == "entry" and s["kind"] == "wide" for s in data["shots"]), ids
    assert data.get("skipped"), data.get("skipped")
    assert any("hero" in sk["id"] for sk in data["skipped"])


def check_manual_still_stops():
    h = _flat_house()
    h["items"][1]["owned"] = False
    h["items"][1]["product"] = {"url": "https://example.com/top", "dims_source": "user", "verified": True}
    h["photo"] = {"concept": "natural", "ratio": "9:16", "shots": [
        {"id": "hero-top", "room": "cook", "kind": "hero", "target": "top",
         "x": 500, "y": 1600, "h": 1100, "yaw": -90, "pitch": -18, "lens": 26},
    ]}
    real = S.item_boxes

    def boxes(ctx, it):
        if it["id"] == "top":
            return [(ctx.geo["top"]["rect"], 0, 2000)]
        return real(ctx, it)

    S.item_boxes = boxes
    try:
        try:
            S.plan(h, tempfile.mkdtemp(prefix="manual-hero-"), max_hero=0)
        except SystemExit as e:
            assert "hero-top" in str(e), e
            return
        raise AssertionError("manual hero should hard-fail")
    finally:
        S.item_boxes = real


def main():
    check_flat_exempt()
    check_auto_hero_continues()
    check_manual_still_stops()
    print("ok flat-hero")


if __name__ == "__main__":
    main()
