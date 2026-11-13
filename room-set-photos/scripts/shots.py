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
NEAR_CUT = 1500             # 넓은 컷에서 이보다 가까운 큰 가구가 화면 끝에 잘려 걸리면 크기가 틀어진다(mm)
NEIGHBOR_SHARE = 0.03       # 트인 문간 너머 방이 화면의 이만큼 넘게 보이면 그 방의 사진도 레퍼런스로 넣는다(칸이 남을 때)
THROUGH = 2000              # 문간 너머 방 품목의 그림 id 시작(이 방 품목 1~, 창·문 1000~)
THROUGH_MIN = 0.01          # 문간 너머가 화면의 이만큼 안 되는 가는 띠면 그 방을 글로 적지 않는다(스케치에는 그린다)
THROUGH_OP_MIN = 0.002      # 문간 너머 방의 창·문이 화면의 이만큼 넘게 보이면 글로 적는다
WALL_WIDE = 0.9             # 트인 개구부가 그 벽 길이의 이만큼을 넘으면 「그 벽 전체가 트였다」 로 적는다
FILL_GAP = 30               # 벽에 붙은 가구가 그 벽보다 이만큼(mm) 안 되게 좁으면 「벽을 모서리까지 채운다」 로 적는다
WIDE_CLOSE = 750            # 전체 컷에서 화면을 크게 차지한 가구가 이보다 가까우면 점수를 깎는다(mm)
BIG_CUT = 600               # 그 검사를 받는 가구의 바닥 긴 변(mm)
NEAR_GAP = 100              # 바닥 가구 둘 사이가 이보다 좁으면 사이를 적는다. 안 적으면 붙거나 한쪽이 밑으로 파고든다(mm)
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
BOARD_CELLS = 4             # 제품 보드 한 장의 칸 수(2×2 × 512px = 1024px, DemoCut 레퍼런스 상자에서 줄지 않는다)
PROMPT_MAX = 4000           # DemoCut ai_image 프롬프트 한도

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

COMMON_LOOK = ("A real photo from an Ohouse (오늘의집) house-tour post, shot by the resident on a smartphone: "
               "phone-photo texture, muted natural colors, low contrast, light sensor noise, tidy but lived-in, "
               "not a 3D render or a staged ad.")
HOME_DETAILS = ("Korean home details: white PVC double-sash windows, white baseboards, silk wallpaper, "
                "a flat round LED ceiling light.")
# 공간 종류마다 마감·소품이 다르다. 방의 벽지·마루·침구 문장을 그대로 쓰면 화장실이 벽지·마루로 나오고 주방·현관에 침구
# 소품이 붙는다(2026-11-13 원룸 계획에서 확인). {walls}·{floor} 는 컨셉 값. photo.rooms.<종류 또는 방 id> 로 덮어쓴다
KIND_FINISH = {
    "bathroom": dict(
        walls="glossy white ceramic wall tiles from floor to ceiling",
        floor="light gray non-slip ceramic floor tiles sloping to a floor drain",
        details="Korean bathroom details: tiled walls and floor, a floor drain, a raised threshold at the door, "
                "a flat square LED ceiling light.",
        props="a white towel on a wall hook, a soap dispenser and a toothbrush cup by the basin"),
    "entrance": dict(
        floor="gray porcelain floor tiles, one step below the next room's floor",
        props="one pair of white sneakers on the floor tiles"),
    "kitchen": dict(
        walls="{walls}, with white ceramic tiles on the wall behind the counter",
        props="a few dishes in the dish rack, a white electric kettle, a folded dish towel"),
}
LIVING_KINDS = {"bedroom", "living", "dressroom", None}   # 컨셉 소품(침구·책)이 맞는 공간. None = 종류를 안 적은 방
FINISH_KEYS = ("walls", "floor", "details", "props")


def negative(concept, extra=()):
    """Avoid 줄. 식물은 사용자가 원할 때만(photo.plants) 넣고, 그 밖에는 막는다. extra 는 보이는 품목의 가구별 규칙이 더한다."""
    # 「glossy」 를 막으면 유광 제품(일광전구 스노우맨 갓)도 무광으로 바뀐다 — 광고 사진 같은 광만 막는다(2026-11-13)
    return ("Avoid: people, pets, text, logos, watermarks, fisheye distortion, CGI look, HDR glow, oversaturated colors, "
            "a glossy ad look, sharp sun patches or light rays, {}furniture floating, intersecting or squeezed under something "
            "lower, {}and any object that is not listed.").format(
                "" if concept.get("plants") else "plants or flowers, ", "".join(a + ", " for a in extra))


PLANTS = "one or two small plants in ceramic pots"   # photo.plants: true 일 때
CURTAINS = "sheer curtains"                          # photo.curtains 가 없을 때 창에 거는 것
# photo.view 가 없을 때의 창밖: 집 유형 → (프롬프트, 확인 목록, Avoid). 적지 않으면 모델은 한국 집 창밖에 아파트 단지를 그린다.
# 원룸은 보통 빌라라 창밖이 바로 옆 빌라다(2026-11-13 사용자 지적: 원룸 창밖에 고층 아파트 단지가 보였다)
VIEWS = {"oneroom": ("facing the next villa's wall and windows 4 m away",
                     "창밖 — 4m 앞 건너편 빌라의 벽과 창(아파트 단지가 아니다)", "apartment towers")}
OPENING_LEGEND = ((WINDOW, "pale blue = window"), (DOOR, "brown = door"), (VOID, "dark gray = open doorway"))

