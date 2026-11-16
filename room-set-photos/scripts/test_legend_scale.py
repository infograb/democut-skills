#!/usr/bin/env python3
"""범례 글자가 겹치거나 다른 글자로 읽히지 않는지, 받침 위 물건이 치수대로인지 본다.

  python3 test_legend_scale.py
"""
import math
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
import shots as S  # noqa: E402
import test_wide_stand as T  # noqa: E402


def _ink_rows(rows):
    return [i for i, bits in enumerate(rows) if bits]


def _same(a, b):
    return a[2] == b[2] and a[3] == b[3] and list(a[4]) == list(b[4])


def check_label(text, first, other, source):
    glyphs = S.legend_glyphs(text, 22, source=source)
    alone = S.legend_glyphs(first, 22, source=source)[0]
    wrong = S.legend_glyphs(other, 22, source=source)[0]
    got = glyphs[0]
    assert got[0] == first, (source, text, got[0])
    assert _same(got, alone), (source, text, "first glyph is not the standalone letter")
    assert not _same(got, wrong), (source, text, "first glyph matches the wrong letter")
    assert _ink_rows(got[4]), (source, first)
    assert len(_ink_rows(got[4])) >= 8, (source, first, len(_ink_rows(got[4])))
    prev = -1
    for ch, x, w, h, rows in glyphs:
        assert x >= prev, (source, ch, x, prev)
        assert w > 0 and h > 0
        prev = x + w
        if ch == " ":
            continue
        assert _ink_rows(rows), (source, ch)
        # 비트는 글자 너비 안이다
        for bits in rows:
            assert bits < (1 << w)


def check_legend_text():
    sources = ["bitmap"]
    if S._legend_font(22) is not None:
        sources.append(None)
    for source in sources:
        check_label("DISH RACK", "D", "R", source)
        check_label("dish rack", "d", "r", source)
    cv = S.Canvas(40, 30)
    for i in range(cv.w * cv.h):
        cv.px[i * 3:i * 3 + 3] = bytes((11, 22, 33))
        cv.ids[i] = 0
    path = os.path.join(tempfile.mkdtemp(prefix="legend-"), "legend.png")
    before = bytes(cv.px)
    S.write_legend(cv, path, [((232, 116, 80), "dish rack"), ((48, 160, 146), "fridge")])
    # 스케치 영역은 그대로다
    w = cv.w
    # re-read is unnecessary: write_legend copies cv.px and does not mutate it
    assert bytes(cv.px) == before
    assert os.path.getsize(path) > 100


def check_counter_scale():
    h = T.house()
    ctx, _ = S.P.check(h)
    cook = S.Scene(ctx, ctx.rooms["cook"], 2300)
    rack = next(it for it in cook.items if it["id"] == "rack")
    counter = next(it for it in cook.items if it["id"] == "counter")
    z0 = min(z for _r, z, _z1 in cook.boxes["rack"])
    z1 = max(z for _r, _z0, z in cook.boxes["rack"])
    top = S.base_z(ctx, counter) + S.item_height(counter, ctx.geo["counter"])
    assert abs(z0 - top) <= 1, (z0, top)
    assert abs((z1 - z0) - S.item_height(rack, ctx.geo["rack"])) <= 1
    W, H, _, sw, _ = S.RATIOS["9:16"]
    cam = S.Cam(1140, 4780, 1200, math.radians(-127.6), 0.0,
                2 * math.atan((sw / 2.0) / S.MAIN_LENS), W, H, S.MAIN_LENS, S.HORIZON["9:16"])
    hall = S.Scene(ctx, ctx.rooms["hall"], 2300)
    cv = S.see_through(hall, cam, hall.render(cam))
    faults = S.scale_faults(hall, cam, cv, cv.stats())
    assert not faults, faults
    # 바닥에서 받침 높이까지 쌓으면 걸린다
    rect = ctx.geo["rack"]["rect"]
    cook.boxes["rack"] = [(rect, 0, top + S.item_height(rack, ctx.geo["rack"]))]
    bad = S.scale_faults(cook, cam, cook.render(cam), cook.render(cam).stats())
    assert bad, "floor-stacked countertop item should be flagged"
    assert any("윗면" in f or "상자" in f for f in bad), bad


def main():
    check_legend_text()
    check_counter_scale()
    print("ok legend-scale")


if __name__ == "__main__":
    main()
