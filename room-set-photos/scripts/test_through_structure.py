#!/usr/bin/env python3
"""같은 문간을 반대에서 본 사진, 얕은 너머, 구조 문장을 한도로 빼지 않는지.

  python3 test_through_structure.py
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
import shots as S  # noqa: E402


def _house():
    return {
        "version": 1, "name": "through probe", "type": "oneroom", "units": "mm", "wall": 100,
        "rooms": [
            {"id": "cook", "kind": "kitchen", "name": "kitchen", "rect": [0, 0, 1600, 1900]},
            {"id": "entry", "kind": "entrance", "name": "entry", "rect": [0, 2000, 1600, 600]},
        ],
        "openings": [
            {"id": "gap", "type": "opening", "room": "cook", "wall": "s",
             "offset": 0, "width": 1600, "to": "entry"},
            {"id": "front", "type": "door", "room": "entry", "wall": "s",
             "offset": 350, "width": 900, "to": "outside", "swing": "out", "hinge": "end"},
        ],
        "items": [],
        "photo": {"concept": "natural", "ratio": "9:16"},
    }


def _cam(yaw):
    W, H, _, sw, _ = S.RATIOS["9:16"]
    return S.Cam(800, 1000, 1200, yaw, 0.0, 2 * math.atan((sw / 2.0) / S.MAIN_LENS),
                  W, H, S.MAIN_LENS, S.HORIZON["9:16"])


def test_opposite_ref():
    assert S._yaw_opposite(0.0, math.pi)
    assert S._yaw_opposite(math.radians(10), math.radians(190))
    assert S._yaw_opposite(-math.pi, 0.0)
    assert not S._yaw_opposite(0.0, math.pi / 2)
    assert not S._yaw_opposite(math.radians(10), math.radians(149))
    kitchen = dict(id="cook-wide", room="cook", yaw=math.pi / 2, through_ops=["gap"])
    entry = dict(id="entry-wide", room="cook", yaw=-math.pi / 2, through_ops=["gap"])
    specs = {s["id"]: s for s in (kitchen, entry)}
    refs, warns = S._room_photo_ref(entry, specs, {"cook": "cook-wide"}, "cook-wide", {"cook-wide"})
    assert len(refs) == 1 and refs[0]["role"] == "neighbor" and refs[0].get("opposite_view"), refs
    assert refs[0].get("same_room") is not True
    assert warns and "반대" in warns[0]
    same = dict(entry, id="later", yaw=math.pi / 2 + 0.2)
    refs, warns = S._room_photo_ref(same, {**specs, "later": same}, {"cook": "cook-wide"}, "cook-wide", {"cook-wide"})
    assert refs[0]["role"] == "master" and refs[0].get("same_room") is True, refs
    assert not warns


def test_shallow_and_wide():
    ctx, _ = S.P.check(_house())
    op = next(o for o in ctx.ops if o["id"] == "gap")
    sent = S._span_sentence(_cam(math.pi / 2), op, ctx.rooms["entry"], False)
    assert "60 cm deep" in sent, sent
    assert "shallow 60 cm-deep space, not a hallway or corridor" in sent, sent
    assert "far wall is only 60 cm past the opening" in sent, sent
    assert "corridor" not in sent.replace("not a hallway or corridor", "")
    ko = S._span_ko(_cam(math.pi / 2), op, ctx.rooms["entry"], False)
    assert "복도 아님" in ko, ko
    hall = dict(ctx.rooms["entry"], kind="hall")
    hall_sent = S._span_sentence(_cam(math.pi / 2), op, hall, False)
    assert "not a hallway or corridor" not in hall_sent, hall_sent
    assert "60 cm" in hall_sent
    sc = type("Sc", (), {})()
    sc.room = ctx.rooms["cook"]
    sc.ceil = 2300
    side = next(m["side"] for m in S.Scene(ctx, sc.room, 2300).ops.values() if m["op"]["id"] == "gap")
    opened = S._opening(sc, {"op": op, "side": side}, _cam(math.pi / 2))
    assert opened.get("wide"), opened
    assert "both side walls continue as one flat wall, same width" in opened["a"]
    assert "do not add a door frame, jambs, or a narrower doorway" in opened["a"]
    assert opened.get("avoid") == S.AVOID_JAMB


def _prompt_parts(head, lines, short, props="a folded towel"):
    house = {"photo": {"concept": "natural", "ceiling": 2300}, "type": "room", "name": "t"}
    concept = S.concept_of(house)
    room = {"id": "cook", "kind": "kitchen", "name": "kitchen", "rect": [0, 0, 1600, 1900]}
    view = dict(room=room, space="a kitchen", finish=S.room_finish(house, concept, room),
                master_finish=S.room_finish(house, concept, room), colors=())
    view["finish"] = dict(view["finish"], props=props)
    thru = [dict(head=head, lines=lines, short=short, shallow=True, full_width=True, avoids=[])]
    refs = [dict(role="master", same_room=True), dict(role="sketch")]
    cam = _cam(0.0)

    def build():
        return S.build_prompt(house, concept, "9:16", cam, "a wide shot", view, [], [], [], refs, None, [], thru)
    return view, thru, build


def test_trim_keeps_structure():
    pair = " The fridge and the shoe cabinet stand side by side against it."
    head = "Through the open wall is the entryway. It is 60 cm deep past this opening, no wider." + pair
    view, thru, build = _prompt_parts(
        head, ["2. Fridge: " + ("a white fridge " * (S.PROMPT_MAX // 8))], ["2. Fridge: 48x50x85 cm."])
    prompt, notes = S._fit_prompt("hero-fridge", build, view, thru)
    assert pair in prompt, prompt[-400:]
    assert "a white fridge a white fridge" not in prompt
    assert len(prompt) <= S.PROMPT_MAX
    assert notes
    huge = "Through the open wall." + (" word" * S.PROMPT_MAX) + pair
    view2, thru2, build2 = _prompt_parts(huge, ["2. x"], ["2. x"])
    try:
        S._fit_prompt("hero-fridge", build2, view2, thru2)
    except SystemExit as e:
        msg = str(e)
        assert "나란히" in msg and "내지 않는다" in msg, msg
    else:
        raise SystemExit("over-limit prompt was emitted")
    line, avoids = S.kitchen_line({"items": [
        {"id": "u", "room": "cook", "category": "upper_cabinet"},
        {"id": "h", "room": "cook", "category": "hood"},
        {"id": "x", "room": "bed", "category": "hood"},
    ]}, {"cook"})
    assert "upper cabinets" in line and "above the sink counter" in line, line
    assert "range hood" in line and "above the cooktop" in line, line
    assert S.AVOID_BARE_WALL in avoids and S.AVOID_NO_HOOD in avoids
    assert S.kitchen_line({"items": []}, {"cook"}) == ("", [])
    print("ok through-structure")


if __name__ == "__main__":
    test_opposite_ref()
    test_shallow_and_wide()
    test_trim_keeps_structure()
