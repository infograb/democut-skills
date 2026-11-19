#!/usr/bin/env python3
"""DemoCut 이미지 프롬프트 한도는 8,000자다. 4,000자를 넘어도 그 안이면 줄이지 않고,
도구가 거절하면 4,000자 이하로 줄이라고 요약에 알린다.

  python3 test_prompt_limit.py
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
import shots as S  # noqa: E402


def _build(words):
    house = {"photo": {"concept": "natural", "ceiling": 2300}, "type": "room", "name": "t"}
    concept = S.concept_of(house)
    room = {"id": "cook", "kind": "kitchen", "name": "kitchen", "rect": [0, 0, 1600, 1900]}
    fin = S.room_finish(house, concept, room)
    view = dict(room=room, space="a kitchen", finish=fin, master_finish=fin, colors=())
    W, H, _, sw, _ = S.RATIOS["9:16"]
    cam = S.Cam(800, 1000, 1200, 0.0, 0.0, 2 * math.atan((sw / 2.0) / S.MAIN_LENS),
                W, H, S.MAIN_LENS, S.HORIZON["9:16"])
    thru = []

    def build():
        lines = ["1. Fridge: " + ("word " * words)] if words else ["1. Fridge: 60x60x180 cm."]
        return S.build_prompt(house, concept, "9:16", cam, "a wide shot", view, lines, [], [], [], None, [], thru)
    return view, thru, build


def test_constants_and_notes():
    assert S.PROMPT_MAX == 8000
    assert S.PROMPT_FALLBACK == 4000
    assert S.prompt_limit_notes(4000) == []
    info = S.prompt_limit_notes(4001)
    assert len(info) == 1 and info[0].startswith("ℹ"), info
    assert "8,000" in info[0] and "4,000" in info[0] and "줄여 다시 낸다" in info[0], info
    near = S.prompt_limit_notes(S.PROMPT_MAX - 100)
    assert any(x.startswith("⚠") and "가깝다" in x for x in near), near
    assert any(x.startswith("ℹ") for x in near), near
    over = S.prompt_limit_notes(S.PROMPT_MAX + 1)
    assert any(x.startswith("⚠") and "넘는다" in x and "거절된다" in x for x in over), over
    assert any(x.startswith("ℹ") for x in over), over


def test_mid_length_is_kept():
    """4,000자와 8,000자 사이는 한도 안이다. 줄이지 않는다."""
    kept = None
    for words in (600, 900, 1200):
        view, thru, build = _build(words)
        prompt, notes = S._fit_prompt("mid", build, view, thru)
        if S.PROMPT_FALLBACK < len(prompt) <= S.PROMPT_MAX and not notes and "word word" in prompt:
            kept = prompt
            break
    assert kept, "4,000자와 8,000자 사이 프롬프트를 만들지 못했다"
    assert any("4,000" in line for line in S.prompt_limit_notes(len(kept)))


def test_over_max_still_stops():
    view, thru, build = _build(S.PROMPT_MAX)
    try:
        S._fit_prompt("over", build, view, thru)
    except SystemExit as e:
        assert "8,000" in str(e) and "내지 않는다" in str(e), e
    else:
        raise SystemExit("over-limit prompt was emitted")
    print("ok prompt-limit")


if __name__ == "__main__":
    test_constants_and_notes()
    test_mid_length_is_kept()
    test_over_max_still_stops()
