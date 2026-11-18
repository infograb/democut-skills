#!/usr/bin/env python3
"""욕실 낮 컷과 저녁 컷은 수건걸이 자리 문장을 같이 쓴다.

  python3 test_towel.py
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
import shots as S  # noqa: E402


def house(light):
    return {
        "version": 1, "name": "bath towel", "type": "room", "units": "mm", "wall": 100,
        "rooms": [
            {"id": "bath", "kind": "bathroom", "name": "화장실", "rect": [0, 0, 1600, 2200]},
        ],
        "openings": [
            {"id": "d", "type": "door", "room": "bath", "wall": "s",
             "offset": 400, "width": 750, "to": "outside", "swing": "out", "hinge": "start"},
        ],
        "items": [
            {"id": "bar", "room": "bath", "category": "towel_bar", "label": "수건걸이",
             "label_en": "towel bar", "size": {"w": 600, "d": 80, "h": 40},
             "place": {"wall": "w", "offset": 400}, "z": 1300, "placeholder": True,
             "look": "a straight chrome towel bar mounted on the wall"},
        ],
        "photo": {"concept": "natural", "ratio": "9:16", "light": light},
    }


def shot(light, light_dir):
    h = house(light)
    ctx, _ = S.P.check(h)
    W, H, _, sw, _ = S.RATIOS["9:16"]
    cam = S.Cam(800, 1800, 1200, -math.pi / 2, 0.0, 2 * math.atan((sw / 2.0) / S.MAIN_LENS),
                W, H, S.MAIN_LENS, S.HORIZON["9:16"])
    sc = S.Scene(ctx, ctx.rooms["bath"], 2300)
    cv = S.see_through(sc, cam, sc.render(cam))
    text, checks, avoids = S.towel_view(ctx, cam, [ctx.rooms["bath"]])
    concept = S.concept_of(h)
    prompt = S.build_prompt(
        h, concept, "9:16", cam, "a wide shot of the bathroom",
        dict(room=ctx.rooms["bath"], space="a bathroom", finish=S.room_finish(h, concept, ctx.rooms["bath"]),
             colors=(), towel=text),
        [], [], [], [dict(role="sketch")], light_dir, list(avoids), [])
    labels = [t for _c, t in S._legend_entries(sc, cv, cv.stats(), cam)]
    return prompt, text, checks, labels, sc, ctx


def _line(prompt):
    for line in prompt.splitlines():
        if line.startswith("Towel bar:"):
            return line
    return None


def main():
    day, text, checks, labels, sc, ctx = shot(
        "soft cream-toned daylight, diffuse, no direct sun",
        "Daylight comes from the doorway, traveling toward the camera.")
    eve, text2, _checks2, labels2, _sc2, _ctx2 = shot(
        "warm early-evening indoor light from the ceiling lamp",
        "Warm evening light fills the room, soft shadows under the bar.")
    line, line2 = _line(day), _line(eve)
    assert line and line == line2 == text == text2, (line, line2, text)
    assert "the left wall" in line, line
    assert "on the left side of the frame" in line, line
    assert "mounted 130 cm above the floor" in line, line
    assert "One white towel hangs on this bar" in line, line
    assert day != eve
    assert "daylight" in day.lower() and "evening" in eve.lower()
    assert "a white towel on a wall hook" not in day and "a white towel on a wall hook" not in eve
    assert S.AVOID_TOWEL in day and S.AVOID_TOWEL in eve
    assert len(day) <= S.PROMPT_MAX and len(eve) <= S.PROMPT_MAX
    assert checks and "수건걸이" in checks[0] and "낮·저녁" in checks[0] and "house.json" in checks[0]
    assert line in labels and line in labels2, labels
    bar = next(it for it in ctx.items if it["id"] == "bar")
    boxes = sc.boxes["bar"]
    assert boxes[0][1] == bar["z"] == 1300, boxes
    assert boxes[0][2] == bar["z"] + bar["size"]["h"]
    print("ok towel-prompt", line)


if __name__ == "__main__":
    main()
