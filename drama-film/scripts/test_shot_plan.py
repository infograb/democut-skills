#!/usr/bin/env python3
"""shot_plan: 샷리스트 검사와 생성 구간 시각.

  python3 test_shot_plan.py
"""
import json
import os
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
import shot_plan as P  # noqa: E402


def _plan(shots, **extra):
    plan = {"fps": 24, "speech_rate": 5.0, "shots": shots}
    plan.update(extra)
    return plan


def _shot(sid, gen, seconds, **kw):
    shot = {"id": sid, "generation": gen, "seconds": seconds, "size": "medium", "camera": "static",
            "action": "looks up"}
    shot.update(kw)
    return shot


def test_beats_are_continuous_and_frames_follow_the_sequence():
    plan = _plan([_shot("S1", 1, 3, size="wide", lens_mm=24), _shot("S2", 1, 4.5), _shot("S3", 1, 2.5),
                  _shot("S4", 2, 5)])
    assert P.check(plan) == ([], [])
    gens = P.beats(plan)
    got = [(g["generation"], g["seconds"], g["frame_count"]) for g in gens]
    assert got == [(1, 10, 240), (2, 5, 120)], got
    rows = [(r["id"], r["label"], r["frames"], r["sequence_frames"]) for g in gens for r in g["shots"]]
    assert rows == [("S1", "0-3s", [1, 72], [1, 72]),
                    ("S2", "3-7.5s", [73, 180], [73, 180]),
                    ("S3", "7.5-10s", [181, 240], [181, 240]),
                    ("S4", "0-5s", [1, 120], [241, 360])], rows


def test_generation_must_be_whole_seconds_within_seedance_range():
    errors, _ = P.check(_plan([_shot("S1", 1, 3.5), _shot("S2", 2, 3), _shot("S3", 3, 16)]))
    assert errors == ["생성 구간 1: 합이 3.50초다. 정수 초여야 한다",
                      "생성 구간 2: 3초다. 4~15초여야 한다",
                      "생성 구간 3: 16초다. 4~15초여야 한다"], errors


def test_line_needs_room_and_a_speaker():
    line = "잠깐만, 그거 내가 어제 말한 거잖아"  # 한글 14음절 → 14/5 + 0.5 = 3.3초
    errors, _ = P.check(_plan([_shot("S1", 1, 3, speaker="민지", line=line), _shot("S2", 1, 2, line="응")]))
    assert errors == ["S1: 대사가 3.3초 걸리는데 샷은 3.0초다(대사를 줄이거나 샷을 늘린다)",
                      "S2: 대사에 speaker 가 없다"], errors


def test_two_speakers_in_one_generation_is_a_warning():
    plan = _plan([_shot("S1", 1, 3, speaker="민지", line="왔어?"), _shot("S2", 1, 3, speaker="준호", line="응.")])
    errors, warnings = P.check(plan)
    assert errors == [] and warnings == [
        "생성 구간 1: 말하는 사람이 2명이다(민지, 준호). 한 생성에 두 사람의 대사는 미확인이다"], (errors, warnings)


def test_split_generation_and_duplicate_ids_are_errors():
    errors, _ = P.check(_plan([_shot("S1", 1, 4), _shot("S2", 2, 4), _shot("S1", 1, 4)]))
    assert errors == ["샷 id S1 가 겹친다", "S1: 생성 구간 1 이 떨어져 있다(같은 구간의 샷은 이어서 적는다)"], errors


def test_cli_check_fails_with_exit_code_1():
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "shots.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(_plan([_shot("S1", 1, 3)]), f)
        res = subprocess.run([sys.executable, os.path.join(os.path.dirname(__file__), "shot_plan.py"), "check", path],
                             capture_output=True, text=True)
    assert res.returncode == 1 and "생성 구간 1: 3초다" in res.stderr, (res.returncode, res.stderr)


def test_cli_beats_json():
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "shots.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(_plan([_shot("S1", 1, 4, speaker="민지", line="왔어?")]), f)
        out = subprocess.run([sys.executable, os.path.join(os.path.dirname(__file__), "shot_plan.py"), "beats", path,
                              "--json"], capture_output=True, text=True, check=True).stdout
    row = json.loads(out)[0]["shots"][0]
    assert (row["label"], row["frames"], row["speaker"], row["line"]) == ("0-4s", [1, 96], "민지", "왔어?"), row


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print("ok", name)
