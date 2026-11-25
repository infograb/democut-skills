#!/usr/bin/env python3
"""방에 책상이 있으면 책상 컷(낮·저녁, 같은 카메라, 높이 1,500mm 이상)을 낸다.

  python3 test_desk_cut.py
"""
import math
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
import shots as S  # noqa: E402


def _room(desk=True):
    items = [
        {"id": "chair", "room": "room", "category": "chair", "label_en": "chair",
         "size": {"w": 480, "d": 480, "h": 900}, "place": {"x": 800, "y": 1500, "facing": "n"},
         "owned": True, "look": "an office chair", **({"with": "desk"} if desk else {})},
        {"id": "bed", "room": "room", "category": "bed", "label_en": "bed",
         "size": {"w": 1100, "d": 2000, "h": 450}, "place": {"wall": "e", "offset": 800},
         "owned": True, "look": "a low bed"},
    ]
    if desk:
        items.insert(0, {"id": "desk", "room": "room", "category": "desk", "label_en": "desk",
                         "size": {"w": 1100, "d": 600, "h": 740}, "place": {"x": 500, "y": 700, "facing": "s"},
                         "owned": True, "look": "a white desk"})
    return {
        "version": 1, "name": "desk cut probe", "type": "room", "units": "mm", "wall": 100,
        "rooms": [
            {"id": "room", "kind": "bedroom", "name": "room", "rect": [0, 0, 4000, 3600]},
            {"id": "hall", "kind": "hall", "name": "hall", "rect": [200, -1100, 900, 1000]},
        ],
        "openings": [
            {"id": "w", "type": "window", "room": "room", "wall": "n",
             "offset": "center", "width": 1200, "height": 1200, "sill": 900},
            {"id": "side", "type": "door", "room": "room", "wall": "n",
             "offset": 0, "width": 400, "to": "hall", "swing": "out", "hinge": "end"},
        ],
        "items": items,
        "photo": {"concept": "natural", "ratio": "9:16"},
    }


def _packed():
    """책상이 북쪽 벽 폭을 채워 뒤 모서리에는 설 자리가 없다. 앞에는 전체 컷이 선다."""
    return {
        "version": 1, "name": "no desk pocket", "type": "room", "units": "mm", "wall": 100,
        "rooms": [
            {"id": "room", "kind": "bedroom", "name": "room", "rect": [0, 0, 2400, 3200]},
        ],
        "openings": [
            {"id": "w", "type": "window", "room": "room", "wall": "s",
             "offset": "center", "width": 900, "height": 900, "sill": 900},
        ],
        "items": [
            {"id": "desk", "room": "room", "category": "desk", "label_en": "desk",
             "size": {"w": 2400, "d": 600, "h": 740}, "place": {"wall": "n", "offset": 0},
             "owned": True, "look": "a long desk"},
            {"id": "bed", "room": "room", "category": "bed", "label_en": "bed",
             "size": {"w": 900, "d": 1900, "h": 400}, "place": {"wall": "s", "offset": 200},
             "owned": True, "look": "a bed"},
        ],
        "photo": {"concept": "natural", "ratio": "9:16"},
    }


def _cam(shot):
    c = shot["camera"]
    return (c["x"], c["y"], c["height"], c["yaw_deg"], c["pitch_deg"], c["lens_mm"])


