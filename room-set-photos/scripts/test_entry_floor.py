#!/usr/bin/env python3
"""현관 타일 구역: 현관 전체를 벽에서 벽까지 덮고, 경계는 옆방 벽 선 한 줄이다.
현관 가구는 통째로 타일 위, 경계에 닿은 옆방 가구는 통째로 마루 위라고 글로 적고, 스케치는 타일을 바둑판으로 칠한다.
이 문장은 프롬프트 한도로 줄이지 않는다.

  python3 test_entry_floor.py
"""
import json
import math
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
import shots as S  # noqa: E402


def _house(floor=None):
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
             "offset": 650, "width": 900, "to": "outside", "swing": "out", "hinge": "end"},
        ],
        "items": [
            # 수납장은 주방 서쪽 벽 남쪽 끝 — 옆면이 개구부 선(주방 벽 선)에 닿는다. 이름은 집 모델에서 온다
            {"id": "cab", "room": "cook", "category": "storage", "label_en": "cabinet",
             "size": {"w": 500, "d": 500, "h": 1100}, "place": {"wall": "w", "offset_end": 0}, "owned": True},
            # 신발장은 현관 서쪽 벽 — 현관 깊이를 다 채운다
            {"id": "shoes", "room": "entry", "category": "shoe_cabinet", "label_en": "shoe cabinet",
             "size": {"w": 600, "d": 350, "h": 1000}, "place": {"wall": "w", "offset": 0}, "owned": True},
        ],
        "photo": {"concept": "natural", "ratio": "9:16"},
    }


def test_tile_area():
    ctx, _ = S.P.check(_house())
    assert S.tile_entry(ctx.rooms["entry"]) and not S.tile_entry(ctx.rooms["cook"])
    rects, edges = S.entry_tile(ctx, "entry")
    assert rects[0] == (0, 2000, 1600, 2600), rects
    assert (0, 1900, 1600, 2000) in rects, rects          # 문간 벽 두께 바닥도 타일
    assert len(edges) == 1 and edges[0]["room"] == "cook" and edges[0]["line"] == 1900, edges
    fr = ctx.geo["cab"]["rect"]
    sh = ctx.geo["shoes"]["rect"]
    assert fr[3] == 1900, fr                              # 옆방 가구 면 = 경계
    assert 2000 <= sh[1] and sh[3] <= 2600, sh            # 신발장은 타일 구역 안에 통째로
    assert not S.tile_entry({"kind": "entrance", "floor": False})
    assert not S.tile_entry({"kind": "entrance", "floor": "oak laminate, no step"})
    assert not S.tile_entry({"kind": "entrance", "floor": {"material": "wood"}})
    assert S.tile_entry({"kind": "entrance", "floor": "gray porcelain tile"})


def test_prompt_line():
    ctx, _ = S.P.check(_house())
    line, avoids = S.entry_floor_line(ctx, ["entry"], {"cab", "shoes"})
    assert "covering the whole entry wall to wall (about 160 x 70 cm)" in line, line
    assert "ends in one straight line at the opening, level with the entry-side face of the cabinet" in line, line
    assert "The shoe cabinet stands entirely on the tile; the tile runs past its full width and depth" in line, line
    assert "The cabinet stands entirely on the wood floor; no tile under any part of it." in line, line
    assert "not any reference photo" in line
    assert S.AVOID_TILE in avoids
    assert "tile spilling under the cabinet" in avoids, avoids
    assert "tile ending partway under the shoe cabinet" in avoids, avoids
    ko = S.entry_floor_checks(ctx, ["entry"], {"cab", "shoes"})
    assert any("통째로 타일 위" in c for c in ko) and any("통째로 마루 위" in c for c in ko), ko
    # 화면에 없는 가구는 이름을 대지 않는다
    bare, avoids2 = S.entry_floor_line(ctx, ["entry"], set())
    assert "cabinet" not in bare and "shoe cabinet" not in bare and "opening" in bare, bare
    assert avoids2 == [S.AVOID_TILE]
    # 마루가 아닌 옆방 바닥 이름
    tiled, _ = S.entry_floor_line(ctx, ["entry"], {"cab"}, {"cook": "kitchen"})
    assert "on the kitchen floor" in tiled, tiled
    # 카메라가 타일 위에 서서 타일이 화면 밖이면 「화면에 타일 없음」
    out, oav = S.entry_floor_line(ctx, ["entry"], {"cab"}, None, in_frame=False)
    assert "out of frame" in out and "draw no tile anywhere" in out, out
    assert "The cabinet stands entirely on that floor." in out, out
    assert S.AVOID_TILE_IN_FRAME in oav and "tile spilling under the cabinet" in oav, oav
    assert "If the entry floor" not in out and "covering the whole entry" not in out
    assert any("화면 밖" in c for c in S.entry_floor_checks(ctx, ["entry"], {"cab"}, False))
    # 타일이 아닌 현관은 글이 없다
    ctx2, _ = S.P.check(_house("oak laminate, no step"))
    assert S.entry_floor_line(ctx2, ["entry"], {"cab"}) == ("", [])