CONCEPTS = {
    "natural": dict(
        ko="내추럴 우드",
        mood="Warm natural-wood style: light oak, white, beige linen and a little rattan.",
        walls="white silk wallpaper", floor="light natural-oak laminate flooring",
        light="soft cream-toned daylight from the window, diffuse with no direct sun on the floor, gentle shadows",
        props="white and beige linen bedding, a knit throw, a few books"),
    "minimal": dict(
        ko="화이트 미니멀",
        mood="Clean white minimal style: white, pale gray and light wood, almost nothing on surfaces.",
        walls="white silk wallpaper", floor="pale whitewashed oak laminate flooring",
        light="bright, even daylight with soft shadows, neutral white balance",
        props="crisp white bedding, a few neatly stacked books"),
    "modern": dict(
        ko="모던 그레이",
        mood="Modern monotone style: warm gray, white and black metal accents.",
        walls="light warm-gray wallpaper", floor="gray-beige oak laminate flooring",
        light="soft overcast daylight, calm and even",
        props="charcoal and gray bedding, black desk accessories"),
    "midcentury": dict(
        ko="미드센추리 빈티지",
        mood="Mid-century vintage style: walnut tones with mustard and olive accents and rounded shapes.",
        walls="warm ivory wallpaper", floor="medium-brown oak laminate flooring",
        light="warm late-afternoon sunlight with long soft shadows",
        props="mustard and olive bedding, empty ceramic vases, a stack of records and books"),
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
    base: dict = dict(CONCEPTS.get(c, CONCEPTS["natural"]))
    if c not in CONCEPTS:                         # 자유 문장이면 분위기로 쓰고 나머지는 natural 값
        base.update(ko=str(c), mood=str(c))
    for k in ("mood", "walls", "floor", "light", "props"):
        if ph.get(k):
            base[k] = ph[k]
    plants = ph.get("plants")                     # 요청이 없으면 식물을 넣지 않는다
    base["plants"] = (PLANTS if plants is True else str(plants)) if plants else None
    base["curtains"] = ph.get("curtains") or CURTAINS
    v = ph.get("view")                            # 없으면 집 유형 기본값, false 면 적지 않는다(커튼을 친 방)
    base["view"] = VIEWS.get(house.get("type")) if v is None else ((str(v), "창밖 — " + str(v), None) if v else None)
    base["key"] = c
    return base


def room_finish(house, concept, room):
    """그 공간의 벽·바닥·공통 문장·소품. 컨셉 값 ← 공간 종류 기본(KIND_FINISH) ← photo.rooms.<종류> ← photo.rooms.<방 id>."""
    kind = room.get("kind")
    f = dict(walls=concept["walls"], floor=concept["floor"], details=HOME_DETAILS,
             props=concept["props"] if kind in LIVING_KINDS else None)
    for k, v in KIND_FINISH.get(kind, {}).items():
        f[k] = v.format(walls=concept["walls"], floor=concept["floor"])
    over = (house.get("photo") or {}).get("rooms") or {}
    for key in (kind, room["id"]):
        f.update({k: v for k, v in (over.get(key) or {}).items() if k in FINISH_KEYS})
    return f


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


MATTRESS_W = (1600, 1500, 1400, 1100, 1000)   # 한국 매트리스 폭: K · Q · D · SS · S (mm)
MATTRESS_L = 2000


def mattress_of(it):
    """침대 프레임에 올리는 매트리스 (폭, 길이)와 프레임이 드러나는 폭 (옆 한쪽, 끝 한쪽) mm. 음수면 매트리스가 프레임
    밖으로 나온다. items[].mattress 가 있으면 그 크기, 없으면 프레임에 들어가는 가장 큰 표준 매트리스다."""
    sz = it.get("size") or {}
    W, D = sz.get("w", 0), sz.get("d", 0)
    m = it.get("mattress") or {}
    if m.get("w") and m.get("d"):
        mw, md = m["w"], m["d"]
    else:
        mw = next((x for x in MATTRESS_W if x <= W), W)
        md = MATTRESS_L if D >= MATTRESS_L else D
    return mw, md, (W - mw) / 2.0, (D - md) / 2.0


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
    if cat == "bed":                   # 프레임과 매트리스를 따로: 매트리스가 프레임 위 어디에 놓이는지가 보이게
        top = 480 if h > 600 else max(300, min(h + 220, 560))     # 매트리스·침구 윗면
        frame = 250 if h > 600 else max(h, 20)                     # 머리판이 있으면 size.h 는 머리판 높이다
        _, _, side, end = mattress_of(it)
        ix, iy = (side, end) if f in "ns" else (end, side)
        out = [((x0, y0, x1, y1), b, b + frame), ((x0 + ix, y0 + iy, x1 - ix, y1 - iy), b + frame, b + top)]
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


def _draw(cv, cam, pts, color, iid=0):
    q = _clip_near([cam.to_cam(p) for p in pts])
    if len(q) < 3:
        return
    p2 = [cam.proj(v) for v in q]
    cv.fill(p2, color, iid)
    lw = max(1, cam.w // 340)
    for i in range(len(p2)):
        cv.line(p2[i], p2[(i + 1) % len(p2)], EDGE, lw)


def _reveal(o, top):
    """문간이 벽 두께를 지나는 네 면(양 옆·바닥·위). 두 방의 벽 선(line·other_line) 사이다."""
    l0, l1, a, b = o["line"], o["other_line"], o["a"], o["b"]

    def pt(u, v, z):                # u: 벽을 따라, v: 벽을 가로질러
        return (u, v, z) if o["axis"] == "x" else (v, u, z)
    return [([pt(u, l0, 0), pt(u, l1, 0), pt(u, l1, top), pt(u, l0, top)], WALLS["w"]) for u in (a, b)] + [
        ([pt(a, l0, z), pt(b, l0, z), pt(b, l1, z), pt(a, l1, z)], col) for z, col in ((0, FLOOR), (top, CEIL))]


class Scene:
    def __init__(self, ctx, room, ceil):
        self.ctx, self.room, self.ceil = ctx, room, ceil
        x0, y0, x1, y1 = P.rr(room)
        C = ceil
        self.shell = [         # (벽 이름 — 바닥·천장은 None, 다각형, 색)
            (None, [(x0, y0, 0), (x1, y0, 0), (x1, y1, 0), (x0, y1, 0)], FLOOR),
            (None, [(x0, y0, C), (x1, y0, C), (x1, y1, C), (x0, y1, C)], CEIL),
            ("n", [(x0, y0, 0), (x1, y0, 0), (x1, y0, C), (x0, y0, C)], WALLS["n"]),
            ("s", [(x0, y1, 0), (x1, y1, 0), (x1, y1, C), (x0, y1, C)], WALLS["s"]),
            ("w", [(x0, y0, 0), (x0, y1, 0), (x0, y1, C), (x0, y0, C)], WALLS["w"]),
            ("e", [(x1, y0, 0), (x1, y1, 0), (x1, y1, C), (x1, y0, C)], WALLS["e"]),
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

    def render(self, cam, skip=None):
        """skip: 그리지 않을 벽(이름). 옆 방에서 문간 너머로 이 방을 볼 때 둘이 나눠 쓰는 벽과 그 벽의 창·문을 뺀다."""
        cv = Canvas(cam.w, cam.h)

        def draw(pts, color, iid=0):
            _draw(cv, cam, pts, color, iid)
        for side, pts, col in self.shell:
            if side != skip:
                draw(pts, col)
        for oid, m in self.ops.items():
            if m["side"] != skip:
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


def see_through(sc, cam, cv):
    """트인 문간(문짝 없는 개구부) 자리에 그 너머 방을 같은 카메라로 그려 넣는다. 비워 두면 생성 모델은 너머 방을
    지어 그려, 같은 집의 그 방 컷과 다른 가구·마감이 나온다. 너머 방의 품목은 THROUGH 부터 id 를 받고
    cv.through[id] = (그 방 Scene, 품목, 문간 id) 로, 그려 넣은 문간은 cv.doorways[문간 id] = 그 방 Scene 으로 적는다
    (가구가 없는 방도 벽·바닥은 적어야 한다). 너머 방의 벽·바닥 픽셀은 문간 id 를 그대로 둔다.
    이 방 품목이나 선이 문간 앞을 가린 픽셀(문간 색이 아닌 픽셀)은 건드리지 않는다."""
    cv.through, cv.doorways, cv.through_ops = {}, {}, {}
    used = {c[1] for c in sc.color.values()}
    free = [c for c in PALETTE if c[1] not in used] or PALETTE      # 이 방 상자와 색이 겹치지 않게
    void, nxt, k = bytes(VOID), THROUGH, 0
    for oid, m in sc.ops.items():
        o = m["op"]
        other = o.get("to") if o["room"] == sc.room["id"] else o["room"]
        if o["type"] != "opening" or other not in sc.ctx.rooms:
            continue
        px = cv.px
        idx = [i for i, v in enumerate(cv.ids) if v == oid and px[i * 3:i * 3 + 3] == void]
        if not idx:
            continue
        nb = Scene(sc.ctx, sc.ctx.rooms[other], sc.ceil)
        side = next(n["side"] for n in nb.ops.values() if n["op"] is o)
        for it in nb.items:
            nb.color[it["id"]] = free[k % len(free)]
            k += 1
        ncv = nb.render(cam, skip=side)
        cv.doorways[oid] = nb
        for pts, col in _reveal(o, min(DOOR_H, sc.ceil - 100)):    # 벽 두께 — 너머 방의 무엇보다 카메라에 가깝다
            _draw(ncv, cam, pts, col)
        gid = {}
        for it in nb.items:
            gid[nb.iid[it["id"]]] = nxt
            cv.through[nxt] = (nb, it, oid)
            cv.drawn[nxt] = ncv.drawn[nb.iid[it["id"]]]
            nxt += 1
        bg = bytes(BG)
        ops = cv.through_ops[oid] = {}      # 너머 방의 창·문 id → [픽셀 수, x 합]. 글로 적을지는 describe_through 가 정한다
        for i in idx:
            if ncv.px[i * 3:i * 3 + 3] == bg:
                continue
            px[i * 3:i * 3 + 3] = ncv.px[i * 3:i * 3 + 3]
            v = ncv.ids[i]
            if 0 < v < 1000:
                cv.ids[i] = gid[v]
            elif v >= 1000:
                c = ops.setdefault(v, [0, 0])
                c[0] += 1
                c[1] += i % cv.w
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


def _visible_part(sc, cam, it):
    """품목 바닥 면을 9x9 점으로 나눠, 화면 가로 화각 안에 드는 점까지의 가장 가까운 거리(mm)와 그 점의 비율.
    화각 안에 드는 점이 없으면 (None, 0). 가장 가까운 점이 화면 밖이면 보이는 부분은 그보다 멀다."""
    x0, y0, x1, y1 = sc.ctx.geo[it["id"]]["rect"]
    z = base_z(sc.ctx, it) + item_height(it, sc.ctx.geo[it["id"]]) / 2.0
    best, n = None, 0
    for i in range(9):
        for j in range(9):
            p = (x0 + (x1 - x0) * i / 8.0, y0 + (y1 - y0) * j / 8.0, z)
            q = cam.to_cam(p)
            if q[2] <= NEAR or abs(cam.proj(q)[0] - cam.w / 2.0) > cam.w / 2.0:
                continue
            n += 1
            d = math.hypot(p[0] - cam.x, p[1] - cam.y)
            if best is None or d < best:
                best = d
    return best, n / 81.0


def near_cuts(sc, cam, st):
    """가까이 있는 큰 가구가 화면 왼쪽·오른쪽 끝에 절반 넘게 잘려 걸린 것: [(품목, 보이는 부분까지 거리 mm, "left"|"right")].
    모서리만 보이면 생성 모델은 크기를 가늠할 단서가 없고, 광각은 가장자리의 가까운 물체를 늘린다. 그래서 그 가구를
    다른 가구보다 크고 높게 그린다(2026-11-11 대표 컷의 책상이 바닥 면 6% 만 보여 서랍장보다 높은 탁자로 나왔다).
    침대처럼 대부분 보이고 끝만 잘린 가구는 길이로 크기가 읽히므로 넘어간다."""
    A = float(cam.w * cam.h)
    out = []
    for it in sc.items:
        s = st.get(sc.iid[it["id"]])
        if not s or s[0] / A < 0.004 or it.get("on") or P.CAT.get(it.get("category"), {}).get("floor"):
            continue
        sz = it.get("size") or {}
        if max(sz.get("w", 0), sz.get("d", 0)) < BIG_CUT:
            continue
        cut_l, cut_r = s[3] <= 0, s[4] >= cam.w - 1
        if not (cut_l or cut_r):
            continue
        d, frac = _visible_part(sc, cam, it)
        if d is not None and d < NEAR_CUT and frac < 0.5:
            out.append((it, d, "left" if cut_l else "right"))
    return out


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
        alongs = [(o["a"] + o["b"]) / 2.0]
        if o["b"] - o["a"] >= 1200:     # 벽이 통째로 트인 문간은 가운데 앞에 가구가 있기 쉽다. 양 끝에도 서 본다
            alongs += [o["a"] + ins, o["b"] - ins]
        for mid in alongs:
            p = (mid, line + inward * 420) if o["axis"] == "x" else (line + inward * 420, mid)
            cands.append((p, "door", oid))
    out = []
    for p, kind, oid in cands:
        q = p
        ok = sc.free(q)
        L = math.hypot(cx - p[0], cy - p[1]) or 1.0
        # 막혔으면 방 가운데 쪽으로 옮기되 가운데를 넘지 않는다. 넘으면 문간 자리가 반대편 끝으로 가서 「문간에 서서」
        # 라는 설명과 다른 데서 그 문간을 돌아본다(2026-11-13 주방: 침실 쪽 문간 자리가 1.2m 걸어 현관 앞으로 갔다)
        for k in range(1, 13):
            if ok or 100 * k > L:
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
        # 방 가운데를 보는 것을 기준으로 좌우 10°·20°·30° 도 본다. 좁은 방(욕실)은 가운데를 보면 변기·세면대가
        # 둘 다 화각 밖으로 나가고 샤워 커튼만 남는다
        for off in (0.0, -0.18, 0.18, -0.36, 0.36, -0.54, 0.54):
            yaw = math.atan2(cy - p[1], cx - p[0]) + off
            cam = Cam(p[0], p[1], cam_h, yaw, 0.0, hfov, w, h, cyf=HORIZON[ratio])
            cv = sc.render(cam)
            st = cv.stats()
            A = float(w * h)
            score, big, close = 0.0, 0.0, False
            for it in sc.items:
                s = _share(st, sc.iid[it["id"]], A)
                if not s:
                    continue
                wgt = 2.0 if it["id"] in review_ids else (0.3 if P.CAT.get(it.get("category"), {}).get("floor") else 1.0)
                score += wgt * min(1.0, s / 0.03)
                big = max(big, s)
                if s > 0.08 and not it.get("on") and not P.CAT.get(it.get("category"), {}).get("floor"):
                    d = _visible_part(sc, cam, it)[0]
                    close = close or (d is not None and d < WIDE_CLOSE)
            win = sum(st[k][0] for k in st if 1000 <= k < THROUGH and sc.ops[k]["op"]["type"] == "window") / A
            if win > 0.01:
                score += 1.5
            if big > 0.45:
                score -= 2.0
            # 큰 가구가 렌즈 바로 앞(WIDE_CLOSE 안)을 막는 전체 컷은 그 가구의 클로즈업이 된다(2026-11-13 주방: 싱크대 0.6m 앞)
            if close:
                score -= 1.5
            scored.append((score, p, yaw, kind, oid, win > 0.01, len(near_cuts(sc, cam, st))))
    scored.sort(key=lambda t: (t[6] > 0, -t[0]))    # 가까운 큰 가구가 끝에 잘려 걸린 자리는 다른 후보가 없을 때만
    picked = []
    shows = any(s[0] > 0 for s in scored)
    for s in scored:
        if s[0] <= 0 and (picked or shows):     # 품목도 창도 안 보이는 빈 벽은 고르지 않는다(2026-11-13 현관)
            continue
        # 둘째 컷은 가까운 큰 가구가 끝에 잘려 걸린 자리로 채우지 않는다. 좁은 방(주방 1.6m·욕실 1.9m)은 둘째 자리가
        # 대개 변기·싱크대에 렌즈를 붙인 그림이라, 없는 편이 낫다(2026-11-13)
        if picked and s[6] > 0:
            continue
        if all(abs(math.atan2(math.sin(s[2] - q[2]), math.cos(s[2] - q[2]))) > math.radians(60)
               or math.hypot(s[1][0] - q[1][0], s[1][1] - q[1][1]) > 1500 for q in picked):
            picked.append(s)
        if len(picked) == 2:
            break
    return [dict(x=p[0], y=p[1], z=cam_h, yaw=yaw, pitch=0.0, lens=WIDE_LENS, kind="wide", where=kind, door=oid,
                 cyf=HORIZON[ratio], window=win)
            for _, p, yaw, kind, oid, win, _ in picked]


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


def _opening(sc, m, cam):
    """트인 개구부(문짝 없음)를 부르는 말. 「open doorway」 라고만 적으면 모델은 그 자리에 벽을 세우고 문틀 달린 좁은 문을
    낸다(2026-11-13 주방·현관: 벽 전체 162cm 가 트인 자리에 벽과 문틀이 섰고 현관은 그 벽만큼 넓어졌다). 그래서 폭·높이를
    cm 로 적고, 벽을 거의 다 차지하면(WALL_WIDE) 그쪽에 벽이 없다고 적는다.
    돌려주는 것: the(너머 방 머리 줄의 「Through {the}」), a(In view 줄 — 「{to}」 자리에 부르는 쪽이 「 to the kitchen」 을
    끼운다), ko(확인 목록 말). 주방 컷은 프롬프트 한도(4,000자) 가까이라 말을 짧게 둔다."""
    o, side = m["op"], m["side"]
    x0, y0, x1, y1 = P.rr(sc.room)
    L = (x1 - x0) if side in "ns" else (y1 - y0)
    W, top = o["b"] - o["a"], min(DOOR_H, sc.ceil - 100)
    rel = REL_EN[_wall_rel(side, cam)]
    if W >= WALL_WIDE * L:              # 「the right wall」 → 「the open right wall」
        return dict(the="the open " + rel[len("the "):],
                    a=rel + " is fully open{to}, with no door frame",
                    ko="벽 전체가 트였다(폭 {}cm, 벽·문틀 없음)".format(_cm(W)))
    noun = "open doorway" if W < 1200 else "opening"
    return dict(the="the {} on {}".format(noun, rel),
                a="a {} cm wide, {} cm high {}{{to}} on {}".format(_cm(W), _cm(top), noun, rel),
                ko="트인 문간(폭 {}cm)".format(_cm(W)))


def light_direction(sc, cam, st):
    """창 빛을 카메라 기준으로 디렉팅한다: 어느 벽 창에서 들어와 어느 쪽으로 퍼지고 그림자가 어디로 지나.
    빛의 질(색·시간대)은 컨셉의 light 가 정하고, 여기서는 방향만 정한다. 창이 없는 방이면 (None, None)."""
    wins = [(oid, m) for oid, m in sc.ops.items()
            if m["op"]["type"] == "window" and m["op"]["room"] == sc.room["id"]]
    if not wins:
        return None, None
    oid, m = max(wins, key=lambda w: w[1]["op"]["b"] - w[1]["op"]["a"])
    rel = _wall_rel(m["side"], cam)
    n, f, r = NORMAL[m["side"]], cam.fwd2(), cam.right2()
    tf = -(n[0] * f[0] + n[1] * f[1])      # 빛이 나아가는 방향(창 → 방 안)의 깊이 성분. + 는 카메라에서 멀어진다
    tr = -(n[0] * r[0] + n[1] * r[1])      # 가로 성분. + 는 화면 오른쪽
    s = st.get(oid)
    seen = bool(s) and s[0] / float(cam.w * cam.h) >= 0.003
    en, ko = [], []
    if tr > 0.3:
        en.append("to the right"); ko.append("오른쪽")
    elif tr < -0.3:
        en.append("to the left"); ko.append("왼쪽")
    if tf < -0.3:
        en.append("toward the camera"); ko.append("카메라 쪽")
    elif tf > 0.3:
        en.append("away from the camera"); ko.append("안쪽")
    way = " and ".join(en)
    return (("Daylight comes only from the window on {}{}, traveling {}: sides facing the window are brighter, "
             "soft shadows fall {}. Ceiling light off.").format(
                REL_EN[rel], "" if seen else ", out of frame", way, way),
            "창({}{})에서 빛이 들어와 그림자가 {}으로 진다".format(WALL_KO[rel], "" if seen else ", 화면 밖", "·".join(ko)))


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


VILLA_STUDIO = "a one-room studio in a 4-story Korean villa (빌라)"   # 오피스텔·아파트는 고층 창밖을 부른다


def _room_space(house, room):
    kind = room.get("kind")
    if house.get("type") == "oneroom":   # 주방·화장실·현관도 그 빌라 원룸의 것이다(전에는 「Korean apartment」 로 나갔다)
        return VILLA_STUDIO if kind == "bedroom" else "the {} of {}".format(KIND_EN.get(kind, "room"), VILLA_STUDIO)
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


# ----------------------------------------------------------------------------- 가구별 규칙

RULES_FILE = os.path.join(HERE, "..", "references", "furniture-rules.json")
RULE_MATCH = {"category", "on", "with", "near"}
RULE_TEXT = ("prompt", "check", "avoid")


def _check_rules(rules, where):
    for r in rules:
        bad = set(r.get("match") or {}) - RULE_MATCH
        if bad or not any(r.get(k) for k in RULE_TEXT):
            raise SystemExit("{} 의 규칙 {}: match 는 {} 만 쓰고, {} 중 하나 이상을 적는다".format(
                where, r.get("id", "?"), "·".join(sorted(RULE_MATCH)), "·".join(RULE_TEXT)))


def load_rules(house, path=RULES_FILE):
    """스킬의 가구별 규칙 + house.json 품목마다 적은 rules."""
    with open(path, encoding="utf-8") as f:
        rules = json.load(f).get("rules") or []
    _check_rules(rules, os.path.basename(path))
    for it in house.get("items", []):
        _check_rules(it.get("rules") or [], "house.json 품목 " + str(it.get("id")))
    return rules


def _top(sc, it):
    if it["id"] in sc.boxes:
        return max(z1 for _, _, z1 in sc.boxes[it["id"]])
    return base_z(sc.ctx, it) + item_height(it, sc.ctx.geo[it["id"]])


def _gap(a, b):
    dx = max(a[0] - b[2], b[0] - a[2], 0)
    dy = max(a[1] - b[3], b[1] - a[3], 0)
    return math.hypot(dx, dy)


def _neighbors(sc, it, seen):
    """it 에서 NEAR_GAP 안에 있는, 이 컷에 보이는 바닥 가구와 그 사이(mm) 목록(가까운 순). 두 가구 중 바닥 면이
    작은 쪽만 받는다(같은 사이를 두 줄에 적지 않는다). 받침 위·벽에 단 것·짝(with)은 다른 규칙이 맡는다."""
    def floor(x):
        return not x.get("on") and not base_z(sc.ctx, x) and x["id"] in sc.ctx.geo

    def size(x, r):
        return ((r[2] - r[0]) * (r[3] - r[1]), x["id"])

    if not floor(it):
        return []
    r = sc.ctx.geo[it["id"]]["rect"]
    out = []
    for o in sc.ctx.items:
        if o["id"] == it["id"] or o["id"] not in seen or not floor(o) or it.get("with") == o["id"] or o.get("with") == it["id"]:
            continue
        q = sc.ctx.geo[o["id"]]["rect"]
        if P.inter(r, q) or size(o, q) <= size(it, r):
            continue
        g = _gap(r, q)
        if g <= NEAR_GAP:
            out.append((o, g))
    return sorted(out, key=lambda t: t[1])


def _frac(r):
    """비율 → 「1/4」. 작은 소품은 cm 만 적으면 모델이 1.5배쯤 크게 그린다(2026-11-12 스노우맨 조명)."""
    if r >= 0.85:
        return "nearly all"
    if r >= 0.6:
        return "2/3"
    return "1/{}".format(max(2, int(round(1.0 / max(r, 0.01)))))


def rule_vars(sc, it, seen=()):
    """규칙 글에 넣을 값. 길이는 cm. 받침(on)·짝(with)·매트리스 값은 그 관계가 있는 품목에만, 곁(near) 값은 이 컷에
    보이는(seen) 가까운 바닥 가구가 있는 품목에만 생긴다."""
    byid = {x["id"]: x for x in sc.ctx.items}
    g = sc.ctx.geo[it["id"]]
    sz = it.get("size") or {}
    v = dict(label=_label_en(it), label_ko=P.label_of(it), w=_cm(sz.get("w", 0)), d=_cm(sz.get("d", 0)),
             h=_cm(sz.get("h", 0) or item_height(it, g)), top=_cm(_top(sc, it)))
    sup = byid.get(it.get("on"))
    if sup and sup["id"] in sc.ctx.geo:
        r, s = g["rect"], sc.ctx.geo[sup["id"]]["rect"]
        over = max(s[0] - r[0], s[1] - r[1], r[2] - s[2], r[3] - s[3], 0)
        ss = sup.get("size") or {}
        v.update(support=_label_en(sup), support_ko=P.label_of(sup),
                 support_size="{}x{}".format(_cm(ss.get("w", 0)), _cm(ss.get("d", 0))),
                 on_fit="inside its edges" if over <= 10 else "sticking out {} cm past its edge".format(_cm(over)),
                 on_fit_ko="가장자리 밖으로 나오지 않았다" if over <= 10 else "가장자리 밖으로 {}cm 나온다(배치대로)".format(_cm(over)))
        sw = max(ss.get("w", 0), ss.get("d", 0)) or 1
        sh = item_height(sup, sc.ctx.geo[sup["id"]]) or 1
        iw = max(sz.get("w", 0), sz.get("d", 0))
        ih = sz.get("h", 0) or item_height(it, g)
        rw, rh = iw / float(sw), ih / float(sh)
        v.update(on_scale="about {} that top's width{}".format(   # 납작한 것(바 조명)은 높이 비율이 뜻이 없다
                     _frac(rw), " and {} the {}'s height".format(_frac(rh), _label_en(sup)) if rh >= 0.1 else ""),
                 on_scale_ko="윗면 폭의 {:.0%}, 받침 높이의 {:.0%}".format(iw / float(sw), ih / float(sh)))
    par = byid.get(it.get("with"))
    if par and par["id"] in sc.ctx.geo:
        top, ptop = _top(sc, it), _top(sc, par)
        rel = ("under" if P.inter(g["rect"], sc.ctx.geo[par["id"]]["rect"]) else "taller" if top >= ptop else "beside")
        v.update(partner=_label_en(par), partner_ko=P.label_of(par), partner_top=_cm(ptop), relation=rel)
    if it.get("category") == "bed":
        mw, md, side, end = mattress_of(it)
        if min(side, end) < -10:
            fit = "hanging {} cm past the frame edges".format(_cm(-min(side, end)))
            fit_ko = "프레임 밖으로 {}cm 나온다(house.json 의 mattress 대로)".format(_cm(-min(side, end)))
        elif max(side, end) <= 30:
            fit, fit_ko = "lying flush on the frame from head to foot", "프레임 밖으로 나오지 않고 가장자리가 맞는다"
        else:
            fit = "lying on the frame from head to foot, {} cm of frame showing at the sides and {} cm at the ends".format(
                _cm(max(side, 0)), _cm(max(end, 0)))
            fit_ko = "프레임 밖으로 나오지 않고 프레임이 옆 {}cm·끝 {}cm 드러난다".format(_cm(max(side, 0)), _cm(max(end, 0)))
        v.update(mattress="{}x{}".format(_cm(mw), _cm(md)), mattress_fit=fit, mattress_fit_ko=fit_ko)
    nbs = _neighbors(sc, it, seen)
    if nbs:
        touch = [o for o, g in nbs if g <= 10]
        apart = [(o, g) for o, g in nbs if g > 10]
        en, ko = [], []
        if apart:
            en.append("Bare floor shows between it and " + " and ".join(
                "the {} ({} cm gap)".format(_label_en(o), _cm(g)) for o, g in apart))
            ko.append(", ".join("{}까지 {}cm".format(P.label_of(o), _cm(g)) for o, g in apart) + " 떨어져 사이로 바닥이 보인다")
        if touch:
            en.append("It touches the {} without overlapping".format(" and the ".join(_label_en(o) for o in touch)))
            ko.append("{}에 바로 붙어 있다".format("·".join(P.label_of(o) for o in touch)))
        o, g = nbs[0]
        v.update(near=_label_en(o), near_ko=P.label_of(o), near_gap=_cm(g), near_fit=". ".join(en), near_fit_ko=", ".join(ko))
    return v


def _rule_hits(rule, it, v):
    m = rule.get("match") or {}
    cat = m.get("category")
    if cat and it.get("category") not in ([cat] if isinstance(cat, str) else cat):
        return False
    if "on" in m and ("support" in v) != bool(m["on"]):
        return False
    if "with" in m and v.get("relation") != m["with"]:
        return False
    if "near" in m and ("near" in v) != bool(m["near"]):
        return False
    return True


def apply_rules(rules, it, v):
    """이 품목에 걸리는 규칙(스킬 규칙 + 그 품목의 rules)의 글: {"prompt": [...], "check": [...], "avoid": [...]}."""
    out = {k: [] for k in RULE_TEXT}
    for r in list(rules) + list(it.get("rules") or []):
        if not _rule_hits(r, it, v):
            continue
        for k in RULE_TEXT:
            if not r.get(k):
                continue
            try:
                out[k].append(r[k].format(**v))
            except KeyError as e:
                raise SystemExit("규칙 {} 의 {{{}}} 를 채울 값이 {} 에 없다. match 로 그 관계가 있는 품목에만 건다".format(
                    r.get("id", "(품목 rules)"), e.args[0], it["id"]))
    return out


def _within(r, outer, tol=1.0):
    return r[0] >= outer[0] - tol and r[1] >= outer[1] - tol and r[2] <= outer[2] + tol and r[3] <= outer[3] + tol


def _center3(sc, it):
    x0, y0, x1, y1 = sc.ctx.geo[it["id"]]["rect"]
    return ((x0 + x1) / 2.0, (y0 + y1) / 2.0, base_z(sc.ctx, it) + item_height(it, sc.ctx.geo[it["id"]]) / 2.0)


def _merge(ss):
    """stats 항목 여럿을 하나로: [픽셀 수, x 합, y 합, x 최소, x 최대, y 최소, y 최대]."""
    ss = [x for x in ss if x]
    if not ss:
        return None
    return [sum(x[0] for x in ss), sum(x[1] for x in ss), sum(x[2] for x in ss), min(x[3] for x in ss),
            max(x[4] for x in ss), min(x[5] for x in ss), max(x[6] for x in ss)]


def _orient(cam, it, g):
    """품목 정면(침대는 발치)이 카메라에 어떻게 보이나."""
    x0, y0, x1, y1 = g["rect"]
    Fv = NORMAL[g["facing"]]
    tc = (cam.x - (x0 + x1) / 2.0, cam.y - (y0 + y1) / 2.0)
    Ln = math.hypot(*tc) or 1.0
    c = (Fv[0] * tc[0] + Fv[1] * tc[1]) / Ln
    f2, r2 = cam.fwd2(), cam.right2()
    ff, fr = Fv[0] * f2[0] + Fv[1] * f2[1], Fv[0] * r2[0] + Fv[1] * r2[1]
    if abs(fr) >= abs(ff):          # 정면이 화면 어느 쪽을 향하나
        way = "to frame right" if fr > 0 else "to frame left"
    else:
        way = "away from the camera" if ff > 0 else "toward the camera"
    if P.CAT.get(it.get("category"), {}).get("floor"):
        if abs((x1 - x0) - (y1 - y0)) < 1:
            return "lying flat on the floor"
        ax = (1.0, 0.0) if (x1 - x0) > (y1 - y0) else (0.0, 1.0)
        along = abs(ax[0] * f2[0] + ax[1] * f2[1]) >= abs(ax[0] * r2[0] + ax[1] * r2[1])
        return "lying flat on the floor, its long side running {}".format(
            "away from the camera" if along else "across the frame")
    if it.get("category") == "bed":
        return ("foot end faces camera" if c > 0.75 else "seen from the head end" if c < -0.75
                else "seen side-on, foot end pointing {}".format(way))
    return ("front faces camera" if c > 0.75 else "seen from behind" if c < -0.75
            else "seen side-on, front turned {}".format(way))


def _depth(d):
    return "foreground" if d < 1200 else "middle ground" if d < 2600 else "background"


def describe_through(sc, cam, cv, st, house, n0):
    """문간 너머로 보이는 옆 방(see_through 가 그려 넣은 것)을 문간마다 정리한다. 품목 번호는 n0+1 부터 잇는다.
    너머 방의 벽·바닥은 그 방 종류의 마감(room_finish)이다 — 그 방 컷과 같은 말로 적어야 같은 방으로 나온다.
    소품은 적지 않는다. 그 방 전체의 소품이라 문간에 안 보이는 가구(책상 위 노트북)까지 불러온다."""
    W, H = cam.w, cam.h
    A = float(W * H)
    con = concept_of(house)
    groups = {oid: (nb, []) for oid, nb in getattr(cv, "doorways", {}).items()}
    for cid, (nb, it, oid) in sorted(getattr(cv, "through", {}).items()):
        groups[oid][1].append((cid, it))
    out, n = [], n0
    for oid, (nb, members) in groups.items():
        ms = _merge([st.get(oid)] + [st[c] for c, _ in members if c in st])     # 문간 + 너머 방 품목
        if not ms or ms[0] / A < THROUGH_MIN:
            continue
        area, xs = ms[0], (ms[3], ms[4])
        big = {it["id"] for c, it in members if c in st and st[c][0] >= 30 and st[c][0] / A >= 0.004}
        vis = []
        for cid, it in members:         # 이 방 품목과 같은 기준: 0.4% 이상, 또는 보이는 받침 위의 알아볼 만한 소품
            s = st.get(cid)
            if not s or s[0] < 30:
                continue
            frac = s[0] / float(cv.drawn[cid] or 1)
            readable = min(s[4] - s[3], s[6] - s[5]) + 1 >= 12
            if it["id"] in big or (it.get("on") in big and frac >= 0.5 and readable):
                vis.append((s[1] / s[0] / W, cid, it, s))
        vis.sort(key=lambda t: t[0])
        seen = {it["id"] for _, _, it, _ in vis}
        lines, short, facts, labels = [], [], [], []
        for hx, cid, it, s in vis:
            n += 1
            g = nb.ctx.geo[it["id"]]
            sz = it.get("size") or {}
            x0, y0, x1, y1 = g["rect"]
            d = _visible_part(nb, cam, it)[0]
            if d is None:
                d = math.hypot(max(x0 - cam.x, 0, cam.x - x1), max(y0 - cam.y, 0, cam.y - y1))
            hpos, vp = _hpos(hx), _vpos(s[2] / s[0] / H)
            parts = ["{}, {}".format(hpos if vp == "middle" else "{} {}".format(vp, hpos), _depth(d)), _orient(cam, it, g)]
            if s[3] <= 0 or s[4] >= W - 1:
                parts.append("cut off at the {} edge".format("left" if s[3] <= 0 else "right"))
            dims = "{}x{}x{} cm. {}.".format(_cm(sz.get("w", 0)), _cm(sz.get("d", 0)),
                                             _cm(sz.get("h", 0) or item_height(it, g)), "; ".join(parts).capitalize())
            line = "{}. {} ({} box): {}. {}".format(n, _label_en(it).capitalize(), nb.color[it["id"]][1], _look(it), dims)
            short.append("{}. {} ({} box): {}".format(n, _label_en(it).capitalize(), nb.color[it["id"]][1], dims))
            for a in nb.items:          # 짝 안의 붙박이(싱크대 밑 세탁기)는 짝에 가려 목록에 없다 — 문간 안에 들면 짝의 줄에 적는다
                if a.get("with") != it["id"] or a["id"] in seen or not _within(nb.ctx.geo[a["id"]]["rect"], g["rect"]):
                    continue
                px = cam.proj(cam.to_cam(_center3(nb, a)))[0]
                if not (xs and min(xs) <= px <= max(xs)):
                    continue
                asz = a.get("size") or {}
                end = ("its left end" if px / W < hx - 0.08 else "its right end" if px / W > hx + 0.08 else "the middle")
                tail = " Built into it at {}: {}, {}x{}x{} cm, its front flush with the {}'s front."
                line += tail.format(end, _look(a), _cm(asz.get("w", 0)), _cm(asz.get("d", 0)), _cm(asz.get("h", 0)),
                                    _label_en(it))
                short[-1] += tail.format(end, "a " + _label_en(a), _cm(asz.get("w", 0)), _cm(asz.get("d", 0)),
                                         _cm(asz.get("h", 0)), _label_en(it))
            lines.append(line)
            labels.append(P.label_of(it))
            facts.append(dict(id=it["id"], label=P.label_of(it), share=round(s[0] / A, 3), x=round(hx, 2),
                              en=dict(id=it["id"], label=_label_en(it), look=_look(it), where="; ".join(parts))))
        m = sc.ops[oid]
        kind = nb.room.get("kind")
        fin = room_finish(house, con, nb.room)
        label, label_ko = KIND_EN.get(kind, "next room"), P.KIND_KO.get(kind or "", "옆 방")
        # 화면 자리(hp)는 In view 줄이 이미 적었다. 벽 이름으로 그 개구부를 가리킨다
        head = "Through {} is the {} (walls: {}; floor: {}).".format(
            _opening(sc, m, cam)["the"], label, fin["walls"], fin["floor"])
        # 너머 방의 창·문. 너머를 글로 적지 않았을 때 모델은 그 방의 대표 사진(창과 침대)을 문간에 옮겨 그렸다(2026-11-13
        # 주방 컷: 문간 너머는 옷장 옆 벽뿐이다). 가구만 적으면 창은 여전히 글에 없는 자리라, 보이는 창·문은 자리와 함께,
        # 창이 있는 방인데 안 보이면 안 보인다고 적는다
        shown, ko_ops, win_seen = [], [], False
        for k, (cnt, xs_) in sorted(getattr(cv, "through_ops", {}).get(oid, {}).items()):
            if cnt / A < THROUGH_OP_MIN:
                continue
            nm = nb.ops[k]
            no = nm["op"]
            rel = _wall_rel(nm["side"], cam)
            php = _hpos(xs_ / float(cnt) / W)
            if no["type"] == "window":
                shown.append("a {} cm wide window on {} ({}), sill {} cm, {}".format(
                    _cm(no["b"] - no["a"]), REL_EN[rel], php, _cm(no.get("sill", 900)), con["curtains"]))
                ko_ops.append("창({})".format(WALL_KO[rel]))
                win_seen = True
            else:
                far = no.get("to") if no["room"] == nb.room["id"] else no["room"]
                dest = "outside" if far == "outside" else (
                    "the " + KIND_EN.get(nb.ctx.rooms.get(far, {}).get("kind"), "next room"))
                if no["type"] == "opening":
                    shown.append(_opening(nb, nm, cam)["a"].format(to=" to " + dest) + " ({})".format(php))
                    ko_ops.append("트인 문간({})".format(WALL_KO[rel]))
                else:
                    shown.append("a closed door to {} on {} ({})".format(dest, REL_EN[rel], php))
                    ko_ops.append("문({})".format(WALL_KO[rel]))
        if shown:
            head += " Visible there: " + "; ".join(shown) + "."
        if not win_seen and any(nm["op"]["type"] == "window" for nm in nb.ops.values()):
            head += " No window shows there."
            ko_ops.append("창은 안 보인다")
        head += " Draw only these there, at true scale:" if lines else " No furniture shows there."
        check = "문간 너머 {} — {}".format(label_ko, "·".join(labels) + " 만 보인다" if labels else "가구 없이 벽·바닥만 보인다")
        if ko_ops:
            check += " · " + " · ".join(ko_ops)
        out.append(dict(oid=oid, room=nb.room["id"], label=label, label_ko=label_ko, share=area / A,
                        head=head, lines=lines, short=short, check=check, items=facts))
    return out


def describe(sc, cam, cv, st, house, rules=()):
    """보이는 품목·창·문을 화면 위치와 함께 정리한다. 보이는 품목마다 가구별 규칙(rules)을 건다."""
    W, H = cam.w, cam.h
    A = float(W * H)
    rooms = {r["id"]: r for r in house.get("rooms", [])}
    con = concept_of(house)
    curtains, view = con["curtains"], con["view"]
    room = sc.room
    rx0, ry0, rx1, ry1 = P.rr(room)
    byid = {it["id"]: it for it in sc.items}
    inv = {v: k for k, v in sc.iid.items()}
    big = {it["id"] for it in sc.items
           if st.get(sc.iid[it["id"]]) and st[sc.iid[it["id"]]][0] >= 30 and st[sc.iid[it["id"]]][0] / A >= 0.004}
    vis = []
    for it in sc.items:
        iid = sc.iid[it["id"]]
        s = st.get(iid)
        if not s or s[0] < 30:
            continue
        frac = s[0] / float(cv.drawn[iid] or 1)
        # 화면의 0.4% 보다 작으면 뺀다. 다만 보이는 가구 위에 놓인 소품(협탁 위 조명)은 작아도 리뷰할 제품이고,
        # 빼면 「목록 밖 물건은 그리지 말라」 는 문장 때문에 받침만 비어 나온다 — 가려지지 않았고 가로·세로 모두
        # 12px(스케치 1024px 기준, 만든 사진에서 약 18px) 이상이라 모양을 알아볼 수 있으면 남긴다.
        # 책상 위 막대 조명(2026-11-12 대표 컷에서 110×8px)처럼 선으로만 보이는 것은 뺀다
        readable = min(s[4] - s[3], s[6] - s[5]) + 1 >= 12
        if s[0] / A < 0.004 and not (it.get("on") in big and frac >= 0.5 and readable):
            continue
        g = sc.ctx.geo[it["id"]]
        x0, y0, x1, y1 = g["rect"]
        cx, cy = (x0 + x1) / 2.0, (y0 + y1) / 2.0
        occ = [(v, inv.get(b)) for (a, b), v in cv.occ.items() if a == iid and b in inv]
        occ.sort(key=lambda t: -t[0])
        dist = _visible_part(sc, cam, it)[0]
        if dist is None:
            dist = math.hypot(max(x0 - cam.x, 0, cam.x - x1), max(y0 - cam.y, 0, cam.y - y1))
        vis.append(dict(it=it, iid=iid, share=s[0] / A, hx=s[1] / s[0] / W, vy=s[2] / s[0] / H,
                        cut_l=s[3] <= 0, cut_r=s[4] >= W - 1, frac=frac,
                        occluder=occ[0][1] if occ and frac < 0.6 else None, dist=dist, center=(cx, cy)))
    vis.sort(key=lambda v: v["hx"])
    # 짝(with)이 보이는데 자신은 화면 밖(한 픽셀도 그려지지 않은)인 품목. 모델은 책상이 보이면 의자를 지어 붙이므로 없다고
    # 적는다. 화면 안에서 짝에 가려진 것은 빼지 않는다: 싱크대 밑 붙박이 세탁기(with: counter)는 싱크대에 다 가려져
    # 목록에 없는데, 「세탁기를 그리지 말라」 고 적으면 싱크대 look 의 「밑에 세탁기」 와 부딪친다(2026-11-13 주방 컷)
    seen = {v["it"]["id"] for v in vis}
    away, atop, built = {}, {}, {}
    for it in sc.items:
        if it.get("with") in seen and it["id"] not in seen and not cv.drawn[sc.iid[it["id"]]]:
            away.setdefault(it["with"], []).append(it)
        # 짝의 바닥 면 안에 든 붙박이(싱크대 밑 세탁기)는 화면 안이어도 짝의 상자에 가려 목록에 없다. 적지 않으면
        # 「목록 밖 가전은 그리지 말라」 때문에 그 자리에 수납장 문을 그린다(2026-11-13 주방). 짝의 줄에 붙여 적는다
        elif it.get("with") in seen and it["id"] not in seen and _within(sc.ctx.geo[it["id"]]["rect"],
                                                                          sc.ctx.geo[it["with"]]["rect"]):
            built.setdefault(it["with"], []).append(it)
        # 받침(on)이 보이는데 자신은 화면 밖(가려진 것이 아니라 한 픽셀도 그려지지 않은)인 소품. 모델은 가장자리에 걸친 받침을
        # 화면 안으로 더 들이고, 소품을 모르면 윗면을 비워 그린다(2026-11-13 제품 컷: 오른쪽 끝에 조금 걸친 협탁을 거의 다
        # 그리고 그 위 조명은 빠졌다). 「그리지 말라」 가 아니라 거기 있다고 적어 받침을 덜 보이게 하거나 소품을 함께 그리게 한다
        if it.get("on") in seen and it["id"] not in seen and not cv.drawn[sc.iid[it["id"]]]:
            atop.setdefault(it["on"], []).append(it)
    lines, checks, board, avoid, facts, fills = [], [], [], [], [], []
    for n, v in enumerate(vis, 1):
        it = v["it"]
        g = sc.ctx.geo[it["id"]]
        sz = it.get("size") or {}
        rv = rule_vars(sc, it, seen)
        rl = apply_rules(rules, it, rv)
        hpos, vp = _hpos(v["hx"]), _vpos(v["vy"])
        depth = _depth(v["dist"])
        parts = ["{}, {}".format(hpos if vp == "middle" else "{} {}".format(vp, hpos), depth)]
        wall = _place_wall(it)
        flat = P.CAT.get(it.get("category"), {}).get("floor")
        if flat:
            pass                            # 바닥에 깔린 것(러그)은 앞면·벽이 없다 — 아래에서 긴 변의 방향만 적는다
        elif "support" in rv or "relation" in rv:
            pass                            # 받침·짝 곁의 자리는 가구별 규칙(rests-on · with-*)이 적는다
        elif wall:
            rel = _wall_rel(wall, cam)
            L = (rx1 - rx0) if wall in "ns" else (ry1 - ry0)
            txt = "{} to {}".format("head end" if it.get("category") == "bed" else "back", REL_EN[rel])
            if rel.startswith("near"):
                pass
            elif L - (sz.get("w") or 0) <= FILL_GAP:
                # 벽을 다 채우는 가구. 「100% of its 60 cm」 로 적으면 모델은 벽을 넓혀 옆에 빈자리를 지었다(2026-11-13 현관:
                # 60cm 끝 벽을 채운 신발장 옆에 바닥을 내고 운동화를 놓았다). 모서리까지 채워 옆에 벽이 없다고 적는다
                txt += ", filling that {} cm wall from corner to corner with no wall showing beside it".format(_cm(L))
                fills.append(it)
            else:
                txt += " ({}% of its {} cm)".format(int(round(100.0 * (sz.get("w") or 0) / L)), _cm(L))
            parts.append(txt)
        else:
            parts.append("free-standing")
        parts.append(_orient(cam, it, g))
        if v["occluder"] and not P.CAT.get(byid[v["occluder"]].get("category"), {}).get("floor"):
            parts.append("partly behind the {}".format(_label_en(byid[v["occluder"]])))
        if v["cut_l"] or v["cut_r"]:
            parts.append("cut off at the {} edge".format("left" if v["cut_l"] else "right"))
        col = sc.color[it["id"]][1]
        prod = it.get("product") or {}
        # ref: false — 그 제품만 따로 찍힌 사진이 없고, 있는 사진이 배치와 부딪치는 것(다른 크기 옵션·다른 조명이 함께 찍힌
        # 침대 사진)을 담는다. 그 사진을 보드에 넣으면 모델은 사진 속 다른 물건과 여백까지 옮긴다(2026-11-12 대표 컷)
        has_img = bool(prod.get("ref_image") or prod.get("image")) and not it.get("owned") and prod.get("ref") is not False
        keep = (it.get("keep") or "").strip().rstrip(".")
        lines.append("{}. {} ({} box): {}. {}x{}x{} cm. {}.".format(
            n, _label_en(it).capitalize(), col, _look(it), _cm(sz.get("w", 0)), _cm(sz.get("d", 0)),
            _cm(sz.get("h", 0) or item_height(it, g)), "; ".join(parts).capitalize()))
        for t in rl["prompt"]:
            lines[-1] += " " + t
        if keep:                            # 생김새의 정체(조사: references/product-fidelity.md). 장면 뒤에 둔다
            lines[-1] += " Keep exactly: {}.".format(keep)
        for a in away.get(it["id"], []):
            lines[-1] += " Its {0} is out of frame: draw no {0} at it.".format(_label_en(a))
        for a in built.get(it["id"], []):
            asz = a.get("size") or {}
            px = cam.proj(cam.to_cam(_center3(sc, a)))[0] / float(cam.w)
            end = "its left end" if px < v["hx"] - 0.08 else "its right end" if px > v["hx"] + 0.08 else "the middle"
            lines[-1] += " Built into it at {}: {}, {}x{}x{} cm, its front flush with the {}'s front.".format(
                end, _look(a), _cm(asz.get("w", 0)), _cm(asz.get("d", 0)), _cm(asz.get("h", 0)), _label_en(it))
        for a in atop.get(it["id"], []):
            edge = " past the {} edge".format("left" if v["cut_l"] else "right") if v["cut_l"] or v["cut_r"] else ""
            lines[-1] += (" Its {0} stands on its top just out of frame{1}: show no more of the {2} than the sketch does; "
                          "if more of its top shows, the {0} stands there too.").format(_label_en(a), edge, _label_en(it))
        facts.append(dict(id=it["id"], label=_label_en(it), look=_look(it), keep=keep or None,
                          size="{}x{}x{}".format(_cm(sz.get("w", 0)), _cm(sz.get("d", 0)),
                                                 _cm(sz.get("h", 0) or item_height(it, g))),
                          where="; ".join(parts), extra=" ".join(rl["prompt"]), ref=has_img,
                          crop=prod.get("ref_crop") if has_img else None))
        checks.append("{}. {} — 화면 {}{}, {}".format(
            n, P.label_of(it), HPOS_KO[hpos], "" if vp == "middle" else " " + VPOS_KO[vp],
            {"foreground": "가까이", "middle ground": "중간 거리", "background": "멀리"}[depth]))
        if it in fills:
            checks.append("{} — 붙은 벽을 모서리부터 모서리까지 채운다(옆에 벽·바닥이 안 보인다)".format(P.label_of(it)))
        checks.extend("{} — {}".format(P.label_of(it), c) for c in rl["check"])
        avoid.extend(a for a in rl["avoid"] if a not in avoid)
        for a in away.get(it["id"], []):
            checks.append("{} — 화면 밖. {} 곁에 그려지지 않았나".format(P.label_of(a), P.label_of(it)))
        for a in built.get(it["id"], []):
            checks.append("{} — {} 안에 붙박이로 보인다".format(P.label_of(a), P.label_of(it)))
        for a in atop.get(it["id"], []):
            checks.append("{} — 화면 밖. {} 윗면이 스케치보다 더 보이면 그 위에 놓여 있나".format(P.label_of(a), P.label_of(it)))
        if has_img:
            board.append(dict(item=it["id"], n=n, label=_label_en(it), crop=prod.get("ref_crop")))
    ops = []
    tst = {}
    for cid, (_, _, oid) in getattr(cv, "through", {}).items():
        if cid in st:
            tst.setdefault(oid, []).append(st[cid])
    for oid, m in sc.ops.items():
        s = _merge([st.get(oid)] + tst.get(oid, []))
        if not s or s[0] / A < 0.003:
            continue
        o = m["op"]
        rel = _wall_rel(m["side"], cam)
        hp = _hpos(s[1] / s[0] / W)
        if o["type"] == "window":
            ops.append("a {} cm wide window on {} ({}), sill {} cm, {}{}".format(
                _cm(o["b"] - o["a"]), REL_EN[rel], hp, _cm(o.get("sill", 900)), curtains,
                ", " + view[0] if view else ""))
            checks.append("창 — {}, 화면 {}".format(WALL_KO[rel], HPOS_KO[hp]))
            if view:
                checks.append(view[1])
                if view[2] and view[2] not in avoid:
                    avoid.append(view[2])
        elif o["type"] == "opening":
            other = o.get("to") if o["room"] == room["id"] else o["room"]
            dest = "outside" if other == "outside" else ("the " + KIND_EN.get(rooms.get(other, {}).get("kind"), "next room"))
            op = _opening(sc, m, cam)
            ops.append("{} ({})".format(op["a"].format(to=" to " + dest), hp))
            checks.append("{} — {}, 화면 {}".format(op["ko"], WALL_KO[rel], HPOS_KO[hp]))
        else:
            other = o.get("to") if o["room"] == room["id"] else o["room"]
            dest = "outside" if other == "outside" else ("the " + KIND_EN.get(rooms.get(other, {}).get("kind"), "next room"))
            ops.append("a door to {} on {} ({})".format(dest, REL_EN[rel], hp))
            checks.append("문 — {}, 화면 {}".format(WALL_KO[rel], HPOS_KO[hp]))
    thru = describe_through(sc, cam, cv, st, house, len(vis))
    checks.extend(t["check"] for t in thru)
    return vis, lines, ops, checks, board, avoid, facts, thru


def _and(words):
    words = list(words)
    return words[0] if len(words) == 1 else ", ".join(words[:-1]) + " and " + words[-1]


def build_prompt(house, concept, ratio, cam, kind_txt, view, lines, ops, board, refs, light_dir=None, avoid=(), thru=()):
    R = RATIOS[ratio]
    room = view["room"]
    rx0, ry0, rx1, ry1 = P.rr(room)
    C = (house.get("photo") or {}).get("ceiling", DEFAULT_CEIL)
    tilt = ("camera level so vertical lines stay vertical" if abs(cam.pitch) < math.radians(3)
            else "camera tilted slightly down" if cam.pitch < 0 else "camera tilted slightly up")
    fin = view["finish"]
    out = [COMMON_LOOK + " " + fin["details"], concept["mood"],
           "Camera: {} photo, {:.0f} mm full-frame-equivalent lens, camera height {} cm, {}.".format(
               R[4], cam.lens_mm, _cm(cam.z), tilt),
           "Space: {}, {:.1f} m x {:.1f} m, ceiling {:.1f} m. Walls: {}. Floor: {}.".format(
               view["space"], (rx1 - rx0) / 1000.0, (ry1 - ry0) / 1000.0, C / 1000.0, fin["walls"], fin["floor"]),
           ("Light: {}. {}".format(concept["light"], light_dir) if light_dir else
            "Light: soft even light from the LED ceiling light, with a little daylight from the doorway."),
           "View: {}.".format(kind_txt)]
    if ops:
        out.append("In view: " + "; ".join(ops) + ".")
    out.append("Furniture in frame, left to right (position, depth; W x D x H). Draw exactly these, at true scale:")
    out.extend(lines)
    # 소품은 적은 것만 놓인다. 「Small soft props only」 는 작은 소품을 더 지어 놓아도 된다는 말로 읽혀, 목록에 없는
    # 조명·상자가 수납장 위에 올라갔다(2026-11-13). 어느 방이든 받침 윗면과 바닥에는 적은 소품 말고는 아무것도 없다
    props = fin["props"] and fin["props"] + (", " + concept["plants"] if concept.get("plants") else "")
    out.append("Styling: {}; nothing else on any surface.".format(props) if props else
               "Styling: nothing on any surface.")
    for t in thru:
        out.append(t["head"])
        out.extend(t["short"] if view.get("short_through") else t["lines"])
    rt = []
    bidx = [i for i, ref in enumerate(refs, 1) if ref["role"] == "board"]
    mf = view.get("master_finish") or fin
    same = [k for k in ("walls", "floor") if fin[k] == mf[k]]
    for i, ref in enumerate(refs, 1):
        if ref["role"] == "master" and ref.get("same_room"):
            rt.append("Reference image {} is a photo of this same room from another angle: keep the identical walls, floor, "
                      "window, curtains, light, colors, bedding and props.".format(i))
        elif ref["role"] == "master" and len(same) == 2:
            rt.append("Reference image {} is a photo of another room in the same home: use the same wall and floor finishes, "
                      "window frames, light and styling.".format(i))
        elif ref["role"] == "master":       # 마감이 다른 공간(화장실·현관): 그 사진의 벽지·마루를 따라 그리지 않게 한다
            differ = [k for k in ("walls", "floor") if k not in same]
            rt.append("Reference image {} is a photo of another room in the same home: use the same {}window frames, door "
                      "and trim colors and light; the {} {} the text above, not that photo.".format(
                          i, "".join(k.rstrip("s") + " finish, " for k in same), _and(differ),
                          "follows" if differ == ["floor"] else "follow"))
        elif ref["role"] == "neighbor":
            rt.append("Reference image {} is a photo of the {} seen through the opening: draw that part of it to "
                      "match the photo (same furniture, appliances, finishes and props).".format(i, ref["label"]))
        elif ref["role"] == "sketch":
            legend = [txt for col, txt in OPENING_LEGEND if col in view.get("colors", ())]   # 스케치에 있는 색만
            rt.append("Reference image {} is a massing sketch of this exact view: match its perspective and each colored "
                      "box's position, size and proportion. Box colors are only labels{}; render real colors and "
                      "materials, never boxes.".format(
                          i, " ({})".format(", ".join(legend)) if legend else ""))
        elif ref["role"] == "board" and i == bidx[0]:
            # 보드 칸의 순서(reading order)는 모델이 잘 못 따른다 — 무엇이 찍혔는지로 가리키고, 품목 줄과는 생김새로
            # 짝짓게 한다(조사: references/product-fidelity.md 「레퍼런스는 내용으로 가리킨다」)
            many = len(board) > 1
            rt.append("Reference image{} {} show{} {}product photo{} of the {}: copy {} exactly (shape, proportions, color, "
                      "finish, details){}; ignore anything else in {}; sizes come only from the numbers above.".format(
                          "s" if len(bidx) > 1 else "", " and ".join(map(str, bidx)), "" if len(bidx) > 1 else "s",
                          "" if many else "a ", "s" if many else "", _and(b["label"] for b in board),
                          "each" if many else "it",
                          ", matched to its line by look" if many else "", "them" if len(bidx) > 1 else "it"))
        elif ref["role"] == "product":
            rt.append("Reference image {} is the actual product photo of item {} ({}): copy its shape, color and material "
                      "exactly, but take sizes only from the numbers above and ignore the props around it.".format(
                          i, ref["n"], ref["label"]))
    out.extend(rt)
    out.append(negative(concept, avoid))
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
            KIND_EN.get((rm.get("kind") if rm else None) or "", "next room"))
        frm_ko = "현관문" if other == "outside" else "{} 쪽 문간".format(
            P.KIND_KO.get(rm.get("kind") or "", "옆 방") if rm else "옆 방")
        return ("a wide shot standing at {}, looking {}".format(frm, toward),
                "{}에서 {} 쪽을 본다".format(frm_ko, toward_ko))
    return ("a wide shot from a corner of the room, looking {}".format(toward),
            "방 모서리에서 {} 쪽을 본다".format(toward_ko))


PHYSICAL = {"overlap", "collide", "with_under", "on_floating", "on_missing", "with_missing", "item_outside", "room_overlap"}
# look 에 적은 크기 관계. 크기·여백은 치수와 가구별 규칙이 정한다. 제품 사진은 다른 옵션을 찍었을 수 있어 사진의
# 여백을 look 에 옮기면 치수와 부딪친다(2026-11-11 SS 프레임에 「매트리스 둘레로 나온 받침」 을 적어 매트리스가 떴다)
SIZE_CLAIM = re.compile(r"\b(?:wider|larger|bigger|longer|taller|deeper|narrower|smaller|shorter)\s+than\b"
                        r"|\bstick(?:s|ing)?\s+out\b|\bover-?hang\w*|\bextend(?:s|ing)?\s+(?:past|beyond)\b"
                        r"|\bprotrud\w*|\bjut\w*|\bledge\b", re.I)


def shot_order(specs, master, first, looks):
    """만드는 순서. 기본은 대표 컷 → 전체 컷 → 제품 컷이고, 레퍼런스 1번으로 받는 컷(대표 컷, 그 방의 첫 전체 컷)은
    반드시 먼저 온다. 다음 컷이 문간 너머로 보는 방(looks)의 첫 전체 컷이 아직이면 그 컷만 앞으로 당겨 사진을 레퍼런스로
    넣게 한다. 두 방이 서로 들여다보면 기본 순서에서 앞선 컷을 먼저 만들고, 그 컷은 너머 방을 스케치와 글로만 받는다."""
    base = sorted(specs, key=lambda x: (x["id"] != master, x["kind"] != "wide"))
    byid = {s["id"]: s for s in specs}
    done = set()

    def need(s):
        m = first.get(s["room"])
        return {m if m and m != s["id"] else master} - {s["id"]}

    def pick(s, path):                  # s 가 보는 방의 첫 전체 컷을 먼저 만들 수 있으면 그 컷(사슬이면 끝까지)
        for r in looks.get(s["id"], ()):
            d = first.get(r)
            if not d or d in done or d == s["id"]:
                continue
            if d in path:
                return None             # 서로 들여다본다 — 당기지 않는다
            if need(byid[d]) <= done:
                got = pick(byid[d], path | {s["id"]})
                if got:
                    return got
        return s
    out = []
    while len(out) < len(base):
        first_ready = next(s for s in base if s["id"] not in done and need(s) <= done)
        s = pick(first_ready, frozenset()) or first_ready
        out.append(s)
        done.add(s["id"])
    return out


def plan(house, out_dir, max_hero=6, ratio=None):
    ctx, _ = P.check(house)
    bad = [i["msg"] for i in ctx.issues if i["level"] == "error" and i["code"] in PHYSICAL]
    if bad:                                       # 놓일 수 없는 배치를 사진으로 만들지 않는다
        raise SystemExit("물리적으로 놓일 수 없는 가구가 있다 — room-set-planner 로 먼저 고친다:\n  " + "\n  ".join(bad))
    ph = house.get("photo") or {}
    ratio = ratio or ph.get("ratio", "9:16")
    if ratio not in RATIOS:
        raise SystemExit("ratio 는 {} 중 하나다".format(", ".join(RATIOS)))
    concept = concept_of(house)
    rules = load_rules(house)
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
    for i, m in enumerate(ph.get("shots") or [], 1):
        room = ctx.rooms[m["room"]]
        yaw = math.radians(m["yaw"]) if "yaw" in m else math.atan2(m["look_at"][1] - m["y"], m["look_at"][0] - m["x"])
        specs.append(dict(id=m.get("id", "shot-{}".format(i)), room=room["id"], x=m["x"], y=m["y"],
                          z=m.get("h", cam_h), yaw=yaw, pitch=math.radians(m.get("pitch", 0)),
                          lens=m.get("lens", WIDE_LENS), kind=m.get("kind", "wide"), target=m.get("target"),
                          where="manual", cyf=HORIZON[ratio] if not m.get("pitch") else 0.5))
    # 직접 적은 컷은 그 방의 자동 컷만 대신한다. 전에는 방 하나만 적어도 다른 방(주방·화장실·현관)의 컷이 통째로 빠졌다
    # (2026-11-13 사용자 「주방 화장실 현관은 안 만들어?」). 방을 빼려면 photo.skip_rooms 에 방 id 를 적는다
    covered = {s["room"] for s in specs}
    skip = set(ph.get("skip_rooms") or [])
    if skip - set(ctx.rooms):
        raise SystemExit("photo.skip_rooms 에 없는 방이 있다: {} (방: {})".format(
            ", ".join(sorted(skip - set(ctx.rooms))), ", ".join(ctx.rooms)))
    taken = {s["id"] for s in specs}
    heroes = sum(1 for s in specs if s["kind"] == "hero")
    for room in rooms:
        if room["id"] in covered or room["id"] in skip:
            continue
        sc = Scene(ctx, room, ceil)
        pre = "" if len(rooms) == 1 else room["id"] + "-"
        for k, s in enumerate(plan_wide(sc, ratio, cam_h, review), 1):
            s.update(id="{}wide-{}".format(pre, k), room=room["id"])
            specs.append(s)
        for it in sc.items:
            if it["id"] not in review or heroes >= max_hero:
                continue
            s = plan_hero(sc, it, ratio)
            hid = "hero-{}".format(re.sub(r"[^A-Za-z0-9_-]", "_", it["id"]))
            if s and hid not in taken:
                s.update(id=hid, room=room["id"])
                specs.append(s)
                heroes += 1
    if not specs:
        raise SystemExit("찍을 자리를 찾지 못했다. photo.shots 로 카메라를 직접 적는다")
    master_of_room, global_master = {}, None
    # 대표 컷은 직접 적은 방에서 먼저 고른다. 품목 수로만 고르면 품목이 같거나 많은 주방의 컷이 대표가 될 수 있다
    rank = {r["id"]: i for i, r in enumerate(sorted(rooms, key=lambda r: r["id"] not in covered))}
    for s in sorted(specs, key=lambda x: (rank.get(x["room"], 99), not x.get("window"))):  # 창이 보이는 와이드가 빛·창틀의 기준
        if s["kind"] == "wide" and s["room"] not in master_of_room:
            master_of_room[s["room"]] = s["id"]
            global_master = global_master or s["id"]
    global_master = global_master or specs[0]["id"]
    master_finish = room_finish(house, concept, ctx.rooms[next(s["room"] for s in specs if s["id"] == global_master)])
    has_ffmpeg = bool(shutil.which("ffmpeg"))
    seen_by = {}                                  # 컷 id → (스케치·글 재료)
    for s in specs:
        room = ctx.rooms[s["room"]]
        sc = Scene(ctx, room, ceil)
        hfov = 2 * math.atan((sw / 2.0) / s["lens"])
        cam = Cam(s["x"], s["y"], s["z"], s["yaw"], s["pitch"], hfov, W, H, s["lens"], s.get("cyf", 0.5))
        cv = see_through(sc, cam, sc.render(cam))
        st = cv.stats()
        # 범례는 스케치에 실제로 칠해진 색만 적는다. 트인 문간은 너머 방이 그려져 짙은 회색이 남지 않는 일이 많다
        painted = set(zip(cv.px[0::3], cv.px[1::3], cv.px[2::3]))
        colors = {c for c, _ in OPENING_LEGEND if tuple(c) in painted}
        sketch = os.path.join("sketch", s["id"] + ".png")
        cv.png(os.path.join(out_dir, sketch))
        seen_by[s["id"]] = (sc, cam, hfov, st, sketch, colors, describe(sc, cam, cv, st, house, rules))
        del cv
    looks = {sid: [t["room"] for t in sorted(v[6][7], key=lambda t: -t["share"]) if t["share"] >= NEIGHBOR_SHARE]
             for sid, v in seen_by.items()}
    shots, made = [], set()
    for s in shot_order(specs, global_master, master_of_room, looks):
        room = ctx.rooms[s["room"]]
        sc, cam, hfov, st, sketch, colors, (vis, lines, ops, checks, board, avoid, facts, thru) = seen_by[s["id"]]
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
                # 보드 한 장은 2×2(512px 칸, 1024px)까지. 여섯 칸 보드는 DemoCut 이 1024px 로 줄여 칸이 약 340px,
                # 작은 소품은 60~80px 가 되어 모양을 잃었다(2026-11-12). 레퍼런스는 3장까지라 대표 컷(스케치 + 보드)은
                # 보드 두 장, 나머지 컷(대표 컷 그림 + 스케치 + 보드)은 한 장이다
                cap = BOARD_CELLS * (2 if is_master else 1)
                share = {v["it"]["id"]: v["share"] for v in vis}
                if len(board) > cap:
                    board = sorted(board, key=lambda b: (b["item"] != s.get("target"), -share[b["item"]]))[:cap]
                    board.sort(key=lambda b: b["n"])
                ng = -(-len(board) // BOARD_CELLS)
                per = -(-len(board) // ng)
                for k in range(ng):
                    grp = board[k * per:(k + 1) * per]
                    refs.append(dict(role="board", file=os.path.join("boards", s["id"] + ("" if k == 0 else "-{}".format(k + 1))
                                                                     + ".png"),
                                     items=[b["item"] for b in grp], crops={b["item"]: b["crop"] for b in grp if b.get("crop")}))
            else:
                pick = next((b for b in board if b["item"] == s.get("target")), None) or max(
                    board, key=lambda b: next(v["share"] for v in vis if v["it"]["id"] == b["item"]))
                refs.append(dict(role="product", item=pick["item"], n=pick["n"], label=pick["label"],
                                 url=(byid[pick["item"]].get("product") or {}).get("image")))
                board = []
        # 문간 너머 방은 스케치와 글(describe_through)이 늘 적는다. 그 방의 첫 전체 컷이 이 컷보다 먼저 만들어지고
        # 레퍼런스 칸이 남으면 그 사진도 넣어 소품·제품 생김새까지 같게 한다. 칸은 제품 보드가 먼저 쓴다
        for t in sorted(thru, key=lambda t: -t["share"]):
            nb = master_of_room.get(t["room"])
            if (len(refs) < 3 and t["share"] >= NEIGHBOR_SHARE and nb in made
                    and all(r.get("shot") != nb for r in refs)):
                refs.append(dict(role="neighbor", shot=nb, room=t["room"], label=t["label"], label_ko=t["label_ko"]))
                checks[checks.index(t["check"])] += " — `{}` 그림과 같다".format(nb)
        made.add(s["id"])
        warns = []
        for v in vis:                             # 리뷰 제품을 글로만 그리지 않는다(2026-11-13 침대를 ref:false 로 뺐다 — 사용자 지적)
            it, prod = v["it"], v["it"].get("product") or {}
            if P.reviewable(it) and (prod.get("ref") is False or not (prod.get("ref_image") or prod.get("image"))):
                warns.append("{}: 리뷰 제품인데 보드에 사진이 없어 글로만 그린다{}. 상세 이미지에서 그 제품만 찍힌 사진을 찾아 "
                             "product.ref_image·ref_crop 으로 넣는다".format(
                                 P.label_of(it), "(이 컷의 대상이다)" if it["id"] == s.get("target") else ""))
        if s["kind"] == "wide":
            for it, d, side in near_cuts(sc, cam, st):
                warns.append("{}: 카메라에서 {:.1f}m, 화면 {} 끝에 잘려 걸린다. 생성 모델이 실제보다 크게 그리기 쉽다. "
                             "photo.shots 로 카메라를 옮겨 화면 밖으로 빼거나 전체가 들어오게 한다".format(
                                 P.label_of(it), d / 1000.0, "왼쪽" if side == "left" else "오른쪽"))
        en, ko = _view_text(sc, cam, s, byid)
        light_en, light_ko = light_direction(sc, cam, st)
        view = dict(room=room, space=_room_space(house, room), finish=room_finish(house, concept, room),
                    master_finish=master_finish, colors=colors)
        prompt = build_prompt(house, concept, ratio, cam, en, view, lines, ops, board, refs, light_en, avoid, thru)
        if len(prompt) > PROMPT_MAX and thru:     # 문간 너머는 이 방보다 덜 중요하다 — 생김새를 빼고 크기·자리만 남긴다
            view["short_through"] = True
            prompt = build_prompt(house, concept, ratio, cam, en, view, lines, ops, board, refs, light_en, avoid, thru)
            warns.append("프롬프트가 한도를 넘어 문간 너머 품목의 생김새를 뺐다(크기·자리만 적는다)")
        if light_ko:
            checks.append("빛 — " + light_ko)
        checks.append("목록·소품 밖 물건(가구·가전·조명·장식·러그·액자)이 없다")
        if board:
            checks.append("제품 모양·비율·색·광택이 보드와 같다 — 다르면 `shots.py fix` 로 그 제품만 고친다")
        if not is_master:
            checks.append("벽지·바닥·창틀·커튼·빛이 대표 컷과 같다")
        shots.append(dict(
            id=s["id"], kind=s["kind"], room=s["room"], master=is_master, title=ko,
            camera=dict(x=int(round(s["x"])), y=int(round(s["y"])), height=int(round(s["z"])),
                        yaw_deg=round(math.degrees(s["yaw"]), 1), pitch_deg=round(math.degrees(s["pitch"]), 1),
                        lens_mm=s["lens"], hfov_deg=round(math.degrees(hfov), 1)),
            target=s.get("target"),
            items=[dict(id=v["it"]["id"], label=P.label_of(v["it"]), share=round(v["share"], 3),
                        x=round(v["hx"], 2), hidden=round(1 - v["frac"], 2), en=f) for v, f in zip(vis, facts)],
            through=[dict(room=t["room"], label=t["label_ko"], share=round(t["share"], 3), items=t["items"]) for t in thru],
            refs=refs, prompt=prompt, prompt_chars=len(prompt), checks=checks, warnings=warns))
    order = shots                                 # shot_order 의 순서 = 만드는 순서
    seen = {i["id"] for sh in shots for i in sh["items"] + [j for t in sh["through"] for j in t["items"]]}
    no_look = [it["id"] for it in ctx.items if it["id"] in seen and not it.get("look")]
    claims = {it["id"]: m.group(0) for it in ctx.items if it["id"] in seen
              for m in [SIZE_CLAIM.search(it.get("look") or "")] if m}
    data = dict(house=house.get("name"), concept=concept["key"], concept_ko=concept["ko"], ratio=ratio, image_size=size,
                model=ph.get("model"), quality=ph.get("quality", "medium"),
                missing_look=no_look, size_claims=claims,
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
           "카메라 자리와 보는 방향: `shots.svg` · 덩어리 스케치: `sketch/` · 제품 보드: `boards/`(board 명령)",
           "이미지 모델 {} · 품질 {} — 견적과 제출에 같은 값을 싣는다".format(
               "`{}`".format(data["model"]) if data.get("model") else "DemoCut 기본", data.get("quality", "medium")), "",
           "만드는 순서: **아래 번호 순서대로** 만든다. 대표 컷을 먼저 만들고 확인한 뒤 그 그림을 나머지 컷의 레퍼런스 1번으로 "
           "넣는다. 레퍼런스에 다른 컷의 그림이 있으면 그 컷이 언제나 앞 번호다.", ""]
    for i, s in enumerate(data["shots"], 1):
        cam = s["camera"]
        out.append("## {}. `{}` — {}{}".format(i, s["id"], s["title"], " ★ 대표 컷(먼저 만든다)" if s["master"] else ""))
        out.append("")
        out.append("- 카메라: ({:,}, {:,}) mm · 높이 {}cm · 렌즈 {:.0f}mm(화각 {}°) · 기울기 {}°".format(
            cam["x"], cam["y"], cam["height"] // 10, cam["lens_mm"], cam["hfov_deg"], cam["pitch_deg"]))
        out.append("- 보이는 품목(왼→오): " + (", ".join(
            "{}({:.0%}{})".format(it["label"], it["share"], ", 일부 가림" if it["hidden"] > 0.4 else "")
            for it in s["items"]) or "없음"))
        for t in s.get("through", []):
            out.append("- 문간 너머 {}({:.0%}): {}".format(t["label"], t["share"], ", ".join(
                "{}({:.0%})".format(it["label"], it["share"]) for it in t["items"]) or "가구 없음"))
        refs = []
        for k, r in enumerate(s["refs"], 1):
            if r["role"] == "master":
                refs.append("{}) `{}` 에서 만든 그림({})".format(k, r["shot"], "같은 방" if r.get("same_room") else "같은 집"))
            elif r["role"] == "neighbor":
                refs.append("{}) `{}` 에서 만든 그림(문간 너머 {})".format(k, r["shot"], r["label_ko"]))
            elif r["role"] == "product":
                refs.append("{}) 제품 사진 {}".format(k, r.get("url")))
            else:
                refs.append("{}) `{}`".format(k, r["file"]))
        out.append("- 레퍼런스: " + " · ".join(refs))
        for w in s.get("warnings", []):
            out.append("- ⚠ " + w)
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
        prod = it.get("product") or {}
        if prod.get("ref") is False:
            continue
        url = prod.get("ref_image") or prod.get("image") or ""   # ref_image: 그 제품만 찍힌 사진(상세 이미지 등)
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


def _crop_filter(crop):
    """ref_crop [왼, 위, 오른, 아래](0~1, 사진 폭·높이에 대한 비율) → ffmpeg crop. 다른 제품·글자·사람을 잘라 낸다."""
    if not crop:
        return ""
    l, t, r, b = (float(x) for x in crop)
    if not (0 <= l < r <= 1 and 0 <= t < b <= 1):
        raise SystemExit("ref_crop 은 [왼, 위, 오른, 아래] 0~1 비율이다(왼<오른, 위<아래): {}".format(crop))
    return "crop=iw*{:.4f}:ih*{:.4f}:iw*{:.4f}:ih*{:.4f},".format(r - l, b - t, l, t)


def make_board(files, out, crops=None, cell=None):
    n = len(files)
    if n > BOARD_CELLS:
        raise SystemExit("보드 한 장은 {}칸까지다".format(BOARD_CELLS))
    crops = crops or [None] * n
    cell = cell or (1024 if n == 1 else 512)
    cols = 1 if n == 1 else 2
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
            fc.append("[{i}:v]{crop}scale={c}:{c}:force_original_aspect_ratio=decrease,pad={c}:{c}:(ow-iw)/2:(oh-ih)/2:"
                      "color=white,setsar=1,format=rgb24[v{i}]".format(i=i, c=cell, crop=_crop_filter(crops[i])))
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
            make_board(files, out, [(r.get("crops") or {}).get(i) for i in r["items"]])
            made += 1
            print("  {} ← {}".format(os.path.relpath(out, base), ", ".join(r["items"])))
    if missing:
        print("사진이 없어 못 만든 보드 — 그 제품 사진을 받거나 house.json 의 product.image 를 고치고 plan 부터 다시:")
        for m in missing:
            print("  - " + m)
    print("보드 {}장".format(made))
    return 1 if missing else 0


# ----------------------------------------------------------------------------- fix(틀린 제품만 고치기)

def fix_prompt(items, has_board, scale=None, changes=()):
    """만든 사진(그림 1)에서 items 만 제품 사진(그림 2)대로 바꾸고 나머지는 그대로 두는 편집 프롬프트.
    OpenAI 이미지 가이드의 「change only X / keep everything else the same」 꼴과 가상 피팅 꼴(사람·배경을 잠그고
    옷만 바꾼다)을 가구에 옮겼다. 출처: references/product-fidelity.md

    scale 을 주면 모양은 맞고 크기만 틀린 것으로 보고, 그림 1 의 지금 크기를 자로 삼아 그 배율로 줄이거나 키운다.
    2026-11-13 gpt-image-2.6 은 cm 와 받침과의 비율을 적어도 손바닥만 한 조명을 생성마다 약 2배로 그렸다. 편집에서는
    그림 속 지금 크기가 자가 된다. changes 는 사진을 만든 뒤 집에서 바뀐 것(뺀 러그·바꾼 침구)을 같은 편집에 싣는 영어 문장이다."""
    names = _and("the " + f["label"] for f in items)
    out = ["Image 1 is a finished photo of a room. Edit it: change only {}{}.".format(
        names, " and make the other changes listed below; change nothing else" if changes else " and nothing else")]
    for f in items:
        extra = " " + f["extra"] if f.get("extra") else ""
        if scale:
            t = ("The {} ({}) is drawn too {}. {} it to about {}% of its current height and width in image 1, so it is its "
                 "true size, {} cm, on the same spot.{}").format(
                f["label"], f["where"], "large" if scale < 1 else "small", "Shrink" if scale < 1 else "Enlarge",
                round(scale * 100), f["size"], extra)
            t += " Keep its shape and look: {}".format(f["keep"] if f.get("keep") else f["look"])
            if f.get("ref") and has_board:
                t += "; it stays the product shown in image 2"
            t += "."
            if scale < 1:
                t += (" Fill the space it no longer covers with what is behind it in image 1, and shrink its glow and "
                      "shadow with it.")
            out.append(t)
            continue
        t = "The {} ({}): make it {}".format(f["label"], f["where"], f["look"])
        if f.get("ref") and has_board:
            t += ", exactly the product shown in image 2"
        t += ". Keep its place and true size: {} cm.{}".format(f["size"], extra)
        if f.get("keep"):
            t += " Keep exactly: {}.".format(f["keep"])
        out.append(t)
    for c in changes:
        out.append("Also: {}".format(c.strip().rstrip(".") + "."))
    if has_board:
        out.append("Image 2 shows the actual product{0} on {1} own: copy {2} shape, proportions, color, finish and details "
                   "exactly; ignore its background and any other object or text in it.".format(
                       "s" if sum(1 for f in items if f.get("ref")) > 1 else "",
                       "their" if sum(1 for f in items if f.get("ref")) > 1 else "its",
                       "each one's" if sum(1 for f in items if f.get("ref")) > 1 else "its"))
    out.append("Keep everything else in image 1 exactly as it is{}: camera angle, framing, perspective, walls, floor, window, "
               "curtains, light, shadows, colors, every other piece of furniture, the bedding and props. Match image 1's "
               "light, shadows and color temperature so {} look{} photographed in the room, not pasted in.".format(
                   " apart from the changes above" if changes else "", names, "" if len(items) > 1 else "s"))
    return "\n".join(out)


def fix(shots_path, shot_id, item_ids, images=None, scale=None, changes=()):
    if scale is not None and not (0.2 <= scale <= 3 and abs(scale - 1) >= 0.05):
        raise SystemExit("--scale 은 0.2~3 사이, 1 이 아닌 값이다(그림 속 지금 크기에 곱할 배율): {}".format(scale))
    with open(shots_path, encoding="utf-8") as f:
        data = json.load(f)
    base = os.path.dirname(os.path.abspath(shots_path))
    shot = next((s for s in data["shots"] if s["id"] == shot_id), None)
    if not shot:
        raise SystemExit("컷 {} 이 shots.json 에 없다: {}".format(shot_id, ", ".join(s["id"] for s in data["shots"])))
    have = {i["id"]: i for i in shot["items"]}
    lack = [i for i in item_ids if i not in have or "en" not in have[i]]
    if lack:
        raise SystemExit("{} 은 이 컷의 보이는 품목이 아니거나 옛 shots.json 이다(plan 을 다시 돌린다). 보이는 품목: {}".format(
            ", ".join(lack), ", ".join(have)))
    items = [have[i]["en"] for i in item_ids]
    on_board = [f for f in items if f.get("ref")][:BOARD_CELLS]
    tag = "{}--{}".format(shot_id, "-".join(_safe(i) for i in item_ids))
    refs: list = [dict(role="photo", shot=shot_id)]
    if on_board:
        refs.append(dict(role="board", file=os.path.join("boards", "fix-" + tag + ".png"), items=[f["id"] for f in on_board],
                         crops={f["id"]: f["crop"] for f in on_board if f.get("crop")}))
    changes = [c for c in changes if c.strip()]
    prompt = fix_prompt(items, bool(on_board), scale, changes)
    checks = ["{} — 제품 사진과 모양·비율·색·광택이 같다".format(have[i]["label"]) for i in item_ids]
    if scale:
        checks += ["{} — 그림 1 의 약 {}% 크기다(실제 {} cm). 받침·곁 가구와 견주어 잰다".format(
            have[i]["label"], round(scale * 100), have[i]["en"]["size"]) for i in item_ids]
    checks += ["추가 변경이 들어갔다: {}".format(c) for c in changes]
    checks += ["카메라·벽·바닥·빛·다른 가구·침구가 그림 1 과 같다(위 변경 말고는 바뀐 곳이 없다)"]
    out = dict(shot=shot_id, items=item_ids, scale=scale, changes=changes, refs=refs, prompt=prompt,
               prompt_chars=len(prompt), model=data.get("model"), quality=data.get("quality", "medium"), checks=checks)
    os.makedirs(os.path.join(base, "fixes"), exist_ok=True)
    path = os.path.join(base, "fixes", tag + ".json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print("→ {}".format(os.path.relpath(path, base)))
    if on_board and images:
        files = [_image_for(images, f["id"]) for f in on_board]
        if not all(files):
            raise SystemExit("사진이 없다: {}".format(", ".join(f["id"] for f, p in zip(on_board, files) if not p)))
        bp = os.path.join(base, refs[1]["file"])
        os.makedirs(os.path.dirname(bp), exist_ok=True)
        make_board(files, bp, [f.get("crop") for f in on_board])
        print("  {} ← {}".format(refs[1]["file"], ", ".join(f["id"] for f in on_board)))
    elif on_board:
        print("  보드는 --images 를 주면 만든다")
    print("레퍼런스: 1) 컷 {} 에서 만든 그림{}".format(shot_id, "  2) " + refs[1]["file"] if on_board else ""))
    print(prompt)
    return 0


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
    d = sub.add_parser("fix", help="만든 사진에서 틀린 제품만 제품 사진대로 고치는 편집 프롬프트·보드")
    d.add_argument("shots")
    d.add_argument("shot")
    d.add_argument("items", nargs="+")
    d.add_argument("--images")
    d.add_argument("--scale", type=float, help="모양은 맞고 크기만 틀렸을 때 그림 속 지금 크기에 곱할 배율(2배로 나왔으면 0.5)")
    d.add_argument("--change", action="append", default=[], help="같은 편집에 실을 집의 변경(영어 문장, 여러 번 줄 수 있다)")
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
            if s["prompt_chars"] > PROMPT_MAX:
                print("     ⚠ 프롬프트가 DemoCut 한도({:,}자)를 넘는다 — 거절된다. look·keep·props 를 줄인다".format(PROMPT_MAX))
            elif s["prompt_chars"] > PROMPT_MAX - 200:
                print("     ⚠ 프롬프트가 DemoCut 한도({:,}자)에 가깝다. look 을 줄인다".format(PROMPT_MAX))
            for w in s["warnings"]:
                print("     ⚠ " + w)
        if data["missing_look"]:
            print("⚠ look 이 없는 품목: {} — 제품 사진을 보고 items[].look 에 영어 한 문장을 적은 뒤 plan 을 다시 돌린다"
                  "(없으면 상품명이 들어가 모양이 틀어진다)".format(", ".join(data["missing_look"])))
        if data["size_claims"]:
            print("⚠ look 에 크기 관계 말이 있다: {} — 크기·여백은 치수와 가구별 규칙이 정한다. 제품 사진이 고른 옵션과 "
                  "다른 크기일 수 있으니 그 말을 빼고 모양·색·재질만 적는다".format(
                      ", ".join("{}('{}')".format(k, v) for k, v in data["size_claims"].items())))
        return 0
    if args.cmd == "fetch":
        fetch(P.load(args.house), args.dest)
        return 0
    if args.cmd == "fix":
        return fix(args.shots, args.shot, args.items, args.images, args.scale, args.change)
    return board(args.shots, args.images, args.out)


if __name__ == "__main__":
    sys.exit(main())
