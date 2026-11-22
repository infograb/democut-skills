#!/usr/bin/env python3
"""샷리스트(shots.json)를 검사하고 생성 구간마다 시각·블록아웃 프레임을 낸다.

  python3 shot_plan.py check shots.json            # 오류가 있으면 종료 코드 1
  python3 shot_plan.py beats shots.json            # 생성 구간마다 프롬프트용 시각과 블록아웃 프레임
  python3 shot_plan.py beats shots.json --json

shots.json 모양:
  {"fps": 24, "speech_rate": 5.0,
   "shots": [{"id": "S1", "generation": 1, "seconds": 3, "size": "wide", "lens_mm": 24,
              "camera": "slow push-in", "action": "…", "speaker": "민지", "line": "어, 왔어?"}]}
"""
import argparse
import json
import re
import sys
from collections import Counter

MIN_GEN_S = 4
MAX_GEN_S = 15
LINE_PAD_S = 0.5
DEFAULT_RATE = 5.0


def syllables(text):
    hangul = len(re.findall(r"[가-힣]", text))
    latin_words = len(re.findall(r"[A-Za-z]+", text))
    digits = len(re.findall(r"\d", text))
    return hangul + 2 * latin_words + digits


def line_seconds(text, rate):
    return syllables(text) / rate + LINE_PAD_S


def _num(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def generations(plan):
    groups = {}
    for shot in plan["shots"]:
        groups.setdefault(shot.get("generation"), []).append(shot)
    return groups


def check(plan):
    errors, warnings = [], []
    shots = plan.get("shots") or []
    if not shots:
        return ["shots 가 비었다"], warnings
    rate = plan.get("speech_rate", DEFAULT_RATE)
    counts = Counter(s.get("id") for s in shots)
    for dup in sorted((i for i, n in counts.items() if n > 1), key=str):
        errors.append("샷 id %s 가 겹친다" % dup)
    order = []
    for shot in shots:
        sid = shot.get("id")
        gen = shot.get("generation")
        if not isinstance(gen, int) or isinstance(gen, bool) or gen < 1:
            errors.append("%s: generation 은 1 이상의 정수다" % sid)
        elif not order or order[-1] != gen:
            if gen in order:
                errors.append("%s: 생성 구간 %d 이 떨어져 있다(같은 구간의 샷은 이어서 적는다)" % (sid, gen))
            order.append(gen)
        if not _num(shot.get("seconds")) or shot["seconds"] <= 0:
            errors.append("%s: seconds 는 0 보다 큰 수다" % sid)
            continue
        line = (shot.get("line") or "").strip()
        if line and not shot.get("speaker"):
            errors.append("%s: 대사에 speaker 가 없다" % sid)
        if line:
            need = line_seconds(line, rate)
            if need > shot["seconds"]:
                errors.append("%s: 대사가 %.1f초 걸리는데 샷은 %.1f초다(대사를 줄이거나 샷을 늘린다)"
                              % (sid, need, shot["seconds"]))
            if shot.get("camera_moves_during_line"):
                warnings.append("%s: 대사 동안 카메라가 움직인다. 결과가 카메라를 따라가지 않을 수 있다" % sid)
    for gen, group in generations(plan).items():
        if not isinstance(gen, int):
            continue
        total = sum(s["seconds"] for s in group if _num(s.get("seconds")))
        if abs(total - round(total)) > 1e-6:
            errors.append("생성 구간 %d: 합이 %.2f초다. 정수 초여야 한다" % (gen, total))
        elif not MIN_GEN_S <= round(total) <= MAX_GEN_S:
            errors.append("생성 구간 %d: %d초다. %d~%d초여야 한다" % (gen, round(total), MIN_GEN_S, MAX_GEN_S))
        speakers = {s.get("speaker") for s in group if (s.get("line") or "").strip()}
        if len(speakers) > 1:
            warnings.append("생성 구간 %d: 말하는 사람이 %d명이다(%s). 한 생성에 두 사람의 대사는 미확인이다"
                            % (gen, len(speakers), ", ".join(sorted(map(str, speakers)))))
    return errors, warnings


def _fmt_s(x):
    return ("%d" % x) if abs(x - round(x)) < 1e-6 else ("%.1f" % x)


def beats(plan):
    fps = plan.get("fps", 24)
    out = []
    seq_t = 0.0
    for gen, group in generations(plan).items():
        t = 0.0
        rows = []
        for shot in group:
            start, end = t, t + shot["seconds"]
            rows.append({
                "id": shot.get("id"),
                "start_s": round(start, 3), "end_s": round(end, 3),
                "label": "%s-%ss" % (_fmt_s(start), _fmt_s(end)),
                "frames": [int(round(start * fps)) + 1, int(round(end * fps))],
                "sequence_frames": [int(round((seq_t + start) * fps)) + 1, int(round((seq_t + end) * fps))],
                "size": shot.get("size"), "lens_mm": shot.get("lens_mm"), "camera": shot.get("camera"),
                "action": shot.get("action"), "speaker": shot.get("speaker"), "line": shot.get("line"),
            })
            t = end
        out.append({"generation": gen, "seconds": int(round(t)), "frame_count": int(round(t * fps)),
                    "shots": rows})
        seq_t += t
    return out


def _print_beats(gens):
    for g in gens:
        print("생성 구간 %s: %d초, 샷 %d개, 블록아웃 %d프레임" % (g["generation"], g["seconds"], len(g["shots"]),
                                                       g["frame_count"]))
        for i, r in enumerate(g["shots"], 1):
            lens = " %smm" % r["lens_mm"] if r["lens_mm"] else ""
            head = "%s Shot %d (%s%s)" % (r["label"], i, r["size"] or "?", lens)
            print("  %s: %s%s" % (head, r["camera"] + ". " if r["camera"] else "", r["action"] or ""))
            if r["line"]:
                print("      %s: \"%s\"" % (r["speaker"], r["line"]))
            print("      블록아웃 프레임 %d-%d (전체 %d-%d)" % (tuple(r["frames"]) + tuple(r["sequence_frames"])))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", choices=["check", "beats"])
    ap.add_argument("plan")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    with open(args.plan, encoding="utf-8") as f:
        plan = json.load(f)
    errors, warnings = check(plan)
    for w in warnings:
        print("주의: " + w, file=sys.stderr)
    for e in errors:
        print("오류: " + e, file=sys.stderr)
    if errors:
        return 1
    if args.command == "check":
        print("통과: 샷 %d개, 생성 구간 %d개" % (len(plan["shots"]), len(generations(plan))))
        return 0
    gens = beats(plan)
    if args.json:
        print(json.dumps(gens, ensure_ascii=False, indent=1))
    else:
        _print_beats(gens)
    return 0


if __name__ == "__main__":
    sys.exit(main())
