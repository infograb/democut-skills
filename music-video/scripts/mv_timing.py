#!/usr/bin/env python3
"""music-video: 곡과 영상의 시각을 잰다. 콘티의 컷 경계를 마디에 맞추고, 비트가 들어오는 자리와
만든 영상의 장면 시각을 숫자로 확인한다.

표준 라이브러리만 쓴다(Python 3.8+). energy·tempo·sheet 는 ffmpeg 가 PATH 에 있어야 한다.

  python3 mv_timing.py grid  --bpm 130 --length 110.7 [--bars-per-row 4] [--shot-beats 4] [--offset 0] [--json]
  python3 mv_timing.py energy song.mp3 [--from 0] [--to 20] [--window-ms 50] [--jump-db 6]
  python3 mv_timing.py tempo  song.mp3 [--from 0] [--to 60] [--min 70] [--max 180]
  python3 mv_timing.py sheet  cut.mp4 out.jpg [--fps 2] [--bpm 130] [--offset 0] [--from 0] [--to 0] [--cols 6] [--width 320]

시각은 모두 초(소수) 또는 ms 정수다. 곡 시각은 곡 파일 맨 앞이 0 이다.
sheet 의 --bpm 은 칸마다 박 번호를 적는다(박 1 = --offset, 기본 0). --fps 0 이면
한 박에 칸 하나(--bpm 필수, fps = bpm / 60). 기본 --fps 2 는 그대로다.
"""
import argparse
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile


def _need_ffmpeg():
    if not shutil.which("ffmpeg"):
        sys.exit("ffmpeg 가 없다. energy·tempo·sheet 는 ffmpeg 가 있어야 한다.")


