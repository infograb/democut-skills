#!/usr/bin/env python3
"""motion_check: 한 프레임 멈칫, 섞인 프레임, 멈춘 구간, 따라잡는 점프를 합성 영상에서 찾는다.

  python3 test_motion_check.py
"""
import os
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
import numpy as np  # noqa: E402

import motion_check as M  # noqa: E402

W, H, N = 160, 90, 48
BLENDED = 4


def _box_x(t):
    if t < 16:
        return 4 * t
    if t < 32:
        return 60
    if t == 40:
        return _box_x(39)
    return 60 + 4 * (t - 31)


def _write(path):
    rng = np.random.default_rng(7)
    bg = rng.integers(40, 120, size=(H, W), dtype=np.uint8)
    bg = np.repeat(np.repeat(bg[::3, ::3], 3, 0), 3, 1)[:H, :W]
    raw = bytearray()

    def frame(t):
        fr = bg.copy()
        x = _box_x(t)
        fr[30:60, 10 + x:40 + x] = 235
        return fr

    for t in range(N):
        fr = frame(t)
        if t == BLENDED:
            fr = ((frame(t - 1).astype(np.uint16) + frame(t + 1)) // 2).astype(np.uint8)
        raw += fr.tobytes()
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "gray", "-s", f"{W}x{H}",
                    "-r", "24", "-i", "-", "-c:v", "ffv1", path], input=bytes(raw), check=True)


def test_stall_hold_and_jump():
    tmp = tempfile.mkdtemp()
    try:
        path = os.path.join(tmp, "box.mkv")
        _write(path)
        r = M.measure(path)
        assert r["frames"] == N, r
        assert r["duplicate_frames"] == [40], r
        assert r["blended_frames"] == [BLENDED], r
        assert r["still_frames"] == 17, r
        assert r["longest_still"] == {"frames": 16, "start_s": round(16 / 24, 2)}, r
        assert r["body_max_at_s"] == round(41 / 24, 2), r
        assert 6.0 <= r["body_px_max"] <= 10.0, r
        h = M.measure(path, hold_from=16 / 24)
        assert h["dance"] == {"frames": 15, "still_frames": 0, "still_share": 0.0,
                              "longest_still": {"frames": 0, "start_s": None}}, h["dance"]
        assert h["hold"]["from_s"] == 0.67 and h["hold"]["frames"] == 32, h["hold"]
        assert h["hold"]["still_share"] == round(17 / 32, 3), h["hold"]
    finally:
        shutil.rmtree(tmp)


if __name__ == "__main__":
    test_stall_hold_and_jump()
    print("ok")
