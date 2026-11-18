#!/usr/bin/env python3
"""원룸 창이 화면에 있으면 간유리와 바깥 쇠창살을 적고, 맑은 유리·선명한 밖은 Avoid 에 있다.

  python3 test_window_glass.py
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
import shots as S  # noqa: E402


def house(window):
    return {
        "version": 1, "name": "glass probe", "type": "oneroom", "units": "mm", "wall": 100,
        "rooms": [
            {"id": "room", "kind": "bedroom", "name": "room", "rect": [0, 0, 3000, 3600]},
            {"id": "entry", "kind": "entrance", "name": "entry", "rect": [3000, 2000, 1000, 1200]},
        ],
        "openings": [
            window,
            {"id": "front", "type": "door", "room": "entry", "wall": "s",
             "offset": 0, "width": 900, "to": "outside", "swing": "out", "hinge": "end"},
        ],
        "items": [
            {"id": "bed", "room": "room", "category": "bed", "label": "bed",
             "size": {"w": 1100, "d": 2000, "h": 900}, "place": {"wall": "w", "offset": 200},
             "owned": True, "look": "a low bed"},
        ],
        "photo": {"concept": "natural", "ratio": "9:16"},
    }


def view(window):
    h = house(window)
    ctx, _ = S.P.check(h)
    W, H, _, sw, _ = S.RATIOS["9:16"]
    cam = S.Cam(1500, 3000, 1200, -math.pi / 2, 0.0, 2 * math.atan((sw / 2.0) / S.MAIN_LENS),
                W, H, S.MAIN_LENS, S.HORIZON["9:16"])
    sc = S.Scene(ctx, ctx.rooms["room"], 2300)
    cv = S.see_through(sc, cam, sc.render(cam))
    _vis, lines, ops, checks, _board, avoid, _facts, _thru = S.describe(sc, cam, cv, cv.stats(), h)
    concept = S.concept_of(h)
    light, _ko = S.light_direction(sc, cam, cv.stats())
    prompt = S.build_prompt(
        h, concept, "9:16", cam, "a wide shot",
        dict(room=ctx.rooms["room"], space="a room", finish=S.room_finish(h, concept, ctx.rooms["room"]),
             colors=()), lines, ops, [], [dict(role="sketch")], light, list(avoid), [])
    return " ".join(ops), avoid, checks, prompt, sc, cam, cv


def main():
    ops, avoid, checks, prompt, sc, cam, cv = view({
        "id": "w", "type": "window", "room": "room", "wall": "n",
        "offset": "center", "width": 1200, "sill": 900,
    })
    assert S._FROSTED in ops, ops
    assert "facing the next villa" not in ops, ops
    assert S._GLASS_AVOID in avoid, avoid
    assert S._GLASS_CHECK in checks, checks
    assert S._FROSTED in prompt and S._GLASS_AVOID in prompt
    assert "Diffuse daylight comes only through the frosted glass" in prompt, prompt
    assert len(prompt) <= S.PROMPT_MAX, len(prompt)
    light, _ko = S.light_direction(sc, cam, cv.stats())
    assert light.startswith("Diffuse daylight comes only through the frosted glass"), light

    ops, avoid, checks, prompt, _sc, _cam, _cv = view({
        "id": "w", "type": "window", "room": "room", "wall": "n",
        "offset": "center", "width": 1200, "sill": 900, "glass": "clear",
    })
    assert "frosted" not in ops, ops
    assert "facing the next villa" in ops, ops
    assert S._GLASS_AVOID not in avoid, avoid
    assert S._GLASS_CHECK not in checks
    assert "Daylight comes only from the window" in prompt, prompt
    assert len(prompt) <= S.PROMPT_MAX

    ops, avoid, checks, _prompt, _sc, _cam, _cv = view({
        "id": "w", "type": "window", "room": "room", "wall": "n",
        "offset": "center", "width": 1200, "sill": 900, "bars": False,
    })
    assert S._FROSTED_PLAIN in ops and "security-bar" not in ops, ops
    assert S._GLASS_AVOID in avoid
    assert S._GLASS_CHECK_PLAIN in checks and S._GLASS_CHECK not in checks, checks
    print("ok window-glass")


if __name__ == "__main__":
    main()
