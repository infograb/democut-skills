#!/usr/bin/env python3
"""화장실 수건걸이는 필수다. 없거나 벽·좌표·설치 높이·크기가 없으면 오류다.

  python3 test_towel.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
import planner as P  # noqa: E402


def house(items=None):
    h = {
        "version": 1, "name": "towel probe", "type": "room", "units": "mm", "wall": 100,
        "rooms": [
            {"id": "bath", "kind": "bathroom", "name": "화장실", "rect": [0, 0, 1600, 2200]},
        ],
        "openings": [
            {"id": "d", "type": "door", "room": "bath", "wall": "s",
             "offset": 200, "width": 750, "to": "outside", "swing": "out", "hinge": "start"},
        ],
        "items": items or [],
    }
    return h


def towel(**over):
    it = {
        "id": "bar", "room": "bath", "category": "towel_bar", "label": "수건걸이",
        "size": {"w": 600, "d": 80, "h": 40},
        "place": {"wall": "n", "offset": 200},
        "z": 1300,
        "placeholder": True,
    }
    it.update(over)
    return it


def codes(h):
    ctx, _ = P.check(h)
    return ctx, [i["code"] for i in ctx.issues]


def main():
    bare = house()
    _ctx, got = codes(bare)
    assert "no_towel" in got, got
    assert bare["items"] == []

    _ctx, got = codes(house([towel(place={"offset": 200})]))
    assert "towel_wall" in got, got

    _ctx, got = codes(house([towel(place={"wall": "n"})]))
    assert "towel_pos" in got, got
    assert "towel_wall" not in got, got

    dropped = towel()
    del dropped["z"]
    _ctx, got = codes(house([dropped]))
    assert "towel_height" in got, got
    assert "no_towel" not in got, got

    _ctx, got = codes(house([towel(z=0)]))
    assert "towel_height" in got, got

    short = towel()
    del short["size"]["h"]
    _ctx, got = codes(house([short]))
    assert "towel_size" in got, got

    _ctx, got = codes(house([towel()]))
    assert not ({"no_towel", "towel_wall", "towel_pos", "towel_height", "towel_size"} & set(got)), got

    bed = {
        "version": 1, "name": "bed only", "type": "room", "units": "mm", "wall": 100,
        "rooms": [{"id": "room", "kind": "bedroom", "name": "방", "rect": [0, 0, 3000, 3600]}],
        "openings": [
            {"id": "d", "type": "door", "room": "room", "wall": "s",
             "offset": 200, "width": 900, "to": "outside", "swing": "in", "hinge": "end"},
        ],
        "items": [],
    }
    _ctx, got = codes(bed)
    assert "no_towel" not in got, got

    beside = house([{
        "id": "basin", "room": "bath", "category": "washbasin", "label": "세면대",
        "size": {"w": 500, "d": 450, "h": 850}, "place": {"wall": "n", "offset": 100},
        "owned": True,
    }])
    P.apply_bathroom_defaults(beside)
    bar = next(it for it in beside["items"] if P.is_towel(it))
    assert bar["place"] == {"wall": "n", "offset": 680}, bar["place"]
    assert bar["z"] == P.TOWEL_Z
    assert bar["size"] == P.TOWEL_SIZE
    assert bar.get("placeholder") is True and not (bar.get("product") or {}).get("price")
    _ctx, got = codes(beside)
    assert "no_towel" not in got and "towel_pos" not in got, got
    P.apply_bathroom_defaults(beside)
    assert sum(1 for it in beside["items"] if P.is_towel(it)) == 1

    near = house()
    P.apply_bathroom_defaults(near)
    bar = near["items"][0]
    assert bar["place"]["wall"] == "w", bar
    assert bar["place"]["offset"] == 1560, bar
    assert "제품·가격은 오늘의집" in " ".join(near["meta"]["notes"])

    h = P.shell({
        "type": "oneroom", "name": "자취방",
        "rooms": [
            {"kind": "bedroom", "w": 3200, "d": 4000},
            {"kind": "bathroom", "w": 1400, "d": 2000},
            {"kind": "entrance", "w": 1000, "d": 1200},
        ],
    })
    bars = [it for it in h["items"] if P.is_towel(it)]
    assert len(bars) == 1, bars
    bar = bars[0]
    assert bar["place"]["wall"] in "nsew" and P._num(bar["place"]["offset"])
    assert bar["z"] == P.TOWEL_Z and bar["size"]["w"] and bar["size"]["d"] and bar["size"]["h"]
    assert "price" not in bar and not (bar.get("product") or {})
    ctx, got = codes(h)
    assert "no_towel" not in got, got
    assert not any(c.startswith("towel_") for c in got), got
    errs = [i for i in ctx.issues if i["level"] == "error"]
    assert not errs, [(i["code"], i["msg"]) for i in errs]
    _ctx, rows = P.inventory_rows(h)
    labels = [P.label_of(it) for _n, it in rows[bar["room"]]]
    assert "수건걸이" in labels, labels
    html, svg = P.render(h)
    assert "수건걸이" in html and "수건걸이" in svg
    assert "설치 1,300" in html and "설치 1,300" in svg
    sym = "".join(P.furniture_symbol(bar, ctx.geo[bar["id"]]))
    assert "<line" in sym, sym
    print("ok towel")


if __name__ == "__main__":
    main()
