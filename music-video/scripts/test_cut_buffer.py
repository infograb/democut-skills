#!/usr/bin/env python3
"""버퍼 선택, 프레임 스냅, 드리프트 이월.

  python3 test_cut_buffer.py
"""
import json
import os
import subprocess
import sys
import tempfile
from fractions import Fraction

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
import mv_timing as M  # noqa: E402


def plan(cuts, **kw):
    kw.setdefault("bpm", 130)
    kw.setdefault("fps", 24)
    return M.plan_cuts(cuts, **kw)


def test_worked_example():
    """130 BPM, 2마디 = 3.692초, both, 5초 생성, 머리 약 0.65초, 24fps."""
    p = plan(["0ms..2bar both id=ex mark=0ms:downbeat"])
    c = p["cuts"][0]
    assert c["duration_s"] == 5, c["duration_s"]
    assert abs(c["used_ms"] - (48000 / 13.0)) < 0.001, c["used_ms"]
    assert abs(c["nominal_head_ms"] - (8500 / 13.0)) < 0.001, c["nominal_head_ms"]
    assert c["head_frames"] == 16, c["head_frames"]
    assert c["used_frames"] == 89, c["used_frames"]
    assert c["tail_frames"] == 15, c["tail_frames"]
    assert c["trim_start_ms"] == c["trim_in_ms"] == 667
    assert c["trim_end_ms"] == c["trim_out_ms"] == 4375
    assert c["trim_start_frame"] == 16 and c["trim_end_frame"] == 105
    assert c["song_start_ms"] == -667
    assert c["track_in_ms"] == 0 and c["track_at_ms"] == 667
    assert c["clip_volume_db"] == -40 and c["track_volume_db"] == 0 and c["bgm"] is None
    assert c["crossfade_ms"] == 500
    assert c["edit"]["trim_in_ms"] == 667 and c["edit"]["tracks"][0]["fade_in_ms"] == 500
    assert abs(c["prompt_shift_ms"] - (16000 / 24.0)) < 0.001
    assert abs(c["drift_ms"]) <= p["half_frame_ms"] + 0.01
    assert c["drift_ok"]
    assert c["marks"][0]["label"] == "downbeat"
    assert abs(c["marks"][0]["prompt_ms"] - c["prompt_shift_ms"]) < 0.01
    assert "0.00-0.67s" in c["prompt_hint"]
    assert "0.67s" in c["prompt_hint"]
    assert "do not drop the arms or settle" in c["prompt_hint"]
    used = [b for b in c["beats"] if b["place"] == "used"]
    assert used[0]["beat"] == 1
    assert abs(used[0]["prompt_s"] - 0.667) < 0.001
    for b in c["beats"]:
        expect = c["prompt_shift_ms"] + (b["song_ms"] - c["song_in_ms"])
        assert abs(b["prompt_ms"] - expect) < 0.02, (b, expect)
    assert M.picture_frames_for_ms(c["trim_out_ms"] - c["trim_in_ms"], 24) == c["used_frames"]
    # 다음 2마디는 프레임을 하나 덜 써서 누적 드리프트를 반 프레임 안에 되돌린다.
    nxt = plan(["0ms..2bar both id=a", "2bar..4bar both id=b"])["cuts"][1]
    assert nxt["used_frames"] == 88, nxt["used_frames"]
    assert nxt["trim_in_ms"] == 667 and nxt["trim_out_ms"] == 4333
    assert nxt["track_in_ms"] == 3692 and nxt["song_start_ms"] == 3025
    assert abs(nxt["drift_ms"] + 9.615) < 0.001


def test_buffer_modes_and_duration_list():
    both = plan(["0ms..2bar both"])["cuts"][0]
    head = plan(["0ms..2bar head"])["cuts"][0]
    tail = plan(["0ms..2bar tail"])["cuts"][0]
    assert both["duration_s"] == head["duration_s"] == tail["duration_s"] == 5
    assert abs(head["nominal_head_ms"] - 500) < 0.001
    assert head["head_frames"] == 12 and head["trim_in_ms"] == 500
    assert head["tail_buffer_ms"] > both["tail_buffer_ms"]
    assert tail["nominal_head_ms"] == 0 and tail["head_frames"] == 0 and tail["trim_in_ms"] == 0
    assert tail["tail_buffer_ms"] >= 500
    assert tail["song_start_ms"] == 0 and tail["track_in_ms"] == 0
    # 최소 버퍼를 채운 가장 짧은 허용 초. 목록이면 그 다음 값.
    short = plan(["0ms..2bar both"], durations="5/10")["cuts"][0]
    assert short["duration_s"] == 5
    long = plan(["0ms..4bar both"], durations="5/10")["cuts"][0]
    assert long["duration_s"] == 10, long["duration_s"]
    four = plan(["0ms..1000ms both"], durations="4-15")["cuts"][0]
    assert four["duration_s"] == 4
    try:
        plan(["0ms..20bar both"], durations="4-15")
        raise AssertionError("길이가 넘는데 통과했다")
    except M.PlanError:
        pass