def _clock(sec):
    sign = "-" if sec < 0 else ""
    sec = abs(sec)
    m = int(sec // 60)
    return "%s%d:%04.1f" % (sign, m, sec - m * 60)


def cmd_grid(a):
    if a.bpm <= 0 or a.length <= 0:
        sys.exit("--bpm 과 --length 는 0 보다 커야 한다.")
    beat = 60.0 / a.bpm
    bar = beat * a.beats_per_bar
    row = bar * a.bars_per_row
    shot = beat * a.shot_beats if a.shot_beats > 0 else 0.0
    rows = []
    t = a.offset
    i = 1
    while t < a.length - 1e-6:
        end = min(t + row, a.length)
        shots = []
        if shot:
            k = 0
            while k * shot < end - t - 1e-6:
                shots.append(round(k * shot, 2))
                k += 1
        rows.append({
            "row": i,
            "start_ms": int(round(t * 1000)),
            "end_ms": int(round(end * 1000)),
            "start": _clock(t),
            "end": _clock(end),
            "bars": round((end - t) / bar, 2),
            "eight_counts": round((end - t) / (beat * 8), 2),
            "shot_starts_s": shots,
        })
        t += row
        i += 1
    out = {
        "bpm": a.bpm,
        "beat_ms": round(beat * 1000, 1),
        "bar_ms": round(bar * 1000, 1),
        "eight_count_ms": round(beat * 8000, 1),
        "row_ms": round(row * 1000, 1),
        "rows": rows,
    }
    if a.json:
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return
    print("박 %.1fms · 마디 %.1fms · 8카운트 %.1fms · 한 줄(%d마디) %.1fms"
          % (out["beat_ms"], out["bar_ms"], out["eight_count_ms"], a.bars_per_row, out["row_ms"]))
    if a.offset:
        print("첫 박 %.3f초부터 셈" % a.offset)
    for r in rows:
        tail = "" if abs(r["bars"] - a.bars_per_row) < 0.01 else "  (짧다: %s마디)" % r["bars"]
        print("%2d  %s~%s  song_start_ms=%-7d 길이 %dms%s"
              % (r["row"], r["start"], r["end"], r["start_ms"], r["end_ms"] - r["start_ms"], tail))
        if r["shot_starts_s"]:
            print("    컷 전환(줄 안 초, %d컷) %s"
                  % (len(r["shot_starts_s"]), " ".join("%.2f" % x for x in r["shot_starts_s"])))


def _rms_series(path, start, end, window_ms):
    """ffmpeg astats 로 window_ms 마다 RMS(dBFS)를 잰다. 소리가 없으면 -120 으로 둔다."""
    _need_ffmpeg()
    rate = 48000
    n = max(1, int(rate * window_ms / 1000))
    with tempfile.TemporaryDirectory() as tmp:
        meta = os.path.join(tmp, "rms.txt")
        cmd = ["ffmpeg", "-v", "error", "-nostdin"]
        if start:
            cmd += ["-ss", "%.3f" % start]
        if end:
            cmd += ["-t", "%.3f" % max(0.0, end - start)]
        cmd += ["-i", path, "-vn", "-ac", "1", "-af",
                "aresample=%d,asetnsamples=%d,astats=metadata=1:reset=1,"
                "ametadata=print:key=lavfi.astats.Overall.RMS_level:file=%s" % (rate, n, meta),
                "-f", "null", "-"]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            sys.exit("ffmpeg 실패: %s" % proc.stderr.strip()[-400:])
        vals = []
        with open(meta, encoding="utf-8") as f:
            for line in f:
                m = re.search(r"RMS_level=(\S+)", line)
                if not m:
                    continue
                try:
                    v = float(m.group(1))
                except ValueError:
                    v = -120.0
                if math.isinf(v) or math.isnan(v):
                    v = -120.0
                vals.append(max(v, -120.0))
    return vals


def cmd_energy(a):
    vals = _rms_series(a.path, a.start, a.end, a.window_ms)
    step = a.window_ms / 1000.0
    print("구간 %.1f~%s초, %dms 마다 RMS(dBFS) %d개" % (a.start, ("%.1f" % a.end) if a.end else "끝", a.window_ms, len(vals)))
    per_line = max(1, int(round(1000 / a.window_ms)))
    for i in range(0, len(vals), per_line):
        t = a.start + i * step
        print("%7.2f  %s" % (t, " ".join("%4d" % round(v) for v in vals[i:i + per_line])))
    look = max(1, int(round(1000 / a.window_ms)))
    jumps = []
    i = look
    while i < len(vals) - look:
        before = sum(vals[i - look:i]) / look
        after = sum(vals[i:i + look]) / look
        if after - before >= a.jump_db:
            # 1초 평균이 오른 자리 근처에서 한 창 사이에 가장 크게 오른 곳을 그 시각으로 잡는다.
            j = max(range(i, min(len(vals), i + look)), key=lambda k: vals[k] - vals[k - 1])
            jumps.append((a.start + j * step, before, after))
            i = j + look
        else:
            i += 1
    if jumps:
        print("\n1초 평균이 %.0fdB 넘게 오르는 자리(구간이 바뀌거나 비트가 크게 들어온다):" % a.jump_db)
        for t, b, f in jumps:
            print("  %s (%.3f초)  %.1f → %.1f dB" % (_clock(t), t, b, f))
    else:
        print("\n1초 평균이 %.0fdB 넘게 오르는 자리는 없다." % a.jump_db)


def cmd_tempo(a):
    window_ms = 10
    vals = _rms_series(a.path, a.start, a.end, window_ms)
    if len(vals) < 400:
        sys.exit("너무 짧다. 적어도 4초는 준다.")
    lin = [10 ** (v / 20.0) for v in vals]
    onset = [max(0.0, lin[i] - lin[i - 1]) for i in range(1, len(lin))]
    mean = sum(onset) / len(onset)
    onset = [x - mean for x in onset]
    n = len(onset)
    fps = 1000.0 / window_ms
    cache = {}

    def ac(lag):
        if lag not in cache:
            cache[lag] = sum(onset[i] * onset[i + lag] for i in range(n - lag)) / (n - lag)
        return cache[lag]

    # 박 간격의 정수배(1~8배)가 모두 박 위에 떨어지는 간격을 고른다. 한 배수만 보면 당김음 때문에
    # 박의 3/2 배 간격(130 BPM 곡이면 87 BPM)이 더 크게 나온다(실측).
    def comb(lag):
        ks = [k for k in range(1, 9) if k * lag < n // 2]
        return sum(ac(k * lag) for k in ks) / len(ks)

    lo = max(2, int(math.floor(fps * 60.0 / a.max_bpm)))
    hi = int(math.ceil(fps * 60.0 / a.min_bpm))
    scores = {lag: comb(lag) for lag in range(lo - 1, hi + 2)}
    peaks = [lag for lag in range(lo, hi + 1) if scores[lag] >= scores[lag - 1] and scores[lag] >= scores[lag + 1]]
    peaks.sort(key=lambda lag: scores[lag], reverse=True)
    print("BPM 후보(박 간격의 1~8배가 함께 맞는 순):")
    for lag in peaks[:4]:
        y0, y1, y2 = scores[lag - 1], scores[lag], scores[lag + 1]
        den = y0 - 2 * y1 + y2
        frac = 0.5 * (y0 - y2) / den if den else 0.0
        bpm = 60.0 * fps / (lag + frac)
        print("  %6.1f BPM" % bpm)
    print("어림값이다. 곡을 만든 설정이나 악보의 BPM 이 있으면 그것을 쓰고, 이 값은 대조에만 쓴다.")


def _sheet_fps(a):
    """--fps 0 이면 한 박에 칸 하나(bpm / 60). 그 외는 주어진 fps."""
    if a.fps < 0:
        sys.exit("--fps 는 0 또는 양수여야 한다.")
    if a.fps == 0:
        if a.bpm is None or a.bpm <= 0:
            sys.exit("--fps 0 은 한 박에 칸 하나이므로 --bpm 이 0 보다 커야 한다.")
        return a.bpm / 60.0
    return a.fps


def _beat_number(t, bpm, offset):
    """박 1 = offset, 박 n = offset + (n-1) * 60/bpm."""
    beat = 60.0 / bpm
    return int(math.floor((t - offset) / beat + 1e-9)) + 1


def _find_font():
    """drawtext 용 글꼴. 없으면 None."""
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
    ]
    for path in candidates:
        if os.path.isfile(path):
            return path
    return None


def _sheet_drawtext_filter(fps, width, cols, rows, start, offset, bpm, font):
    """타일 전에 각 프레임에 `1.85s  b4` 꼴을 그리는 -vf 값. 글꼴 경로는 이미 확인된 것이다."""
    escaped_font = font.replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")
    beat = 60.0 / bpm
    draw = (
        "drawtext=fontfile='%s':fontcolor=white:fontsize=16:x=6:y=6:borderw=2:bordercolor=black:"
        "text='%%{eif\\:t+%.6f\\:d}.%%{eif\\:mod(t+%.6f\\,1)*100\\:d\\:2}s  "
        "b%%{eif\\:1+floor((t+%.6f-%.6f)/%.8f)\\:d}'"
        % (escaped_font, start, start, start, offset, beat)
    )
    return "fps=%g,scale=%d:-2,%s,tile=%dx%d" % (fps, width, draw, cols, rows)


def cmd_sheet(a):
    _need_ffmpeg()
    if os.path.exists(a.out):
        sys.exit("%s 가 이미 있다. 다른 이름을 준다." % a.out)
    fps = _sheet_fps(a)
    probe = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", a.path],
                           capture_output=True, text=True)
    try:
        duration = float(probe.stdout.strip())
    except ValueError:
        sys.exit("영상 길이를 못 읽었다: %s" % probe.stderr.strip()[-200:])
    end = a.end if a.end else duration
    span = max(0.0, end - a.start)
    count = max(1, int(math.floor(span * fps + 1e-6)))
    rows = int(math.ceil(count / float(a.cols)))
    times = [a.start + i / fps for i in range(count)]
    tiled = "fps=%g,scale=%d:-2,tile=%dx%d" % (fps, a.width, a.cols, rows)
    drew_text = False
    # --bpm 이 있을 때만 칸 위에 시각·박 번호를 겹친다. 없으면 예전과 같은 격자만 만든다.
    vf = tiled
    if a.bpm and a.bpm > 0:
        font = _find_font()
        if font:
            vf = _sheet_drawtext_filter(fps, a.width, a.cols, rows, a.start, a.offset, a.bpm, font)
    def _run_vf(vf_value):
        cmd = ["ffmpeg", "-v", "error", "-nostdin", "-y", "-ss", "%.3f" % a.start, "-t", "%.3f" % span,
               "-i", a.path, "-vf", vf_value, "-frames:v", "1", a.out]
        return subprocess.run(cmd, capture_output=True, text=True)

    proc = _run_vf(vf)
    if proc.returncode != 0 and vf != tiled:
        if os.path.exists(a.out):
            os.remove(a.out)
        proc = _run_vf(tiled)
        vf = tiled
    if proc.returncode != 0:
        sys.exit("ffmpeg 실패: %s" % proc.stderr.strip()[-400:])
    drew_text = vf != tiled
    print("%s  (%d칸, %d열 x %d행, 왼쪽 위부터 가로로 읽는다)" % (a.out, count, a.cols, rows))
    if a.fps == 0:
        print("한 박에 칸 하나 (fps = %.4f, BPM %.3f)" % (fps, a.bpm))
    if a.bpm and a.bpm > 0:
        print("박 1 = %.3f초, 한 박 = %.3f초" % (a.offset, 60.0 / a.bpm))
        if not drew_text:
            print("칸 위 시각·박 번호는 그리지 못했다(drawtext 또는 글꼴 없음). 박 번호는 아래에만 적는다.")
    for i, t in enumerate(times):
        extra = ""
        if a.bpm and a.bpm > 0:
            extra = "  박 %d" % _beat_number(t, a.bpm, a.offset)
        print("  칸 %2d (행 %d, 열 %d) = %.3f초%s" % (i, i // a.cols + 1, i % a.cols + 1, t, extra))


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    g = sub.add_parser("grid", help="BPM 으로 박·마디·8카운트와 콘티 줄(컷) 경계를 계산한다")
    g.add_argument("--bpm", type=float, required=True)
    g.add_argument("--length", type=float, required=True, help="곡 길이(초)")
    g.add_argument("--beats-per-bar", type=int, default=4)
    g.add_argument("--bars-per-row", type=int, default=4, help="콘티 한 줄(컷 하나)의 마디 수")
    g.add_argument("--shot-beats", type=int, default=0,
                   help="줄 안에서 컷을 바꾸는 간격(박 수). 4 는 마디마다, 2 는 두 박마다. 0 이면 적지 않는다")
    g.add_argument("--offset", type=float, default=0.0, help="첫 박이 곡 파일의 몇 초인가")
    g.add_argument("--json", action="store_true")
    g.set_defaults(fn=cmd_grid)

    e = sub.add_parser("energy", help="곡의 음량을 짧은 창마다 재고 크게 오르는 자리를 찾는다")
    e.add_argument("path")
    e.add_argument("--from", dest="start", type=float, default=0.0)
    e.add_argument("--to", dest="end", type=float, default=0.0, help="0 이면 끝까지")
    e.add_argument("--window-ms", type=int, default=50)
    e.add_argument("--jump-db", type=float, default=6.0)
    e.set_defaults(fn=cmd_energy)

    t = sub.add_parser("tempo", help="BPM 을 어림한다(악보·생성 설정의 BPM 이 없을 때)")
    t.add_argument("path")
    t.add_argument("--from", dest="start", type=float, default=0.0)
    t.add_argument("--to", dest="end", type=float, default=60.0)
    t.add_argument("--min", dest="min_bpm", type=float, default=70.0)
    t.add_argument("--max", dest="max_bpm", type=float, default=180.0)
    t.set_defaults(fn=cmd_tempo)

    s = sub.add_parser("sheet", help="영상을 칸 격자 한 장으로 만들고 칸마다 시각을 적는다")
    s.add_argument("path")
    s.add_argument("out")
    s.add_argument("--fps", type=float, default=2.0,
                   help="초당 칸 수. 0 이면 한 박에 칸 하나(--bpm 필수, fps = bpm / 60). 기본 2")
    s.add_argument("--bpm", type=float, default=None,
                   help="있으면 칸마다 박 번호를 적는다. 박 1 = --offset")
    s.add_argument("--offset", type=float, default=0.0, help="박 1 이 되는 시각(초). 기본 0")
    s.add_argument("--from", dest="start", type=float, default=0.0)
    s.add_argument("--to", dest="end", type=float, default=0.0, help="0 이면 끝까지")
    s.add_argument("--cols", type=int, default=6)
    s.add_argument("--width", type=int, default=320)
    s.set_defaults(fn=cmd_sheet)

    a = p.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
