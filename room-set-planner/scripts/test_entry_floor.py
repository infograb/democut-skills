#!/usr/bin/env python3
"""현관 바닥은 타일, 경계는 방 가장자리다.

  python3 test_entry_floor.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
import planner as P  # noqa: E402


def house(floor=None):
    entry = {"id": "entry", "kind": "entrance", "name": "entry", "rect": [0, 2000, 1600, 600]}
    if floor is not None:
        entry["floor"] = floor
    return {
        "version": 1, "name": "entry floor", "type": "oneroom", "units": "mm", "wall": 100,
        "rooms": [
            {"id": "cook", "kind": "kitchen", "name": "kitchen", "rect": [0, 0, 1600, 1900]},
            entry,
        ],
        "openings": [
            {"id": "gap", "type": "opening", "room": "cook", "wall": "s",
             "offset": 0, "width": 1600, "to": "entry"},
            {"id": "front", "type": "door", "room": "entry", "wall": "s",
             "offset": 200, "width": 900, "to": "outside", "swing": "out", "hinge": "end"},
        ],
        "items": [
            {"id": "cab", "room": "cook", "category": "storage", "label": "cabinet",
             "size": {"w": 600, "d": 500, "h": 1800}, "place": {"wall": "s", "offset": 0},
             "owned": True},
        ],
    }


def main():
    h = house()
    ctx, _ = P.check(h)
    floor = next(r for r in h["rooms"] if r["id"] == "entry")["floor"]
    assert floor == {"material": "tile", "step_mm": 50, "boundary": "room_edge"}, floor
    shell = P.shell({"type": "oneroom", "name": "studio", "rooms": [{"kind": "bedroom", "w": 3200, "d": 4000}]})
    ent = next(r for r in shell["rooms"] if r["kind"] == "entrance")
    assert ent["floor"]["boundary"] == "room_edge" and ent["floor"]["material"] == "tile"

    kept = house("oak laminate, no step")
    P.check(kept)
    assert next(r["floor"] for r in kept["rooms"] if r["id"] == "entry") == "oak laminate, no step"
    print("ok entry-floor")


if __name__ == "__main__":
    main()
