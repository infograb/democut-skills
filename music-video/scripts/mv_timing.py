#!/usr/bin/env python3
"""music-video: 곡과 영상의 시각을 잰다. 콘티의 컷 경계를 마디에 맞추고, 비트가 들어오는 자리와
만든 영상의 장면 시각을 숫자로 확인한다.

표준 라이브러리만 쓴다(Python 3.8+). energy·accents·tempo·sheet·follow 는 ffmpeg 가 PATH 에 있어야 한다.

  python3 mv_timing.py grid  --bpm 130 --length 110.7 [--bars-per-row 4] [--shot-beats 4] [--offset 0] [--json]
  python3 mv_timing.py energy song.mp3 [--from 0] [--to 20] [--window-ms 50] [--jump-db 6]
  python3 mv_timing.py accents song.mp3 --bpm 130 --from 44.508 --to 52.508 [--offset 44.508] [--align] [--fps 24] [--json]
  python3 mv_timing.py tempo  song.mp3 [--from 0] [--to 60] [--min 70] [--max 180]
  python3 mv_timing.py sheet  cut.mp4 out.jpg [--fps 2] [--bpm 130] [--offset 0] [--from 0] [--to 0] [--cols 6] [--width 320]
  python3 mv_timing.py follow previs.mp4 result.mp4 [--from 22] [--to 0] [--max-lag 8] [--json]
  python3 mv_timing.py buffer --bpm 130 --cut "0ms..2bar both" [--fps 24] [--json]
  python3 mv_timing.py cutplan --bpm 130 --durations 5/10 --cut "0ms..2bar head" --cut "2bar..4bar tail"

시각은 모두 초(소수) 또는 ms 정수다. 곡 시각은 곡 파일 맨 앞이 0 이다.
sheet 의 --bpm 은 칸마다 박 번호를 적는다(박 1 = --offset, 기본 0). --fps 0 이면
한 박에 칸 하나(--bpm 필수, fps = bpm / 60). 기본 --fps 2 는 그대로다.

buffer 와 cutplan 은 같은 명령이다. 영상 모델은 정수 초만 만들므로, 컷마다 머리·꼬리
버퍼를 두고 그 초로 만든 뒤 DemoCut 트림을 프레임에 맞춘다. 반올림 오차는 다음 컷으로
넘겨 그림의 누적이 곡과 반 프레임 안에 있게 한다. 박 1·마디 1 은 첫 다운비트다.
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
from fractions import Fraction


def _need_ffmpeg():
    if not shutil.which("ffmpeg"):
        sys.exit("ffmpeg 가 없다. energy·accents·tempo·sheet·follow 는 ffmpeg 가 있어야 한다.")


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


def _rms_series(path, start, end, window_ms, pre=""):
    """ffmpeg astats 로 window_ms 마다 RMS(dBFS)를 잰다. 소리가 없으면 -120 으로 둔다.

    pre 는 RMS 를 재기 전에 거는 ffmpeg 필터(대역을 나눌 때)다.
    """
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
                (pre + "," if pre else "") +
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


ACCENT_BANDS = (
    ("kick", "lowpass=f=120,lowpass=f=120,lowpass=f=120"),
    ("snare", "highpass=f=1500,highpass=f=1500,lowpass=f=4000,lowpass=f=4000"),
    ("hat", "highpass=f=8000,highpass=f=8000,highpass=f=8000"),
)


def _onsets(vals, step, rise_db, min_gap_s):
    """소리가 들어온 창의 (시각, 오른 dB). 직전 30ms 의 최댓값보다 rise_db 넘게 오른 국소 최대다."""
    look = max(1, int(round(0.03 / step)))
    floor = min(vals) if vals else -120.0
    rises = []
    for i, v in enumerate(vals):
        rises.append(v - (max(vals[max(0, i - look):i]) if i else floor))
    found = []
    for i, r in enumerate(rises):
        if r < rise_db or r < max(rises[max(0, i - look):i + look + 1]):
            continue
        t = i * step
        if found and t - found[-1][0] < min_gap_s:
            continue
        found.append((t, r))
    return found


def _half_beat_slot(t, bpm, offset):
    """곡 시각 t 에 가장 가까운 반 박 자리(박 1 = offset)와 거기서 벗어난 ms."""
    pos = (t - offset) * bpm / 60.0
    half = round(pos * 2) / 2.0
    return half + 1, (pos - half) * 60000.0 / bpm


def _slot_label(slot):
    return "%d" % slot if slot == int(slot) else "%d&" % int(slot)


def accent_map(path, bpm, start, end, offset=None, fps=24.0, window_ms=10, rise_db=6.0,
               min_gap_ms=80, tolerance_ms=60, align=False):
    """대역마다 소리가 들어온 시각을 반 박 격자에 놓는다. 격자에서 tolerance_ms 넘게 벗어난 것은 따로 모은다.

    phase_ms 는 소리가 반 박 자리보다 늦은 ms 의 중앙값이다. align 이면 박 1 을 그만큼 옮겨 다시 놓는다.
    """
    offset = start if offset is None else offset
    pre_roll = min(0.1, start)
    step = window_ms / 1000.0
    heard = []
    for name, flt in ACCENT_BANDS:
        vals = _rms_series(path, start - pre_roll, end, window_ms, pre=flt)
        for t, rise in _onsets(vals, step, rise_db, min_gap_ms / 1000.0):
            song_t = start - pre_roll + t
            if song_t >= start - step / 2:
                heard.append((name, song_t, rise))
    devs = sorted(_half_beat_slot(t, bpm, offset)[1] for _, t, _ in heard)
    phase_ms = devs[len(devs) // 2] if devs else 0.0
    if align:
        offset += phase_ms / 1000.0
    slots, off_grid = {}, []
    for name, song_t, rise in heard:
        slot, dev = _half_beat_slot(song_t, bpm, offset)
        if abs(dev) > tolerance_ms:
            off_grid.append({"band": name, "song_s": round(song_t, 3), "cut_s": round(song_t - start, 3)})
            continue
        row = slots.setdefault(slot, {})
        if rise > row.get(name, (0, 0))[0]:
            row[name] = (round(rise, 1), round(dev))
    rows = []
    for slot in sorted(slots):
        song_t = offset + (slot - 1) * 60.0 / bpm
        rows.append({
            "beat": _slot_label(slot),
            "song_s": round(song_t, 3),
            "cut_s": round(song_t - start, 3),
            "frame": int(round((song_t - start) * fps)),
            "bands": {k: {"rise_db": v[0], "dev_ms": v[1]} for k, v in slots[slot].items()},
        })
    return {"bpm": bpm, "start_s": start, "end_s": end, "offset_s": round(offset, 4), "fps": fps,
            "phase_ms": round(phase_ms), "aligned": bool(align), "slots": rows, "off_grid": off_grid}


def cmd_accents(a):
    end = a.end
    if not end:
        sys.exit("--to 가 필요하다(컷이 끝나는 곡 시각).")
    res = accent_map(a.path, a.bpm, a.start, end, offset=a.offset, fps=a.fps, window_ms=a.window_ms,
                     rise_db=a.rise_db, tolerance_ms=a.tolerance_ms, align=a.align)
    if a.json:
        print(json.dumps(res, ensure_ascii=False, indent=1))
        return
    print("곡 %.3f~%.3f초, %g BPM, 박 1 = %.3f초%s. 숫자는 그 대역이 직전보다 오른 dB(클수록 센 강세)."
          % (a.start, end, a.bpm, res["offset_s"], " (--align 으로 옮김)" if res["aligned"] else ""))
    if abs(res["phase_ms"]) >= 20 and not res["aligned"]:
        print("소리가 반 박 자리보다 가운데값 %+dms 어긋난다. 박 1 이 %.3f초일 수 있다. --align 으로 옮겨 다시 본다."
              % (res["phase_ms"], res["offset_s"] + res["phase_ms"] / 1000.0))
    print("%-5s %8s %7s %5s  %6s %6s %6s" % ("박", "곡 시각", "컷 시각", "프레임", "kick", "snare", "hat"))
    for r in res["slots"]:
        cells = ["%6s" % (("%.0f" % r["bands"][b]["rise_db"]) if b in r["bands"] else "-") for b, _ in ACCENT_BANDS]
        print("%-5s %8.3f %7.3f %5d  %s" % (r["beat"], r["song_s"], r["cut_s"], r["frame"], " ".join(cells)))
    both = [r["beat"] for r in res["slots"] if "kick" in r["bands"] and "snare" in r["bands"]]
    halves = [r["beat"] for r in res["slots"] if r["beat"].endswith("&")]
    n_beats = int(math.floor((end - res["offset_s"]) * a.bpm / 60.0 + 1e-9))
    heard = {r["beat"] for r in res["slots"]}
    silent = ["%d" % b for b in range(1, n_beats + 1) if "%d" % b not in heard]
    print("\n킥과 스네어가 같이 오는 박(크게 찍는 히트 후보): %s" % (", ".join(both) or "없음"))
    print("반 박에 소리가 있는 자리(잘게 쪼갠 팝·탭 후보): %s" % (", ".join(halves) or "없음"))
    print("어느 대역도 들어오지 않는 박(멈춤·흐름 후보): %s" % (", ".join(silent) or "없음"))
    if res["off_grid"]:
        print("반 박 격자에서 %dms 넘게 벗어난 소리 %d개(16분음표 이하의 잔리듬일 수 있다): %s"
              % (a.tolerance_ms, len(res["off_grid"]),
                 ", ".join("%s %.3f" % (o["band"], o["cut_s"]) for o in res["off_grid"][:12])))


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


# --- buffer / cutplan -------------------------------------------------------
# 영상 모델은 정수 초만 굽는다. 마디로 자른 구간은 그 초에 떨어지지 않으므로
# 컷마다 버퍼를 두고 더 길게 만든 뒤, 쓰는 구간만 프레임 경계로 남긴다.
MOTION_W, MOTION_H = 64, 36


def _motion_energy(path):
    """프레임마다 바로 앞 프레임과의 평균 밝기 차(0~255). 첫 프레임은 0."""
    _need_ffmpeg()
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-vf",
                          "scale=%d:%d,format=gray" % (MOTION_W, MOTION_H), "-f", "rawvideo", "-"],
                         capture_output=True, check=True).stdout
    size = MOTION_W * MOTION_H
    frames = [raw[i:i + size] for i in range(0, len(raw) - size + 1, size)]
    return [0.0] + [sum(abs(x - y) for x, y in zip(frames[i], frames[i - 1])) / size
                    for i in range(1, len(frames))]


def _pearson(xs, ys):
    if not xs:
        return 0.0
    mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
    sx = math.sqrt(sum((x - mx) ** 2 for x in xs))
    sy = math.sqrt(sum((y - my) ** 2 for y in ys))
    if not sx or not sy:
        return 0.0
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / (sx * sy)


def follow_lag(ref_energy, out_energy, start=0, end=0, max_lag=8):
    """결과가 참고 영상보다 몇 프레임 늦게 움직이는지(lag)와 그때의 상관 r."""
    end = min(end or len(ref_energy), len(ref_energy), len(out_energy))
    start = min(max(start, 0), end)
    scores = {}
    for lag in range(-max_lag, max_lag + 1):
        idx = [i for i in range(start, end) if 0 <= i + lag < len(out_energy)]
        scores[lag] = _pearson([ref_energy[i] for i in idx], [out_energy[i + lag] for i in idx])
    best = max(scores, key=lambda k: (scores[k], -abs(k)))
    return {"from_frame": start, "to_frame": end, "lag_frames": best,
            "r": round(scores[best], 2), "r_at_0": round(scores[0], 2)}


def cmd_follow(a):
    res = follow_lag(_motion_energy(a.reference), _motion_energy(a.result), a.start, a.end, a.max_lag)
    if res["to_frame"] - res["from_frame"] < 2:
        sys.exit("비교할 프레임이 없다(%d~%d). --from·--to 를 영상 길이 안으로 준다." % (res["from_frame"], res["to_frame"]))
    if a.json:
        print(json.dumps(res, ensure_ascii=False))
        return
    print("프레임 %d~%d: 결과가 참고 영상보다 %+d 프레임 늦게 움직인다(r=%.2f, 시차 0 의 r=%.2f)."
          % (res["from_frame"], res["to_frame"], res["lag_frames"], res["r"], res["r_at_0"]))
    if res["r"] < 0.5:
        print("r 이 0.5 아래다. 결과가 참고 영상의 움직임을 따르지 않았을 수 있다. 격자로 같은 프레임을 맞대어 본다.")


# DemoCut 은 그림 길이를 프레임으로 올리고 소리는 ms 그대로 둔다. 컷마다 올리면
# 오차가 쌓이므로, 여기서는 누적 그림이 곡의 합에 가장 가까운 프레임 수를 고른다.

DEFAULT_MIN_BUFFER_MS = 500
DEFAULT_FPS = 24
DEFAULT_DURATIONS = "4-15"  # Seedance 2.5
CROSSFADE_MS = 500
CLIP_VOLUME_DB = -40
TRACK_VOLUME_DB = 0


class PlanError(Exception):
    pass


def as_fraction(x):
    if isinstance(x, Fraction):
        return x
    if isinstance(x, bool) or not isinstance(x, (int, float, str)):
        raise PlanError("숫자가 아니다: %r" % (x,))
    if isinstance(x, float):
        return Fraction(str(x))
    return Fraction(x)


def nearest_int(x):
    """양수에서 0.5 는 위로. 프레임 수에 은행가 반올림을 쓰지 않는다."""
    x = as_fraction(x)
    if x >= 0:
        return int(x + Fraction(1, 2))
    return -int((-x) + Fraction(1, 2))


def num(x, places=3):
    """JSON 에 넣을 수. 정수로 떨어지면 int."""
    f = float(x)
    r = round(f, places)
    if abs(r - round(r)) < 1e-9:
        return int(round(r))
    return r


def parse_durations(spec):
    """'4-15' 는 그 범위의 정수 초, '5/10'·'5,10' 은 그 목록만."""
    if isinstance(spec, (list, tuple)):
        try:
            vals = [int(x) for x in spec]
        except (TypeError, ValueError):
            raise PlanError("생성 길이는 정수 초다: %r" % (spec,))
    else:
        text = str(spec).strip()
        m = re.fullmatch(r"(\d+)\s*-\s*(\d+)", text)
        if m:
            lo, hi = int(m.group(1)), int(m.group(2))
            if hi < lo or lo <= 0:
                raise PlanError("생성 길이 범위가 잘못되었다: %s" % text)
            vals = list(range(lo, hi + 1))
        else:
            parts = [p for p in re.split(r"[\s,/;]+", text) if p]
            if not parts:
                raise PlanError("생성 길이가 비었다.")
            try:
                vals = [int(p) for p in parts]
            except ValueError:
                raise PlanError("생성 길이는 정수 초다: %s" % text)
    vals = sorted(set(vals))
    if not vals or any(v <= 0 for v in vals):
        raise PlanError("생성 길이는 1초 이상의 정수여야 한다.")
    return vals


def picture_frames_for_ms(duration_ms, fps):
    """DemoCut 이 그림 길이를 프레임으로 올릴 때의 프레임 수. 딱 맞으면 그 프레임."""
    if duration_ms <= 0:
        return 0
    x = Fraction(int(duration_ms)) * as_fraction(fps) / 1000
    if x.denominator == 1:
        return int(x)
    return int(x) + 1


def _ms_on_frame(frame, fps):
    """그 프레임으로 반올림되는 정수 ms 가운데, 프레임 시각에 가장 가까운 것."""
    fps_f = as_fraction(fps)
    exact = Fraction(int(frame)) * 1000 / fps_f
    guess = nearest_int(exact)
    best = None
    for delta in (0, -1, 1, -2, 2, -3, 3):
        ms = guess + delta
        if ms < 0:
            continue
        if nearest_int(Fraction(ms) * fps_f / 1000) != frame:
            continue
        err = abs(Fraction(ms) - exact)
        if best is None or err < best[0]:
            best = (err, ms)
    if best is None:
        raise PlanError("프레임 %d 에 맞는 ms 가 없다." % frame)
    return best[1]


def snap_trim_ms(start_frame, n_frames, fps):
    """트림 시작·끝(정수 ms).

    시작과 끝은 그 프레임으로 반올림되고, (끝-시작) 을 프레임으로 올리면
    n_frames 가 된다. DemoCut 이 그림만 프레임으로 올리는 길이와 같다.
    """
    if n_frames < 1 or start_frame < 0:
        raise PlanError("프레임 창이 잘못되었다.")
    fps_f = as_fraction(fps)
    end_frame = int(start_frame) + int(n_frames)
    start_ms = _ms_on_frame(start_frame, fps)
    exact_end = Fraction(end_frame) * 1000 / fps_f
    guess = nearest_int(exact_end)
    candidates = []
    for delta in range(-4, 5):
        end_ms = guess + delta
        if end_ms <= start_ms:
            continue
        if nearest_int(Fraction(end_ms) * fps_f / 1000) != end_frame:
            continue
        if picture_frames_for_ms(end_ms - start_ms, fps) != n_frames:
            continue
        candidates.append((abs(Fraction(end_ms) - exact_end), end_ms))
    if not candidates:
        raise PlanError("트림을 프레임에 맞추지 못했다 (%d+%d, fps %s)." % (start_frame, n_frames, fps))
    candidates.sort()
    return start_ms, candidates[0][1]


def _frames_at_least(ms, fps):
    ms = as_fraction(ms)
    if ms <= 0:
        return 0
    x = ms * as_fraction(fps) / 1000
    if x.denominator == 1:
        return int(x)
    return int(x) + 1


def _duration_frames(duration_s, fps):
    x = as_fraction(duration_s) * as_fraction(fps)
    if x.denominator == 1:
        return int(x)
    return nearest_int(x)


class _Ctx(object):
    def __init__(self, bpm, offset_ms, beats, beats_per_bar):
        self.bpm = None if bpm is None else as_fraction(bpm)
        if self.bpm is not None and self.bpm <= 0:
            raise PlanError("--bpm 은 0보다 커야 한다.")
        self.offset_ms = as_fraction(0 if offset_ms is None else offset_ms)
        self.beats = None
        if beats:
            self.beats = [as_fraction(b) for b in beats]
            if any(self.beats[i] > self.beats[i + 1] for i in range(len(self.beats) - 1)):
                raise PlanError("박 파일은 시간이 오르는 순이어야 한다.")
        self.beats_per_bar = int(beats_per_bar)
        if self.beats_per_bar < 1:
            raise PlanError("--beats-per-bar 는 1 이상이어야 한다.")


def _beat_whole(index, ctx):
    index = int(index)
    if index < 0:
        raise PlanError("박 위치가 첫 다운비트보다 앞이다.")
    if ctx.beats is not None:
        n = len(ctx.beats)
        if index < n:
            return ctx.beats[index]
        if n >= 2:
            step = ctx.beats[-1] - ctx.beats[-2]
            if step <= 0:
                raise PlanError("박 파일의 마지막 간격이 0이다.")
            return ctx.beats[-1] + step * (index - (n - 1))
        if ctx.bpm is not None:
            return ctx.beats[0] + Fraction(index) * (Fraction(60000) / ctx.bpm)
        raise PlanError("박 파일이 %d박까지 없다. --bpm 을 주거나 박을 더 적는다." % (index + 1))
    if ctx.bpm is None:
        raise PlanError("박·마디 위치에는 --bpm 또는 --beats 가 필요하다.")
    return ctx.offset_ms + Fraction(index) * (Fraction(60000) / ctx.bpm)


def time_of_beat_index(index, ctx):
    """index 0 은 첫 다운비트. 소수는 이웃 박 사이를 나눈다."""
    index = as_fraction(index)
    if index < 0:
        raise PlanError("박 위치가 첫 다운비트보다 앞이다.")
    whole = int(index)
    frac = index - whole
    t0 = _beat_whole(whole, ctx)
    if frac == 0:
        return t0
    t1 = _beat_whole(whole + 1, ctx)
    return t0 + (t1 - t0) * frac


def parse_position(text, ctx):
    """곡 파일 ms. 숫자·Nms 는 파일 시각, Nbar·Nbeat 는 첫 다운비트에서의 거리,
    bar:N·beat:N 은 grid 와 같은 1부터의 번호다."""
    if isinstance(text, bool):
        raise PlanError("위치가 아니다.")
    if isinstance(text, (int, float, Fraction)):
        return as_fraction(text)
    s = str(text).strip()
    m = re.fullmatch(r"(-?\d+(?:\.\d+)?)ms", s)
    if m:
        return as_fraction(m.group(1))
    m = re.fullmatch(r"(-?\d+(?:\.\d+)?)s", s)
    if m:
        return as_fraction(m.group(1)) * 1000
    m = re.fullmatch(r"(\d+(?:\.\d+)?)bars?", s)
    if m:
        return time_of_beat_index(as_fraction(m.group(1)) * ctx.beats_per_bar, ctx)
    m = re.fullmatch(r"(\d+(?:\.\d+)?)beats?", s)
    if m:
        return time_of_beat_index(as_fraction(m.group(1)), ctx)
    m = re.fullmatch(r"bar:(\d+(?:\.\d+)?)", s)
    if m:
        n = as_fraction(m.group(1))
        if n < 1:
            raise PlanError("마디 번호는 1부터다: %s" % s)
        return time_of_beat_index((n - 1) * ctx.beats_per_bar, ctx)
    m = re.fullmatch(r"beat:(\d+(?:\.\d+)?)", s)
    if m:
        n = as_fraction(m.group(1))
        if n < 1:
            raise PlanError("박 번호는 1부터다: %s" % s)
        return time_of_beat_index(n - 1, ctx)
    raise PlanError("위치를 못 읽는다(0ms, 3.692s, 2bar, 8beat, bar:1, beat:1): %s" % s)


_POS_PREFIX = re.compile(
    r"^("
    r"-?\d+(?:\.\d+)?ms|"
    r"-?\d+(?:\.\d+)?s|"
    r"\d+(?:\.\d+)?bars?|"
    r"\d+(?:\.\d+)?beats?|"
    r"bar:\d+(?:\.\d+)?|"
    r"beat:\d+(?:\.\d+)?"
    r")"
)


def _split_mark(value):
    m = _POS_PREFIX.match(str(value).strip())
    if not m:
        raise PlanError("표시 시각을 못 읽는다: %s" % value)
    pos = m.group(1)
    rest = str(value).strip()[m.end():]
    if not rest:
        return pos, ""
    if not rest.startswith(":"):
        raise PlanError("표시는 위치:이름 이다: %s" % value)
    return pos, rest[1:]


def _parse_cut_token(text):
    text = text.strip()
    if not text or text.startswith("#"):
        return None
    parts = text.split()
    if ".." not in parts[0]:
        raise PlanError("컷 형식은 0ms..2bar both 이다: %s" % text)
    inn, out = parts[0].split("..", 1)
    if not inn or not out:
        raise PlanError("컷의 시작과 끝이 없다: %s" % text)
    cut = {"in": inn, "out": out, "marks": []}
    i = 1
    if i < len(parts) and parts[i] in ("head", "tail", "both"):
        cut["buffer"] = parts[i]
        i += 1
    for p in parts[i:]:
        if "=" not in p:
            raise PlanError("알 수 없는 컷 옵션: %s" % p)
        k, v = p.split("=", 1)
        if k == "id":
            cut["id"] = v
        elif k in ("min", "min-buffer-ms", "min_buffer_ms"):
            cut["min_buffer_ms"] = v
        elif k in ("mark", "at"):
            pos, label = _split_mark(v)
            cut["marks"].append({"at": pos, "label": label})
        elif k == "buffer":
            if v not in ("head", "tail", "both"):
                raise PlanError("버퍼는 head, tail, both 중 하나다: %s" % v)
            cut["buffer"] = v
        else:
            raise PlanError("알 수 없는 컷 옵션: %s" % k)
    return cut


def _as_end(value):
    if isinstance(value, str) or isinstance(value, (int, float, Fraction)):
        return value
    raise PlanError("컷의 시작·끝이 아니다: %r" % (value,))


def _cut_ends(raw):
    if "in" in raw and "out" in raw:
        return _as_end(raw["in"]), _as_end(raw["out"])
    if "in_ms" in raw and "out_ms" in raw:
        return _as_end(raw["in_ms"]), _as_end(raw["out_ms"])
    if "in_beat" in raw and "out_beat" in raw:
        return "beat:%s" % raw["in_beat"], "beat:%s" % raw["out_beat"]
    if "in_bar" in raw and "out_bar" in raw:
        return "bar:%s" % raw["in_bar"], "bar:%s" % raw["out_bar"]
    raise PlanError("컷에 in/out (또는 in_ms/out_ms, in_beat/out_beat, in_bar/out_bar) 이 없다.")


def _normalize_marks(raw_marks):
    marks = []
    for m in raw_marks or []:
        if isinstance(m, str):
            pos, label = _split_mark(m)
            marks.append({"at": pos, "label": label})
        elif isinstance(m, dict):
            at = m.get("at", m.get("song"))
            if at is None:
                raise PlanError("mark 에 at 이 없다.")
            marks.append({"at": at, "label": m.get("label") or ""})
        else:
            raise PlanError("mark 형식이 아니다.")
    return marks


def _normalize_cut(raw, index, default_buffer, default_min):
    if isinstance(raw, str):
        raw = _parse_cut_token(raw)
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise PlanError("컷은 문자열이나 객체여야 한다.")
    inn, out = _cut_ends(raw)
    buf = raw.get("buffer") or raw.get("mode") or default_buffer
    if buf not in ("head", "tail", "both"):
        raise PlanError("버퍼는 head, tail, both 중 하나다: %s" % buf)
    if "min_buffer_ms" in raw:
        min_b = raw["min_buffer_ms"]
    elif "min" in raw:
        min_b = raw["min"]
    else:
        min_b = default_min
    min_b = as_fraction(min_b)
    if min_b < 0:
        raise PlanError("최소 버퍼는 0 이상이어야 한다.")
    return {
        "id": str(raw["id"]) if raw.get("id") not in (None, "") else str(index + 1),
        "in": inn,
        "out": out,
        "buffer": buf,
        "min_buffer_ms": min_b,
        "marks": _normalize_marks(raw.get("marks")),
    }


def load_beats(path):
    """한 줄에 박 하나. 정수와 JSON 숫자는 ms, 소수(점이 있음)와 Ns 는 초."""
    with open(path, encoding="utf-8") as f:
        text = f.read()
    stripped = text.lstrip()
    if not stripped:
        raise PlanError("박 파일이 비었다.")
    if stripped.startswith("["):
        data = json.loads(text)
        if not isinstance(data, list) or not data:
            raise PlanError("박 파일은 비어 있지 않은 배열이어야 한다.")
        return [_beat_value(x, from_json=True) for x in data]
    beats = []
    for line in text.splitlines():
        body = line.split("#", 1)[0].strip()
        if body:
            beats.append(_beat_value(body, from_json=False))
    if not beats:
        raise PlanError("박 파일이 비었다.")
    return beats


def _beat_value(x, from_json):
    if isinstance(x, bool):
        raise PlanError("박 시각이 아니다.")
    if isinstance(x, (int, float)):
        return float(x) if from_json else float(x)
    s = str(x).strip()
    if s.endswith("ms"):
        return float(s[:-2])
    if s.endswith("s"):
        return float(s[:-1]) * 1000.0
    if not from_json and "." in s:
        return float(s) * 1000.0
    return float(s)


def load_cuts_file(path):
    """JSON 객체(cuts 배열)이거나, 한 줄에 컷 하나인 텍스트."""
    with open(path, encoding="utf-8") as f:
        text = f.read()
    stripped = text.lstrip()
    if not stripped:
        raise PlanError("컷 파일이 비었다.")
    if stripped.startswith("{") or stripped.startswith("["):
        data = json.loads(text)
        if isinstance(data, list):
            return {}, data
        if not isinstance(data, dict):
            raise PlanError("컷 파일은 객체나 배열이어야 한다.")
        if "cuts" not in data:
            raise PlanError("컷 파일에 cuts 가 없다.")
        meta = dict(data)
        cuts = meta.pop("cuts")
        return meta, cuts
    cuts = []
    for line in text.splitlines():
        body = line.split("#", 1)[0].strip()
        if not body:
            continue
        parsed = _parse_cut_token(body)
        if parsed:
            cuts.append(parsed)
    return {}, cuts


def _select_duration(used, mode, min_buf, allowed, fps, n_frames):
    need_head = min_buf if mode in ("head", "both") else Fraction(0)
    need_tail = min_buf if mode in ("tail", "both") else Fraction(0)
    need = used + need_head + need_tail
    min_head_f = _frames_at_least(need_head, fps)
    min_tail_f = _frames_at_least(need_tail, fps)
    for dur in allowed:
        if Fraction(dur) * 1000 < need:
            continue
        dframes = _duration_frames(dur, fps)
        if dframes >= min_head_f + n_frames + min_tail_f:
            return dur, dframes, need_head, need_tail, need
    return None


def _beats_in_clip(song_in, song_out, head_ms, duration_ms, ctx):
    if ctx.bpm is None and not ctx.beats:
        return []
    beats = []
    if ctx.beats is not None:
        # 파일 간격은 고르지 않을 수 있다. 앞에서부터 본다.
        start_idx = 0
    elif ctx.bpm is not None:
        beat = Fraction(60000) / ctx.bpm
        t_lo = song_in - head_ms
        start_idx = int((t_lo - ctx.offset_ms) / beat) - 1
        if start_idx < 0:
            start_idx = 0
    else:
        start_idx = 0
    idx = start_idx
    for _ in range(10000):
        try:
            t = time_of_beat_index(idx, ctx)
        except PlanError:
            break
        prompt = head_ms + (t - song_in)
        if prompt > duration_ms + Fraction(1, 10):
            break
        if prompt >= Fraction(-1, 10):
            if t < song_in - Fraction(1, 100):
                place = "head"
            elif t <= song_out + Fraction(1, 100):
                place = "used"
            else:
                place = "tail"
            beats.append({
                "beat": idx + 1,
                "bar": idx // ctx.beats_per_bar + 1,
                "beat_in_bar": (idx % ctx.beats_per_bar) + 1,
                "song_ms": num(t),
                "prompt_ms": num(prompt),
                "prompt_s": round(float(prompt) / 1000.0, 3),
                "place": place,
            })
        idx += 1
    return beats


def _prompt_hint(head_ms, tail_ms, used_end_ms, duration_ms, marks):
    head_s = float(head_ms) / 1000.0
    tail_s = float(tail_ms) / 1000.0
    used_end_s = float(used_end_ms) / 1000.0
    gen_s = float(duration_ms) / 1000.0
    parts = []
    if head_s > 0.0005:
        parts.append(
            "0.00-%.2fs: already in motion, neutral pre-roll continuing into the first beat, no walk-in."
            % head_s
        )
        parts.append("First downbeat hit at %.2fs." % head_s)
    else:
        parts.append("First downbeat hit at 0.00s. Start already on the beat, no walk-in.")
    if marks:
        bits = []
        for m in marks:
            label = m["label"] or "action"
            bits.append("%s at %.2fs" % (label, m["prompt_ms"] / 1000.0))
        parts.append("Actions shifted by the head buffer: %s." % ", ".join(bits))
    if tail_s > 0.0005:
        parts.append(
            "%.2f-%.2fs: keep the choreography moving on the beat past the used end; do not drop the arms or settle."
            % (used_end_s, gen_s)
        )
    return " ".join(parts)


def _plan_one(raw, ctx, allowed, fps, cum_song, cum_frames):
    song_in = parse_position(raw["in"], ctx)
    song_out = parse_position(raw["out"], ctx)
    if song_in < 0 or song_out < 0:
        raise PlanError("컷 %s: 곡 시각이 0보다 앞이다." % raw["id"])
    if song_out <= song_in:
        raise PlanError("컷 %s: 끝이 시작보다 뒤여야 한다." % raw["id"])
    used = song_out - song_in
    mode = raw["buffer"]
    min_buf = raw["min_buffer_ms"]
    cum_song_next = cum_song + used
    target = cum_song_next * as_fraction(fps) / 1000
    desired = nearest_int(target)
    n = desired - cum_frames
    clamped = n < 1
    if n < 1:
        n = 1
    picked = _select_duration(used, mode, min_buf, allowed, fps, n)
    if picked is None and clamped:
        raise PlanError("컷 %s: 쓰는 구간이 한 프레임보다 짧다." % raw["id"])
    if picked is None:
        raise PlanError(
            "컷 %s: 쓰는 길이 %.0fms 에 버퍼를 더하면 허용 생성 길이(%s)에 안 들어간다. 컷을 나누거나 --durations 를 늘린다."
            % (raw["id"], float(used), "/".join(str(d) for d in allowed))
        )
    dur_s, dframes, need_head, need_tail, need = picked
    if mode == "head":
        nominal_head = need_head
    elif mode == "tail":
        nominal_head = Fraction(0)
    else:
        nominal_head = (Fraction(dur_s) * 1000 - used) / 2
    min_head_f = _frames_at_least(need_head, fps)
    min_tail_f = _frames_at_least(need_tail, fps)
    lo = min_head_f
    hi = dframes - n - min_tail_f
    if lo > hi:
        raise PlanError("컷 %s: 프레임으로 맞춘 창이 생성 길이에 안 들어간다." % raw["id"])
    ideal = nearest_int(nominal_head * as_fraction(fps) / 1000)
    if ideal < lo:
        start = lo
    elif ideal > hi:
        start = hi
    else:
        start = ideal
    end_frame = start + n
    duration_ms = int(dur_s) * 1000
    trim_start_ms, trim_end_ms = snap_trim_ms(start, n, fps)
    if trim_end_ms > duration_ms:
        # 끝 ms 가 생성 길이를 넘으면 창을 한 프레임 앞으로 당긴다.
        if start <= lo:
            raise PlanError("컷 %s: 트림이 생성 길이를 넘는다." % raw["id"])
        start -= 1
        end_frame = start + n
        trim_start_ms, trim_end_ms = snap_trim_ms(start, n, fps)
        if trim_end_ms > duration_ms or trim_start_ms < 0:
            raise PlanError("컷 %s: 트림이 생성 길이를 넘는다." % raw["id"])
    head_ms = Fraction(start) * 1000 / as_fraction(fps)
    picture_ms = Fraction(n) * 1000 / as_fraction(fps)
    tail_frames = dframes - end_frame
    tail_ms = Fraction(tail_frames) * 1000 / as_fraction(fps)
    cum_frames_next = cum_frames + n
    cum_picture = Fraction(cum_frames_next) * 1000 / as_fraction(fps)
    drift = cum_picture - cum_song_next
    half = Fraction(500) / as_fraction(fps)
    drift_ok = abs(drift) <= half + Fraction(1, 1000)
    song_in_i = nearest_int(song_in)
    song_start_ms = song_in_i - trim_start_ms
    span = trim_end_ms - trim_start_ms
    fade = min(CROSSFADE_MS, span // 2)
    marks = []
    for m in raw["marks"]:
        at = parse_position(m["at"], ctx)
        prompt = head_ms + (at - song_in)
        marks.append({
            "label": m["label"],
            "song_ms": num(at),
            "prompt_ms": num(prompt),
            "prompt_s": round(float(prompt) / 1000.0, 3),
        })
    warnings = []
    if song_start_ms < 0:
        warnings.append(
            "song_start_ms 가 음수다. BGM 에 넣지 말고 편집 트랙의 in_ms 를 쓴다. "
            "생성을 이 머리로 하려면 곡이 0초보다 앞에서 시작해야 하므로, 곡의 맨 앞에서 시작하는 컷은 tail 로 다시 잡는다."
        )
    if not drift_ok:
        warnings.append("누적 그림 드리프트가 반 프레임을 넘는다.")
    if fade < CROSSFADE_MS:
        warnings.append("컷이 짧아 크로스페이드를 %dms 로 줄였다." % fade)
    hint = _prompt_hint(head_ms, tail_ms, head_ms + picture_ms, Fraction(duration_ms), marks)
    cut = {
        "id": raw["id"],
        "buffer": mode,
        "song_in_ms": num(song_in),
        "song_out_ms": num(song_out),
        "used_ms": num(used),
        "min_buffer_ms": num(min_buf),
        "need_ms": num(need),
        "duration_s": int(dur_s),
        "duration_ms": duration_ms,
        "duration_frames": dframes,
        "nominal_head_ms": num(nominal_head),
        "head_buffer_ms": num(head_ms),
        "tail_buffer_ms": num(tail_ms),
        "head_frames": start,
        "used_frames": n,
        "tail_frames": tail_frames,
        "trim_start_frame": start,
        "trim_end_frame": end_frame,
        "trim_start_ms": trim_start_ms,
        "trim_end_ms": trim_end_ms,
        "trim_in_ms": trim_start_ms,
        "trim_out_ms": trim_end_ms,
        "picture_ms": num(picture_ms),
        "cum_song_ms": num(cum_song_next),
        "cum_picture_ms": num(cum_picture),
        "drift_ms": num(drift),
        "drift_ok": drift_ok,
        "song_start_ms": song_start_ms,
        "track_at_ms": trim_start_ms,
        "track_in_ms": song_in_i,
        "track_length_ms": span,
        "clip_volume_db": CLIP_VOLUME_DB,
        "track_volume_db": TRACK_VOLUME_DB,
        "bgm": None,
        "crossfade_ms": fade,
        "fade_in_ms": fade,
        "fade_out_ms": fade,
        "prompt_shift_ms": num(head_ms),
        "beats": _beats_in_clip(song_in, song_out, head_ms, Fraction(duration_ms), ctx),
        "marks": marks,
        "prompt_hint": hint,
        "warnings": warnings,
        "edit": {
            "trim_in_ms": trim_start_ms,
            "trim_out_ms": trim_end_ms,
            "volume_db": CLIP_VOLUME_DB,
            "tracks": [{
                "at_ms": trim_start_ms,
                "in_ms": song_in_i,
                "length_ms": span,
                "volume_db": TRACK_VOLUME_DB,
                "fade_in_ms": fade,
                "fade_out_ms": fade,
            }],
        },
    }
    return cut, cum_song_next, cum_frames_next


def plan_cuts(cuts, bpm=None, offset_ms=0, beats=None, beats_per_bar=4,
              fps=DEFAULT_FPS, min_buffer_ms=DEFAULT_MIN_BUFFER_MS,
              durations=DEFAULT_DURATIONS, default_buffer="both"):
    """컷 목록의 생성 길이·트림·곡 시작·프롬프트 이동을 계산한다.

    cuts 의 각 항목은 '0ms..2bar both' 문자열이거나
    {in, out, buffer, id, min_buffer_ms, marks} 객체다.
    순서는 타임라인 순서다. 드리프트는 그 순서로 넘긴다.
    """
    if fps is None or as_fraction(fps) <= 0:
        raise PlanError("--fps 는 0보다 커야 한다.")
    if default_buffer not in ("head", "tail", "both"):
        raise PlanError("버퍼는 head, tail, both 중 하나다.")
    ctx = _Ctx(bpm, offset_ms, beats, beats_per_bar)
    allowed = parse_durations(durations)
    min_default = as_fraction(min_buffer_ms)
    if min_default < 0:
        raise PlanError("최소 버퍼는 0 이상이어야 한다.")
    norm = []
    for i, raw in enumerate(cuts):
        item = _normalize_cut(raw, i, default_buffer, min_default)
        if item is not None:
            norm.append(item)
    if not norm:
        raise PlanError("컷이 없다.")
    cum_song = Fraction(0)
    cum_frames = 0
    out = []
    for raw in norm:
        cut, cum_song, cum_frames = _plan_one(raw, ctx, allowed, fps, cum_song, cum_frames)
        out.append(cut)
    reported_offset = ctx.beats[0] if ctx.beats else ctx.offset_ms
    return {
        "bpm": None if ctx.bpm is None else num(ctx.bpm, 4),
        "offset_ms": num(reported_offset),
        "timing": "beats" if ctx.beats else "bpm",
        "fps": num(as_fraction(fps), 4),
        "frame_ms": num(Fraction(1000) / as_fraction(fps), 4),
        "half_frame_ms": num(Fraction(500) / as_fraction(fps), 4),
        "min_buffer_ms": num(min_default),
        "durations_s": allowed,
        "beats_per_bar": ctx.beats_per_bar,
        "crossfade_ms": CROSSFADE_MS,
        "cuts": out,
    }


def format_plan(plan):
    durs = plan["durations_s"]
    if len(durs) == 1:
        dur_s = str(durs[0])
    elif durs == list(range(durs[0], durs[-1] + 1)):
        dur_s = "%d-%d" % (durs[0], durs[-1])
    else:
        dur_s = "/".join(str(d) for d in durs)
    lines = []
    head = "fps %s · 프레임 %sms · 반 프레임 %sms · 최소 버퍼 %sms · 생성 %s" % (
        plan["fps"], plan["frame_ms"], plan["half_frame_ms"], plan["min_buffer_ms"], dur_s)
    lines.append(head)
    if plan.get("bpm") is not None:
        lines.append("BPM %s · 첫 다운비트 %sms (%s)" % (plan["bpm"], plan["offset_ms"], plan["timing"]))
    elif plan.get("timing") == "beats":
        lines.append("박 파일 · 첫 다운비트 %sms" % plan["offset_ms"])
    lines.append("드리프트는 타임라인에 쌓인 그림과, 그 컷까지 쓴 곡 길이의 합이다. 반 프레임을 넘기지 않게 프레임 수를 고른다.")
    lines.append("")
    lines.append("%-8s %-5s %10s %8s %6s %8s %8s %8s %8s %9s" % (
        "컷", "버퍼", "곡ms", "사용", "생성", "머리", "trim_in", "trim_out", "in_ms", "drift"))
    for c in plan["cuts"]:
        lines.append("%-8s %-5s %5.0f~%-4.0f %6.0fms %5ds %6.0fms %8d %8d %8d %+8.1fms" % (
            c["id"], c["buffer"], c["song_in_ms"], c["song_out_ms"], c["used_ms"],
            c["duration_s"], c["head_buffer_ms"], c["trim_in_ms"], c["trim_out_ms"],
            c["track_in_ms"], c["drift_ms"]))
        lines.append("         계산 머리 %.1fms → %d프레임(%.3f초) · 꼬리 %.1fms · song_start_ms=%d · at_ms=%d · 프롬프트 +%sms" % (
            c["nominal_head_ms"], c["head_frames"], c["head_buffer_ms"] / 1000.0,
            c["tail_buffer_ms"], c["song_start_ms"], c["track_at_ms"], c["prompt_shift_ms"]))
        for w in c["warnings"]:
            lines.append("         ! %s" % w)
        lines.append("         %s" % c["prompt_hint"])
        used = [b for b in c["beats"] if b["place"] == "used"]
        tail = [b for b in c["beats"] if b["place"] == "tail"]
        if used:
            lines.append("         쓸 박(프롬프트 초) %s" % " ".join(
                "b%d@%.3f" % (b["beat"], b["prompt_s"]) for b in used))
        if tail:
            lines.append("         꼬리 박(프롬프트 초) %s" % " ".join(
                "b%d@%.3f" % (b["beat"], b["prompt_s"]) for b in tail))
    return "\n".join(lines)


def cmd_buffer(a):
    file_meta = {}
    file_cuts = []
    try:
        if a.cuts:
            file_meta, file_cuts = load_cuts_file(a.cuts)
        if a.offset_ms is not None and a.offset is not None:
            sys.exit("--offset-ms 와 --offset 은 같이 쓰지 않는다.")
        if a.offset_ms is not None:
            offset_ms = a.offset_ms
        elif a.offset is not None:
            offset_ms = a.offset * 1000.0
        elif "offset_ms" in file_meta:
            offset_ms = file_meta["offset_ms"]
        elif "offset_s" in file_meta:
            offset_ms = float(file_meta["offset_s"]) * 1000.0
        else:
            offset_ms = 0
        bpm = a.bpm if a.bpm is not None else file_meta.get("bpm")
        fps = a.fps if a.fps is not None else file_meta.get("fps", DEFAULT_FPS)
        min_buffer = a.min_buffer_ms if a.min_buffer_ms is not None else file_meta.get(
            "min_buffer_ms", DEFAULT_MIN_BUFFER_MS)
        durations = a.durations if a.durations is not None else file_meta.get("durations", DEFAULT_DURATIONS)
        bpb = a.beats_per_bar if a.beats_per_bar is not None else file_meta.get("beats_per_bar", 4)
        default_buffer = a.buffer if a.buffer else file_meta.get("buffer", "both")
        beats = None
        beats_path = a.beats or file_meta.get("beats")
        if isinstance(beats_path, list):
            beats = beats_path
        elif beats_path:
            beats = load_beats(beats_path)
        if beats and (a.offset_ms is not None or a.offset is not None or "offset_ms" in file_meta):
            sys.stderr.write("박 파일이 있으면 박·마디 위치는 파일 시각을 쓴다. offset 은 파일 시각에 더하지 않는다.\n")
        cuts = list(file_cuts)
        if a.cut:
            cuts.extend(a.cut)
        if not cuts:
            sys.exit("컷이 없다. 예: --cut \"0ms..2bar both\"  또는 --cuts 파일")
        plan = plan_cuts(
            cuts, bpm=bpm, offset_ms=offset_ms, beats=beats, beats_per_bar=bpb,
            fps=fps, min_buffer_ms=min_buffer, durations=durations, default_buffer=default_buffer)
    except PlanError as err:
        sys.exit(str(err))
    except (OSError, ValueError, json.JSONDecodeError) as err:
        sys.exit("컷 계획을 읽지 못했다: %s" % err)
    if a.json:
        print(json.dumps(plan, ensure_ascii=False, indent=2))
    else:
        print(format_plan(plan))


def _add_buffer_parser(sub, name):
    b = sub.add_parser(name, help="정수 초 생성에 버퍼를 두고, 프레임에 맞춘 트림·곡 시작·프롬프트 시각을 계산한다")
    b.add_argument("--bpm", type=float, default=None)
    b.add_argument("--offset-ms", type=float, default=None, help="첫 다운비트(ms)")
    b.add_argument("--offset", type=float, default=None, help="첫 다운비트(초). --offset-ms 와 같이 쓰지 않는다")
    b.add_argument("--beats", default=None, help="박 시각 파일. 정수 ms, 소수면 초, Ns·Nms, 또는 JSON 배열(ms)")
    b.add_argument("--beats-per-bar", type=int, default=None)
    b.add_argument("--fps", type=float, default=None, help="기본 24")
    b.add_argument("--min-buffer-ms", type=float, default=None, help="쓰는 쪽마다의 최소 버퍼. 기본 500")
    b.add_argument("--durations", default=None, help="허용 생성 길이. 4-15(기본, Seedance 2.5) 또는 5/10")
    b.add_argument("--buffer", default=None, choices=["head", "tail", "both"],
                   help="컷에 버퍼를 안 적었을 때의 기본. 기본 both")
    b.add_argument("--cut", action="append", default=None,
                   help="시작..끝 [head|tail|both] id=이름 min=500 mark=0ms:hit  를 반복한다")
    b.add_argument("--cuts", default=None, help="컷 목록 파일. JSON 이거나 한 줄에 컷 하나")
    b.add_argument("--json", action="store_true")
    b.set_defaults(fn=cmd_buffer)


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

    ac = sub.add_parser("accents", help="킥·스네어·하이햇이 들어오는 자리를 반 박 격자에 놓는다(안무의 히트·멈춤을 정할 때)")
    ac.add_argument("path")
    ac.add_argument("--bpm", type=float, required=True)
    ac.add_argument("--from", dest="start", type=float, default=0.0, help="컷이 시작하는 곡 시각(초)")
    ac.add_argument("--to", dest="end", type=float, default=0.0, help="컷이 끝나는 곡 시각(초)")
    ac.add_argument("--offset", type=float, default=None, help="박 1 이 되는 곡 시각(초). 기본 --from")
    ac.add_argument("--fps", type=float, default=24.0)
    ac.add_argument("--window-ms", type=int, default=10)
    ac.add_argument("--rise-db", type=float, default=6.0, help="직전 30ms 보다 이만큼 오르면 소리가 들어온 것으로 본다")
    ac.add_argument("--tolerance-ms", type=float, default=60.0, help="반 박 자리에서 이만큼까지 벗어난 소리를 그 자리로 센다")
    ac.add_argument("--align", action="store_true", help="박 1 을 잰 위상만큼 옮겨 격자를 소리에 맞춘다")
    ac.add_argument("--json", action="store_true")
    ac.set_defaults(fn=cmd_accents)

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

    fo = sub.add_parser("follow", help="결과 영상이 참고 영상(프리비즈)의 움직임을 몇 프레임 늦게 따랐는지 잰다")
    fo.add_argument("reference")
    fo.add_argument("result")
    fo.add_argument("--from", dest="start", type=int, default=0, help="비교를 시작할 프레임")
    fo.add_argument("--to", dest="end", type=int, default=0, help="비교를 끝낼 프레임. 0 이면 끝까지")
    fo.add_argument("--max-lag", type=int, default=8)
    fo.add_argument("--json", action="store_true")
    fo.set_defaults(fn=cmd_follow)

    _add_buffer_parser(sub, "buffer")
    _add_buffer_parser(sub, "cutplan")

    a = p.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