def test_frame_snap_property():
    for fps in (24, 30):
        for start in range(0, 60):
            for n in range(1, 36):
                a, b = M.snap_trim_ms(start, n, fps)
                assert M.picture_frames_for_ms(b - a, fps) == n, (fps, start, n, a, b)
                assert M.nearest_int(Fraction(a) * fps / 1000) == start
                assert M.nearest_int(Fraction(b) * fps / 1000) == start + n


def test_drift_carry():
    half = 500 / 24.0
    # 1020ms 는 24.48프레임. 컷마다 반올림하면 24+24 로 반 프레임을 넘고,
    # 이월하면 둘째 컷이 25프레임을 집어 누적을 되돌린다.
    p = plan(["%dms..%dms both" % (i * 1020, (i + 1) * 1020) for i in range(7)], bpm=None)
    frames = [c["used_frames"] for c in p["cuts"]]
    assert frames[0] == 24 and frames[1] == 25, frames
    independent = 24 * 7
    carried = sum(frames)
    assert carried != independent
    for c in p["cuts"]:
        assert c["drift_ok"], c
        assert abs(c["drift_ms"]) <= half + 0.02, c["drift_ms"]
    # 프레임 경계 1ms 뒤. 길이만 올리면 컷마다 거의 한 프레임이 쌓인다.
    ceil_cuts = plan(["%dms..%dms tail" % (i * 3667, (i + 1) * 3667) for i in range(7)], bpm=None)
    for c in ceil_cuts["cuts"]:
        assert abs(c["drift_ms"]) <= half + 0.02, c["drift_ms"]
    naive = 0.0
    song = 0.0
    for i in range(7):
        song += 3667
        naive += M.picture_frames_for_ms(3667, 24) * (1000 / 24.0)
    assert naive - song > 250  # 7컷이면 약 +0.29초. 실측의 +0.27초와 같은 현상이다.
    assert abs(ceil_cuts["cuts"][-1]["drift_ms"]) < naive - song


def test_positions_offset_and_beats_file():
    a = plan(["bar:1..bar:3 both"], bpm=130)["cuts"][0]
    b = plan(["beat:1..beat:9 both"], bpm=130)["cuts"][0]
    c = plan(["0ms..2bar both"], bpm=130)["cuts"][0]
    assert a["used_ms"] == b["used_ms"] == c["used_ms"]
    shifted = plan(["beat:1..beat:5 head"], bpm=120, offset_ms=1000)["cuts"][0]
    assert shifted["song_in_ms"] == 1000, shifted["song_in_ms"]
    assert shifted["used_ms"] == 2000, shifted["used_ms"]
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "beats.txt")
        with open(path, "w", encoding="utf-8") as f:
            f.write("# ms\n0\n500\n1000\n1500\n")
        beats = M.load_beats(path)
        p = plan(["beat:1..beat:3 both id=file"], bpm=None, beats=beats, durations="4-15")
        cut = p["cuts"][0]
        assert cut["song_in_ms"] == 0 and cut["song_out_ms"] == 1000, cut
        assert cut["duration_s"] == 4
        assert p["timing"] == "beats"
    via_json = plan([{"id": "j", "in_ms": 0, "out_ms": 1000, "buffer": "head",
                      "marks": [{"at": "0ms", "label": "hit"}]}], bpm=None)
    assert via_json["cuts"][0]["used_ms"] == 1000 and via_json["cuts"][0]["duration_s"] == 4
    assert via_json["cuts"][0]["marks"][0]["prompt_ms"] == via_json["cuts"][0]["prompt_shift_ms"]
    via_beat = plan([{"in_beat": 1, "out_beat": 9, "buffer": "both"}], bpm=130)["cuts"][0]
    assert via_beat["used_ms"] == plan(["0ms..2bar both"], bpm=130)["cuts"][0]["used_ms"]


def test_cli_json():
    script = os.path.join(os.path.dirname(os.path.realpath(__file__)), "mv_timing.py")
    proc = subprocess.run(
        [sys.executable, script, "cutplan", "--bpm", "130", "--fps", "24",
         "--cut", "0ms..2bar both id=ex", "--json"],
        capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    data = json.loads(proc.stdout)
    assert data["cuts"][0]["duration_s"] == 5
    assert data["cuts"][0]["trim_in_ms"] == 667
    table = subprocess.run(
        [sys.executable, script, "buffer", "--bpm", "130", "--cut", "0ms..2bar head"],
        capture_output=True, text=True)
    assert table.returncode == 0, table.stderr
    assert "trim_in" in table.stdout and "500" in table.stdout


def main():
    test_worked_example()
    test_buffer_modes_and_duration_list()
    test_frame_snap_property()
    test_drift_carry()
    test_positions_offset_and_beats_file()
    test_cli_json()
    print("ok cut-buffer")


if __name__ == "__main__":
    main()