def check_present():
    with tempfile.TemporaryDirectory() as out:
        data = S.plan(_room(True), out)
    ids = [s["id"] for s in data["shots"]]
    assert "day-desk-to-bed" in ids, ids
    assert "evening-desk-to-bed" in ids, ids
    day = next(s for s in data["shots"] if s["id"] == "day-desk-to-bed")
    eve = next(s for s in data["shots"] if s["id"] == "evening-desk-to-bed")
    assert day["kind"] == "desk" and eve["kind"] == "desk"
    assert day["camera"]["height"] >= S.DESK_H_MIN, day["camera"]
    assert eve["camera"]["height"] >= S.DESK_H_MIN, eve["camera"]
    assert _cam(day) == _cam(eve), (_cam(day), _cam(eve))
    assert eve.get("pair") == "day-desk-to-bed", eve.get("pair")
    assert day["camera"]["pitch_deg"] < 0
    assert "The chair must not hide the bed." in day["prompt"]
    assert "cut off at the left or right edge" in day["prompt"]
    assert S.DESK_AVOID_CHAIR in day["prompt"] and S.DESK_AVOID_DOOR in day["prompt"]
    assert "evening" in eve["prompt"].lower()
    assert len(day["prompt"]) <= S.PROMPT_MAX and len(eve["prompt"]) <= S.PROMPT_MAX
    assert "의자 — 침대를 가리지 않는다" in day["checks"]
    assert "낮·저녁 — 같은 카메라의 한 쌍이다" in day["checks"]
    assert any("빛만 저녁이다" in c for c in eve["checks"]), eve["checks"]
    assert not any("빛이 대표 컷과 같다" in c for c in eve["checks"])
    refs = S.seated_room_refs(data["shots"])
    assert refs == ["day-desk-to-bed", "evening-desk-to-bed"] or set(refs) == {
        "day-desk-to-bed", "evening-desk-to-bed"}, refs
    assert all("desk-to-" in i for i in refs)
    assert not data.get("desk_unplaced"), data.get("desk_unplaced")
    # 카메라는 책상 밖, 뒤 모서리 근처이고 침대 발치 쪽을 본다
    ctx, _ = S.P.check(_room(True))
    rect = ctx.geo["desk"]["rect"]
    x, y = day["camera"]["x"], day["camera"]["y"]
    assert not (rect[0] < x < rect[2] and rect[1] < y < rect[3]), (x, y, rect)
    corners = [(c[0], c[1]) for c in S._back_corners(rect, ctx.geo["desk"]["facing"])]
    near = min((x - c[0]) ** 2 + (y - c[1]) ** 2 for c in corners) ** 0.5
    assert near <= 600, (x, y, corners, near)
    bed = ctx.geo["bed"]["rect"]
    foot = S._foot_point(bed, ctx.geo["bed"]["facing"], "mid")
    yaw = math.radians(day["camera"]["yaw_deg"])
    fx, fy = math.cos(yaw), math.sin(yaw)
    vx, vy = foot[0] - x, foot[1] - y
    norm = (vx ** 2 + vy ** 2) ** 0.5
    assert (fx * vx + fy * vy) / norm > 0.7, (day["camera"], foot)


def check_absent_without_desk():
    with tempfile.TemporaryDirectory() as out:
        data = S.plan(_room(False), out)
    ids = [s["id"] for s in data["shots"]]
    assert not any("desk-to-" in i for i in ids), ids
    assert not data.get("desk_unplaced")
    assert S.seated_room_refs(data["shots"]) == []


def check_unplaced():
    with tempfile.TemporaryDirectory() as out:
        data = S.plan(_packed(), out)
    ids = [s["id"] for s in data["shots"]]
    assert not any("desk-to-" in i for i in ids), ids
    assert data.get("desk_unplaced"), data
    assert data["desk_unplaced"][0]["room"] == "room"
    assert "책상" in data["desk_unplaced"][0]["why"]


def check_manual_warns():
    h = _room(True)
    h["photo"]["shots"] = [
        {"id": "wide", "room": "room", "x": 2000, "y": 2800, "look_at": [2000, 400]},
    ]
    with tempfile.TemporaryDirectory() as out:
        data = S.plan(h, out)
    ids = [s["id"] for s in data["shots"]]
    assert "wide" in ids
    assert not any("desk-to-" in i for i in ids), ids
    assert data.get("desk_unplaced"), data.get("desk_unplaced")


def main():
    check_present()
    check_absent_without_desk()
    check_unplaced()
    check_manual_warns()
    print("ok desk-cut")


if __name__ == "__main__":
    main()
