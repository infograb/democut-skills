#!/usr/bin/env python3
"""lyrics: whisper 단어 시각을 컷의 반 박 격자와 프레임에 놓는다.

  python3 test_lyrics.py
"""
import json
import os
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
import mv_timing as M  # noqa: E402


def test_words_land_on_half_beats():
    words = [("Melt", 0.95, 1.20), (" down", 1.26, 1.70), ("밖", 5.0, 5.2), ("앞", 0.1, 0.4)]
    res = M.lyric_beats(words, 120, 1.0, 3.0, offset=1.0, fps=24, audio_start=0.0)
    got = [(r["word"], r["beat"], r["dev_ms"], r["beat_frame"], r["frame"]) for r in res["words"]]
    assert got == [("Melt", "1", -50, 0, -1), ("down", "1&", 10, 6, 6)], got


def test_pickup_words_before_the_cut_keep_negative_beats():
    res = M.lyric_beats([("a", 0.7, 1.1), ("b", 0.2, 1.1)], 120, 1.0, 3.0, offset=1.0, fps=24)
    got = [(r["word"], r["beat"], r["beat_frame"], r["frame"]) for r in res["words"]]
    assert got == [("a", "0&", -6, -7), ("b", "-1&", -18, -19)], got


def test_audio_start_shifts_to_song_time():
    res = M.lyric_beats([("up", 2.0, 2.3)], 120, 44.0, 48.0, offset=44.0, audio_start=43.0)
    row = res["words"][0]
    assert (row["song_s"], row["cut_s"], row["beat"], row["frame"]) == (45.0, 1.0, "3", 24), row


def _whisper_json(tmp, words):
    path = os.path.join(tmp, "w.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"segments": [{"words": words}]}, f)
    return path


def test_cli_reads_whisper_json():
    with tempfile.TemporaryDirectory() as tmp:
        path = _whisper_json(tmp, [{"word": " Squish", "start": 10.54, "end": 11.3}])
        out = subprocess.run([sys.executable, os.path.join(os.path.dirname(__file__), "mv_timing.py"), "lyrics",
                              path, "--bpm", "130", "--from", "44.508", "--to", "52.508", "--offset", "44.558",
                              "--audio-start", "40", "--json"], capture_output=True, text=True, check=True).stdout
    row = json.loads(out)["words"][0]
    assert (row["word"], row["beat"], row["beat_frame"], row["frame"]) == ("Squish", "14", 145, 145), row


def test_words_without_times_are_skipped():
    with tempfile.TemporaryDirectory() as tmp:
        path = _whisper_json(tmp, [{"word": " 2026"}, {"word": " up", "start": 2.0, "end": 2.3}])
        assert M._whisper_words(path) == [(" up", 2.0, 2.3)]


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print("ok", name)
