#!/usr/bin/env python3
"""follow: 결과 영상이 참고 영상의 움직임을 몇 프레임 늦게 따랐는지 잰다.

  python3 test_follow.py
"""
import os
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
import mv_timing as M  # noqa: E402


def _flashes(path, late):
    lum = "if(gte(N,{d})*lt(mod((N-{d})*7,23),3),255,0)".format(d=late)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i",
                    "color=c=black:s=64x36:r=24:d=4,format=gray,geq=lum='%s'" % lum,
                    "-c:v", "ffv1", path], check=True)


def test_flat_signal_has_no_correlation():
    assert M._pearson([1.0, 1.0, 1.0], [0.0, 2.0, 4.0]) == 0.0


def test_late_copy():
    tmp = tempfile.mkdtemp()
    try:
        ref, late = os.path.join(tmp, "ref.mkv"), os.path.join(tmp, "late.mkv")
        _flashes(ref, 0)
        _flashes(late, 3)
        ref_e, late_e = M._motion_energy(ref), M._motion_energy(late)
        assert len(ref_e) == 96, len(ref_e)
        res = M.follow_lag(ref_e, late_e, 0, 0, 8)
        assert res["lag_frames"] == 3 and res["r"] > 0.95, res
        same = M.follow_lag(ref_e, ref_e, 0, 0, 8)
        assert same["lag_frames"] == 0 and same["r"] == 1.0, same
        assert M.follow_lag(ref_e, late_e, 0, 500, 8) == res
        past = M.follow_lag(ref_e, late_e, 200, 0, 8)
        assert (past["from_frame"], past["to_frame"], past["r"]) == (96, 96, 0.0), past
    finally:
        shutil.rmtree(tmp)


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print("ok", name)
