#!/usr/bin/env python3
"""room-set-photos — room-set-planner 의 house.json 으로 촬영 컷을 정하고, 컷마다 AI 이미지 프롬프트와
레퍼런스(카메라 시점 덩어리 스케치 PNG, 제품 보드 PNG)를 만든다.

표준 라이브러리만 쓴다(Python 3.8+). 집 구조 계산은 같은 곳에 설치된 room-set-planner 의 planner.py 를 쓴다.
제품 보드는 ffmpeg 가 있을 때 만든다.

  python3 shots.py plan  house.json [-o photos/] [--max-hero 6]   # shots.json · shots.md · sketch/*.png · shots.svg
  python3 shots.py fetch house.json photos/products                # 제품 대표 사진 받기(새 빈 디렉터리)
  python3 shots.py board photos/shots.json --images photos/products  # 컷마다 제품 보드 → photos/boards/*.png

좌표는 house.json 과 같다(mm, 도면 왼쪽 위 원점, x 오른쪽, y 아래). 높이 z 는 바닥에서 위로.
"""
import argparse
import datetime
import json
import math
import os
import re
import shutil
import struct
import subprocess
import sys
import urllib.request
import zlib
from array import array
from collections import Counter

HERE = os.path.dirname(os.path.realpath(__file__))


def _find_planner():
    for c in (os.path.join(HERE, "..", "..", "room-set-planner", "scripts"),
              os.path.expanduser("~/.claude/skills/room-set-planner/scripts")):
        if os.path.isfile(os.path.join(c, "planner.py")):
            return os.path.realpath(c)
    return None


_PD = _find_planner()
if not _PD:
    sys.stderr.write("room-set-planner 스킬을 찾지 못했다. 이 스킬과 같은 디렉터리(…/skills/room-set-planner)에 설치한다\n")
    sys.exit(2)
sys.path.insert(0, _PD)
import planner as P  # noqa: E402

# ----------------------------------------------------------------------------- 상수

NEAR = 60.0                 # 카메라 앞 이보다 가까운 면은 자른다(mm)
DEFAULT_CEIL = 2300
WIN_HEAD = 2100             # 창 위 끝 높이
DOOR_H = 2100
NORMAL = {"n": (0, -1), "s": (0, 1), "w": (-1, 0), "e": (1, 0)}
RATIOS = {                  # DemoCut 프로젝트 비율 → (스케치 가로, 세로, 그림 크기, 센서 가로 mm, 설명)
    "9:16": (683, 1024, "1024x1536", 24.0, "vertical 2:3"),
    "1:1": (1024, 1024, "1024x1024", 24.0, "square 1:1"),
    "16:9": (1024, 683, "1536x1024", 36.0, "horizontal 3:2"),
}
WIDE_LENS, HERO_LENS = 18.0, 28.0
# 수평 촬영의 수평선 높이(위에서 비율). 건축 사진처럼 렌즈를 올려(시프트) 수직선을 세운 채 천장을 덜 담는다
HORIZON = {"9:16": 0.38, "1:1": 0.42, "16:9": 0.46}
SCORE_DIV = 6               # 후보를 고를 때는 1/6 크기로 그려 본다

BG = (250, 250, 250)
FLOOR = (150, 150, 152)
CEIL = (238, 238, 238)
WALLS = {"n": (214, 214, 214), "s": (204, 204, 204), "w": (224, 224, 224), "e": (196, 196, 196)}
WINDOW = (190, 225, 248)
DOOR = (176, 148, 118)
VOID = (92, 92, 98)
EDGE = (55, 55, 60)
PALETTE = [((232, 116, 80), "orange"), ((48, 160, 146), "teal"), ((236, 196, 92), "yellow"),
           ((70, 120, 184), "blue"), ((160, 96, 204), "purple"), ((118, 172, 78), "green"),
           ((218, 72, 112), "pink"), ((140, 98, 66), "brown"), ((90, 200, 222), "cyan"),
           ((108, 108, 204), "indigo"), ((200, 160, 60), "ochre"), ((60, 60, 60), "charcoal")]
DEFAULT_H = {"bed": 300, "desk": 740, "dining_table": 740, "chair": 900, "lamp": 500, "sofa": 800}

KIND_EN = {"bedroom": "bedroom", "living": "living room", "kitchen": "kitchen", "bathroom": "bathroom",
           "entrance": "entryway", "hall": "hallway", "dressroom": "dressing room", "utility": "utility room"}

# ----------------------------------------------------------------------------- 오늘의집 컨셉

COMMON_LOOK = ("A real photo from an Ohouse (오늘의집) house-tour post: the resident's own home shot with a good camera, "
               "bright natural light, true-to-life colors, tidy but lived-in, photorealistic, not a 3D render. "
               "Korean home details: white PVC double-sash window frames, white baseboards, smooth silk wallpaper, "
               "a flat round LED ceiling light.")
NEGATIVE = ("Avoid: people, pets, text, logos, watermarks, fisheye distortion, CGI look, and any furniture, appliance, "
            "rug or wall art that is not listed.")

CONCEPTS = {
    "natural": dict(
        ko="내추럴 우드",
        mood="Warm natural-wood style: light oak, white, beige linen and a little rattan, with fresh green plants.",
        walls="white silk wallpaper", floor="light natural-oak laminate flooring",
        light="soft late-morning daylight through the window, gentle shadows, slightly warm white balance",
        props="white and beige linen bedding, a knit throw, a few books, one or two small plants in ceramic pots"),
    "minimal": dict(
        ko="화이트 미니멀",
        mood="Clean white minimal style: white, pale gray and light wood, almost nothing on surfaces.",
        walls="white silk wallpaper", floor="pale whitewashed oak laminate flooring",
        light="bright, even daylight with soft shadows, neutral white balance",
        props="crisp white bedding, one small plant, a few neatly stacked books"),
    "modern": dict(
        ko="모던 그레이",
        mood="Modern monotone style: warm gray, white and black metal accents.",
        walls="light warm-gray wallpaper", floor="gray-beige oak laminate flooring",
        light="soft overcast daylight, calm and even",
        props="charcoal and gray bedding, black desk accessories, a single sculptural plant"),
    "midcentury": dict(
        ko="미드센추리 빈티지",
        mood="Mid-century vintage style: walnut tones with mustard and olive accents and rounded shapes.",
        walls="warm ivory wallpaper", floor="medium-brown oak laminate flooring",
        light="warm late-afternoon sunlight with long soft shadows",
        props="mustard and olive bedding, ceramic vases, a stack of records and books, a trailing pothos"),
    "cozy": dict(
        ko="아늑한 웜톤",
        mood="Cozy warm-tone style: cream, beige and soft brown with layered fabric textures.",
        walls="cream wallpaper", floor="warm honey-oak laminate flooring",
        light="golden early-evening light from the window mixed with warm indoor light",
        props="layered cream and beige bedding, boucle cushions, a small tray with a mug, a candle"),
}


def concept_of(house):
    ph = house.get("photo") or {}
    c = ph.get("concept", "natural")
    base = dict(CONCEPTS.get(c, CONCEPTS["natural"]))
    if c not in CONCEPTS:                         # 자유 문장이면 분위기로 쓰고 나머지는 natural 값
        base.update(ko=str(c), mood=str(c))
    for k in ("mood", "walls", "floor", "light", "props"):
        if ph.get(k):
            base[k] = ph[k]
    base["key"] = c
    return base


# ----------------------------------------------------------------------------- 그리기(표준 라이브러리)

def _clip_seg(a, b, xmin, ymin, xmax, ymax):
    x0, y0 = a
    dx, dy = b[0] - x0, b[1] - y0
    t0, t1 = 0.0, 1.0
    for p, q in ((-dx, x0 - xmin), (dx, xmax - x0), (-dy, y0 - ymin), (dy, ymax - y0)):
        if p == 0:
            if q < 0:
                return None
            continue
        t = q / p
        if p < 0:
            if t > t1:
                return None
            t0 = max(t0, t)
        else:
            if t < t0:
                return None
            t1 = min(t1, t)
    return (x0 + t0 * dx, y0 + t0 * dy), (x0 + t1 * dx, y0 + t1 * dy)