def _cam(x, y, yaw):
    W, H, _, sw, _ = S.RATIOS["9:16"]
    return S.Cam(x, y, 1200, yaw, math.radians(-12), 2 * math.atan((sw / 2.0) / S.MAIN_LENS),
                 W, H, S.MAIN_LENS, S.HORIZON["9:16"])


def _count(cv, colors):
    want = {bytes(c) for c in colors}
    px = cv.px
    return sum(1 for i in range(0, len(px), 3) if bytes(px[i:i + 3]) in want)


def test_sketch_tile():
    ctx, _ = S.P.check(_house())
    # 주방에서 남쪽(현관)을 본다 — 너머 현관 바닥과 문간 벽 두께 바닥이 타일 색이다
    sc = S.Scene(ctx, ctx.rooms["cook"], 2300)
    cam = _cam(1000, 800, math.pi / 2)
    cv = S.see_through(sc, cam, sc.render(cam))
    tile = _count(cv, (S.TILE, S.TILE_ALT))
    assert tile > 500, tile
    assert _count(cv, (S.TILE_ALT,)) > 50       # 바둑판 — 두 색이 다 있다
    # 주방 바닥은 타일 색이 아니다: 현관 없이 그린 주방 바닥에는 타일 색이 없다
    plain = sc.render(cam)
    assert _count(plain, (S.TILE, S.TILE_ALT)) == 0
    # 현관 안에서 그리면 바닥이 바둑판이다
    se = S.Scene(ctx, ctx.rooms["entry"], 2300)
    floor = [col for side, _pts, col in se.shell if side is None and col != S.CEIL]
    assert len(floor) == 12 and set(floor) == {S.TILE, S.TILE_ALT}, floor     # 1600x600 → 6x2 칸
    # 범례와 레퍼런스 설명에 타일이 들어간다
    assert any(c == S.TILE and "entry tile" in t for c, t in S.OPENING_LEGEND)
    # 타일이 아닌 현관은 바둑판을 그리지 않는다
    ctx3, _ = S.P.check(_house(False))
    sc3 = S.Scene(ctx3, ctx3.rooms["cook"], 2300)
    cv3 = S.see_through(sc3, cam, sc3.render(cam))
    assert _count(cv3, (S.TILE, S.TILE_ALT)) == 0


def test_never_trimmed():
    """한도를 넘겨 소품·레퍼런스·너머 생김새를 줄여도 타일 문장과 Avoid 는 남는다."""
    ctx, _ = S.P.check(_house())
    line, avoids = S.entry_floor_line(ctx, ["entry"], {"cab", "shoes"})
    house = {"photo": {"concept": "natural", "ceiling": 2300}, "type": "room", "name": "t"}
    concept = S.concept_of(house)
    room = ctx.rooms["cook"]
    fin = S.room_finish(house, concept, room)
    view = dict(room=room, space="a kitchen", finish=dict(fin, props="a folded towel " * 60),
                master_finish=fin, colors=(S.TILE,), entry_floor=line)
    thru = [dict(head="Through the open wall is the entryway.",
                 lines=["2. Shoe cabinet: " + "white " * (S.PROMPT_MAX // 3)],
                 short=["2. Shoe cabinet: 60x35x100 cm."], avoids=[])]
    refs = [dict(role="master", same_room=True), dict(role="sketch")]

    def build():
        return S.build_prompt(house, concept, "9:16", _cam(1000, 800, math.pi / 2), "a wide shot", view,
                              ["1. Cabinet: 50x50x110 cm."], [], [], refs, None, list(avoids), thru)
    prompt, notes = S._fit_prompt("entry-wide", build, view, thru)
    assert notes and len(prompt) <= S.PROMPT_MAX, (notes, len(prompt))
    assert line in prompt
    for a in avoids:
        assert a in prompt, a
    assert "checkered floor is the entry tile" in prompt or "entry tile" in prompt


def test_plan():
    """plan 이 스케치에 칠해진 타일을 보고 컷마다 글을 고른다."""
    h = _house()
    h["photo"]["shots"] = [{"id": "look-entry", "room": "cook", "x": 1000, "y": 700, "look_at": [600, 2600]},
                           {"id": "look-kitchen", "room": "entry", "x": 900, "y": 2450, "look_at": [800, 0]}]
    with tempfile.TemporaryDirectory() as out:
        S.plan(h, out)
        shots = {x["id"]: x for x in json.load(open(os.path.join(out, "shots.json")))["shots"]}
    into = shots["look-entry"]["prompt"]
    assert "The shoe cabinet stands entirely on the tile" in into, into
    assert "The cabinet stands entirely on the wood floor" in into, into
    assert "checkered slate floor = entry tile" in into, into
    assert "tile ending partway under the shoe cabinet" in into and "tile spilling under the cabinet" in into
    away = shots["look-kitchen"]["prompt"]
    assert "out of frame in this shot" in away and "draw no tile anywhere" in away, away
    assert S.AVOID_TILE_IN_FRAME in away
    assert any("통째로 타일 위" in c for c in shots["look-entry"]["checks"])


def main():
    test_tile_area()
    test_prompt_line()
    test_sketch_tile()
    test_never_trimmed()
    test_plan()
    print("ok entry-floor")


if __name__ == "__main__":
    main()
