#!/usr/bin/env python3
"""가구 개수는 방 전체의 항목 수이고, 좌우는 이 화면에서 본 쪽이다.

  python3 test_furniture_count.py
"""
import json
import math
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
import shots as S  # noqa: E402


def _house():
    return {
        "version": 1, "name": "count probe", "type": "room", "units": "mm", "wall": 100,
        "rooms": [
            {"id": "room", "kind": "bedroom", "name": "room", "rect": [0, 0, 4000, 3600]},
        ],
        "openings": [
            {"id": "w", "type": "window", "room": "room", "wall": "n",
             "offset": "center", "width": 1200, "height": 1200, "sill": 900},
            {"id": "front", "type": "door", "room": "room", "wall": "s",
             "offset": 2800, "width": 900, "to": "outside", "swing": "in", "hinge": "end"},
        ],
        "items": [
            {"id": "desk", "room": "room", "category": "desk", "label_en": "desk",
             "size": {"w": 1000, "d": 600, "h": 740}, "place": {"x": 900, "y": 900, "facing": "s"},
             "owned": True, "look": "a white desk"},
            {"id": "chair", "room": "room", "category": "chair", "label_en": "chair",
             "size": {"w": 500, "d": 500, "h": 900}, "place": {"x": 1400, "y": 1700, "facing": "s"},
             "owned": True, "look": "an office chair"},
            {"id": "bed", "room": "room", "category": "bed", "label_en": "bed",
             "size": {"w": 1100, "d": 2000, "h": 450}, "place": {"wall": "e", "offset": 400},
             "owned": True, "look": "a low bed"},
        ],
        "photo": {"concept": "natural", "ratio": "9:16", "shots": [
            {"id": "wide", "room": "room", "x": 2000, "y": 2800, "look_at": [2000, 400]},
        ]},
    }


def _describe(h):
    ctx, _ = S.P.check(h)
    W, H, _, sw, _ = S.RATIOS["9:16"]
    cam = S.Cam(2000, 2800, 1200, -math.pi / 2, 0.0, 2 * math.atan((sw / 2.0) / S.MAIN_LENS),
                W, H, S.MAIN_LENS, S.HORIZON["9:16"])
    sc = S.Scene(ctx, ctx.rooms["room"], 2300)
    cv = S.see_through(sc, cam, sc.render(cam))
    return S.describe(sc, cam, cv, cv.stats(), h)


def main():
    chair = "Exactly one chair in the whole room. No second chair, no extra empty chair."
    bed = "Exactly one bed in the whole room. No second bed, no extra empty bed."
    layout = "chair and desk on the left side of the frame, bed on the right side of the frame"
    _vis, lines, _ops, checks, _board, _avoid, _facts, _thru = _describe(_house())
    text = " ".join(lines)
    assert chair in text, text
    assert bed in text, text
    assert "Exactly one lamp" not in text
    assert layout in text, text
    assert S._COUNT_CHECK in checks, checks
    assert S._LAYOUT_CHECK in checks, checks
    assert S.person_same_furniture("chair") == (
        "the single chair from the reference, and she is sitting in that same chair")

    two = S.room_count_lines([
        {"id": "a", "category": "chair", "qty": 4},
        {"id": "b", "category": "chair"},
        {"id": "rug", "category": "rug"},
        {"id": "lamp", "category": "lamp", "on": "desk"},
    ])
    assert two == ["Exactly two chairs in the whole room. No extra chair, no extra empty chair."], two

    h = _house()
    with tempfile.TemporaryDirectory() as out:
        data = S.plan(h, out)
        shot = data["shots"][0]
        assert chair in shot["prompt"] and layout in shot["prompt"], shot["prompt"]
        assert S._COUNT_CHECK in shot["checks"] and S._LAYOUT_CHECK in shot["checks"]
        assert len(shot["prompt"]) <= S.PROMPT_MAX, len(shot["prompt"])
        md = open(os.path.join(out, "shots.md"), encoding="utf-8").read()
        assert "the single chair from the reference, and she is sitting in that same chair" in md
        saved = json.load(open(os.path.join(out, "shots.json"), encoding="utf-8"))
        assert saved["shots"][0]["id"] == "wide"
    print("ok furniture-count")


if __name__ == "__main__":
    main()