class Canvas:
    """다각형 채우기 + 선. 픽셀마다 무엇이 그려졌는지(id) 함께 적어 보이는 품목을 센다."""

    def __init__(self, w, h):
        self.w, self.h = w, h
        self.px = bytearray(bytes(BG) * (w * h))
        self.ids = array("H", [0]) * (w * h)
        self.drawn = Counter()     # id → 그려진 픽셀(가려지기 전)
        self.occ = Counter()       # (가려진 id, 가린 id) → 픽셀

    def fill(self, pts, color, iid=0):
        ys = [p[1] for p in pts]
        ya = max(0, int(math.ceil(min(ys) - 0.5)))
        yb = min(self.h - 1, int(math.floor(max(ys) - 0.5)))
        if yb < ya:
            return
        col = bytes(color)
        n = len(pts)
        edges = [(pts[i], pts[(i + 1) % n]) for i in range(n) if pts[i][1] != pts[(i + 1) % n][1]]
        for y in range(ya, yb + 1):
            sy = y + 0.5
            xs = sorted(ax + (sy - ay) * (bx - ax) / (by - ay)
                        for (ax, ay), (bx, by) in edges if (ay <= sy < by) or (by <= sy < ay))
            row = y * self.w
            for j in range(0, len(xs) - 1, 2):
                xa = max(0, int(math.ceil(xs[j] - 0.5)))
                xb = min(self.w - 1, int(math.floor(xs[j + 1] - 0.5)))
                if xb < xa:
                    continue
                m = xb - xa + 1
                s0, s1 = row + xa, row + xb + 1
                self.px[s0 * 3:s1 * 3] = col * m
                if iid:
                    for k, v in Counter(self.ids[s0:s1]).items():
                        if k and k != iid:
                            self.occ[(k, iid)] += v
                    self.drawn[iid] += m
                self.ids[s0:s1] = array("H", [iid]) * m

    def line(self, a, b, color, wdt=2):
        c = _clip_seg(a, b, -2, -2, self.w + 1, self.h + 1)
        if not c:
            return
        (x0, y0), (x1, y1) = c
        n = int(max(abs(x1 - x0), abs(y1 - y0))) + 1
        col = bytes(color)
        h0 = wdt // 2
        for i in range(n + 1):
            t = i / float(n)
            x, y = int(x0 + (x1 - x0) * t), int(y0 + (y1 - y0) * t)
            xa, xb = max(0, x - h0), min(self.w, x - h0 + wdt)
            if xb <= xa:
                continue
            for yy in range(max(0, y - h0), min(self.h, y - h0 + wdt)):
                self.px[(yy * self.w + xa) * 3:(yy * self.w + xb) * 3] = col * (xb - xa)

    def png(self, path):
        w = self.w * 3
        raw = b"".join(b"\x00" + bytes(self.px[y * w:(y + 1) * w]) for y in range(self.h))

        def chunk(t, d):
            return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
        with open(path, "wb") as f:
            f.write(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", self.w, self.h, 8, 2, 0, 0, 0))
                    + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))

    def stats(self):
        """id → [픽셀 수, x 합, y 합, x 최소, x 최대, y 최소, y 최대]"""
        st = {}
        ids, w = self.ids, self.w
        for y in range(self.h):
            row = ids[y * w:(y + 1) * w]
            if not any(row):
                continue
            for x, v in enumerate(row):
                if v:
                    s = st.get(v)
                    if s is None:
                        st[v] = s = [0, 0, 0, x, x, y, y]
                    s[0] += 1
                    s[1] += x
                    s[2] += y
                    if x < s[3]:
                        s[3] = x
                    elif x > s[4]:
                        s[4] = x
                    if y > s[6]:
                        s[6] = y
        return st


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


class Cam:
    """핀홀 카메라. yaw 는 도면에서 보는 방향(라디안, x 축에서 y 축 쪽으로), pitch 는 위가 +."""

    def __init__(self, x, y, z, yaw, pitch, hfov, w, h, lens_mm=None, cyf=0.5):
        self.x, self.y, self.z, self.yaw, self.pitch, self.hfov = x, y, z, yaw, pitch, hfov
        self.lens_mm, self.cyf = lens_mm, cyf
        cy, sy, cp, sp = math.cos(yaw), math.sin(yaw), math.cos(pitch), math.sin(pitch)
        self.f = (cp * cy, cp * sy, sp)
        self.r = (-sy, cy, 0.0)
        self.u = (-sp * cy, -sp * sy, cp)
        self.w, self.h = w, h
        self.F = (w / 2.0) / math.tan(hfov / 2.0)

    def to_cam(self, p):
        d = (p[0] - self.x, p[1] - self.y, p[2] - self.z)
        return (_dot(d, self.r), _dot(d, self.u), _dot(d, self.f))

    def proj(self, q):
        return (self.w / 2.0 + self.F * q[0] / q[2], self.h * self.cyf - self.F * q[1] / q[2])

    def fwd2(self):
        return (math.cos(self.yaw), math.sin(self.yaw))

    def right2(self):
        return (-math.sin(self.yaw), math.cos(self.yaw))


def _clip_near(poly):
    out = []
    n = len(poly)
    for i in range(n):
        a, b = poly[i], poly[(i + 1) % n]
        ai, bi = a[2] > NEAR, b[2] > NEAR
        if ai:
            out.append(a)
        if ai != bi:
            t = (NEAR - a[2]) / (b[2] - a[2])
            out.append(tuple(a[k] + t * (b[k] - a[k]) for k in range(3)))
    return out


# ----------------------------------------------------------------------------- 장면

def _shade(c, k):
    return tuple(max(0, min(255, int(v * k))) for v in c)


def _box_faces(rect, z0, z1):
    x0, y0, x1, y1 = rect
    return [
        ([(x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)], (0, 0, 1), 1.0),
        ([(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0)], (0, 0, -1), 0.6),
        ([(x0, y0, z0), (x1, y0, z0), (x1, y0, z1), (x0, y0, z1)], (0, -1, 0), 0.8),
        ([(x0, y1, z0), (x1, y1, z0), (x1, y1, z1), (x0, y1, z1)], (0, 1, 0), 0.72),
        ([(x0, y0, z0), (x0, y1, z0), (x0, y1, z1), (x0, y0, z1)], (-1, 0, 0), 0.9),
        ([(x1, y0, z0), (x1, y1, z0), (x1, y1, z1), (x1, y0, z1)], (1, 0, 0), 0.66),
    ]


def item_height(it, g):
    h = g.get("h") or 0
    if P.CAT.get(it.get("category"), {}).get("floor"):
        return 12
    return h or DEFAULT_H.get(it.get("category"), 450)


def base_z(ctx, it, depth=0):
    par = it.get("on")
    if par and par in ctx.geo and depth < 5:
        pit = next(x for x in ctx.items if x["id"] == par)
        return base_z(ctx, pit, depth + 1) + item_height(pit, ctx.geo[par])
    return it.get("z", 0) or 0


