#!/usr/bin/env python3
"""화면에 있는 받침의 올린 품목은 한도로 줄여도 조건문과 함께 남는다.
손으로 고친 프롬프트에도 missing_stacked 가 빠진 이름을 잡는다.

  python3 test_stacked_on.py
"""
import json
import math
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
import shots as S  # noqa: E402


def _items():
    return [
        {"id": "cab", "category": "storage", "label_en": "cabinet"},
        {"id": "lamp", "category": "lamp", "label_en": "lamp", "on": "cab"},
        {"id": "book", "category": "other", "label_en": "book", "on": "cab"},
        {"id": "vase", "category": "other", "label_en": "vase", "on": "shelf"},
    ]


def test_clause_survives_brief():
    child = {"id": "lamp", "category": "lamp", "label_en": "lamp"}
    base = {"id": "cab", "category": "storage", "label_en": "cabinet"}
    full = S._on_out_of_frame(child, base, " past the right edge")
    brief = S._on_out_of_frame(child, base, " past the right edge", brief=True)
    clause = "if the cabinet top shows, the lamp stands on it"
    assert clause in full and "just out of frame past the right edge" in full, full
    assert clause in brief.lower() and "just out of frame" in brief, brief
    assert "show no more of the cabinet" not in brief
    assert S.AVOID_BARE_TOP.format("cabinet") == "a bare cabinet top"


def test_missing_stacked():
    items = _items()
    good = ("The cabinet is at the right. Its lamp stands on its top just out of frame. "
            "If the cabinet top shows, the lamp stands on it. A book lies beside the lamp.")
    assert S.missing_stacked(good, items, {"cab"}) == []
    # 화면 밖 다른 받침의 품목은 보지 않는다
    assert S.missing_stacked(good, items, {"cab", "shelf"}) == ["vase"]
    dropped = good.replace("lamp", "object").replace("book", "thing")
    miss = S.missing_stacked(dropped, items, {"cab"})
    assert miss == ["lamp", "book"], miss
    # 같은 이름이 둘이면 두 번 있어야 한다. 한 번만 적힌 글은 하나가 빠진다
    once = "If the cabinet top shows, the lamp stands on it. The book is next to it."
    twins = items + [{"id": "lamp2", "category": "lamp", "label_en": "lamp", "on": "cab"}]
    assert S.missing_stacked(once, items, {"cab"}) == []
    assert S.missing_stacked(once, twins, {"cab"}) == ["lamp"]


def test_trim_keeps_clause():
    """한도로 문간 너머 생김새·소품·레퍼런스를 줄여도 조건과 Avoid 는 남는다."""
    child = {"id": "lamp", "category": "lamp", "label_en": "lamp", "on": "cab"}
    base = {"id": "cab", "category": "storage", "label_en": "cabinet"}
    clause = S._stack_clause(child, base)
    note = S._on_out_of_frame(child, base, brief=True)
    house = {"photo": {"concept": "natural", "ceiling": 2300}, "type": "room", "name": "t"}
    concept = S.concept_of(house)
    room = {"id": "hall", "kind": "hall", "name": "hall", "rect": [0, 0, 1400, 1600]}
    fin = S.room_finish(house, concept, room)
    view = dict(room=room, space="a hall", finish=dict(fin, props="a folded towel " * 80),
                master_finish=fin, colors=())
    long = "2. Cabinet: " + "white " * 400
    short = "2. Cabinet: 80x40x90 cm." + note
    thru = [dict(head="Through the open wall is the room.", lines=[long], short=[short], avoids=[])]
    avoid = [S.AVOID_BARE_TOP.format("cabinet")]
    refs = [dict(role="master", same_room=True), dict(role="sketch")]
    W, H, _, sw, _ = S.RATIOS["9:16"]
    cam = S.Cam(700, 800, 1200, 0.0, 0.0, 2 * math.atan((sw / 2.0) / S.MAIN_LENS),
                W, H, S.MAIN_LENS, S.HORIZON["9:16"])

    def build():
        return S.build_prompt(house, concept, "9:16", cam, "a wide shot", view, ["1. Bench: 100x40x45 cm."],
                              [], [], refs, None, list(avoid), thru)

    prompt, notes = S._fit_prompt("hall-wide", build, view, thru)
    assert notes and len(prompt) <= S.PROMPT_MAX, (notes, len(prompt))
    assert clause in prompt.lower(), prompt
    assert "a bare cabinet top" in prompt
    assert S.missing_stacked(prompt, [base, child], {"cab"}) == []
    edited = prompt.replace("lamp", "object")
    assert S.missing_stacked(edited, [base, child], {"cab"}) == ["lamp"]


def test_cli_on_edited_prompt():
    items = _items()
    house = {"version": 1, "name": "stacked", "units": "mm", "items": items}
    prompt = "If the cabinet top shows, the lamp stands on it. The book is there too."
    edited = "The cabinet top is empty."
    with tempfile.TemporaryDirectory() as d:
        hp = os.path.join(d, "house.json")
        pp = os.path.join(d, "prompt.txt")
        json.dump(house, open(hp, "w", encoding="utf-8"))
        open(pp, "w", encoding="utf-8").write(prompt)
        assert S.main(["stacked", hp, "--prompt", pp, "--visible", "cab"]) == 0
        open(pp, "w", encoding="utf-8").write(edited)
        try:
            S.main(["stacked", hp, "--prompt", pp, "--visible", "cab"])
        except SystemExit as e:
            assert "lamp" in str(e) and "book" in str(e), e
        else:
            raise SystemExit("edited prompt was accepted")
        shots = {"shots": [{"id": "wide", "prompt": edited, "items": [{"id": "cab"}], "through": []}]}
        sp = os.path.join(d, "shots.json")
        json.dump(shots, open(sp, "w", encoding="utf-8"))
        try:
            S.main(["stacked", hp, "--shots", sp, "--shot", "wide"])
        except SystemExit as e:
            assert "lamp" in str(e), e
        else:
            raise SystemExit("shot prompt was accepted")


def main():
    test_clause_survives_brief()
    test_missing_stacked()
    test_trim_keeps_clause()
    test_cli_on_edited_prompt()
    print("ok stacked-on")


if __name__ == "__main__":
    main()
