#!/usr/bin/env python3
"""만든 춤 영상이 「프레임이 떨어지는 것처럼」 보이는 까닭을 가른다.

  python3 motion_check.py result.mp4 [--json]

파일 문제인지 움직임 문제인지를 나눈다.
  겹친 프레임   앞뒤로는 움직이는데 앞 프레임과 거의 같은 프레임(한 프레임 멈칫).
  섞인 프레임   앞뒤 프레임을 반씩 섞은 것 같은 프레임(디졸브로 메운 자리).
  멈춘 프레임   카메라 움직임을 빼고 몸이 화면 너비의 0.35% 도 움직이지 않은 프레임.
  최대 속도     카메라 움직임을 뺀 몸 움직임(광학 흐름 잔차 98번째 백분위)이 가장 큰 프레임.
겹친·섞인 프레임이 있으면 생성이나 인코딩을, 멈춘 프레임이 많고 최대 속도가 크면 안무 문장을 고친다
(references/choreography.md 「끊겨 보이는 춤」).

numpy 와 OpenCV 가 필요하다(pip install numpy opencv-python-headless).
"""
import argparse
import json
import sys

try:
    import cv2
    import numpy as np
except ImportError:
    sys.exit("numpy 와 OpenCV 가 필요하다: pip install numpy opencv-python-headless")

WORK_WIDTH = 427
DUP_MAD = 0.5
MOVING_MAD = 1.5
STILL_SHARE = 0.0035
BLEND_RATIO = 0.12
# A7 v12 의 젤리 바닥처럼 밝기가 서서히 바뀌는 한 칸은 섞인 프레임과 구별되지 않아 세 칸부터 센다.
BLEND_MIN_TILES = 3
GRID = (12, 8)


def _frames(path):
    cap = cv2.VideoCapture(path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 24.0
    frames, src_w = [], 0
    while True:
        ok, fr = cap.read()
        if not ok:
            break
        src_w = fr.shape[1]
        w = min(WORK_WIDTH, src_w)
        h = int(round(fr.shape[0] * w / src_w))
        frames.append(cv2.cvtColor(cv2.resize(fr, (w, h)), cv2.COLOR_BGR2GRAY))
    if len(frames) < 3:
        sys.exit(f"프레임이 셋보다 적다: {path}")
    return frames, fps, src_w


def _body_motion(prev, cur):
    h, w = prev.shape
    flow = cv2.calcOpticalFlowFarneback(prev, cur, None, 0.5, 3, 15, 3, 5, 1.2, 0)
    ys, xs = np.mgrid[0:h:4, 0:w:4]
    src = np.stack([xs.ravel(), ys.ravel()], 1).astype(np.float32)
    dst = src + flow[ys, xs].reshape(-1, 2)
    affine, _ = cv2.estimateAffinePartial2D(src, dst, method=cv2.RANSAC, ransacReprojThreshold=1.0)
    if affine is None:
        affine = np.array([[1, 0, 0], [0, 1, 0]], np.float32)
    residual = np.linalg.norm(dst - (src @ affine[:, :2].T + affine[:, 2]), axis=1)
    return float(np.percentile(residual, 98))


def _blended(before, cur, after):
    b, c, a = (x.astype(np.float32) for x in (before, cur, after))
    off_mid = np.abs(c - (b + a) / 2)
    span = np.abs(a - b)
    h, w = c.shape
    th, tw = h // GRID[1], w // GRID[0]
    tiles = 0
    for j in range(GRID[1]):
        for i in range(GRID[0]):
            tile = (slice(j * th, (j + 1) * th), slice(i * tw, (i + 1) * tw))
            moved = span[tile].mean()
            if moved >= 6 and off_mid[tile].mean() / moved < BLEND_RATIO:
                tiles += 1
    return tiles >= BLEND_MIN_TILES


def measure(path):
    frames, fps, src_w = _frames(path)
    work_w = frames[0].shape[1]
    scale = src_w / work_w
    mad = [float(np.mean(cv2.absdiff(a, b))) for a, b in zip(frames, frames[1:])]
    body = [_body_motion(a, b) * scale for a, b in zip(frames, frames[1:])]
    dup = [i + 1 for i in range(1, len(mad) - 1)
           if mad[i] < DUP_MAD and mad[i - 1] > MOVING_MAD and mad[i + 1] > MOVING_MAD]
    blend = [t for t in range(1, len(frames) - 1) if _blended(frames[t - 1], frames[t], frames[t + 1])]
    still_px = STILL_SHARE * src_w
    still = [i + 1 for i, v in enumerate(body) if v < still_px]
    run, best, best_start = 0, 0, None
    for i, v in enumerate(body):
        run = run + 1 if v < still_px else 0
        if run > best:
            best, best_start = run, i + 2 - run
    peak = int(np.argmax(body))
    return {
        "frames": len(frames), "fps": round(fps, 3), "width": src_w,
        "duplicate_frames": dup, "blended_frames": blend,
        "still_frames": len(still), "still_share": round(len(still) / len(body), 3),
        "longest_still": {"frames": best, "start_s": None if best_start is None else round(best_start / fps, 2)},
        "body_px_p50": round(float(np.median(body)), 1), "body_px_p95": round(float(np.percentile(body, 95)), 1),
        "body_px_max": round(body[peak], 1), "body_max_at_s": round((peak + 1) / fps, 2),
        "body_max_share_of_width": round(body[peak] / src_w, 4),
    }


def main():
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("video")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    r = measure(args.video)
    if args.json:
        print(json.dumps(r, ensure_ascii=False))
        return
    print(f"{args.video}: {r['frames']}프레임 {r['fps']}fps 너비 {r['width']}px")
    print(f"  겹친 프레임 {len(r['duplicate_frames'])}개 {r['duplicate_frames'][:20]}")
    print(f"  섞인 프레임 {len(r['blended_frames'])}개 {r['blended_frames'][:20]}")
    print(f"  멈춘 프레임 {r['still_frames']}개({r['still_share']:.0%}), 가장 길게 멈춘 구간 "
          f"{r['longest_still']['frames']}프레임({r['longest_still']['start_s']}초부터)")
    print(f"  몸 움직임 가운데값 {r['body_px_p50']}px, 95% {r['body_px_p95']}px, "
          f"최대 {r['body_px_max']}px(너비의 {r['body_max_share_of_width']:.1%}, {r['body_max_at_s']}초)")


if __name__ == "__main__":
    main()