def item_boxes(ctx, it):
    """품목을 덩어리 몇 개로: [(바닥 사각형, z0, z1)]. 침대·소파·책상·의자는 모양이 읽히게 나눈다."""
    g = ctx.geo[it["id"]]
    x0, y0, x1, y1 = g["rect"]
    f = g["facing"]
    back = P.OPP[f]
    b = base_z(ctx, it)
    h = item_height(it, g)
    cat = it.get("category")

    def band(side, t):
        return {"n": (x0, y0, x1, y0 + t), "s": (x0, y1 - t, x1, y1),
                "w": (x0, y0, x0 + t, y1), "e": (x1 - t, y0, x1, y1)}[side]
    lat = ("w", "e") if f in "ns" else ("n", "s")
    if cat == "bed":
        top = 480 if h > 600 else max(300, min(h + 220, 560))     # 매트리스·침구 윗면
        out = [((x0, y0, x1, y1), b, b + top)]
        if h > 600:
            out.append((band(back, 80), b, b + h))              # 헤드보드
        return out
    if cat == "sofa":
        seat = min(h, 430)
        out = [((x0, y0, x1, y1), b, b + seat), (band(back, min(230, (y1 - y0 if f in "ns" else x1 - x0) * 0.3)), b, b + h)]
        for s in lat:
            out.append((band(s, 160), b, b + min(h, 620)))
        return out
    if cat in ("desk", "dining_table"):
        out = [((x0, y0, x1, y1), b + h - 40, b + h)]
        for s in lat:
            out.append((band(s, 45), b, b + h - 40))
        return out
    if cat == "chair":                 # 좌판 · 등받이 · 기둥: 판자 하나로 그리면 문처럼 읽힌다
        ins = 40
        seat = min(460, h)
        bk = band(back, 70)
        k = 0.14 * ((bk[2] - bk[0]) if f in "ns" else (bk[3] - bk[1]))
        bk = (bk[0] + k, bk[1], bk[2] - k, bk[3]) if f in "ns" else (bk[0], bk[1] + k, bk[2], bk[3] - k)
        mx, my = (x0 + x1) / 2.0, (y0 + y1) / 2.0
        return [((x0 + ins, y0 + ins, x1 - ins, y1 - ins), b + seat - 70, b + seat),
                (bk, b + seat + 60, b + h),
                ((mx - 40, my - 40, mx + 40, my + 40), b, b + seat - 70)]
    return [((x0, y0, x1, y1), b, b + h)]


