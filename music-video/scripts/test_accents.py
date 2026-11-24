#!/usr/bin/env python3
"""accents: 대역별 소리 시작을 반 박 격자에 놓는다.

  python3 test_accents.py
"""
import os
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
import mv_timing as M  # noqa: E402


def test_half_beat_slot():
    assert M._half_beat_slot(0.0, 120, 0.0) == (1.0, 0.0)
    slot, dev = M._half_beat_slot(0.26, 120, 0.0)
    assert slot == 1.5 and round(dev) == 10, (slot, dev)
    slot, dev = M._half_beat_slot(1.48, 120, 0.0)
    assert slot == 4.0 and round(dev) == -20, (slot, dev)
    assert M._slot_label(3.0) == "3" and M._slot_label(3.5) == "3&"


def test_onsets_need_a_rise():
    quiet, loud = -60.0, -20.0
    vals = [quiet] * 10 + [loud] * 5 + [quiet] * 10 + [-55.0] * 5
    found = M._onsets(vals, 0.01, 6.0, 0.08)
    assert [round(t, 2) for t, _ in found] == [0.1], found


def _synth(path):
    env = "min(1,{x}/0.005)*exp(-{x}/0.04)"
    kick = env.format(x="mod(t,0.5)")
    snare = env.format(x="mod(t+0.5,1.0)")
    hat = env.format(x="mod(t+0.25,0.5)")
    expr = ("0.5*sin(2*PI*60*t)*%s+0.3*sin(2*PI*2500*t)*%s+0.1*sin(2*PI*12000*t)*%s"
            "+0.003*(random(0)*2-1)" % (kick, snare, hat))
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i",
                    "aevalsrc='%s':s=48000:d=4" % expr, path], check=True)


def test_synthetic_groove():
    """120 BPM: 킥은 박마다, 스네어는 2·4·6·8박, 하이햇은 반 박마다."""
    if not shutil.which("ffmpeg"):
        print("  ffmpeg 가 없어 건너뜀")
        return
    with tempfile.TemporaryDirectory() as tmp:
        wav = os.path.join(tmp, "groove.wav")
        _synth(wav)
        res = M.accent_map(wav, 120, 0.0, 4.0)
        by_band = {"kick": [], "snare": [], "hat": []}
        for row in res["slots"]:
            for band in row["bands"]:
                by_band[band].append(row["beat"])
        assert by_band["kick"] == ["1", "2", "3", "4", "5", "6", "7", "8"], by_band
        assert by_band["snare"] == ["2", "4", "6", "8"], by_band
        assert by_band["hat"] == ["1&", "2&", "3&", "4&", "5&", "6&", "7&", "8&"], by_band
        assert abs(res["phase_ms"]) <= 10, res["phase_ms"]
        assert res["slots"][2]["frame"] == 12 and res["slots"][2]["beat"] == "2", res["slots"][2]

        late = M.accent_map(wav, 120, 0.0, 4.0, offset=-0.04)
        assert 30 <= late["phase_ms"] <= 50, late["phase_ms"]
        fixed = M.accent_map(wav, 120, 0.0, 4.0, offset=-0.04, align=True)
        assert abs(fixed["offset_s"]) <= 0.01, fixed["offset_s"]
        assert [r["beat"] for r in fixed["slots"] if "snare" in r["bands"]] == ["2", "4", "6", "8"]


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
        print("ok", t.__name__)
