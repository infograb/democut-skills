#!/usr/bin/env python3
"""현관 타일 경계는 개구부 선이고, 그 선에 닿은 가구 앞면과 맞춘다.

  python3 test_entry_floor.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
import shots as S  # noqa: E402


def main():
    house = {
        "version": 1, "name": "entry floor", "type": "oneroom", "units": "mm", "wall": 100,
        "rooms": [
            {"id": "cook", "kind": "kitchen", "name": "kitchen", "rect": [0, 0, 1600, 1900]},
            {"id": "entry", "kind": "entrance", "name": "entry", "rect": [0, 2000, 1600, 600]},
        ],
        "openings": [
            {"id": "gap", "type": "opening", "room": "cook", "wall": "s",
             "offset": 0, "width": 1600, "to": "entry"},
            {"id": "front", "type": "door", "room": "entry", "wall": "s",
             "offset": 200, "width": 900, "to": "outside", "swing": "out", "hinge": "end"},
        ],
        "items": [
            {"id": "fridge", "room": "cook", "category": "fridge", "label_en": "fridge",
             "size": {"w": 600, "d": 500, "h": 1800}, "place": {"wall": "s", "offset": 0},
             "owned": True},
        ],
    }
    ctx, _ = S.P.check(house)
    line, avoid = S.entry_floor_line(ctx, ["entry"], {"fridge"})
    assert "tile starts at the opening line" in line, line
    assert "level with the front of the fridge" in line, line
    assert "one small step" in line
    assert avoid == S.AVOID_TILE
    bare, avoid2 = S.entry_floor_line(ctx, ["entry"], set())
    assert "opening line" in bare and "fridge" not in bare, bare
    assert avoid2 == S.AVOID_TILE
    print("ok entry-floor")


if __name__ == "__main__":
    main()