class Scene:
    def __init__(self, ctx, room, ceil):
        self.ctx, self.room, self.ceil = ctx, room, ceil
        x0, y0, x1, y1 = P.rr(room)
        C = ceil
        self.shell = [
            ([(x0, y0, 0), (x1, y0, 0), (x1, y1, 0), (x0, y1, 0)], FLOOR),
            ([(x0, y0, C), (x1, y0, C), (x1, y1, C), (x0, y1, C)], CEIL),
            ([(x0, y0, 0), (x1, y0, 0), (x1, y0, C), (x0, y0, C)], WALLS["n"]),
            ([(x0, y1, 0), (x1, y1, 0), (x1, y1, C), (x0, y1, C)], WALLS["s"]),
            ([(x0, y0, 0), (x0, y1, 0), (x0, y1, C), (x0, y0, C)], WALLS["w"]),
            ([(x1, y0, 0), (x1, y1, 0), (x1, y1, C), (x1, y0, C)], WALLS["e"]),
        ]
        self.ops = {}          # id(1000+) → dict(op, side, poly, color)
        k = 0
        for o in ctx.ops:
            if o["room"] == room["id"]:
                side, line = o["wall"], o["line"]
            elif o.get("to") == room["id"]:
                side, line = P.OPP[o["wall"]], o["other_line"]
            else:
                continue
            k += 1
            nx, ny = NORMAL[side]
            if o["axis"] == "x":
                lv = line - ny * 4

                def mk(a, z, lv=lv):
                    return (a, lv, z)
            else:
                lv = line - nx * 4

                def mk(a, z, lv=lv):
                    return (lv, a, z)
            if o["type"] == "window":
                z0, z1, col = o.get("sill", 900), min(WIN_HEAD, C - 150), WINDOW
            elif o["type"] == "opening":
                z0, z1, col = 0, min(DOOR_H, C - 100), VOID
            else:
                z0, z1, col = 0, min(DOOR_H, C - 100), DOOR
            self.ops[1000 + k] = dict(op=o, side=side, color=col,
                                      poly=[mk(o["a"], z0), mk(o["b"], z0), mk(o["b"], z1), mk(o["a"], z1)])
        self.items = [it for it in ctx.items if it["room"] == room["id"]]
        order = {it["id"]: i for i, it in enumerate(ctx.items)}
        self.iid = {it["id"]: i + 1 for i, it in enumerate(self.items)}
        self.color = {it["id"]: PALETTE[order[it["id"]] % len(PALETTE)] for it in self.items}
        self.boxes = {it["id"]: item_boxes(ctx, it) for it in self.items}

    def obstacles(self, exclude=()):
        out = []
        for it in self.items:
            if it["id"] in exclude or it.get("on") or P.CAT.get(it.get("category"), {}).get("floor"):
                continue
            if (it.get("z", 0) or 0) >= P.WALL_MOUNT_Z:
                continue
            out.append(self.ctx.geo[it["id"]]["rect"])
        return out

    def free(self, pt, exclude=(), margin=220):
        x, y = pt
        x0, y0, x1, y1 = P.rr(self.room)
        if not (x0 + 200 <= x <= x1 - 200 and y0 + 200 <= y <= y1 - 200):
            return False
        for r in self.obstacles(exclude):
            if r[0] - margin < x < r[2] + margin and r[1] - margin < y < r[3] + margin:
                return False
        return True

    def render(self, cam):
        cv = Canvas(cam.w, cam.h)
        lw = max(1, cam.w // 340)

        def draw(pts, color, iid=0):
            q = _clip_near([cam.to_cam(p) for p in pts])
            if len(q) < 3:
                return
            p2 = [cam.proj(v) for v in q]
            cv.fill(p2, color, iid)
            for i in range(len(p2)):
                cv.line(p2[i], p2[(i + 1) % len(p2)], EDGE, lw)
        for pts, col in self.shell:
            draw(pts, col)
        for oid, m in self.ops.items():
            draw(m["poly"], m["color"], oid)

        def near_dist(it):
            x0, y0, x1, y1 = self.ctx.geo[it["id"]]["rect"]
            dx = max(x0 - cam.x, 0, cam.x - x1)
            dy = max(y0 - cam.y, 0, cam.y - y1)
            return math.hypot(dx, dy)
        seq = sorted(self.items, key=near_dist, reverse=True)
        for it in [x for x in seq if x.get("on")]:          # 올려 둔 것은 받침 다음에
            par = it["on"]
            seq.remove(it)
            idx = next((i for i, x in enumerate(seq) if x["id"] == par), len(seq) - 1)
            seq.insert(idx + 1, it)
        for it in seq:
            base = self.color[it["id"]][0]
            for rect, z0, z1 in sorted(self.boxes[it["id"]], key=lambda bx: bx[1]):   # 아래 부품부터(위에서 내려다본다)
                for pts, nrm, k in _box_faces(rect, z0, z1):
                    p = pts[0]
                    if (cam.x - p[0]) * nrm[0] + (cam.y - p[1]) * nrm[1] + (cam.z - p[2]) * nrm[2] <= 0:
                        continue
                    draw(pts, _shade(base, k), self.iid[it["id"]])
        return cv


# ----------------------------------------------------------------------------- 촬영 자리 고르기

def _wall_hit(room, cx, cy, yaw):
    """카메라에서 정면으로 나간 선이 닿는 벽."""
    x0, y0, x1, y1 = P.rr(room)
    dx, dy = math.cos(yaw), math.sin(yaw)
    best = None
    for side, t in (("w", (x0 - cx) / dx if dx < -1e-9 else None), ("e", (x1 - cx) / dx if dx > 1e-9 else None),
                    ("n", (y0 - cy) / dy if dy < -1e-9 else None), ("s", (y1 - cy) / dy if dy > 1e-9 else None)):
        if t is not None and t > 0 and (best is None or t < best[1]):
            best = (side, t)
    return best[0] if best else "n"


def _share(st, iid, A):
    return st[iid][0] / A if iid in st else 0.0


def wide_candidates(sc):
    room = sc.room
    x0, y0, x1, y1 = P.rr(room)
    cx, cy = (x0 + x1) / 2.0, (y0 + y1) / 2.0
    cands = []
    ins = 380
    for px, py in ((x0 + ins, y0 + ins), (x1 - ins, y0 + ins), (x0 + ins, y1 - ins), (x1 - ins, y1 - ins)):
        cands.append(((px, py), "corner", None))
    for oid, m in sc.ops.items():
        o = m["op"]
        if o["type"] == "window":
            continue
        line = o["line"] if o["room"] == room["id"] else o["other_line"]
        inward = -NORMAL[m["side"]][0 if o["axis"] == "y" else 1]
        mid = (o["a"] + o["b"]) / 2.0
        p = (mid, line + inward * 420) if o["axis"] == "x" else (line + inward * 420, mid)
        cands.append((p, "door", oid))
    out = []
    for p, kind, oid in cands:
        q = p
        ok = sc.free(q)
        L = math.hypot(cx - p[0], cy - p[1]) or 1.0
        for k in range(1, 13):
            if ok:
                break
            q = (p[0] + (cx - p[0]) / L * 100 * k, p[1] + (cy - p[1]) / L * 100 * k)
            ok = sc.free(q)
        if ok:
            out.append((q, kind, oid))
    return out


def plan_wide(sc, ratio, cam_h, review_ids):
    W, H, _, sw, _ = RATIOS[ratio]
    w, h = W // SCORE_DIV, H // SCORE_DIV
    hfov = 2 * math.atan((sw / 2.0) / WIDE_LENS)
    x0, y0, x1, y1 = P.rr(sc.room)
    cx, cy = (x0 + x1) / 2.0, (y0 + y1) / 2.0
    scored = []
    for p, kind, oid in wide_candidates(sc):
        for off in (0.0, -0.18, 0.18):
            yaw = math.atan2(cy - p[1], cx - p[0]) + off
            cam = Cam(p[0], p[1], cam_h, yaw, 0.0, hfov, w, h, cyf=HORIZON[ratio])
            cv = sc.render(cam)
            st = cv.stats()
            A = float(w * h)
            score, big = 0.0, 0.0
            for it in sc.items:
                s = _share(st, sc.iid[it["id"]], A)
                if not s:
                    continue
                wgt = 2.0 if it["id"] in review_ids else (0.3 if P.CAT.get(it.get("category"), {}).get("floor") else 1.0)
                score += wgt * min(1.0, s / 0.03)
                big = max(big, s)
            win = sum(st[k][0] for k in st if k >= 1000 and sc.ops[k]["op"]["type"] == "window") / A
            if win > 0.01:
                score += 1.5
            if big > 0.45:
                score -= 2.0
            scored.append((score, p, yaw, kind, oid, win > 0.01))
    scored.sort(key=lambda t: -t[0])
    picked = []
    for s in scored:
        if all(abs(math.atan2(math.sin(s[2] - q[2]), math.cos(s[2] - q[2]))) > math.radians(60)
               or math.hypot(s[1][0] - q[1][0], s[1][1] - q[1][1]) > 1500 for q in picked):
            picked.append(s)
        if len(picked) == 2:
            break
    return [dict(x=p[0], y=p[1], z=cam_h, yaw=yaw, pitch=0.0, lens=WIDE_LENS, kind="wide", where=kind, door=oid,
                 cyf=HORIZON[ratio], window=win)
            for _, p, yaw, kind, oid, win in picked]


def plan_hero(sc, it, ratio):
    W, H, _, sw, _ = RATIOS[ratio]
    w, h = W // SCORE_DIV, H // SCORE_DIV
    A = float(w * h)
    g = sc.ctx.geo[it["id"]]
    x0, y0, x1, y1 = g["rect"]
    cx, cy = (x0 + x1) / 2.0, (y0 + y1) / 2.0
    F = NORMAL[g["facing"]]
    fc = {"n": (cx, y0), "s": (cx, y1), "w": (x0, cy), "e": (x1, cy)}[g["facing"]]
    b = base_z(sc.ctx, it)
    top = max(z1 for _, _, z1 in sc.boxes[it["id"]])
    ch = max(900.0, min(1450.0, top + 350.0))
    tz = b + (top - b) * 0.5
    iid = sc.iid[it["id"]]
    best = None
    for lens, pen in ((HERO_LENS, 0.0), (WIDE_LENS, 0.15)):
        hfov = 2 * math.atan((sw / 2.0) / lens)
        angles = (0, 20, -20, 40, -40, 60, -60)
        if best is None and lens == WIDE_LENS:      # 앞이 막힌 품목(책상에 넣은 의자): 옆·뒤에서
            angles += (90, -90, 120, -120, 150, -150, 180)
        for ang in angles:
            a = math.radians(ang)
            dx, dy = F[0] * math.cos(a) - F[1] * math.sin(a), F[0] * math.sin(a) + F[1] * math.cos(a)
            for dist in (700, 1000, 1400, 1900, 2500):
                p = (fc[0] + dx * dist, fc[1] + dy * dist)
                if not sc.free(p, exclude=(it["id"],), margin=150):
                    continue
                yaw = math.atan2(cy - p[1], cx - p[0])
                horiz = math.hypot(cx - p[0], cy - p[1])
                pitch = max(math.radians(-30), min(math.radians(5), math.atan2(tz - ch, horiz)))
                cam = Cam(p[0], p[1], ch, yaw, pitch, hfov, w, h)
                cv = sc.render(cam)
                st = cv.stats()
                if iid not in st:
                    continue
                s = st[iid]
                share = s[0] / A
                frac = s[0] / float(cv.drawn[iid] or 1)
                cut = s[3] <= 0 or s[4] >= w - 1
                score = -abs(share - 0.3) * 3 - (1 - frac) * 1.5 - (0.6 if cut else 0) - 0.2 * abs(ang) / 60.0 - pen
                if share < 0.05:
                    score -= 2
                if best is None or score > best[0]:
                    best = (score, dict(x=p[0], y=p[1], z=ch, yaw=yaw, pitch=pitch, lens=lens, kind="hero",
                                        target=it["id"], angle=ang, dist=dist))
    return best[1] if best else None


# ----------------------------------------------------------------------------- 글

def _cm(v):
    return int(round(v / 10.0))


def _hpos(x):
    return ("far left" if x < 0.2 else "left" if x < 0.4 else "center" if x < 0.6 else "right" if x < 0.8 else "far right")


HPOS_KO = {"far left": "맨 왼쪽", "left": "왼쪽", "center": "가운데", "right": "오른쪽", "far right": "맨 오른쪽"}


def _vpos(y):
    return "upper" if y < 0.38 else "middle" if y < 0.66 else "lower"


VPOS_KO = {"upper": "위", "middle": "가운데 높이", "lower": "아래"}


def _wall_rel(side, cam):
    n = NORMAL[side]
    f, r = cam.fwd2(), cam.right2()
    df, dr = n[0] * f[0] + n[1] * f[1], n[0] * r[0] + n[1] * r[1]
    if df < -0.5:
        return "near" if abs(dr) < 0.5 else ("near-left" if dr < 0 else "near-right")
    if df > 0.85:
        return "far"
    if df > 0.35:                      # 대각선으로 볼 때 정면에 보이는 두 벽
        return "far-left" if dr < 0 else "far-right"
    return "left" if dr < 0 else "right"


WALL_KO = {"far": "정면 벽", "far-left": "정면 왼쪽 벽", "far-right": "정면 오른쪽 벽",
           "left": "왼쪽 벽", "right": "오른쪽 벽", "near": "카메라 뒤 벽",
           "near-left": "카메라 왼쪽 뒤 벽", "near-right": "카메라 오른쪽 뒤 벽"}
REL_EN = {"far": "the far wall", "far-left": "the far-left wall", "far-right": "the far-right wall",
          "left": "the left wall", "right": "the right wall", "near": "the wall behind the camera",
          "near-left": "the wall just left of the camera, out of frame",
          "near-right": "the wall just right of the camera, out of frame"}


def _wall_desc(sc, side):
    """벽을 그 벽에 있는 것으로 부른다: 창 벽, 옷장 벽."""
    if any(m["side"] == side and m["op"]["type"] == "window" for m in sc.ops.values()):
        return "the window wall", "창 벽"
    on = [it for it in sc.items if _place_wall(it) == side and not it.get("on")]
    if on:
        big = max(on, key=lambda it: (it.get("size") or {}).get("w", 0))
        return "the wall with the {}".format(_label_en(big)), "{} 벽".format(P.label_of(big))
    if any(m["side"] == side for m in sc.ops.values()):
        return "the wall with the doorway", "문간 벽"
    return "a plain wall", "빈 벽"


def _place_wall(it):
    pl = it.get("place") or {}
    return pl.get("wall") if pl.get("wall") in NORMAL else None


def _room_space(house, room):
    kind = room.get("kind")
    if house.get("type") == "oneroom" and kind == "bedroom":
        return "the main room of a Korean one-room studio apartment (officetel)"
    if house.get("type") == "room":
        nm = room.get("name")
        return "a room in a Korean home{}".format(' used as "{}"'.format(nm) if nm else "")
    return "the {} of a Korean apartment".format(KIND_EN.get(kind, "room"))


def _look(it):
    if it.get("look"):
        return it["look"]
    p = it.get("product") or {}        # look 이 없으면 상품명만(옵션 문구는 그림에 잡음이다). plan 이 경고한다
    return p.get("title") or it.get("name") or P.label_of(it)


def _label_en(it):
    cat = it.get("category") or "item"
    return (it.get("label_en") or cat.replace("_", " "))


def describe(sc, cam, cv, st, house):
    """보이는 품목·창·문을 화면 위치와 함께 정리한다."""
    W, H = cam.w, cam.h
    A = float(W * H)
    rooms = {r["id"]: r for r in house.get("rooms", [])}
    room = sc.room
    rx0, ry0, rx1, ry1 = P.rr(room)
    byid = {it["id"]: it for it in sc.items}
    inv = {v: k for k, v in sc.iid.items()}
    vis = []
    for it in sc.items:
        iid = sc.iid[it["id"]]
        s = st.get(iid)
        if not s or s[0] < 30 or s[0] / A < 0.004:
            continue
        g = sc.ctx.geo[it["id"]]
        x0, y0, x1, y1 = g["rect"]
        cx, cy = (x0 + x1) / 2.0, (y0 + y1) / 2.0
        frac = s[0] / float(cv.drawn[iid] or 1)
        occ = [(v, inv.get(b)) for (a, b), v in cv.occ.items() if a == iid and b in inv]
        occ.sort(key=lambda t: -t[0])
        dist = math.hypot(max(x0 - cam.x, 0, cam.x - x1), max(y0 - cam.y, 0, cam.y - y1))
        vis.append(dict(it=it, iid=iid, share=s[0] / A, hx=s[1] / s[0] / W, vy=s[2] / s[0] / H,
                        cut_l=s[3] <= 0, cut_r=s[4] >= W - 1, frac=frac,
                        occluder=occ[0][1] if occ and frac < 0.6 else None, dist=dist, center=(cx, cy)))
    vis.sort(key=lambda v: v["hx"])
    lines, checks, board = [], [], []
    for n, v in enumerate(vis, 1):
        it = v["it"]
        g = sc.ctx.geo[it["id"]]
        sz = it.get("size") or {}
        hpos, vp = _hpos(v["hx"]), _vpos(v["vy"])
        depth = "foreground" if v["dist"] < 1200 else "middle ground" if v["dist"] < 2600 else "background"
        parts = ["{}, {}".format(hpos if vp == "middle" else "{} {}".format(vp, hpos), depth)]
        wall = _place_wall(it)
        if it.get("on") and it["on"] in byid:
            parts.append("on the {}".format(_label_en(byid[it["on"]])))
        elif it.get("with") and it["with"] in byid:
            parts.append("at the {}".format(_label_en(byid[it["with"]])))
        elif wall:
            rel = _wall_rel(wall, cam)
            L = (rx1 - rx0) if wall in "ns" else (ry1 - ry0)
            txt = "{} to {}".format("head end" if it.get("category") == "bed" else "back", REL_EN[rel])
            if not rel.startswith("near"):
                txt += " ({}% of its {} cm)".format(int(round(100.0 * (sz.get("w") or 0) / L)), _cm(L))
            parts.append(txt)
        else:
            parts.append("free-standing")
        Fv = NORMAL[g["facing"]]
        tc = (cam.x - v["center"][0], cam.y - v["center"][1])
        Ln = math.hypot(*tc) or 1.0
        c = (Fv[0] * tc[0] + Fv[1] * tc[1]) / Ln
        f2, r2 = cam.fwd2(), cam.right2()
        ff, fr = Fv[0] * f2[0] + Fv[1] * f2[1], Fv[0] * r2[0] + Fv[1] * r2[1]
        if abs(fr) >= abs(ff):          # 정면(침대는 발치)이 화면 어느 쪽을 향하나
            way = "to frame right" if fr > 0 else "to frame left"
        else:
            way = "away from the camera" if ff > 0 else "toward the camera"
        if it.get("category") == "bed":
            orient = ("foot end faces camera" if c > 0.75 else "seen from the head end" if c < -0.75
                      else "seen side-on, foot end pointing {}".format(way))
        else:
            orient = ("front faces camera" if c > 0.75 else "seen from behind" if c < -0.75
                      else "seen side-on, front turned {}".format(way))
        parts.append(orient)
        if v["occluder"]:
            parts.append("partly behind the {}".format(_label_en(byid[v["occluder"]])))
        if v["cut_l"] or v["cut_r"]:
            parts.append("cut off at the {} edge".format("left" if v["cut_l"] else "right"))
        col = sc.color[it["id"]][1]
        has_img = bool((it.get("product") or {}).get("image")) and not it.get("owned")
        made = ""
        if it.get("category") == "bed":
            top = max(z1 for _, _, z1 in sc.boxes[it["id"]]) - base_z(sc.ctx, it)
            made = " Made up with mattress and bedding, {} cm high on top.".format(_cm(top))
        lines.append("{}. {} ({} box): {}. {}x{}x{} cm.{} {}.".format(
            n, _label_en(it).capitalize(), col, _look(it), _cm(sz.get("w", 0)), _cm(sz.get("d", 0)),
            _cm(sz.get("h", 0) or item_height(it, g)), made, "; ".join(parts).capitalize()))
        checks.append("{}. {} — 화면 {}{}, {}".format(
            n, P.label_of(it), HPOS_KO[hpos], "" if vp == "middle" else " " + VPOS_KO[vp],
            {"foreground": "가까이", "middle ground": "중간 거리", "background": "멀리"}[depth]))
        if has_img:
            board.append(dict(item=it["id"], n=n, label=_label_en(it)))
    ops = []
    for oid, m in sc.ops.items():
        s = st.get(oid)
        if not s or s[0] / A < 0.003:
            continue
        o = m["op"]
        rel = _wall_rel(m["side"], cam)
        hp = _hpos(s[1] / s[0] / W)
        if o["type"] == "window":
            ops.append("a {} cm wide window on {} ({}), sill {} cm, sheer curtains".format(
                _cm(o["b"] - o["a"]), REL_EN[rel], hp, _cm(o.get("sill", 900))))
            checks.append("창 — {}, 화면 {}".format(WALL_KO[rel], HPOS_KO[hp]))
        else:
            other = o.get("to") if o["room"] == room["id"] else o["room"]
            dest = "outside" if other == "outside" else ("the " + KIND_EN.get(rooms.get(other, {}).get("kind"), "next room"))
            ops.append("{} to {} on {} ({})".format(
                "an open doorway" if o["type"] == "opening" else "a door", dest, REL_EN[rel], hp))
            checks.append("{} — {}, 화면 {}".format("트인 문간" if o["type"] == "opening" else "문", WALL_KO[rel], HPOS_KO[hp]))
    return vis, lines, ops, checks, board


def build_prompt(house, concept, ratio, cam, kind_txt, view, lines, ops, board, refs):
    R = RATIOS[ratio]
    room = view["room"]
    rx0, ry0, rx1, ry1 = P.rr(room)
    C = (house.get("photo") or {}).get("ceiling", DEFAULT_CEIL)
    tilt = ("camera level so vertical lines stay vertical" if abs(cam.pitch) < math.radians(3)
            else "camera tilted slightly down" if cam.pitch < 0 else "camera tilted slightly up")
    out = [COMMON_LOOK, concept["mood"],
           "Camera: {} photo, {:.0f} mm full-frame-equivalent lens, camera height {} cm, {}.".format(
               R[4], cam.lens_mm, _cm(cam.z), tilt),
           "Space: {}, {:.1f} m x {:.1f} m, ceiling {:.1f} m. Walls: {}. Floor: {}. Light: {}.".format(
               view["space"], (rx1 - rx0) / 1000.0, (ry1 - ry0) / 1000.0, C / 1000.0,
               concept["walls"], concept["floor"], concept["light"]),
           "View: {}.".format(kind_txt)]
    if ops:
        out.append("In view: " + "; ".join(ops) + ".")
    out.append("Furniture in frame, left to right (frame position, depth; size W x D x H). Draw exactly these, at true scale:")
    out.extend(lines)
    out.append("Styling: {}. Small soft props only.".format(concept["props"]))
    rt = []
    for i, ref in enumerate(refs, 1):
        if ref["role"] == "master":
            rt.append(("Reference image {} is a photo of this same room from another angle: keep the identical walls, floor, "
                       "window, curtains, light, colors, bedding and props." if ref.get("same_room") else
                       "Reference image {} is a photo of another room in the same home: use the same wall and floor finishes, "
                       "window frames, light and styling.").format(i))
        elif ref["role"] == "sketch":
            rt.append("Reference image {} is a massing sketch of this exact camera view: match its perspective and the "
                      "position, size and proportion of every colored box. Box colors only label the items above "
                      "(pale blue = window, brown = door, dark gray = open doorway) and must never appear in the photo: "
                      "render every item in its real colors and materials, not as a box.".format(i))
        elif ref["role"] == "board":
            rt.append("Reference image {} is a board of the actual products, items {} in grid reading order: copy each "
                      "product's shape, color, material and details exactly, and ignore the props and rooms around them "
                      "in those photos.".format(i, ", ".join(str(b["n"]) for b in board)))
        elif ref["role"] == "product":
            rt.append("Reference image {} is the actual product photo of item {} ({}): copy its shape, color and material "
                      "exactly, and ignore the props around it.".format(i, ref["n"], ref["label"]))
    out.extend(rt)
    out.append(NEGATIVE)
    return "\n".join(out)


# ----------------------------------------------------------------------------- plan

def _view_text(sc, cam, spec, byid):
    rel = {sd: _wall_rel(sd, cam) for sd in NORMAL}
    fl = next((sd for sd in NORMAL if rel[sd] == "far-left"), None)
    fr = next((sd for sd in NORMAL if rel[sd] == "far-right"), None)
    if fl and fr:
        (le, lk), (re_, rk) = _wall_desc(sc, fl), _wall_desc(sc, fr)
        toward = "diagonally across to the far corner, {} on the left and {} on the right".format(le, re_)
        toward_ko = "건너편 모서리({} · {})".format(lk, rk)
    else:
        fe, fk = _wall_desc(sc, _wall_hit(sc.room, cam.x, cam.y, cam.yaw))
        toward, toward_ko = "straight toward {}".format(fe), fk
    if spec["kind"] == "hero":
        it = byid[spec["target"]]
        g = sc.ctx.geo[it["id"]]
        F = NORMAL[g["facing"]]
        rgt = (-F[1], F[0])
        x0, y0, x1, y1 = g["rect"]
        vx, vy = cam.x - (x0 + x1) / 2.0, cam.y - (y0 + y1) / 2.0
        a = math.degrees(math.atan2(vx * rgt[0] + vy * rgt[1], vx * F[0] + vy * F[1]))   # 직접 적은 컷도 자리로 잰다
        sgn = vx * rgt[0] + vy * rgt[1]
        sd, sd_ko = ("right", "오른쪽") if sgn > 0 else ("left", "왼쪽")
        if abs(a) < 10:
            where, where_ko = "the front", "정면"
        elif abs(a) < 75:
            where, where_ko = "its front-" + sd, "앞 " + sd_ko
        elif abs(a) < 135:
            where, where_ko = "its {} side".format(sd), sd_ko + " 옆"
        else:
            where, where_ko = "behind", "뒤"
        if it.get("category") == "bed":
            where = where.replace("the front", "the foot end").replace("front", "foot")
        en = "a closer product shot of the {} from {}, about {:.1f} m away".format(
            _label_en(it), where, spec.get("dist", 1000) / 1000.0)
        ko = "{} {}에서 가까이".format(P.label_of(it), where_ko)
        return en, ko
    if spec.get("where") == "door" and spec.get("door") in sc.ops:
        o = sc.ops[spec["door"]]["op"]
        other = o.get("to") if o["room"] == sc.room["id"] else o["room"]
        rm = {r["id"]: r for r in sc.ctx.rooms.values()}.get(other) if other != "outside" else None
        frm = "the entrance door" if other == "outside" else "the doorway from the {}".format(
            KIND_EN.get(rm.get("kind") if rm else None, "next room"))
        frm_ko = "현관문" if other == "outside" else "{} 쪽 문간".format(
            P.KIND_KO.get(rm.get("kind") or "", "옆 방") if rm else "옆 방")
        return ("a wide shot standing at {}, looking {}".format(frm, toward),
                "{}에서 {} 쪽을 본다".format(frm_ko, toward_ko))
    return ("a wide shot from a corner of the room, looking {}".format(toward),
            "방 모서리에서 {} 쪽을 본다".format(toward_ko))


def plan(house, out_dir, max_hero=6, ratio=None):
    ctx, _ = P.check(house)
    ph = house.get("photo") or {}
    ratio = ratio or ph.get("ratio", "9:16")
    if ratio not in RATIOS:
        raise SystemExit("ratio 는 {} 중 하나다".format(", ".join(RATIOS)))
    concept = concept_of(house)
    ceil = ph.get("ceiling", DEFAULT_CEIL)
    cam_h = ph.get("camera_height", 1200)
    W, H, size, sw, _ = RATIOS[ratio]
    byid = {it["id"]: it for it in ctx.items}
    review = {it["id"] for it in ctx.items if P.reviewable(it)}
    rooms = [r for r in ctx.rooms.values() if any(it["room"] == r["id"] for it in ctx.items)]
    rooms.sort(key=lambda r: -sum(1 for it in ctx.items if it["room"] == r["id"]))
    if not rooms:
        raise SystemExit("가구가 놓인 방이 없다. room-set-planner 로 먼저 배치한다")
    os.makedirs(os.path.join(out_dir, "sketch"), exist_ok=True)
    specs = []
    manual = ph.get("shots")
    if manual:
        for i, m in enumerate(manual, 1):
            room = ctx.rooms[m["room"]]
            yaw = math.radians(m["yaw"]) if "yaw" in m else math.atan2(m["look_at"][1] - m["y"], m["look_at"][0] - m["x"])
            specs.append(dict(id=m.get("id", "shot-{}".format(i)), room=room["id"], x=m["x"], y=m["y"],
                              z=m.get("h", cam_h), yaw=yaw, pitch=math.radians(m.get("pitch", 0)),
                              lens=m.get("lens", WIDE_LENS), kind=m.get("kind", "wide"), target=m.get("target"),
                              where="manual", cyf=HORIZON[ratio] if not m.get("pitch") else 0.5))
    else:
        heroes = 0
        for room in rooms:
            sc = Scene(ctx, room, ceil)
            pre = "" if len(rooms) == 1 else room["id"] + "-"
            for k, s in enumerate(plan_wide(sc, ratio, cam_h, review), 1):
                s.update(id="{}wide-{}".format(pre, k), room=room["id"])
                specs.append(s)
            for it in sc.items:
                if it["id"] not in review or heroes >= max_hero:
                    continue
                s = plan_hero(sc, it, ratio)
                if s:
                    s.update(id="hero-{}".format(re.sub(r"[^A-Za-z0-9_-]", "_", it["id"])), room=room["id"])
                    specs.append(s)
                    heroes += 1
    if not specs:
        raise SystemExit("찍을 자리를 찾지 못했다. photo.shots 로 카메라를 직접 적는다")
    master_of_room, global_master = {}, None
    rank = {r["id"]: i for i, r in enumerate(rooms)}
    for s in sorted(specs, key=lambda x: (rank.get(x["room"], 99), not x.get("window"))):  # 창이 보이는 와이드가 빛·창틀의 기준
        if s["kind"] == "wide" and s["room"] not in master_of_room:
            master_of_room[s["room"]] = s["id"]
            global_master = global_master or s["id"]
    global_master = global_master or specs[0]["id"]
    has_ffmpeg = bool(shutil.which("ffmpeg"))
    shots = []
    for s in specs:
        room = ctx.rooms[s["room"]]
        sc = Scene(ctx, room, ceil)
        hfov = 2 * math.atan((sw / 2.0) / s["lens"])
        cam = Cam(s["x"], s["y"], s["z"], s["yaw"], s["pitch"], hfov, W, H, s["lens"], s.get("cyf", 0.5))
        cv = sc.render(cam)
        st = cv.stats()
        sketch = os.path.join("sketch", s["id"] + ".png")
        cv.png(os.path.join(out_dir, sketch))
        vis, lines, ops, checks, board = describe(sc, cam, cv, st, house)
        refs = []
        is_master = s["id"] == global_master
        if not is_master:
            m = master_of_room.get(s["room"])
            if m and m != s["id"]:
                refs.append(dict(role="master", shot=m, same_room=True))
            else:
                refs.append(dict(role="master", shot=global_master, same_room=False))
        refs.append(dict(role="sketch", file=sketch))
        if board:
            if has_ffmpeg:
                if len(board) > 6:
                    board = sorted(board, key=lambda b: -next(v["share"] for v in vis if v["it"]["id"] == b["item"]))[:6]
                    board.sort(key=lambda b: b["n"])
                refs.append(dict(role="board", file=os.path.join("boards", s["id"] + ".png"),
                                 items=[b["item"] for b in board]))
            else:
                pick = next((b for b in board if b["item"] == s.get("target")), None) or max(
                    board, key=lambda b: next(v["share"] for v in vis if v["it"]["id"] == b["item"]))
                refs.append(dict(role="product", item=pick["item"], n=pick["n"], label=pick["label"],
                                 url=(byid[pick["item"]].get("product") or {}).get("image")))
                board = []
        en, ko = _view_text(sc, cam, s, byid)
        prompt = build_prompt(house, concept, ratio, cam, en,
                              dict(room=room, space=_room_space(house, room)), lines, ops, board, refs)
        checks.append("목록 밖 가구·가전·러그·액자가 없다")
        if board:
            checks.append("제품 모양·색이 보드와 같다")
        if not is_master:
            checks.append("벽지·바닥·창틀·커튼·빛이 대표 컷과 같다")
        shots.append(dict(
            id=s["id"], kind=s["kind"], room=s["room"], master=is_master, title=ko,
            camera=dict(x=int(round(s["x"])), y=int(round(s["y"])), height=int(round(s["z"])),
                        yaw_deg=round(math.degrees(s["yaw"]), 1), pitch_deg=round(math.degrees(s["pitch"]), 1),
                        lens_mm=s["lens"], hfov_deg=round(math.degrees(hfov), 1)),
            target=s.get("target"),
            items=[dict(id=v["it"]["id"], label=P.label_of(v["it"]), share=round(v["share"], 3),
                        x=round(v["hx"], 2), hidden=round(1 - v["frac"], 2)) for v in vis],
            refs=refs, prompt=prompt, prompt_chars=len(prompt), checks=checks))
    order = sorted(shots, key=lambda x: (not x["master"], x["kind"] != "wide"))
    seen = {i["id"] for sh in shots for i in sh["items"]}
    no_look = [it["id"] for it in ctx.items if it["id"] in seen and not it.get("look")]
    data = dict(house=house.get("name"), concept=concept["key"], concept_ko=concept["ko"], ratio=ratio, image_size=size,
                missing_look=no_look,
                created=datetime.date.today().isoformat(), shots=order)
    with open(os.path.join(out_dir, "shots.json"), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    with open(os.path.join(out_dir, "shots.md"), "w", encoding="utf-8") as f:
        f.write(shots_md(data))
    with open(os.path.join(out_dir, "shots.svg"), "w", encoding="utf-8") as f:
        f.write(shots_svg(house, ctx, order))
    return data


def shots_md(data):
    out = ["# {} 촬영 컷".format(data["house"] or ""), "",
           "컨셉: {} · 프로젝트 비율 {} (그림 {}) · 컷 {}개".format(data["concept_ko"], data["ratio"],
                                                            data["image_size"], len(data["shots"])),
           "카메라 자리와 보는 방향: `shots.svg` · 덩어리 스케치: `sketch/` · 제품 보드: `boards/`(board 명령)", "",
           "만드는 순서: **대표 컷을 먼저 만들고 확인한 뒤**, 그 그림을 나머지 컷의 레퍼런스 1번으로 넣는다.", ""]
    for i, s in enumerate(data["shots"], 1):
        cam = s["camera"]
        out.append("## {}. `{}` — {}{}".format(i, s["id"], s["title"], " ★ 대표 컷(먼저 만든다)" if s["master"] else ""))
        out.append("")
        out.append("- 카메라: ({:,}, {:,}) mm · 높이 {}cm · 렌즈 {:.0f}mm(화각 {}°) · 기울기 {}°".format(
            cam["x"], cam["y"], cam["height"] // 10, cam["lens_mm"], cam["hfov_deg"], cam["pitch_deg"]))
        out.append("- 보이는 품목(왼→오): " + (", ".join(
            "{}({:.0%}{})".format(it["label"], it["share"], ", 일부 가림" if it["hidden"] > 0.4 else "")
            for it in s["items"]) or "없음"))
        refs = []
        for k, r in enumerate(s["refs"], 1):
            if r["role"] == "master":
                refs.append("{}) `{}` 에서 만든 그림({})".format(k, r["shot"], "같은 방" if r.get("same_room") else "같은 집"))
            elif r["role"] == "product":
                refs.append("{}) 제품 사진 {}".format(k, r.get("url")))
            else:
                refs.append("{}) `{}`".format(k, r["file"]))
        out.append("- 레퍼런스: " + " · ".join(refs))
        out.append("- 확인할 것:")
        for c in s["checks"]:
            out.append("  - [ ] " + c)
        out.append("")
        out.append("```text")
        out.append(s["prompt"])
        out.append("```")
        out.append("")
    return "\n".join(out)


def shots_svg(house, ctx, shots):
    _, svg = P.render(house)
    rects = [P.rr(r) for r in ctx.rooms.values()]
    Wd = max(r[2] for r in rects) - min(r[0] for r in rects)
    Hd = max(r[3] for r in rects) - min(r[1] for r in rects)
    fs = max(Wd, Hd) / 62.0
    add = []
    for i, s in enumerate(shots, 1):
        c = s["camera"]
        x, y = c["x"], c["y"]
        yaw = math.radians(c["yaw_deg"])
        hf = math.radians(c["hfov_deg"]) / 2.0
        L = fs * 11
        p1 = (x + L * math.cos(yaw - hf), y + L * math.sin(yaw - hf))
        p2 = (x + L * math.cos(yaw + hf), y + L * math.sin(yaw + hf))
        col = "#e8590c" if s["kind"] == "wide" else "#7048e8"
        add.append('<polygon points="{:.0f},{:.0f} {:.0f},{:.0f} {:.0f},{:.0f}" fill="{}" fill-opacity="0.16" '
                   'stroke="{}" stroke-width="{:.0f}"/>'.format(x, y, p1[0], p1[1], p2[0], p2[1], col, col, fs * 0.12))
        add.append('<circle cx="{:.0f}" cy="{:.0f}" r="{:.0f}" fill="{}"/>'.format(x, y, fs * 0.62, col))
        add.append('<text x="{:.0f}" y="{:.0f}" font-size="{:.0f}" fill="#ffffff" text-anchor="middle" '
                   'font-weight="700">{}</text>'.format(x, y + fs * 0.32, fs * 0.85, i))
    k = svg.rfind("</svg>")
    return svg[:k] + "\n".join(add) + "\n</svg>"


# ----------------------------------------------------------------------------- fetch · board

MAX_BYTES = 8 * 1024 * 1024
EXT = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp", "image/gif": "gif"}


def _safe(s):
    return re.sub(r"[^A-Za-z0-9_-]", "_", str(s))


def fetch(house, dest):
    if os.path.exists(dest) and os.listdir(dest):
        raise SystemExit("{} 가 비어 있지 않다. 새 빈 디렉터리를 준다(내려받은 파일은 믿을 수 없는 데이터다)".format(dest))
    os.makedirs(dest, exist_ok=True)
    got = 0
    for it in house.get("items", []):
        if it.get("owned") or it.get("placeholder"):
            continue
        url = (it.get("product") or {}).get("image") or ""
        if not url.startswith("https://"):
            print("  - {}: 대표 사진 주소가 없다(https 만 받는다)".format(it.get("id")))
            continue
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=20) as r:
                ct = r.headers.get_content_type()
                data = r.read(MAX_BYTES + 1)
        except Exception as e:  # noqa: BLE001
            print("  - {}: 받지 못했다({})".format(it["id"], e))
            continue
        if ct not in EXT or len(data) > MAX_BYTES:
            print("  - {}: 이미지가 아니거나 너무 크다({}, {} bytes)".format(it["id"], ct, len(data)))
            continue
        path = os.path.join(dest, "{}.{}".format(_safe(it["id"]), EXT[ct]))
        with open(path, "wb") as f:
            f.write(data)
        got += 1
        print("  {} ← {}".format(os.path.basename(path), url))
    print("{}장 받았다 → {}".format(got, dest))


def _image_for(images, item):
    for ext in ("jpg", "png", "webp", "gif"):
        p = os.path.join(images, "{}.{}".format(_safe(item), ext))
        if os.path.isfile(p):
            return p
    return None


def make_board(files, out, cell=512):
    n = len(files)
    cols = 1 if n == 1 else (2 if n <= 4 else 3)
    rows = (n + cols - 1) // cols
    total = cols * rows
    args = ["ffmpeg", "-y", "-loglevel", "error"]
    for f in files:
        args += ["-i", f]
    for _ in range(total - n):
        args += ["-f", "lavfi", "-i", "color=c=white:s={0}x{0}:d=1".format(cell)]
    fc = []
    for i in range(total):
        if i < n:
            fc.append("[{i}:v]scale={c}:{c}:force_original_aspect_ratio=decrease,pad={c}:{c}:(ow-iw)/2:(oh-ih)/2:color=white,"
                      "setsar=1,format=rgb24[v{i}]".format(i=i, c=cell))
        else:
            fc.append("[{i}:v]setsar=1,format=rgb24[v{i}]".format(i=i))
    if total == 1:
        fc[0] = fc[0].replace("[v0]", "[out]")
    else:
        layout = "|".join("{}_{}".format((i % cols) * cell, (i // cols) * cell) for i in range(total))
        fc.append("".join("[v{}]".format(i) for i in range(total)) + "xstack=inputs={}:layout={}[out]".format(total, layout))
    args += ["-filter_complex", ";".join(fc), "-map", "[out]", "-frames:v", "1", out]
    subprocess.run(args, check=True)


def board(shots_path, images, out_dir=None):
    if not shutil.which("ffmpeg"):
        raise SystemExit("ffmpeg 가 없다. 설치하거나, plan 을 다시 돌리면 보드 대신 제품 사진 한 장을 레퍼런스로 쓴다")
    with open(shots_path, encoding="utf-8") as f:
        data = json.load(f)
    base = os.path.dirname(os.path.abspath(shots_path))
    missing, made = [], 0
    for s in data["shots"]:
        for r in s["refs"]:
            if r["role"] != "board":
                continue
            files = [_image_for(images, i) for i in r["items"]]
            lack = [i for i, p in zip(r["items"], files) if not p]
            if lack:
                missing.append("{}: {}".format(s["id"], ", ".join(lack)))
                continue
            out = os.path.join(out_dir or base, r["file"]) if not out_dir else os.path.join(out_dir, os.path.basename(r["file"]))
            os.makedirs(os.path.dirname(out), exist_ok=True)
            make_board(files, out)
            made += 1
            print("  {} ← {}".format(os.path.relpath(out, base), ", ".join(r["items"])))
    if missing:
        print("사진이 없어 못 만든 보드 — 그 제품 사진을 받거나 house.json 의 product.image 를 고치고 plan 부터 다시:")
        for m in missing:
            print("  - " + m)
    print("보드 {}장".format(made))
    return 1 if missing else 0


# ----------------------------------------------------------------------------- CLI

def main(argv=None):
    ap = argparse.ArgumentParser(description="house.json → 촬영 컷·프롬프트·레퍼런스")
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("plan")
    a.add_argument("house")
    a.add_argument("-o", "--out")
    a.add_argument("--max-hero", type=int, default=6)
    a.add_argument("--ratio", choices=sorted(RATIOS))
    b = sub.add_parser("fetch")
    b.add_argument("house")
    b.add_argument("dest")
    c = sub.add_parser("board")
    c.add_argument("shots")
    c.add_argument("--images", required=True)
    c.add_argument("-o", "--out")
    args = ap.parse_args(argv)
    if args.cmd == "plan":
        house = P.load(args.house)
        out = args.out or os.path.join(os.path.dirname(os.path.abspath(args.house)), "photos")
        data = plan(house, out, args.max_hero, args.ratio)
        print("{} · 컨셉 {} · 비율 {} · 컷 {}개 → {}".format(data["house"], data["concept_ko"], data["ratio"],
                                                         len(data["shots"]), out))
        for i, s in enumerate(data["shots"], 1):
            print("  {}. {:<18} {} · 보이는 품목 {} · 프롬프트 {}자{}".format(
                i, s["id"], s["title"], len(s["items"]), s["prompt_chars"], " ★대표" if s["master"] else ""))
            if s["prompt_chars"] > 3800:
                print("     ⚠ 프롬프트가 DemoCut 한도(4,000자)에 가깝다. look 을 줄인다")
        if data["missing_look"]:
            print("⚠ look 이 없는 품목: {} — 제품 사진을 보고 items[].look 에 영어 한 문장을 적은 뒤 plan 을 다시 돌린다"
                  "(없으면 상품명이 들어가 모양이 틀어진다)".format(", ".join(data["missing_look"])))
        return 0
    if args.cmd == "fetch":
        fetch(P.load(args.house), args.dest)
        return 0
    return board(args.shots, args.images, args.out)


if __name__ == "__main__":
    sys.exit(main())
