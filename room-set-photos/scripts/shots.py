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
SEAM_PAD = 50               # 한 면으로 이어진 벽의 가짜 모서리 선을 지울 때 두 방 벽 쪽으로 더 덮는 폭(mm)
SIDE_BY_SIDE = 600          # 한 면으로 이어진 벽에 붙은 이 방 가구와 너머 가구가 이만큼(mm) 안쪽이면 「나란히」 로 적는다
FILL_GAP = 30               # 벽에 붙은 가구가 그 벽보다 이만큼(mm) 안 되게 좁으면 「벽을 모서리까지 채운다」 로 적는다
WIDE_CLOSE = 750            # 전체 컷에서 화면을 크게 차지한 가구가 이보다 가까우면 점수를 깎는다(mm)
BIG_CUT = 600               # 그 검사를 받는 가구의 바닥 긴 변(mm)
NEAR_GAP = 100              # 바닥 가구 둘 사이가 이보다 좁으면 사이를 적는다. 안 적으면 붙거나 한쪽이 밑으로 파고든다(mm)
DEFAULT_CEIL = 2300
DOOR_H = 2100
NORMAL = {"n": (0, -1), "s": (0, 1), "w": (-1, 0), "e": (1, 0)}
RATIOS = {                  # DemoCut 프로젝트 비율 → (스케치 가로, 세로, 그림 크기, 센서 가로 mm, 설명)
    "9:16": (683, 1024, "1024x1536", 24.0, "vertical 2:3"),
    "1:1": (1024, 1024, "1024x1024", 24.0, "square 1:1"),
    "16:9": (1024, 683, "1536x1024", 36.0, "horizontal 3:2"),
}
# 폰 카메라(35mm 환산). 세로 사진은 센서 가로 24mm 로 화각을 낸다(RATIOS).
# 기본 26mm → 가로 약 50°. 초광각 16mm 는 13–16mm 구간에서 덜 넓은 쪽(약 74°).
# 18mm 는 기본과 초광각 사이라 가까이서 앞면을 늘린다. 제안에는 쓰지 않는다.
MAIN_LENS, ULTRA_LENS = 26.0, 16.0
HERO_LENS = MAIN_LENS
WIDE_LENS = 18.0             # 직접 카메라를 만드는 옛 호출용. plan 은 MAIN_LENS·ULTRA_LENS 만 고른다
# 서는 자리. 카메라는 폰이다.
WALL_CLEAR = 300             # 벽에서 30cm. 폰을 가슴 앞에 들면 어깨가 벽 안에 들어가지 않는다
BODY_CLEAR = 350             # 가구 면에서 35cm. 몸통이 가구에 닿지 않는다
NEAR_MIN = 800               # 화면에 들어온 가구까지 80cm(한 걸음). 26mm 에서 이보다 가까우면 앞면이 늘어나고
                             # 30cm 그릇 건조대가 가전만 해진다. 초광각으로도 이 거리 안에서는 찍지 않는다
SHARE_MAX = 0.38             # 한 물건이 화면의 이 비율을 넘으면 전체 컷이 아니라 그 물건의 근접 사진
SPAN_MAX = 0.65              # 상자 가로·세로가 화면의 이 비율을 넘으면 그 물건이 화면을 덮는다
SCALE_RATIO = 2.5            # 화면크기×거리/실제크기 가 다른 물건 중앙값의 이 배보다 크면 거리만으로 설명이 안 된다
PROMINENT = 0.06             # 이 비율 이상 보이면 「화면에 들어왔다」(가장자리 조각은 거리 검사에서 뺀다)
# 수평 촬영의 수평선 높이(위에서 비율). 건축 사진처럼 렌즈를 올려(시프트) 수직선을 세운 채 천장을 덜 담는다
HORIZON = {"9:16": 0.38, "1:1": 0.42, "16:9": 0.46}
SCORE_DIV = 6               # 후보를 고를 때는 1/6 크기로 그려 본다
BOARD_CELLS = 4             # 제품 보드 한 장의 칸 수(2×2 × 512px = 1024px, DemoCut 레퍼런스 상자에서 줄지 않는다)
PROMPT_MAX = 4000           # DemoCut ai_image 프롬프트 한도
SHALLOW_MM = 1000           # 문간 너머 깊이가 이하면 복도로 늘리지 말라고 적는다
AVOID_SHALLOW = "a hallway or corridor longer than the stated depth"
AVOID_JAMB = "a door frame or jambs in a full-width opening"
AVOID_SIDE = "furniture on the opposite side of the frame from this shot's sketch"
AVOID_BARE_WALL = "an open bare wall above the counter"
AVOID_NO_HOOD = "a cooktop with no hood"
AVOID_BARE_TOP = "a bare {} top"          # 화면에 있는 받침인데 그 위 품목이 빠질 때. 이름은 집 모델에서 온다
AVOID_TILE = "tile boundary shifted into the kitchen/room or set back into the entry"
AVOID_TILE_UNDER = "tile spilling under the {}"
AVOID_TILE_PARTWAY = "tile ending partway under the {}"
AVOID_TILE_IN_FRAME = "any tile floor in frame"
AVOID_TOWEL = "a towel bar or towel hook on another wall or at a different height"

BG = (250, 250, 250)
FLOOR = (150, 150, 152)
# 현관 타일 구역은 스케치에서 바둑판으로 칠한다. 바닥을 한 색으로 그리면 모델이 타일과 마루의 경계를 제 마음대로 두어,
# 타일이 옆방 가구 밑까지 들어오거나 현관 가구 중간에서 끝났다(2026-11-17 저녁 컷). 타일 칸 크기는 TILE_GRID mm
TILE = (112, 128, 150)
TILE_ALT = (138, 152, 172)
TILE_GRID = 300
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
# 문간 너머 방은 이 방 상자와 색 이름이 겹치지 않게 고른다. 팔레트가 부족하면 이쪽을 쓴다.
# 이 목록은 카메라가 선 방의 상자 색(PALETTE 의 순번)을 바꾸지 않는다.
MORE_COLORS = [((184, 92, 48), "rust"), ((48, 92, 72), "pine"), ((92, 48, 72), "plum"),
               ((48, 72, 120), "navy"), ((176, 148, 96), "tan"), ((120, 60, 48), "brick"),
               ((72, 140, 120), "sage"), ((150, 80, 130), "mauve")]


def _next_box_color(used):
    """이미 쓴 색 이름을 피한다. 이름까지 떨어지면 번호 색을 만든다."""
    for color in PALETTE + MORE_COLORS:
        if color[1] not in used:
            used.add(color[1])
            return color
    n = len(used)
    name = "box{}".format(n)
    while name in used:
        n += 1
        name = "box{}".format(n)
    used.add(name)
    return ((40 + (n * 47) % 180, 50 + (n * 29) % 180, 60 + (n * 67) % 180), name)
DEFAULT_H = {"bed": 300, "desk": 740, "dining_table": 740, "chair": 900, "lamp": 500, "sofa": 800}

KIND_EN = {"bedroom": "bedroom", "living": "living room", "kitchen": "kitchen", "bathroom": "bathroom",
           "entrance": "entryway", "hall": "hallway", "dressroom": "dressing room", "utility": "utility room"}

# ----------------------------------------------------------------------------- 오늘의집 컨셉

COMMON_LOOK = ("A real photo from an Ohouse (오늘의집) house-tour post, shot by the resident on a smartphone: "
               "phone-photo texture, muted natural colors, low contrast, light sensor noise, tidy but lived-in, "
               "not a 3D render or a staged ad.")
HOME_DETAILS = ("Korean home: PVC sash, white baseboards, silk wallpaper, LED ceiling light.")
# 공간 종류마다 마감·소품이 다르다. 방의 벽지·마루·침구 문장을 그대로 쓰면 화장실이 벽지·마루로 나오고 주방·현관에 침구
# 소품이 붙는다(2026-11-13 원룸 계획에서 확인). {walls}·{floor} 는 컨셉 값. photo.rooms.<종류 또는 방 id> 로 덮어쓴다
KIND_FINISH = {
    "bathroom": dict(
        walls="glossy white ceramic wall tiles from floor to ceiling",
        floor="light gray non-slip ceramic floor tiles sloping to a floor drain",
        details="Korean bathroom details: tiled walls and floor, a floor drain, a raised threshold at the door, "
                "a flat square LED ceiling light.",
        props="a soap dispenser and a toothbrush cup by the basin"),
    "entrance": dict(
        floor="gray porcelain floor tiles, one step below the next room's floor",
        props="one pair of white sneakers on the floor tiles"),
    "kitchen": dict(
        walls="{walls}, with white ceramic tiles on the wall behind the counter",
        props="a few dishes in the dish rack, a white electric kettle, a folded dish towel"),
}
LIVING_KINDS = {"bedroom", "living", "dressroom", None}   # 컨셉 소품(침구·책)이 맞는 공간. None = 종류를 안 적은 방
FINISH_KEYS = ("walls", "floor", "details", "props")


# 도면이 style 을 적지 않은 창은 한국 샷시다. 한쪽 짝만 옆으로 밀려 열린다.
_SASH_STYLES = {"", "sash", "sliding", "sliding-sash", "pvc"}
_SASH_AVOID = "casement, hinged, or push-out windows"


def _win_size(o):
    """(sill, height) mm. 높이가 없으면 1200. 위 끝은 턱+높이."""
    raw = o.get("op") if isinstance(o.get("op"), dict) else {}
    sill = o.get("sill", raw.get("sill", 900))
    height = o.get("height", raw.get("height")) or 1200
    return sill, height


def _below_window(sc, o):
    """창 바로 아래 가구의 영어 이름. 창이 그 가구 위에 앉는다."""
    wall = o.get("wall")
    if not wall or not sc:
        return ""
    a, b = sorted((o["a"], o["b"]))
    sill, _h = _win_size(o)
    best, best_ov = None, 0
    for it in sc.items:
        if it.get("on") or P.CAT.get(it.get("category"), {}).get("floor"):
            continue
        if _place_wall(it) != wall:
            continue
        g = sc.ctx.geo[it["id"]]
        if item_height(it, g) > sill + 250:
            continue
        lo, hi = (g["rect"][0], g["rect"][2]) if wall in "ns" else (g["rect"][1], g["rect"][3])
        ov = min(hi, b) - max(lo, a)
        if ov > best_ov:
            best, best_ov = it, ov
    if not best or best_ov < 200:
        return ""
    return _label_en(best)


def _window_words(o):
    """(짧은 이름, 기본 샷시인지). style 이 있으면 그 창이고, 금지어를 붙이지 않는다.
    플래너가 감싼 개구부는 원본이 op 안에 있다."""
    raw = o.get("op") if isinstance(o.get("op"), dict) else o
    style = str(raw.get("style") or "").strip().lower().replace("_", "-")
    if style not in _SASH_STYLES:
        return style.replace("-", " "), False
    if raw.get("open") in (True, "open", "slid", "yes"):
        return "sliding sash, one pane slid open behind the other", True
    return "sliding sash", True


# 원룸·작은 방 창은 간유리다. 바깥 쇠창살 실루엣이 그 유리에 비치고, 나무·하늘·건물은 선명하지 않다(2026-11-18).
_FROSTED = "frosted translucent glass with the outside security-bar silhouette on it"
_FROSTED_PLAIN = "frosted translucent glass"
_GLASS_AVOID = "clear transparent glass, a sharp outdoor view of trees, sky, or buildings"
_GLASS_CHECK = "창 — 간유리(반투명)에 바깥 쇠창살 실루엣. 맑은 유리로 나무·하늘·건물이 선명하지 않다"
_GLASS_CHECK_PLAIN = "창 — 간유리(반투명). 맑은 유리로 나무·하늘·건물이 선명하지 않다"
_SASH_CHECK = "창 — 샷시 미닫이(한쪽 짝만 옆으로). 여닫이·들창·틸트 아님"


def _glass_phrase(o):
    """플래너가 채운 glass·bars. 간유리면 짧은 영어 구, 아니면 빈 문자열."""
    raw = o.get("op") if isinstance(o.get("op"), dict) else {}
    glass = o.get("glass", raw.get("glass"))
    bars = o.get("bars") if "bars" in o else raw.get("bars")
    if glass != "frosted":
        return ""
    if bars == "outside":
        return _FROSTED
    return _FROSTED_PLAIN


def _window_text(o, rel, hp, above, curtains, view):
    """In view 의 창 한 토막. 간유리면 창밖이 선명한 문장은 붙이지 않는다."""
    wname, sash = _window_words(o)
    _sill, height = _win_size(o)
    phrase = _glass_phrase(o)
    outdoor = "" if phrase else (", " + view[0] if view else "")
    text = "a {}x{} cm {}{} on {} ({}){}, sill {} cm, {}{}".format(
        _cm(o["b"] - o["a"]), _cm(height), wname, (", " + phrase) if phrase else "",
        rel, hp, above, _cm(_sill), curtains, outdoor)
    return text, sash, phrase


def _note_window(checks, avoid, sash, phrase, view):
    if sash and _SASH_CHECK not in checks:
        checks.append(_SASH_CHECK)
    if sash and _SASH_AVOID not in avoid:
        avoid.append(_SASH_AVOID)
    if phrase:
        chk = _GLASS_CHECK if "security-bar" in phrase else _GLASS_CHECK_PLAIN
        if chk not in checks:
            checks.append(chk)
        if _GLASS_AVOID not in avoid:
            avoid.append(_GLASS_AVOID)
    elif view:
        if view[1] not in checks:
            checks.append(view[1])
        if view[2] and view[2] not in avoid:
            avoid.append(view[2])


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
OPENING_LEGEND = ((WINDOW, "pale blue = window"), (DOOR, "brown = door"), (VOID, "dark gray = open doorway"),
                  (TILE, "checkered slate floor = entry tile, ending at its edge line"))

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
        with open(path, "wb") as f:
            f.write(_png(self.w, self.h, self.px))

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


def _png(w, h, px):
    raw = b"".join(b"\x00" + bytes(px[y * w * 3:(y + 1) * w * 3]) for y in range(h))

    def chunk(t, d):
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))


# 범례 글자. 글꼴 파일이 있으면 그 크기로 그리고, 없으면 아래 비트맵(DejaVu Sans 17px)을 정수배로 키운다.
# 모델에 넣는 스케치에는 글자를 그리지 않는다.
_BITMAP_H = 21
_BITMAP = {
    ' ': (6, [0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0]),
    'a': (11, [0,0,0,0,0,0,0,504,28,12,508,908,780,780,796,492,0,0,0,0,0]),
    'b': (11, [0,0,0,768,768,768,768,888,972,902,774,774,774,902,972,888,0,0,0,0,0]),
    'c': (10, [0,0,0,0,0,0,0,124,196,384,384,384,384,384,196,124,0,0,0,0,0]),
    'd': (11, [0,0,0,4,4,4,4,244,412,780,780,772,780,780,412,244,0,0,0,0,0]),
    'e': (11, [0,0,0,0,0,0,0,248,396,772,774,1022,768,768,388,248,0,0,0,0,0]),
    'f': (6, [0,0,0,7,12,12,12,63,12,12,12,12,12,12,12,12,0,0,0,0,0]),
    'g': (11, [0,0,0,0,0,0,0,244,412,780,780,772,780,780,412,244,12,12,284,248,0]),
    'h': (11, [0,0,0,768,768,768,768,888,972,908,772,774,774,774,774,774,0,0,0,0,0]),
    'i': (5, [0,0,0,12,12,0,0,12,12,12,12,12,12,12,12,12,0,0,0,0,0]),
    'j': (5, [0,0,0,12,12,0,0,12,12,12,12,12,12,12,12,12,12,12,12,24,0]),
    'k': (10, [0,0,0,384,384,384,384,390,396,440,496,480,432,408,396,390,0,0,0,0,0]),
    'l': (5, [0,0,0,12,12,12,12,12,12,12,12,12,12,12,12,12,0,0,0,0,0]),
    'm': (17, [0,0,0,0,0,0,0,56952,62412,58252,49932,49932,49932,49932,49932,49932,0,0,0,0,0]),
    'n': (11, [0,0,0,0,0,0,0,888,972,908,772,774,774,774,774,774,0,0,0,0,0]),
    'o': (11, [0,0,0,0,0,0,0,248,412,780,774,774,774,780,412,248,0,0,0,0,0]),
    'p': (11, [0,0,0,0,0,0,0,888,972,902,774,774,774,902,972,888,768,768,768,768,0]),
    'q': (11, [0,0,0,0,0,0,0,244,412,780,780,772,780,780,412,244,4,4,4,4,0]),
    'r': (7, [0,0,0,0,0,0,0,55,61,56,48,48,48,48,48,48,0,0,0,0,0]),
    's': (9, [0,0,0,0,0,0,0,124,198,192,224,124,14,6,134,124,0,0,0,0,0]),
    't': (7, [0,0,0,0,48,48,48,126,48,48,48,48,48,48,24,30,0,0,0,0,0]),
    'u': (11, [0,0,0,0,0,0,0,772,772,772,772,772,780,780,412,244,0,0,0,0,0]),
    'v': (11, [0,0,0,0,0,0,0,518,780,780,408,408,408,240,240,96,0,0,0,0,0]),
    'w': (14, [0,0,0,0,0,0,0,6342,6598,6630,6628,3372,3900,3900,1848,1560,0,0,0,0,0]),
    'x': (11, [0,0,0,0,0,0,0,780,408,248,240,96,240,408,924,780,0,0,0,0,0]),
    'y': (11, [0,0,0,0,0,0,0,774,780,780,408,408,248,240,240,96,96,96,192,896,0]),
    'z': (9, [0,0,0,0,0,0,0,254,6,12,28,56,112,96,192,254,0,0,0,0,0]),
    'A': (12, [0,0,0,0,224,240,240,432,408,280,780,1020,1540,1542,1542,3078,0,0,0,0,0]),
    'B': (12, [0,0,0,0,2040,1820,1804,1804,1820,2040,1820,1804,1806,1806,1820,2040,0,0,0,0,0]),
    'C': (12, [0,0,0,0,252,390,770,1536,1536,1536,1536,1536,1536,770,390,252,0,0,0,0,0]),
    'D': (14, [0,0,0,0,8160,7224,7192,7180,7180,7180,7180,7180,7180,7192,7224,8160,0,0,0,0,0]),
    'E': (11, [0,0,0,0,1022,896,896,896,896,1020,896,896,896,896,896,1022,0,0,0,0,0]),
    'F': (10, [0,0,0,0,510,448,448,448,448,508,448,448,448,448,448,448,0,0,0,0,0]),
    'G': (14, [0,0,0,0,1016,1564,3076,6144,6144,6144,6268,6156,6156,3084,1564,1016,0,0,0,0,0]),
    'H': (13, [0,0,0,0,3596,3596,3596,3596,3596,4092,3596,3596,3596,3596,3596,3596,0,0,0,0,0]),
    'I': (6, [0,0,0,0,28,28,28,28,28,28,28,28,28,28,28,28,0,0,0,0,0]),
    'J': (6, [0,0,0,0,28,28,28,28,28,28,28,28,28,28,28,28,24,24,48,0,0]),
    'K': (12, [0,0,0,0,1806,1820,1848,1888,1984,1920,1984,2016,1904,1816,1804,1798,0,0,0,0,0]),
    'L': (10, [0,0,0,0,448,448,448,448,448,448,448,448,448,448,448,511,0,0,0,0,0]),
    'M': (15, [0,0,0,0,15388,15388,15420,15932,13868,12908,13164,13260,12748,12748,12300,12300,0,0,0,0,0]),
    'N': (13, [0,0,0,0,3596,3852,3852,3468,3532,3276,3180,3180,3132,3132,3100,3100,0,0,0,0,0]),
    'O': (14, [0,0,0,0,1008,3640,3100,6156,6156,6158,6158,6156,6156,3100,3640,1008,0,0,0,0,0]),
    'P': (11, [0,0,0,0,1016,908,902,902,902,908,1016,896,896,896,896,896,0,0,0,0,0]),
    'Q': (14, [0,0,0,0,1008,3640,3100,6156,6156,6158,6158,6156,6156,3100,3640,1008,48,24,0,0,0]),
    'R': (12, [0,0,0,0,2032,1816,1804,1804,1804,1816,2032,1816,1820,1804,1798,1798,0,0,0,0,0]),
    'S': (11, [0,0,0,0,248,396,772,768,896,496,124,14,6,518,908,504,0,0,0,0,0]),
    'T': (11, [0,0,0,0,2047,96,96,96,96,96,96,96,96,96,96,96,0,0,0,0,0]),
    'U': (13, [0,0,0,0,3084,3084,3084,3084,3084,3084,3084,3084,3084,1548,1816,1008,0,0,0,0,0]),
    'V': (12, [0,0,0,0,3078,1542,1542,1548,780,796,408,408,432,240,240,224,0,0,0,0,0]),
    'W': (17, [0,0,0,0,50054,50054,50054,50830,26316,26316,25804,27736,15480,15480,14456,14384,0,0,0,0,0]),
    'X': (12, [0,0,0,0,1542,780,408,440,240,96,240,240,408,796,1804,1542,0,0,0,0,0]),
    'Y': (11, [0,0,0,0,1542,782,396,408,240,112,96,96,96,96,96,96,0,0,0,0,0]),
    'Z': (12, [0,0,0,0,2046,14,28,56,48,96,224,448,896,768,1536,2046,0,0,0,0,0]),
    '0': (11, [0,0,0,0,248,412,396,774,774,774,774,774,774,396,412,248,0,0,0,0,0]),
    '1': (11, [0,0,0,0,240,432,48,48,48,48,48,48,48,48,48,508,0,0,0,0,0]),
    '2': (11, [0,0,0,0,496,924,524,12,12,28,56,112,224,448,384,1020,0,0,0,0,0]),
    '3': (11, [0,0,0,0,504,284,12,12,28,248,28,12,6,12,796,504,0,0,0,0,0]),
    '4': (11, [0,0,0,0,56,56,120,216,216,408,792,792,1022,24,24,24,0,0,0,0,0]),
    '5': (11, [0,0,0,0,508,384,384,384,504,284,12,12,12,12,796,504,0,0,0,0,0]),
    '6': (11, [0,0,0,0,120,196,384,768,1016,972,902,774,774,390,460,248,0,0,0,0,0]),
    '7': (11, [0,0,0,0,1022,12,12,24,24,56,48,48,96,96,96,192,0,0,0,0,0]),
    '8': (11, [0,0,0,0,248,396,780,780,396,248,396,774,774,774,396,248,0,0,0,0,0]),
    '9': (11, [0,0,0,0,248,412,780,782,782,782,414,246,12,12,280,496,0,0,0,0,0]),
    '-': (7, [0,0,0,0,0,0,0,0,0,0,60,60,0,0,0,0,0,0,0,0,0]),
    '?': (10, [0,0,0,0,248,412,12,12,24,48,96,96,96,0,96,96,0,0,0,0,0]),
}


_FONT_FILES = (
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
    "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",
)
_FONT_CACHE = {}


def _font_file():
    for path in _FONT_FILES:
        if os.path.isfile(path):
            return path
    roots = ("/usr/share/fonts", "/usr/local/share/fonts")
    names = {"dejavusans.ttf", "liberationsans-regular.ttf", "notosans-regular.ttf"}
    for root in roots:
        if not os.path.isdir(root):
            continue
        for dirpath, _dirs, files in os.walk(root):
            for name in files:
                if name.lower() in names:
                    return os.path.join(dirpath, name)
    return None


def _legend_font(px):
    """요청한 크기의 트루타입. 없거나 PIL 이 없으면 None."""
    try:
        from PIL import ImageFont
    except ImportError:
        return None
    path = _font_file()
    if not path:
        return None
    key = (path, int(px))
    font = _FONT_CACHE.get(key)
    if font is None:
        font = ImageFont.truetype(path, int(px))
        _FONT_CACHE[key] = font
    return font


def _scale_rows(w, rows, k):
    if k <= 1:
        return w, list(rows)
    nw = w * k
    out = []
    for bits in rows:
        row = 0
        for x in range(w):
            if bits & (1 << (w - 1 - x)):
                for dx in range(k):
                    row |= 1 << (nw - 1 - (x * k + dx))
        out.extend([row] * k)
    return nw, out


def _bitmap_glyph(ch, px):
    spec = _BITMAP.get(ch) or _BITMAP.get(ch.lower()) or _BITMAP["?"]
    k = max(1, int(round(float(px) / _BITMAP_H)))
    return _scale_rows(spec[0], spec[1], k) + (k,)


def _ttf_glyph(font, ch):
    from PIL import Image, ImageDraw
    ascent, descent = font.getmetrics()
    h = ascent + descent
    adv = max(3, int(math.ceil(font.getlength(ch) or (h * 0.35))))
    im = Image.new("L", (adv + 2, h + 2), 0)
    ImageDraw.Draw(im).text((1, ascent + 1), ch, font=font, fill=255, anchor="ls")
    px = im.load()
    rows = []
    for y in range(h):
        bits = 0
        for x in range(adv):
            if px[x + 1, y + 1] > 80:
                bits |= 1 << (adv - 1 - x)
        rows.append(bits)
    return adv, h, rows


def legend_glyphs(text, px=22, source=None):
    """글자마다 (문자, 왼쪽 x, 너비, 높이, 행 비트). 상자는 겹치지 않고 글자를 잘라 내지 않는다.
    source 가 bitmap 이면 글꼴 파일이 있어도 비트맵을 쓴다."""
    px = max(8, int(px))
    font = None if source == "bitmap" else _legend_font(px)
    gap = max(2, px // 10)
    out, x = [], 0
    for ch in text:
        if font is not None:
            w, h, rows = _ttf_glyph(font, ch)
        else:
            w, rows, _k = _bitmap_glyph(ch, px)
            h = len(rows)
        out.append((ch, x, w, h, rows))
        x += w + gap
    return out


def _legend_entries(sc, cv, st, cam=None):
    """스케치에 실제로 칠해진 상자와 창·문. 빈 문간(VOID)은 범례에 넣지 않는다.
    수건걸이는 픽셀이 적어도 범례에 자리를 적는다. cam 이 있으면 그 문장이다."""
    out, seen = [], set()

    def add(color, text):
        key = (tuple(color), text)
        if key in seen:
            return
        seen.add(key)
        out.append((tuple(color), text))

    def show(it, pixels):
        return (pixels and pixels[0] >= 20) or P.is_towel(it)

    for it in sc.items:
        iid = sc.iid[it["id"]]
        if show(it, st.get(iid)):
            add(sc.color[it["id"]][0], _legend_label(it, sc.ctx, cam))
    for cid, (nb, it, _oid) in getattr(cv, "through", {}).items():
        s = st.get(cid)
        if show(it, s):
            add(nb.color[it["id"]][0], _legend_label(it, nb.ctx, cam))
    for col, txt in OPENING_LEGEND:
        if col == VOID:
            continue
        if tuple(col) in {(r, g, b) for r, g, b in zip(cv.px[0::3], cv.px[1::3], cv.px[2::3])}:
            add(col, txt.split("=")[-1].strip())
    return out


def write_legend(cv, path, entries, px=22):
    """사람용. 스케치 오른쪽에 색 견본과 이름을 붙인다. 모델에 넣는 파일은 이쪽이 아니다."""
    layouts = [legend_glyphs(label, px) for _color, label in entries]
    line_h = 1
    text_w = 0
    for gs in layouts:
        if not gs:
            continue
        line_h = max(line_h, max(g[3] for g in gs))
        text_w = max(text_w, gs[-1][1] + gs[-1][2])
    sw = max(16, int(px))
    gap = max(8, int(px) // 3)
    panel = 10 + sw + 12 + text_w + 14
    row_h = line_h + gap
    W = cv.w + panel
    H = max(cv.h, 12 + max(1, len(entries)) * row_h + 10)
    buf = bytearray(bytes((255, 255, 255)) * (W * H))
    for y in range(cv.h):
        buf[y * W * 3:y * W * 3 + cv.w * 3] = cv.px[y * cv.w * 3:(y + 1) * cv.w * 3]
    for y in range(H):
        i = (y * W + cv.w) * 3
        buf[i:i + 3] = bytes((180, 180, 180))

    def pix(x, y, rgb):
        if 0 <= x < W and 0 <= y < H:
            i = (y * W + x) * 3
            buf[i:i + 3] = bytes(rgb)

    y = 12
    for (color, _label), gs in zip(entries, layouts):
        x0 = cv.w + 10
        for dy in range(sw):
            for dx in range(sw):
                pix(x0 + dx, y + dy, color if 1 <= dx < sw - 1 and 1 <= dy < sw - 1 else (40, 40, 40))
        tx = x0 + sw + 12
        ty = y + max(0, (sw - line_h) // 2)
        for _ch, gx, w, h, rows in gs:
            for r, bits in enumerate(rows):
                for c in range(w):
                    if bits & (1 << (w - 1 - c)):
                        pix(tx + gx + c, ty + r, (20, 20, 20))
        y += row_h
    with open(path, "wb") as f:
        f.write(_png(W, H, buf))



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
    if cat == "sink":
        # 볼의 부피는 상판 안에 숨는다. 옆면을 통으로 그리면 카메라 쪽에서 상판 앞면을 가리는 큰 상자가 된다.
        # 보이는 것은 윗면에 딱 붙은 어두운 개구와, 뒤 테두리의 가는 수전뿐이다.
        mrg = max(8.0, min(20.0, (x1 - x0) * 0.08, (y1 - y0) * 0.08))
        basin = (x0 + mrg, y0 + mrg, x1 - mrg, y1 - mrg)
        stub = h if 40 <= h <= 450 else 140
        half = 25.0                                 # 수전 폭 약 50mm
        cx, cy = (x0 + x1) / 2.0, (y0 + y1) / 2.0
        if back == "n":
            faucet = (cx - half, y0, cx + half, min(y1, y0 + 40))
        elif back == "s":
            faucet = (cx - half, max(y0, y1 - 40), cx + half, y1)
        elif back == "w":
            faucet = (x0, cy - half, min(x1, x0 + 40), cy + half)
        else:
            faucet = (max(x0, x1 - 40), cy - half, x1, cy + half)
        return [(basin, b - 3, b - 0.5), (faucet, b, b + stub)]
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


def _on_wall(o, u, v, z):
    """개구부 o 의 벽 좌표 → 집 좌표. u: 벽을 따라, v: 벽을 가로질러."""
    return (u, v, z) if o["axis"] == "x" else (v, u, z)


def _seam_sides(sc, nb, o):
    """개구부가 모서리에 붙어 있고 그쪽 옆 벽이 너머 방 벽과 한 면(좌표가 같다)인 쪽: [(벽 이름, 벽을 따른 좌표)].
    그 자리에는 모서리가 없다. 두 방의 옆 벽과 벽 두께 면이 한 벽이다."""
    hr, nr = P.rr(sc.room), P.rr(nb.room)
    lo, hi = min(o["a"], o["b"]), max(o["a"], o["b"])
    ends = (("w", 0, lo), ("e", 2, hi)) if o["axis"] == "x" else (("n", 1, lo), ("s", 3, hi))
    return [(side, u) for side, k, u in ends if abs(u - hr[k]) <= 1 and abs(u - nr[k]) <= 1]


def _reveal(o, top, floor=FLOOR):
    """문간이 벽 두께를 지나는 네 면(양 옆·바닥·위). 두 방의 벽 선(line·other_line) 사이다.
    floor: 바닥 면 색. 현관 타일 문간이면 TILE(경계는 옆방 벽 선이라 벽 두께 바닥도 타일이다)."""
    l0, l1, a, b = o["line"], o["other_line"], o["a"], o["b"]

    def pt(u, v, z):
        return _on_wall(o, u, v, z)
    return [([pt(u, l0, 0), pt(u, l1, 0), pt(u, l1, top), pt(u, l0, top)], WALLS["w"]) for u in (a, b)] + [
        ([pt(a, l0, z), pt(b, l0, z), pt(b, l1, z), pt(a, l1, z)], col) for z, col in ((0, floor), (top, CEIL))]


def tile_entry(room):
    """타일 바닥 현관인가. floor 가 false, 타일이 아닌 material, 'tile' 이 없는 문자열이면 아니다."""
    if not room or room.get("kind") != "entrance":
        return False
    f = room.get("floor")
    if f is False:
        return False
    if isinstance(f, str):
        return "tile" in f.lower()
    if isinstance(f, dict):
        return f.get("material") in (None, "tile") and f.get("tile") is not False
    return True


def entry_tile(ctx, eid):
    """현관 타일 구역. 현관 방 전체와, 옆방과 잇는 문간의 벽 두께 바닥이다. 경계는 옆방 쪽 벽 선이다.
    → (사각형 목록, 경계 목록[dict(op, room=옆방, line=경계 좌표, a, b)])"""
    rects, edges = [tuple(P.rr(ctx.rooms[eid]))], []
    for o in ctx.ops:
        if o["type"] == "window" or eid not in (o["room"], o.get("to")):
            continue
        other = o["to"] if o["room"] == eid else o["room"]
        if other not in ctx.rooms or "other_line" not in o:
            continue
        a, b = sorted((o["a"], o["b"]))
        plane = o["line"] if o["room"] == other else o["other_line"]
        near = o["other_line"] if o["room"] == other else o["line"]
        lo, hi = sorted((plane, near))
        rects.append((a, lo, b, hi) if o["axis"] == "x" else (lo, a, hi, b))
        edges.append(dict(op=o, room=other, line=plane, a=a, b=b))
    return rects, edges


def tile_squares(rect, grid=TILE_GRID):
    """바닥 사각형을 grid mm 바둑판으로 나눈 (다각형, 색) 목록. 스케치에서 타일 구역을 마루와 다르게 보인다."""
    x0, y0, x1, y1 = rect
    out = []
    i = 0
    x = x0
    while x < x1 - 1:
        xe = min(x1, x + grid)
        j = 0
        y = y0
        while y < y1 - 1:
            ye = min(y1, y + grid)
            out.append(([(x, y, 0), (xe, y, 0), (xe, ye, 0), (x, ye, 0)], TILE if (i + j) % 2 == 0 else TILE_ALT))
            y, j = ye, j + 1
        x, i = xe, i + 1
    return out


class Scene:
    def __init__(self, ctx, room, ceil):
        self.ctx, self.room, self.ceil = ctx, room, ceil
        x0, y0, x1, y1 = P.rr(room)
        C = ceil
        floor = ([(None, pts, col) for pts, col in tile_squares((x0, y0, x1, y1))] if tile_entry(room) else
                 [(None, [(x0, y0, 0), (x1, y0, 0), (x1, y1, 0), (x0, y1, 0)], FLOOR)])
        self.shell = floor + [         # (벽 이름 — 바닥·천장은 None, 다각형, 색)
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
                sill, height = _win_size(o)
                z0, z1, col = sill, sill + height, WINDOW
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
        seq = sorted(self.items, key=near_dist, reverse=True)   # 먼 것부터. 가까운 것이 나중에 덮는다
        # 받침 위에 올린 것은 받침 바로 뒤에, 그 안에서는 다시 먼 것부터. 한 번에 받침 바로 뒤에 꽂으면
        # 나중에 꽂은(가까운) 것이 앞자리를 차지해 먼 싱크가 가까운 건조대 위에 칠해진다.
        kids = {}
        for it in seq:
            if it.get("on"):
                kids.setdefault(it["on"], []).append(it)
        base = [it for it in seq if not it.get("on")]

        def _with_kids(it):
            out = [it]
            for child in kids.get(it["id"], []):
                out.extend(_with_kids(child))
            return out

        seq = []
        for it in base:
            seq.extend(_with_kids(it))
        for it in seq:
            base = self.color[it["id"]][0]
            rim = base_z(self.ctx, it)
            for rect, z0, z1 in sorted(self.boxes[it["id"]], key=lambda bx: bx[1]):   # 아래 부품부터(위에서 내려다본다)
                sunk = it.get("category") == "sink" and z1 <= rim + 2
                for pts, nrm, k in _box_faces(rect, z0, z1):
                    p = pts[0]
                    if (cam.x - p[0]) * nrm[0] + (cam.y - p[1]) * nrm[1] + (cam.z - p[2]) * nrm[2] <= 0:
                        continue
                    shade = 0.55 if sunk else k
                    draw(pts, _shade(base, shade), self.iid[it["id"]])
        return cv


def see_through(sc, cam, cv, depth=0, visited=None, palette_used=None):
    """트인 문간 자리에 그 너머 방을 같은 카메라로 그려 넣는다. 그 방에 또 문간이 보이면 그 너머도 이어서 그린다.
    한 단계만 그리면 그 다음 문간은 빈 회색 판으로 남고, 생성 모델이 도면에 없는 방을 지어 그린다.
    너머 방의 품목은 THROUGH 부터 id 를 받고 cv.through[id] = (그 방 Scene, 품목, 이 방 문간 id).
    이미 그린 방으로 다시 들어가지 않는다."""
    visited = set(visited or ())
    visited.add(sc.room["id"])
    if palette_used is None:
        palette_used = {c[1] for c in sc.color.values()}
    else:
        palette_used = set(palette_used)
        palette_used.update(c[1] for c in sc.color.values())
    cv.through, cv.doorways, cv.through_ops, cv.through_cover = {}, {}, {}, {}
    cv.shell_of, cv.far_shell = {}, {}
    cv.undrawn = []          # (너머 방 Scene, 품목) — 카메라 화면에 한 픽셀도 안 그려진 것
    void, nxt = bytes(VOID), THROUGH
    for oid, m in sc.ops.items():
        o = m["op"]
        other = o.get("to") if o["room"] == sc.room["id"] else o["room"]
        if o["type"] != "opening" or other not in sc.ctx.rooms or other in visited:
            continue
        px = cv.px
        idx = [i for i, v in enumerate(cv.ids) if v == oid and px[i * 3:i * 3 + 3] == void]
        if not idx:
            continue
        nb = Scene(sc.ctx, sc.ctx.rooms[other], sc.ceil)
        side = next(n["side"] for n in nb.ops.values() if n["op"] is o)
        for it in nb.items:
            nb.color[it["id"]] = _next_box_color(palette_used)
        ncv = nb.render(cam, skip=side)
        if depth < 6:
            see_through(nb, cam, ncv, depth + 1, visited, palette_used)
        for it in nb.items:
            if not ncv.drawn.get(nb.iid[it["id"]]):
                cv.undrawn.append((nb, it))
        for pair in getattr(ncv, "undrawn", ()):
            cv.undrawn.append(pair)
        cv.doorways[oid] = nb
        tiled = any(tile_entry(sc.ctx.rooms.get(r)) for r in (o["room"], o.get("to")))
        for pts, col in _reveal(o, min(DOOR_H, sc.ceil - 100), TILE if tiled else FLOOR):    # 벽 두께 — 너머 방의 무엇보다 카메라에 가깝다
            _draw(ncv, cam, pts, col)
        gid = {}
        for it in nb.items:
            gid[nb.iid[it["id"]]] = nxt
            cv.through[nxt] = (nb, it, oid)
            cv.drawn[nxt] = 0
            nxt += 1
        nested = {}          # 한 단계 더 들어간 방의 id → 이 캔버스 id
        shell_ids = {}
        bg = bytes(BG)
        ops = cv.through_ops[oid] = {}      # 바로 너머 방의 창·문 id → [픽셀 수, x 합]
        for i in idx:
            if ncv.px[i * 3:i * 3 + 3] == bg:
                continue
            px[i * 3:i * 3 + 3] = ncv.px[i * 3:i * 3 + 3]
            v = ncv.ids[i]
            if 0 < v < 1000 and v in gid:
                cv.ids[i] = gid[v]
                cv.drawn[gid[v]] += 1
            elif v in getattr(ncv, "through", {}):
                if v not in nested:
                    nb2, it2, _inner = ncv.through[v]
                    nested[v] = nxt
                    cv.through[nxt] = (nb2, it2, oid)
                    cv.drawn[nxt] = 0
                    nxt += 1
                cv.ids[i] = nested[v]
                cv.drawn[nested[v]] += 1
            elif v in getattr(ncv, "shell_of", {}) or (v == 0 and depth > 0):
                # 바로 너머 방의 벽·바닥이 아니라, 그 방의 문간 너머로 또 그린 방이다.
                # 문간 id 로 남겨 두면 프롬프트가 그 자리를 빈 문간이라고 적는다.
                shells = getattr(ncv, "shell_of", {})
                scene = shells[v] if v in shells else nb
                key = scene.room["id"]
                sid = shell_ids.get(key)
                if sid is None:
                    sid = shell_ids[key] = nxt
                    cv.shell_of[sid] = scene
                    cv.drawn[sid] = 0
                    nxt += 1
                cv.ids[i] = sid
                cv.drawn[sid] += 1
                rec = cv.far_shell.setdefault(oid, {}).setdefault(key, [scene, 0])
                rec[1] += 1
            elif v in nb.ops:
                c = ops.setdefault(v, [0, 0])
                c[0] += 1
                c[1] += i % cv.w
        # 개구부가 모서리에 붙고 그 옆 벽이 너머 방 벽과 한 면이면 그 자리에 모서리가 없다. 그런데 이 방 벽의 끝, 문간 테두리,
        # 벽 두께 면, 너머 방 벽의 끝이 저마다 선을 그어 세로줄 둘이 남는다. 모델은 그것을 튀어나온 벽 토막으로 읽고 세웠다
        # (2026-11-13 현관: 신발장 벽과 주방 벽 사이에 옆면·끝면 달린 벽을 세우고 주방 벽을 뒤로 물렸다). 그 면을 벽 색으로
        # 다시 칠한다. 가구(id 가 다른 픽셀)와 창·문(색이 다른 픽셀)은 건드리지 않는다
        top = min(DOOR_H, sc.ceil - 100)
        v0, v1 = sorted((o["line"], o["other_line"]))
        for side, u in _seam_sides(sc, nb, o):
            mask = Canvas(cv.w, cv.h)
            _draw(mask, cam, [_on_wall(o, u, v0 - SEAM_PAD, 0), _on_wall(o, u, v1 + SEAM_PAD, 0),
                              _on_wall(o, u, v1 + SEAM_PAD, top), _on_wall(o, u, v0 - SEAM_PAD, top)], BG, 1)
            wall = bytes(WALLS[side])
            plain = {bytes(EDGE), bytes(WALLS["w"]), wall}     # 선 · 벽 두께 면(늘 w 색) · 그 벽
            for i, v in enumerate(mask.ids):
                if v and cv.ids[i] in (0, oid) and bytes(px[i * 3:i * 3 + 3]) in plain:
                    px[i * 3:i * 3 + 3] = wall
        # 이 방 가구가 가린 너머 가구. 벽(id 0) 뒤에 있는 것은 세지 않는다 — 문간 밖은 당연히 벽이다.
        # 싱크대처럼 문간을 덮은 가구만 「partly behind」 의 근거가 된다
        inv = {sc.iid[it["id"]]: it["id"] for it in sc.items}
        for i, v in enumerate(ncv.ids):
            tid = gid.get(v)
            if not tid:
                continue
            kid = inv.get(cv.ids[i])
            if kid:
                bucket = cv.through_cover.setdefault(tid, {})
                bucket[kid] = bucket.get(kid, 0) + 1
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


def _gap_point(x, y, rect):
    dx = max(rect[0] - x, 0, x - rect[2])
    dy = max(rect[1] - y, 0, y - rect[3])
    return math.hypot(dx, dy)


def _stand_grid(sc, step=280):
    """폰을 들고 설 수 있는 점. 벽에서 WALL_CLEAR, 가구 면에서 BODY_CLEAR 밖."""
    x0, y0, x1, y1 = P.rr(sc.room)
    obs = sc.obstacles()
    pts, x = [], x0 + WALL_CLEAR
    while x <= x1 - WALL_CLEAR + 0.5:
        y = y0 + WALL_CLEAR
        while y <= y1 - WALL_CLEAR + 0.5:
            if all(_gap_point(x, y, r) >= BODY_CLEAR for r in obs):
                pts.append((x, y))
            y += step
        x += step
    return pts


def _through_opening(x, y, tx, ty, o):
    """(x,y)에서 대상 방 중심 (tx,ty)로 가는 선이 트인 개구부를 지나는가."""
    plane = (o["line"] + o["other_line"]) / 2.0
    a, b = sorted((o["a"], o["b"]))
    if o["axis"] == "x":
        if (y - plane) * (ty - plane) >= 0 or abs(ty - y) < 1:
            return False
        t = (plane - y) / (ty - y)
        ix = x + t * (tx - x)
        return a - 80 <= ix <= b + 80 and abs(y - plane) <= 2500
    if (x - plane) * (tx - plane) >= 0 or abs(tx - x) < 1:
        return False
    t = (plane - x) / (tx - x)
    iy = y + t * (ty - y)
    return a - 80 <= iy <= b + 80 and abs(x - plane) <= 2500


def _linear(it, scene):
    sz = it.get("size") or {}
    return max(sz.get("w", 0), sz.get("d", 0), sz.get("h", 0), item_height(it, scene.ctx.geo[it["id"]])) or 1


def wide_faults(sc, cam, cv, st):
    """넓은 컷이 폰 사진으로 성립하지 않으면 이유(한국어) 목록. 비어 있으면 내도 된다.
    서 있는 방의 가구와, 문간 너머로 보이는 가구를 같이 본다."""
    A = float(cam.w * cam.h)
    rows = []

    def add(it, scene, iid):
        s = st.get(iid)
        if not s or s[0] < 20:
            return
        if P.CAT.get(it.get("category"), {}).get("floor"):
            return
        share = s[0] / A
        rect = scene.ctx.geo[it["id"]]["rect"]
        dist = _gap_point(cam.x, cam.y, rect)
        rows.append(dict(it=it, share=share, dist=dist, bw=(s[4] - s[3] + 1) / cam.w,
                         bh=(s[6] - s[5] + 1) / cam.h, px=s[0], lin=_linear(it, scene)))

    for it in sc.items:
        add(it, sc, sc.iid[it["id"]])
    for cid, (nb, it, _oid) in getattr(cv, "through", {}).items():
        add(it, nb, cid)
    faults = []
    for r in rows:
        name = P.label_of(r["it"])
        if r["share"] >= 0.02 and r["dist"] < BODY_CLEAR:
            faults.append("{} — 렌즈에서 {:.0f}cm, 몸에 닿는다({:.0f}cm 이상)".format(name, r["dist"] / 10, BODY_CLEAR / 10))
        elif r["share"] >= PROMINENT and r["dist"] < NEAR_MIN:
            faults.append("{} — {:.0f}cm 앞에 화면의 {:.0%}. 전체 컷은 {:.0f}cm 이상 물러선다".format(
                name, r["dist"] / 10, r["share"], NEAR_MIN / 10))
        if r["share"] >= 0.04 and (r["share"] > SHARE_MAX or r["bw"] > SPAN_MAX or r["bh"] > SPAN_MAX):
            faults.append("{} — 화면의 {:.0%}(가로 {:.0%}·세로 {:.0%}). 전체 컷이 그 물건의 근접 사진이다".format(
                name, r["share"], r["bw"], r["bh"]))
    # 거리가 비슷한 물건끼리만 비교한다. 멀리 있는 침대와 가까운 협탁의 원근은 왜곡이 아니다
    big = [r for r in rows if r["share"] >= 0.02 and r["lin"] >= 200 and r["dist"] > 1]
    if big:
        near_d = min(r["dist"] for r in big)
        cohort = [r for r in big if r["dist"] <= near_d * 1.6]
        if len(cohort) >= 2:
            bulk = [math.sqrt(r["px"]) * r["dist"] / r["lin"] for r in cohort]
            med = sorted(bulk)[len(bulk) // 2] or 1
            worst = max(range(len(cohort)), key=lambda i: bulk[i])
            if bulk[worst] > SCALE_RATIO * med:
                faults.append("{} — 같은 거리의 다른 가구보다 화면에서 {:.1f}배 크다".format(
                    P.label_of(cohort[worst]["it"]), bulk[worst] / med))
    return faults


def _proj_span(cam, boxes):
    """상자의 여덟 모서리를 화면에 비춘 가로·세로(px). 화면 밖으로 나간 모서리도 포함한다.
    모서리가 카메라 뒤나 아주 가까이 있으면 None. 그때는 잘린 다각형이 모서리 상자보다 커져 비교가 거짓이다."""
    xs, ys = [], []
    for rect, z0, z1 in boxes:
        x0, y0, x1, y1 = rect
        cams = [cam.to_cam(p) for p in (
            (x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0),
            (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1))]
        if any(q[2] <= NEAR for q in cams):
            return None
        for q in cams:
            u, v = cam.proj(q)
            xs.append(u)
            ys.append(v)
    if len(xs) < 2:
        return None
    return max(xs) - min(xs), max(ys) - min(ys)


def scale_faults(sc, cam, cv, st):
    """그린 상자가 치수와 안 맞으면 이유. 비어 있으면 이 검사는 통과다.
    올려 둔 물건은 받침 윗면에서 자기 높이만 차지해야 한다. 바닥에서 쌓거나 면을 부풀리면 걸린다.
    가려져 작아진 것은 넘어간다. 비슷한 거리에서 이웃보다 화면 배율이 크면 그것도 건다."""
    faults = []
    rows = []
    pairs = [(sc, it, sc.iid[it["id"]]) for it in sc.items]
    for cid, (nb, it, _oid) in getattr(cv, "through", {}).items():
        pairs.append((nb, it, cid))
    for scene, it, iid in pairs:
        boxes = scene.boxes.get(it["id"]) if getattr(scene, "boxes", None) else None
        if not boxes:
            continue
        name = P.label_of(it)
        if it.get("on"):
            parent = next((x for x in scene.ctx.items if x["id"] == it["on"]), None)
            if parent is None or it["on"] not in scene.ctx.geo:
                faults.append("{} — 받침의 위치를 집 데이터에서 못 찾았다".format(name))
            else:
                top = base_z(scene.ctx, parent) + item_height(parent, scene.ctx.geo[parent["id"]])
                z0 = min(z for _r, z, _z1 in boxes)
                z1 = max(z for _r, _z0, z in boxes)
                ih = item_height(it, scene.ctx.geo[it["id"]])
                # 싱크 볼은 상판 아래로 파고든다. 테두리가 상판 윗면에 닿는지만 본다
                if it.get("category") == "sink":
                    if z1 < top - 30 or z0 > top + 30:
                        faults.append("{} — 개수대 테두리가 받침 윗면({:.0f}cm)에 닿지 않는다".format(name, top / 10.0))
                else:
                    if abs(z0 - top) > 30:
                        faults.append("{} — 받침 윗면({:.0f}cm)이 아니라 {:.0f}cm 높이에서 그린다".format(
                            name, top / 10.0, z0 / 10.0))
                    if z1 - z0 > ih + 30:
                        faults.append("{} — 높이 {:.0f}cm 인데 상자는 {:.0f}cm 다".format(name, ih / 10.0, (z1 - z0) / 10.0))
                gx0, gy0, gx1, gy1 = scene.ctx.geo[it["id"]]["rect"]
                for rect, _za, _zb in boxes:
                    if rect[0] < gx0 - 15 or rect[1] < gy0 - 15 or rect[2] > gx1 + 15 or rect[3] > gy1 + 15:
                        faults.append("{} — 바닥 면이 치수보다 크다".format(name))
                        break
        s = st.get(iid)
        if not s or s[0] < 30:
            continue
        span = _proj_span(cam, boxes)
        if not span:
            continue
        pw, ph = s[4] - s[3] + 1, s[6] - s[5] + 1
        ew, eh = span
        if ph > eh * 1.35 + 6 or pw > ew * 1.35 + 6:
            faults.append("{} — 그린 크기 {:.0f}×{:.0f}px 가 치수 투영 {:.0f}×{:.0f}px 보다 크다".format(
                name, pw, ph, ew, eh))
        ih = item_height(it, scene.ctx.geo[it["id"]])
        # 인덕션처럼 납작한 상판 위 물건은 화면 높이가 키보다 윗면의 원근이다. 키로 나누면 같은 거리의
        # 키 큰 가구보다 배율이 큰 것처럼 나온다. 가장 긴 변으로 재고, 키 12cm 미만은 이 비교에서 뺀다.
        lin = _linear(it, scene)
        if not (it.get("on") and ih < 120) and lin >= 50 and eh > 1 and max(pw, ph) > 0.7 * max(ew, eh):
            dist = _gap_point(cam.x, cam.y, scene.ctx.geo[it["id"]]["rect"])
            rows.append((it, max(pw, ph) / float(lin), dist, name))
    if len(rows) >= 2:
        near = min(r[2] for r in rows)
        cohort = [r for r in rows if r[2] <= near * 1.6 and r[2] > 1]
        if len(cohort) >= 2:
            med = sorted(r[1] for r in cohort)[len(cohort) // 2] or 1
            worst = max(cohort, key=lambda r: r[1])
            if worst[1] > 1.75 * med:
                faults.append("{} — 같은 거리의 다른 가구보다 가장 긴 변 대비 화면이 {:.1f}배 크다".format(
                    worst[3], worst[1] / med))
    return faults


def void_faults(cv):
    """화면에 남은 빈 문간(VOID). 너머 방을 못 그렸으면 컷으로 내지 않는다."""
    void = bytes(VOID)
    n = sum(1 for i in range(cv.w * cv.h) if cv.px[i * 3:i * 3 + 3] == void)
    share = n / float(cv.w * cv.h or 1)
    if share >= 0.003:
        return ["화면에 안 그린 트인 문간이 {:.1%} 남았다. 너머 방을 집 데이터로 채우지 못했다".format(share)]
    return []


def _subject_share(cv, st, cam, subject_id):
    """카메라가 옆 방에 있을 때, 대상 방이 화면에서 차지하는 비율(벽·바닥·가구)."""
    A = float(cam.w * cam.h)
    total = 0
    seen = set()
    for oid, nb in getattr(cv, "doorways", {}).items():
        if nb.room["id"] != subject_id or oid not in st:
            continue
        total += st[oid][0]
        seen.add(oid)
    for cid, (nb, _it, oid) in getattr(cv, "through", {}).items():
        if oid in seen and cid in st:
            total += st[cid][0]
    return total / A


def _wide_score(sc, cam, st, review_ids):
    A = float(cam.w * cam.h)
    score, win = 0.0, False
    for it in sc.items:
        s = _share(st, sc.iid[it["id"]], A)
        if not s:
            continue
        wgt = 2.0 if it["id"] in review_ids else (0.3 if P.CAT.get(it.get("category"), {}).get("floor") else 1.0)
        score += wgt * min(1.0, s / 0.03)
    for k, s in st.items():
        if 1000 <= k < THROUGH and k in sc.ops and sc.ops[k]["op"]["type"] == "window":
            if s[0] / A > 0.01:
                win = True
    if win:
        score += 1.5
    return score, win


def plan_wide(sc, ratio, cam_h, review_ids):
    """전체 컷. 폰 기본 렌즈(26mm)로, 가구에서 NEAR_MIN 이상 물러선 자리만 고른다.
    방 안에 그런 자리가 없으면 트인 문간 너머(옆 방)에서 이 방을 본다. 그래도 안 되면 초광각(16mm)을
    같은 거리 조건으로 한 번 더 본다. 왜곡된 자리는 후보에서 빼므로, 빈 목록이면 그 방의 전체 컷을 내지 않는다."""
    ctx, subject = sc.ctx, sc.room
    W, H, _, sw, _ = RATIOS[ratio]
    w, h = max(8, W // SCORE_DIV), max(8, H // SCORE_DIV)
    sx0, sy0, sx1, sy1 = P.rr(subject)
    cx, cy = (sx0 + sx1) / 2.0, (sy0 + sy1) / 2.0
    aims = [(cx, cy)]
    mass = [it for it in sc.items if not it.get("on") and not P.CAT.get(it.get("category"), {}).get("floor")]
    if mass:
        acc = [0.0, 0.0, 0.0]
        for it in mass:
            x0, y0, x1, y1 = ctx.geo[it["id"]]["rect"]
            area = max(1.0, (x1 - x0) * (y1 - y0))
            acc[0] += area * (x0 + x1) / 2.0
            acc[1] += area * (y0 + y1) / 2.0
            acc[2] += area
        aims.insert(0, (acc[0] / acc[2], acc[1] / acc[2]))
    scenes = {subject["id"]: sc}
    # (x, y, stand_room_id, where)
    spots = [(x, y, subject["id"], "inside") for x, y in _stand_grid(sc)]
    for m in sc.ops.values():
        o = m["op"]
        if o["type"] != "opening":
            continue
        other = o["to"] if o["room"] == subject["id"] else o["room"]
        if other not in ctx.rooms:
            continue
        if other not in scenes:
            scenes[other] = Scene(ctx, ctx.rooms[other], sc.ceil)
        for x, y in _stand_grid(scenes[other]):
            if _through_opening(x, y, cx, cy, o):
                spots.append((x, y, other, "adjacent"))
    offs = (0.0, -0.22, 0.22, -0.45, 0.45)

    def _furn_share(cv, st, cam, subject_id, stand):
        """대상 방 가구가 화면에서 차지하는 비율. 빈 벽만 보이면 전체 컷이 아니다."""
        A = float(cam.w * cam.h)
        if stand == subject_id:
            scene = scenes[stand]
            return sum(_share(st, scene.iid[it["id"]], A) for it in scene.items
                       if not P.CAT.get(it.get("category"), {}).get("floor"))
        total, seen = 0, set()
        for oid, nb in getattr(cv, "doorways", {}).items():
            if nb.room["id"] == subject_id:
                seen.add(oid)
        for cid, (nb, it, oid) in getattr(cv, "through", {}).items():
            if oid in seen and cid in st and not P.CAT.get(it.get("category"), {}).get("floor"):
                total += st[cid][0]
        return total / A

    def search(lens):
        hfov = 2 * math.atan((sw / 2.0) / lens)
        found = []
        for x, y, stand, where in spots:
            scene = scenes[stand]
            for aim in aims:
                base = math.atan2(aim[1] - y, aim[0] - x)
                for off in offs:
                    yaw = base + off
                    cam = Cam(x, y, cam_h, yaw, 0.0, hfov, w, h, lens, cyf=HORIZON[ratio])
                    raw = scene.render(cam)
                    cv = see_through(scene, cam, raw) if stand != subject["id"] else raw
                    st = cv.stats()
                    if wide_faults(scene, cam, cv, st):
                        continue
                    if stand != subject["id"] and void_faults(cv):
                        continue
                    furn = _furn_share(cv, st, cam, subject["id"], stand)
                    if furn < 0.08:
                        continue
                    if stand != subject["id"] and _subject_share(cv, st, cam, subject["id"]) < 0.18:
                        continue
                    score, win = _wide_score(scene, cam, st, review_ids)
                    score += furn * 6.0
                    if stand == subject["id"] and furn >= 0.15:
                        score += 0.4          # 방 안에서도 가구가 보이면 문간 밖보다 조금 낫다
                    cuts = len(near_cuts(scene, cam, st))
                    if cuts:
                        score -= 1.5
                    found.append(dict(score=score, x=x, y=y, yaw=yaw, stand=stand, where=where,
                                      window=win, cuts=cuts, lens=lens))
        return found

    found = search(MAIN_LENS) or search(ULTRA_LENS)
    found.sort(key=lambda s: (s["cuts"] > 0, -s["score"]))
    # 고른 자리는 원 해상도로 다시 재서, 축소 화면에서 놓친 왜곡이 있으면 버린다
    picked = []
    shows = any(s["score"] > 0 for s in found)
    for s in found:
        if s["score"] <= 0 and (picked or shows):
            continue
        if picked and s["cuts"] > 0:
            continue
        if not all(abs(math.atan2(math.sin(s["yaw"] - q["yaw"]), math.cos(s["yaw"] - q["yaw"]))) > math.radians(60)
                   or math.hypot(s["x"] - q["x"], s["y"] - q["y"]) > 1500 for q in picked):
            continue
        hfov = 2 * math.atan((sw / 2.0) / s["lens"])
        cam = Cam(s["x"], s["y"], cam_h, s["yaw"], 0.0, hfov, W, H, s["lens"], cyf=HORIZON[ratio])
        scene = scenes[s["stand"]]
        cv = see_through(scene, cam, scene.render(cam))
        if wide_faults(scene, cam, cv, cv.stats()) or void_faults(cv) or scale_faults(scene, cam, cv, cv.stats()):
            continue
        if s["stand"] != subject["id"] and _subject_share(cv, cv.stats(), cam, subject["id"]) < 0.18:
            continue
        picked.append(s)
        if len(picked) == 2:
            break
    return [dict(x=p["x"], y=p["y"], z=cam_h, yaw=p["yaw"], pitch=0.0, lens=p["lens"], kind="wide",
                 where=p["where"], stand=p["stand"], room=p["stand"], for_room=subject["id"],
                 cyf=HORIZON[ratio], window=p["window"])
            for p in picked]


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
    # 제품 컷도 폰 기본 렌즈. 앞이 막히면 같은 렌즈로 옆·뒤를 본다. 18mm 로 바짝 붙지 않는다
    for angles in ((0, 20, -20, 40, -40, 60, -60), (90, -90, 120, -120, 150, -150, 180)):
        if best is not None:
            break
        lens = HERO_LENS
        hfov = 2 * math.atan((sw / 2.0) / lens)
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
                score = -abs(share - 0.3) * 3 - (1 - frac) * 1.5 - (0.6 if cut else 0) - 0.2 * abs(ang) / 60.0
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
_FRAME_KO = {"left": "왼쪽", "right": "오른쪽"}


def _towel_frame_side(cam, x, y, z):
    """이 카메라로 본 수건걸이의 화면 쪽. 왼쪽 아니면 오른쪽."""
    q = cam.to_cam((x, y, z))
    if q[2] > NEAR:
        u, _v = cam.proj(q)
        return "left" if u < cam.w / 2.0 else "right"
    rx, ry = cam.right2()
    return "left" if (x - cam.x) * rx + (y - cam.y) * ry < 0 else "right"


def _one_towel_line(ctx, cam, it):
    """수건걸이 한 개의 영어 자리 문장과 확인 목록. 빛(낮·저녁)은 넣지 않는다."""
    g = ctx.geo.get(it["id"])
    if not g:
        return None, None
    wall = (it.get("place") or {}).get("wall")
    rel = _wall_rel(wall, cam) if wall in NORMAL else None
    wall_en = REL_EN[rel] if rel else "the wall"
    cx = (g["rect"][0] + g["rect"][2]) / 2.0
    cy = (g["rect"][1] + g["rect"][3]) / 2.0
    z = it["z"] if isinstance(it.get("z"), (int, float)) and not isinstance(it.get("z"), bool) else (g.get("z") or 0)
    side = _towel_frame_side(cam, cx, cy, z + (g.get("h") or 0) / 2.0)
    where = "on the {} side of the frame".format(side)
    line = ("Towel bar: on {}, {}, mounted {} cm above the floor. "
            "One white towel hangs on this bar.".format(wall_en, where, _cm(z)))
    check = ("수건걸이 — 화장실에 있고, 모든 컷(낮·저녁)에서 house.json 과 같은 자리다 "
             "({}, 화면 {}, 설치 높이 {}cm)".format(WALL_KO.get(rel, "벽"), _FRAME_KO[side], _cm(z)))
    return line, check


def towel_view(ctx, cam, rooms):
    """욕실이 화면에 있을 때 프롬프트에 붙일 수건걸이 문장. → (글, 확인 목록, Avoid)."""
    lines, checks = [], []
    seen = set()
    for room in rooms or []:
        if not room or room.get("kind") != "bathroom" or room.get("id") in seen:
            continue
        seen.add(room["id"])
        for it in ctx.items:
            if it.get("room") != room["id"] or not P.is_towel(it):
                continue
            line, check = _one_towel_line(ctx, cam, it)
            if line:
                lines.append(line)
                checks.append(check)
    return "\n".join(lines), checks, ([AVOID_TOWEL] if lines else [])


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
                    a=(rel + " is fully open{to}, with no door frame; both side walls continue as one flat wall, "
                       "same width; do not add a door frame, jambs, or a narrower doorway"),
                    ko="벽 전체가 트였다(폭 {}cm, 양쪽 벽이 한 면, 문틀 없음)".format(_cm(W)),
                    wide=True, avoid=AVOID_JAMB)
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
    where = "{}{}".format(REL_EN[rel], "" if seen else ", out of frame")
    where_ko = "{}{}".format(WALL_KO[rel], "" if seen else ", 화면 밖")
    shadow = "·".join(ko)
    # 간유리여도 낮·저녁 빛은 퍼져 들어온다. 직사와 선명한 밖은 아니다.
    if _glass_phrase(m["op"]):
        return (("Diffuse daylight comes only through the frosted glass of the window on {}, traveling {}: "
                 "sides facing the window are brighter, soft shadows fall {}. Ceiling light off.").format(where, way, way),
                "창({})의 간유리로 퍼진 빛이 들어와 그림자가 {}으로 진다".format(where_ko, shadow))
    return (("Daylight comes only from the window on {}, traveling {}: sides facing the window are brighter, "
             "soft shadows fall {}. Ceiling light off.").format(where, way, way),
            "창({})에서 빛이 들어와 그림자가 {}으로 진다".format(where_ko, shadow))


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


# 개수·좌우는 빈 방 프롬프트에 적고, 그 사진을 사람이 앉는 컷의 레퍼런스로 쓸 때도 그대로 옮긴다.
_COUNT_SKIP = {"plant", "lamp", "mirror", "tv"}
_COUNT_CHECK = "가구 개수 — 도면과 같다(빈 의자·침대가 더 없다)"
_LAYOUT_CHECK = "좌우 — 화면의 왼쪽·오른쪽이 도면과 같다"
_NUM_WORD = {1: "one", 2: "two", 3: "three", 4: "four", 5: "five",
             6: "six", 7: "seven", 8: "eight", 9: "nine", 10: "ten"}


def _plural(name, n):
    if n == 1 or name.endswith("s"):
        return name
    return name + "s"


def _count_sentence(name, n):
    if n == 1:
        return "Exactly one {} in the whole room. No second {}, no extra empty {}.".format(name, name, name)
    word = _NUM_WORD.get(n, str(n))
    return "Exactly {} {} in the whole room. No extra {}, no extra empty {}.".format(
        word, _plural(name, n), name, name)


def room_count_lines(items):
    """이 방 가구의 개수 문장. 항목 하나당 하나다. qty 는 가격용이라 세지 않는다.
    러그·화분·받침 위 소품은 빼 글자를 아낀다. 화면 밖 가구도 방 안에 있으면 센다."""
    groups = {}
    order = []
    for it in items:
        if it.get("on") or P.CAT.get(it.get("category"), {}).get("floor"):
            continue
        if it.get("category") in _COUNT_SKIP:
            continue
        name = _label_en(it)
        if name not in groups:
            order.append(name)
        groups[name] = groups.get(name, 0) + 1
    return [_count_sentence(name, groups[name]) for name in order]


def _join_names(names):
    seen, count = [], {}
    for n in names:
        if n not in count:
            seen.append(n)
        count[n] = count.get(n, 0) + 1
    return _and(_plural(n, count[n]) if count[n] > 1 else n for n in seen)


def frame_layout(vis):
    """화면에서 본 좌우. house.json 자리를 이 카메라로 비춘 것이다."""
    sides = {"left": [], "center": [], "right": []}
    for v in vis:
        it = v["it"]
        if it.get("on") or P.CAT.get(it.get("category"), {}).get("floor"):
            continue
        if it.get("category") in _COUNT_SKIP:
            continue
        hx = v["hx"]
        side = "left" if hx < 0.45 else "right" if hx > 0.55 else "center"
        sides[side].append(_label_en(it))
    bits = []
    if sides["left"]:
        bits.append("{} on the left side of the frame".format(_join_names(sides["left"])))
    if sides["center"]:
        bits.append("{} in the center of the frame".format(_join_names(sides["center"])))
    if sides["right"]:
        bits.append("{} on the right side of the frame".format(_join_names(sides["right"])))
    return ", ".join(bits)


def person_same_furniture(name, person="<person name>"):
    """레퍼런스에 이미 있는, 사람이 앉거나 쓰는 가구. 소품으로 따로 적지 않고 같은 물건이라고 적는다.
    person 은 앉는 사람의 이름이다. 비어 있으면 `<person name>` 을 넣는다. 성별 대명사는 쓰지 않는다."""
    who = (person or "").strip() or "<person name>"
    return "the single {} from the reference, and {} is sitting in that same {}".format(name, who, name)


def _legend_label(it, ctx=None, cam=None):
    """범례는 사람용이라 영문 이름이 있으면 그것을, 없으면 분류를 적는다.
    수건걸이는 카메라로 본 자리 문장을 적는다(프롬프트와 같은 문장)."""
    if ctx is not None and cam is not None and P.is_towel(it):
        line, _check = _one_towel_line(ctx, cam, it)
        if line:
            return line
    for key in ("label_en", "label"):
        lab = it.get(key) or ""
        if lab and all(32 <= ord(c) < 127 for c in lab):
            return lab
    return _label_en(it)


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
        fw = _frac(rw)   # 「about nearly all」 은 말이 겹친다. nearly all 일 때는 about 을 빼다
        v.update(on_scale="{}{} that top's width{}".format(   # 납작한 것(바 조명)은 높이 비율이 뜻이 없다
                     "" if fw == "nearly all" else "about ", fw,
                     " and {} the {}'s height".format(_frac(rh), _label_en(sup)) if rh >= 0.1 else ""),
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

        def hbit(o):
            """곁 가구와의 높이. cm 만 적으면 모델은 흔한 크기로 줄인다(2026-11-16 싱크대와 같은 85cm 냉장고가 더 낮게 나왔다)."""
            ha = (it.get("size") or {}).get("h") or 0
            hb = (o.get("size") or {}).get("h") or 0
            if ha <= 0 or hb <= 0:
                return "", ""
            d = ha - hb
            if abs(d) <= 20:
                return "same height", "높이 같다"
            n = _cm(abs(d))
            return ("{} cm taller".format(n), "{}cm 높다".format(n)) if d > 0 else (
                "{} cm shorter".format(n), "{}cm 낮다".format(n))

        if apart:
            en.append("Bare floor shows between it and " + " and ".join(
                "the {} ({} cm gap{})".format(_label_en(o), _cm(g), ", " + hbit(o)[0] if hbit(o)[0] else "")
                for o, g in apart))
            ko.append(", ".join("{}까지 {}cm{}".format(
                P.label_of(o), _cm(g), "({})".format(hbit(o)[1]) if hbit(o)[1] else "") for o, g in apart)
                + " 떨어져 사이로 바닥이 보인다")
        if touch:
            te, tk = [], []
            for o in touch:
                he, hk = hbit(o)
                te.append(_label_en(o) + (" ({})".format(he) if he else ""))
                tk.append(P.label_of(o) + ("({})".format(hk) if hk else ""))
            en.append("It touches the {} without overlapping".format(" and the ".join(te)))
            ko.append("{}에 바로 붙어 있다".format("·".join(tk)))
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


def _beyond_geom(o, room):
    """개구부 너머 방의 크기. depth 는 너머 쪽 면에서 맞은편 벽까지(mm), width 는 그 벽을 따른 방의 길이.
    before/after 는 개구부 구간 밖으로 방이 더 나간 길이(a 쪽, b 쪽)."""
    plane = o["line"] if o["room"] == room["id"] else o["other_line"]
    x0, y0, x1, y1 = P.rr(room)
    if o["axis"] == "x":
        sign = 1.0 if (y0 + y1) / 2.0 > plane else -1.0
        depth = max((y0 - plane) * sign, (y1 - plane) * sign)
        along0, along1 = x0, x1
    else:
        sign = 1.0 if (x0 + x1) / 2.0 > plane else -1.0
        depth = max((x0 - plane) * sign, (x1 - plane) * sign)
        along0, along1 = y0, y1
    a, b = (o["a"], o["b"]) if o["b"] >= o["a"] else (o["b"], o["a"])
    return dict(plane=plane, sign=sign, axis=o["axis"], depth=max(0.0, depth), width=along1 - along0,
                before=max(0.0, a - along0), after=max(0.0, along1 - b))


def _end_right(cam, o, toward_b):
    """개구부 좌표가 커지는 쪽(toward_b)이 화면 오른쪽인가."""
    d = 1.0 if toward_b == (o["b"] >= o["a"]) else -1.0
    vx, vy = (d, 0.0) if o["axis"] == "x" else (0.0, d)
    rx, ry = cam.right2()
    return vx * rx + vy * ry > 0


def _past_mm(geom, rect):
    """가구의 가장 가까운 면이 개구부 면에서 너머 방 안쪽으로 떨어진 거리(mm). 면에 걸치면 0."""
    c0, c1 = (rect[1], rect[3]) if geom["axis"] == "x" else (rect[0], rect[2])
    near = min((c0 - geom["plane"]) * geom["sign"], (c1 - geom["plane"]) * geom["sign"])
    return 0.0 if near < 0 else near


def _past_phrase(near):
    """카메라에서의 foreground/middle ground 는 문간에서의 위치를 말하지 못한다. 모델은 middle ground 를
    너머 방 한가운데로 읽고 문간에 붙은 가구를 멀리 물렸다(2026-11-16)."""
    if near <= 30:
        return "flush with the opening"
    return "{} cm past the opening".format(_cm(near))


def _span_sentence(cam, o, room, narrow):
    """너머 방의 깊이·폭. narrow 면 이 화면에는 그 방의 가는 띠만 들어온다."""
    g = _beyond_geom(o, room)
    left = g["before"] if not _end_right(cam, o, False) else 0.0
    right = g["before"] if _end_right(cam, o, False) else 0.0
    if _end_right(cam, o, True):
        right += g["after"]
    else:
        left += g["after"]
    extra = []
    if left > 50:
        extra.append("{} cm {}".format(_cm(left), "left"))
    if right > 50:
        extra.append("{} cm {}".format(_cm(right), "right"))
    d, w = _cm(g["depth"]), _cm(g["width"])
    ow = abs(o["b"] - o["a"])
    # 주방 컷은 4,000자에 붙어 있어 문장을 짧게 둔다. 뜻은 같다: 문간에서 잰 깊이·폭, 개구부 밖으로 더 나간 쪽.
    if not extra and abs(g["width"] - ow) <= 50:
        s = "It is {} cm deep past this opening, no wider".format(d)
    elif not extra:
        s = "It is {} cm deep, {} cm wide past this opening".format(d, w)
    else:
        s = "It is {} cm deep, {} cm wide, {}".format(d, w, " and ".join(extra))
    if narrow:
        s += ", narrow in frame"
    s += "."
    # 「no wider」 만으로는 깊이가 늘지 않는다. 1m 이하는 얕은 공간이라고 적고, 복도 종류가 아니면 hallway 로 부르지 않는다.
    if g["depth"] <= SHALLOW_MM:
        if room.get("kind") == "hall":
            s += " The far wall is only {} cm past the opening and fills the frame as in the sketch.".format(d)
        else:
            s += (" It is a shallow {} cm-deep space, not a hallway or corridor; the far wall is only {} cm "
                  "past the opening and fills the frame as in the sketch.").format(d, d)
    return s


def _span_ko(cam, o, room, narrow):
    g = _beyond_geom(o, room)
    left = g["before"] if not _end_right(cam, o, False) else 0.0
    right = g["before"] if _end_right(cam, o, False) else 0.0
    if _end_right(cam, o, True):
        right += g["after"]
    else:
        left += g["after"]
    bits = ["문간에서 {}cm 깊이".format(_cm(g["depth"])), "폭 {}cm".format(_cm(g["width"]))]
    side = []
    if left > 50:
        side.append("왼쪽 {}cm".format(_cm(left)))
    if right > 50:
        side.append("오른쪽 {}cm".format(_cm(right)))
    if side:
        bits.append("개구부 밖으로 " + "·".join(side))
    elif abs(g["width"] - abs(o["b"] - o["a"])) <= 50:
        bits.append("개구부보다 넓지 않다")
    if narrow:
        bits.append("화면에는 가는 띠만")
    if g["depth"] <= SHALLOW_MM and room.get("kind") != "hall":
        bits.append("얕은 {}cm, 복도 아님. 맞은편 벽은 문간에서 {}cm이고 스케치처럼 화면을 채운다".format(
            _cm(g["depth"]), _cm(g["depth"])))
    elif g["depth"] <= SHALLOW_MM:
        bits.append("맞은편 벽은 문간에서 {}cm이고 스케치처럼 화면을 채운다".format(_cm(g["depth"])))
    return " · ".join(bits)


def _stack_clause(child, support):
    """구조 문장. 받침 윗면이 보이면 그 위 품목이 서 있다고 적는다. 한도로 줄여도 빼지 않는다."""
    return "if the {} top shows, the {} stands on it".format(_label_en(support), _label_en(child))


def _on_out_of_frame(child, support, edge="", brief=False):
    """받침은 보이는데 그 위 품목은 화면에 한 픽셀도 없을 때. 같은 방·문간 너머가 같은 말을 쓴다.
    brief 는 프롬프트 한도로 문간 너머 생김새를 줄일 때다. 「just out of frame」만 남기면 모델이 윗면을 비운다.
    조건(if the … top shows)은 구조라 brief 에도 그대로 둔다."""
    clause = _stack_clause(child, support)
    name = _label_en(child)
    if brief:
        return " Its {0} stands on its top just out of frame{1}. {2}.".format(name, edge, clause[0].upper() + clause[1:])
    return (" Its {0} stands on its top just out of frame{1}: show no more of the {2} than the sketch does; "
            "{3}.").format(name, edge, _label_en(support), clause)


def _mentioned(prompt, name):
    """프롬프트에 그 이름이 단어로 몇 번 있나. 손으로 고친 글에도 같은 기준으로 센다."""
    return len(re.findall(r"(?<!\w)" + re.escape(name) + r"(?!\w)", prompt or "", re.I))


def missing_stacked(prompt, items, visible_ids):
    """화면에 있는 받침(`visible_ids`)의 `on` 품목이 prompt 에 없으면 그 영어 이름.
    생성한 프롬프트와, 손으로 고치거나 합친 최종 프롬프트에 같이 쓴다. 같은 이름이 여러 개면 그 횟수만큼 있어야 한다.
    빈 목록이면 통과다."""
    need = {}
    for it in items:
        base = it.get("on")
        if not base or base not in visible_ids:
            continue
        name = _label_en(it)
        need[name] = need.get(name, 0) + 1
    missing = []
    for name, n in need.items():
        got = _mentioned(prompt, name)
        if got < n:
            missing.extend([name] * (n - got))
    return missing


def _undrawn_on(cv, scene, seen):
    """scene 에서 보이는 받침 위에 있으나 카메라 화면에 안 그려진 품목. 받침 id → [품목]."""
    out = {}
    for room_sc, it in getattr(cv, "undrawn", ()):
        if room_sc.room["id"] != scene.room["id"]:
            continue
        if it.get("on") in seen and it["id"] not in seen:
            out.setdefault(it["on"], []).append(it)
    return out


def _far_room_lines(cam, st, house, con, here_scene, parent, far_scene, members, n, W, H, A, cv=None):
    """parent 방의 문간 너머로 far_scene 이 더 보일 때, 스케치에 그려진 그 가구만 적는다."""
    link = None
    for m in parent.ops.values():
        o = m["op"]
        other = o.get("to") if o["room"] == parent.room["id"] else o["room"]
        if o["type"] == "opening" and other == far_scene.room["id"]:
            link = m
            break
    if link is None:
        return n, [], [], [], "", [], []
    geom = _beyond_geom(link["op"], far_scene.room)
    vis = []
    for cid, it in members:
        s = st.get(cid)
        if not s or s[0] < 30 or s[0] / A < 0.004:
            continue
        vis.append((s[1] / s[0] / W, cid, it, s))
    vis.sort(key=lambda t: t[0])
    lines, briefs, labels, ids, bare = [], [], [], [], []
    for hx, cid, it, s in vis:
        n += 1
        g = far_scene.ctx.geo[it["id"]]
        sz = it.get("size") or {}
        near = _past_mm(geom, g["rect"])
        hpos, vp = _hpos(hx), _vpos(s[2] / s[0] / H)
        parts = ["{}, {}".format(hpos if vp == "middle" else "{} {}".format(vp, hpos), _past_phrase(near)),
                 _orient(cam, it, g)]
        pw = _place_wall(it)
        if pw and not it.get("on") and not P.CAT.get(it.get("category"), {}).get("floor"):
            parts.insert(1, "{} to {}".format("head end" if it.get("category") == "bed" else "back",
                                              REL_EN[_wall_rel(pw, cam)]))
        if s[3] <= 0 or s[4] >= W - 1:
            parts.append("cut off at the {} edge".format("left" if s[3] <= 0 else "right"))
        dims = "{}x{}x{} cm. {}.".format(_cm(sz.get("w", 0)), _cm(sz.get("d", 0)),
                                         _cm(sz.get("h", 0) or item_height(it, g)), "; ".join(parts).capitalize())
        name = _label_en(it).capitalize()
        col = far_scene.color[it["id"]][1]
        line = "{}. {} ({} box): {}. {}".format(n, name, col, _look(it), dims)
        brief = "{}. {} ({} box): {}".format(n, name, col, dims)
        ids.append(it["id"])
        for a in _undrawn_on(cv, far_scene, {t[2]["id"] for t in vis}).get(it["id"], []):
            note = _on_out_of_frame(a, it)
            line += note
            brief += _on_out_of_frame(a, it, brief=True)
            top = AVOID_BARE_TOP.format(_label_en(it))
            if top not in bare:
                bare.append(top)
        lines.append(line)
        briefs.append(brief)
        labels.append(P.label_of(it))
    kind = far_scene.room.get("kind")
    fin, here = room_finish(house, con, far_scene.room), room_finish(house, con, here_scene.room)
    label, label_ko = KIND_EN.get(kind, "next room"), P.KIND_KO.get(kind or "", "옆 방")
    head = "Through {} is the {} (walls: {}; floor: {}). {}".format(
        _opening(parent, link, cam)["the"], label,
        "same as here" if fin["walls"] == here["walls"] else fin["walls"],
        "same as here" if fin["floor"] == here["floor"] else fin["floor"],
        _span_sentence(cam, link["op"], far_scene.room, False))
    tail = " Draw only these there:" if lines else " No furniture shows there."
    check = "그 너머 {} — {}".format(label_ko, "·".join(labels) + " 만 보인다" if labels else "벽·바닥만 보인다")
    return n, [head + tail] + lines, [head + tail] + briefs, labels, check, ids, bare


def describe_through(sc, cam, cv, st, house, n0, seen_here=()):
    """문간 너머로 보이는 옆 방(see_through 가 그려 넣은 것)을 문간마다 정리한다. 품목 번호는 n0+1 부터 잇는다.
    seen_here: 이 컷에 보이는 이 방 품목(한 면으로 이어진 벽에 나란히 붙은 이 방 가구·너머 가구를 짝지어 적는다).
    너머 방의 벽·바닥은 그 방 종류의 마감(room_finish)이다 — 그 방 컷과 같은 말로 적어야 같은 방으로 나온다.
    소품은 적지 않는다. 그 방 전체의 소품이라 문간에 안 보이는 가구(책상 위 노트북)까지 불러온다."""
    W, H = cam.w, cam.h
    A = float(W * H)
    con = concept_of(house)
    groups = {oid: (nb, []) for oid, nb in getattr(cv, "doorways", {}).items()}
    far_of = {}
    for cid, (room_sc, it, oid) in sorted(getattr(cv, "through", {}).items()):
        if oid not in groups:
            continue
        if room_sc.room["id"] == groups[oid][0].room["id"]:
            groups[oid][1].append((cid, it))
        else:
            far_of.setdefault(oid, {}).setdefault(room_sc.room["id"], (room_sc, []))[1].append((cid, it))
    out, n = [], n0
    for oid, (nb, members) in groups.items():
        ms = _merge([st.get(oid)] + [st[c] for c, _ in members if c in st])     # 문간 + 너머 방 품목
        if not ms or ms[0] / A < THROUGH_MIN:
            continue
        area, xs = ms[0], (ms[3], ms[4])
        m = sc.ops[oid]
        geom = _beyond_geom(m["op"], nb.room)
        narrow = (ms[4] - ms[3] + 1) / float(W) < 0.18
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
        lines, short, facts, labels, places = [], [], [], [], []
        stacked_avoid, far_ids = [], []
        for hx, cid, it, s in vis:
            n += 1
            g = nb.ctx.geo[it["id"]]
            sz = it.get("size") or {}
            near = _past_mm(geom, g["rect"])
            hpos, vp = _hpos(hx), _vpos(s[2] / s[0] / H)
            parts = ["{}, {}".format(hpos if vp == "middle" else "{} {}".format(vp, hpos), _past_phrase(near)),
                     _orient(cam, it, g)]
            # 붙은 벽. 안 적으면 모델은 너머 가구를 벽에서 떼어 문간 앞으로 내놓고, 그 뒤 먼 벽에 그 방 사진의 다른 가구를
            # 그린다(2026-11-13 현관: 서쪽 벽에 붙은 냉장고를 앞으로 내고 뒤에 싱크대를 그렸다)
            pw = _place_wall(it)
            if pw and not it.get("on") and not P.CAT.get(it.get("category"), {}).get("floor"):
                parts.insert(1, "{} to {}".format("head end" if it.get("category") == "bed" else "back",
                                                  REL_EN[_wall_rel(pw, cam)]))
            if s[3] <= 0 or s[4] >= W - 1:
                parts.append("cut off at the {} edge".format("left" if s[3] <= 0 else "right"))
            cover = (getattr(cv, "through_cover", {}) or {}).get(cid) or {}
            if cover:
                hid, npx = max(cover.items(), key=lambda kv: kv[1])
                if npx >= 0.4 * (npx + s[0]):
                    # category kitchen_counter 의 영어 이름은 「kitchen counter」. 문장은 이미 그 방 안이라 앞 단어를 뺀다
                    name = _label_en(next(x for x in sc.items if x["id"] == hid))
                    if name.startswith("kitchen "):
                        name = name[len("kitchen "):]
                    parts.append("partly behind the {}".format(name))
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
                tail = " Built into it at {}: {}, {}x{}x{} cm, front flush."
                line += tail.format(end, _look(a), _cm(asz.get("w", 0)), _cm(asz.get("d", 0)), _cm(asz.get("h", 0)))
                short[-1] += tail.format(end, "a " + _label_en(a), _cm(asz.get("w", 0)), _cm(asz.get("d", 0)),
                                         _cm(asz.get("h", 0)))
            for a in _undrawn_on(cv, nb, seen).get(it["id"], []):
                line += _on_out_of_frame(a, it)
                short[-1] += _on_out_of_frame(a, it, brief=True)
                top = AVOID_BARE_TOP.format(_label_en(it))
                if top not in stacked_avoid:
                    stacked_avoid.append(top)
            lines.append(line)
            labels.append(P.label_of(it))
            places.append("문간에 붙음" if near <= 30 else "문간에서 {}cm".format(_cm(near)))
            facts.append(dict(id=it["id"], label=P.label_of(it), share=round(s[0] / A, 3), x=round(hx, 2),
                              en=dict(id=it["id"], label=_label_en(it), look=_look(it), where="; ".join(parts))))
        kind = nb.room.get("kind")
        fin, here = room_finish(house, con, nb.room), room_finish(house, con, sc.room)
        label, label_ko = KIND_EN.get(kind, "next room"), P.KIND_KO.get(kind or "", "옆 방")
        # 화면 자리(hp)는 In view 줄이 이미 적었다. 벽 이름으로 그 개구부를 가리킨다. 마감이 이 방과 같으면 「same as here」
        # (이어진 한 바닥이라는 말이기도 하고, 프롬프트 한도 가까운 컷의 글자를 아낀다)
        opened = _opening(sc, m, cam)
        head = "Through {} is the {} (walls: {}; floor: {}). {}".format(
            opened["the"], label, "same as here" if fin["walls"] == here["walls"] else fin["walls"],
            "same as here" if fin["floor"] == here["floor"] else fin["floor"],
            _span_sentence(cam, m["op"], nb.room, narrow))
        # 이 방 벽과 한 줄로 이어지는 너머 방 벽(개구부 벽에 수직인 두 벽 중 좌표가 같은 것). 안 적으면 모델은 너머 방을
        # 더 깊게 지어 이 방 벽보다 뒤에 그 방의 벽을 세운다(2026-11-13 현관: 신발장 벽과 한 줄인 주방 벽을 뒤로 물렸다).
        # 개구부가 그 모서리에 붙어 있으면(_seam_sides) 두 벽은 한 면이다. 「한 줄」 이라고만 적었을 때 모델은 그 자리에
        # 벽 토막을 세우고 주방 벽을 여전히 물렸다(같은 날 두 번째) — 한 면이라고 적고, 그 벽에 붙은 이 방 가구와 너머
        # 가구가 가까우면 둘을 이름으로 잇는다
        nr, hr = P.rr(nb.room), P.rr(sc.room)
        seam = {side for side, _ in _seam_sides(sc, nb, m["op"])}
        lined, ko_lined = [], []        # (벽 문장, 짝 문장) — 짝은 그 벽 문장 바로 뒤에 와야 「it」 이 그 벽이다
        for side in (("w", "e") if m["side"] in "ns" else ("n", "s")):
            k = {"w": 0, "n": 1, "e": 2, "s": 3}[side]      # P.rr 의 (x0, y0, x1, y1) 자리
            rel = _wall_rel(side, cam)
            if abs(nr[k] - hr[k]) > 1 or rel.startswith("near"):
                continue
            w = REL_EN[rel][len("the "):]
            if side not in seam:
                lined.append((" Its {0} is in line with this room's {0}.".format(w), ""))
                ko_lined.append("{}이 이 방 {}과 한 줄".format(WALL_KO[rel], WALL_KO[rel]))
                continue
            ko_lined.append("{}이 이 방 {}과 한 면(튀어나온 벽 없음)".format(WALL_KO[rel], WALL_KO[rel]))
            ax = (1, 3) if side in "we" else (0, 2)          # 그 벽을 따르는 축의 rect 자리

            def on_wall(ctx, it):
                if _place_wall(it) != side or it.get("on") or P.CAT.get(it.get("category"), {}).get("floor"):
                    return None
                r = ctx.geo[it["id"]]["rect"]
                return r[ax[0]], r[ax[1]]
            best = None
            for a in seen_here:
                ra = on_wall(sc.ctx, a)
                for _, _, b, _ in vis:
                    rb = ra and on_wall(nb.ctx, b)
                    if rb:
                        gap = max(ra[0] - rb[1], rb[0] - ra[1], 0)
                        if gap <= SIDE_BY_SIDE and (best is None or gap < best[0]):
                            best = (gap, a, b)
            lined.append((" Its {0} continues this room's {0} as one flat wall.".format(w),
                          best and " The {} and the {} stand side by side against it.".format(
                              _label_en(best[1]), _label_en(best[2])) or ""))
            if best:
                ko_lined.append("그 벽에 {}·{} 나란히".format(P.label_of(best[1]), P.label_of(best[2])))
        start, head = head, ""
        # 너머 방의 창·문. 너머를 글로 적지 않았을 때 모델은 그 방의 대표 사진(창과 침대)을 문간에 옮겨 그렸다(2026-11-13
        # 주방 컷: 문간 너머는 옷장 옆 벽뿐이다). 가구만 적으면 창은 여전히 글에 없는 자리라, 보이는 창·문은 자리와 함께,
        # 창이 있는 방인데 안 보이면 안 보인다고 적는다
        shown, ko_ops, win_seen, extra_avoid = [], [], False, []
        if opened.get("avoid"):
            extra_avoid.append(opened["avoid"])
        for k, (cnt, xs_) in sorted(getattr(cv, "through_ops", {}).get(oid, {}).items()):
            if cnt / A < THROUGH_OP_MIN:
                continue
            nm = nb.ops[k]
            no = nm["op"]
            rel = _wall_rel(nm["side"], cam)
            php = _hpos(xs_ / float(cnt) / W)
            if no["type"] == "window":
                under = _below_window(nb, no)
                above = ", above the {}".format(under) if under else ""
                text, _sash, phrase = _window_text(no, REL_EN[rel], php, above, con["curtains"], None)
                shown.append(text)
                ko_ops.append("창({})".format(WALL_KO[rel]))
                win_seen = True
                if phrase and _GLASS_AVOID not in extra_avoid:
                    extra_avoid.append(_GLASS_AVOID)
            else:
                far = no.get("to") if no["room"] == nb.room["id"] else no["room"]
                dest = "outside" if far == "outside" else (
                    "the " + KIND_EN.get(nb.ctx.rooms.get(far, {}).get("kind"), "next room"))
                if no["type"] == "opening":
                    opx = _opening(nb, nm, cam)
                    shown.append(opx["a"].format(to=" to " + dest) + " ({})".format(php))
                    ko_ops.append("트인 문간({})".format(WALL_KO[rel]))
                    if opx.get("avoid") and opx["avoid"] not in extra_avoid:
                        extra_avoid.append(opx["avoid"])
                else:
                    shown.append("a closed door to {} on {} ({})".format(dest, REL_EN[rel], php))
                    ko_ops.append("문({})".format(WALL_KO[rel]))
        if shown:
            head += " Visible there: " + "; ".join(shown) + "."
        if not win_seen and any(nm["op"]["type"] == "window" for nm in nb.ops.values()):
            head += " No window shows there."
            ko_ops.append("창은 안 보인다")
        tail = " Draw only these there:" if lines else " No furniture shows there."
        # 나란히·깊이·폭·벽이 이어진다는 문장은 구조다. 한도가 넘어도 빼지 않는다.
        head = start + "".join(a + b for a, b in lined) + head + tail
        check = "문간 너머 {} — {}".format(label_ko, "·".join(labels) + " 만 보인다" if labels else "가구 없이 벽·바닥만 보인다")
        ko_ops = [_span_ko(cam, m["op"], nb.room, narrow)] + [
            "{} {}".format(a, b) for a, b in zip(labels, places)] + ko_lined + ko_ops
        if ko_ops:
            check += " · " + " · ".join(ko_ops)
        merged = {}
        for rid, (far_sc, far_members) in (far_of.get(oid) or {}).items():
            merged[rid] = [far_sc, far_members]
        for rid, (far_sc, npx) in (getattr(cv, "far_shell", {}).get(oid) or {}).items():
            if npx >= 30:
                merged.setdefault(rid, [far_sc, []])
        for _rid, (far_sc, far_members) in merged.items():
            n, extra, brief, _flabels, fcheck, fids, fbare = _far_room_lines(
                cam, st, house, con, sc, nb, far_sc, far_members, n, W, H, A, cv)
            lines.extend(extra)
            short.extend(brief)
            far_ids.extend(fids)
            for top in fbare:
                if top not in stacked_avoid:
                    stacked_avoid.append(top)
            if fcheck:
                check += " · " + fcheck
        for top in stacked_avoid:
            if top not in extra_avoid:
                extra_avoid.append(top)
        out.append(dict(oid=oid, room=nb.room["id"], label=label, label_ko=label_ko, share=area / A,
                        head=head, lines=lines, short=short, check=check, items=facts, far_ids=far_ids,
                        shallow=geom["depth"] <= SHALLOW_MM, depth_cm=_cm(geom["depth"]),
                        full_width=bool(opened.get("wide")), avoids=extra_avoid))
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
            lines[-1] += " Built into it at {}: {}, {}x{}x{} cm, front flush.".format(
                end, _look(a), _cm(asz.get("w", 0)), _cm(asz.get("d", 0)), _cm(asz.get("h", 0)))
        for a in atop.get(it["id"], []):
            edge = " past the {} edge".format("left" if v["cut_l"] else "right") if v["cut_l"] or v["cut_r"] else ""
            lines[-1] += _on_out_of_frame(a, it, edge)
            top = AVOID_BARE_TOP.format(_label_en(it))
            if top not in avoid:
                avoid.append(top)
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
            under = _below_window(sc, o)
            above = ", above the {}".format(under) if under else ""
            text, sash, phrase = _window_text(o, REL_EN[rel], hp, above, curtains, view)
            ops.append(text)
            checks.append("창 — {}, 화면 {}".format(WALL_KO[rel], HPOS_KO[hp]))
            _note_window(checks, avoid, sash, phrase, None if phrase else view)
        elif o["type"] == "opening":
            other = o.get("to") if o["room"] == room["id"] else o["room"]
            dest = "outside" if other == "outside" else ("the " + KIND_EN.get(rooms.get(other, {}).get("kind"), "next room"))
            op = _opening(sc, m, cam)
            ops.append("{} ({})".format(op["a"].format(to=" to " + dest), hp))
            checks.append("{} — {}, 화면 {}".format(op["ko"], WALL_KO[rel], HPOS_KO[hp]))
            if op.get("avoid") and op["avoid"] not in avoid:
                avoid.append(op["avoid"])
        else:
            other = o.get("to") if o["room"] == room["id"] else o["room"]
            dest = "outside" if other == "outside" else ("the " + KIND_EN.get(rooms.get(other, {}).get("kind"), "next room"))
            ops.append("a door to {} on {} ({})".format(dest, REL_EN[rel], hp))
            checks.append("문 — {}, 화면 {}".format(WALL_KO[rel], HPOS_KO[hp]))
    thru = describe_through(sc, cam, cv, st, house, len(vis), [v["it"] for v in vis])
    checks.extend(t["check"] for t in thru)
    thru_txt = [ln for t in thru for ln in (t["head"],) + tuple(t["lines"])]
    if any("sliding sash" in ln for ln in thru_txt) and _SASH_AVOID not in avoid:
        avoid.append(_SASH_AVOID)
        if _SASH_CHECK not in checks:
            checks.append(_SASH_CHECK)
    if any("frosted translucent glass" in ln for ln in thru_txt):
        if _GLASS_AVOID not in avoid:
            avoid.append(_GLASS_AVOID)
        chk = _GLASS_CHECK if any("security-bar" in ln for ln in thru_txt) else _GLASS_CHECK_PLAIN
        if chk not in checks:
            checks.append(chk)
    # 방 사진을 레퍼런스로 사람을 앉히면 빈 의자가 더 생기고 좌우가 뒤집혔다(2026-11-18).
    # 개수는 이 방 항목 수(화면 밖 포함)이고, 좌우는 이 화면에서 본 쪽이다.
    counts = room_count_lines(sc.items)
    layout = frame_layout(vis)
    prefix = []
    if layout:
        prefix.append("Layout: " + layout + ".")
    prefix.extend(counts)
    if prefix:
        lines[0:0] = prefix
    if counts and _COUNT_CHECK not in checks:
        checks.append(_COUNT_CHECK)
    if layout and _LAYOUT_CHECK not in checks:
        checks.append(_LAYOUT_CHECK)
    return vis, lines, ops, checks, board, avoid, facts, thru


def _and(words):
    words = list(words)
    return words[0] if len(words) == 1 else ", ".join(words[:-1]) + " and " + words[-1]


def kitchen_line(house, room_ids):
    """주방이 화면에 있으면 상부장과 쿡탑 위 후드를 적는다. 집 데이터에 그 품목이 있을 때만."""
    items = [it for it in house.get("items") or [] if it.get("room") in room_ids]
    bits, avoids = [], []
    if any(it.get("category") == "upper_cabinet" for it in items):
        bits.append("White wall-hung upper cabinets run above the sink counter.")
        avoids.append(AVOID_BARE_WALL)
    if any(it.get("category") == "hood" for it in items):
        bits.append("A range hood is mounted directly above the cooktop.")
        avoids.append(AVOID_NO_HOOD)
    return " ".join(bits), avoids


def _standing(it):
    """바닥에 서는 가구인가. 올린 것·벽에 높이 단 것·러그처럼 납작한 바닥 품목은 아니다."""
    return not (it.get("on") or (it.get("z", 0) or 0) >= P.WALL_MOUNT_Z
                or P.CAT.get(it.get("category"), {}).get("floor"))


def _flush_at_entry(ctx, entry_id, visible_ids):
    """타일 경계(옆방 벽 선)에 면이 닿는, 화면에 있는 옆방 가구. 그 가구는 마루 위에 서고 타일은 그 면에서 멈춘다."""
    _rects, edges = entry_tile(ctx, entry_id)
    out = []
    for e in edges:
        o = e["op"]
        for it in ctx.items:
            if it.get("room") != e["room"] or not _standing(it) or it["id"] not in visible_ids:
                continue
            g = ctx.geo.get(it["id"])
            if not g:
                continue
            rect = g["rect"]
            if o["axis"] == "x":
                near = min(abs(rect[1] - e["line"]), abs(rect[3] - e["line"]))
                lo, hi = rect[0], rect[2]
            else:
                near = min(abs(rect[0] - e["line"]), abs(rect[2] - e["line"]))
                lo, hi = rect[1], rect[3]
            if min(hi, e["b"]) - max(lo, e["a"]) < 80 or near > 80:
                continue
            if it not in out:
                out.append(it)
    return out


def _on_tile(ctx, entry_id, visible_ids):
    """현관 안에 서 있는, 화면에 있는 가구. 타일 구역은 현관 방 전체라 발판까지 통째로 타일 위다."""
    return [it for it in ctx.items if it.get("room") == entry_id and _standing(it) and it["id"] in visible_ids]


def _pl(items):
    return len(items) > 1


def entry_floor_line(ctx, entry_ids, visible_ids, floor_word=None, in_frame=True):
    """현관 바닥이 보일 때 타일 구역을 글로 못 박는다. → (문장, Avoid 목록)
    타일은 현관 방 전체(문간 벽 두께 포함)를 벽에서 벽까지 덮고, 경계는 옆방 벽 선 한 줄이다. 화면에 있는 현관 가구는
    통째로 타일 위, 경계에 닿은 옆방 가구는 통째로 마루 위라고 이름으로 적는다. 레퍼런스 사진보다 이 글과 스케치를 따른다.
    floor_word: 옆방 id → 그 방 바닥 이름(기본 'wood').
    in_frame: 스케치에 타일이 한 픽셀이라도 칠해졌나. 아니면(카메라가 타일 위에 서서 발밑이 화면 밖) 「화면에 타일 없음」 을
    적는다. 「보이면 타일」 처럼 열어 두면 모델이 화면 아래에 타일을 지어 옆방 바닥까지 깔았다(2026-11-17)."""
    for eid in entry_ids:
        if not tile_entry(ctx.rooms.get(eid)):
            continue
        rects, _edges = entry_tile(ctx, eid)
        xs = [v for r in rects for v in (r[0], r[2])]
        ys = [v for r in rects for v in (r[1], r[3])]
        w, d = (max(xs) - min(xs)) / 10.0, (max(ys) - min(ys)) / 10.0
        tiled = _on_tile(ctx, eid, visible_ids)
        flush = _flush_at_entry(ctx, eid, visible_ids)
        fws = [(floor_word or {}).get(it["room"], "wood") if isinstance(floor_word, dict) else (floor_word or "wood")
               for it in flush]
        if not in_frame:
            out = ["Entry floor: tile, one small step down, but it is out of frame in this shot. Every floor surface in "
                   "frame is the {} floor; draw no tile anywhere.".format(fws[0] if fws else "wood")]
            if flush:
                out.append("The {} stand{} entirely on that floor.".format(
                    _and(_label_en(it) for it in flush), "" if _pl(flush) else "s"))
            out.append("Follow this text and the sketch, not any reference photo.")
            return " ".join(out), [AVOID_TILE_IN_FRAME] + [AVOID_TILE_UNDER.format(_label_en(it)) for it in flush]
        head = ("Entry floor: gray tile, one small step down, covering the whole entry wall to wall "
                "(about {:.0f} x {:.0f} cm). The tile ends in one straight line at the opening".format(w, d))
        if flush:
            head += ", level with the entry-side face of the " + _and(_label_en(it) for it in flush)
        out = [head + "."]
        if tiled:
            names = _and(_label_en(it) for it in tiled)
            out.append("The {} stand{} entirely on the tile; the tile runs past {} full width and depth to the walls "
                       "and the opening line.".format(names, "" if _pl(tiled) else "s", "their" if _pl(tiled) else "its"))
        if flush:
            words = {}
            for it, fw in zip(flush, fws):
                words.setdefault(fw, []).append(it)
            for fw, its in words.items():
                out.append("The {} stand{} entirely on the {} floor; no tile under any part of {}.".format(
                    _and(_label_en(it) for it in its), "" if _pl(its) else "s", fw, "them" if _pl(its) else "it"))
        out.append("The tile area and its boundary follow this text and the sketch, not any reference photo.")
        avoids = [AVOID_TILE] + [AVOID_TILE_UNDER.format(_label_en(it)) for it in flush] + [
            AVOID_TILE_PARTWAY.format(_label_en(it)) for it in tiled]
        return " ".join(out), avoids
    return "", []


def entry_floor_checks(ctx, entry_ids, visible_ids, in_frame=True):
    """사람용 확인 목록(한국어)."""
    for eid in entry_ids:
        if not tile_entry(ctx.rooms.get(eid)):
            continue
        if not in_frame:
            return ["현관 타일은 화면 밖이다. 화면 안 바닥은 모두 마루이고 타일이 없다"] + [
                "{} — 통째로 마루 위다".format(P.label_of(it)) for it in _flush_at_entry(ctx, eid, visible_ids)]
        out = ["현관 타일은 현관 전체를 벽에서 벽까지 덮고, 경계는 개구부 선 한 줄이다. 옆방 안이나 현관 안쪽으로 밀리지 않는다"]
        for it in _on_tile(ctx, eid, visible_ids):
            out.append("{} — 통째로 타일 위다. 타일이 그 밑 중간에서 끝나지 않는다".format(P.label_of(it)))
        for it in _flush_at_entry(ctx, eid, visible_ids):
            out.append("{} — 통째로 마루 위다. 타일이 그 밑으로 들어가지 않는다".format(P.label_of(it)))
        return out
    return []


def build_prompt(house, concept, ratio, cam, kind_txt, view, lines, ops, board, refs, light_dir=None, avoid=(), thru=()):
    R = RATIOS[ratio]
    room = view["room"]
    rx0, ry0, rx1, ry1 = P.rr(room)
    C = (house.get("photo") or {}).get("ceiling", DEFAULT_CEIL)
    tilt = ("camera level so vertical lines stay vertical" if abs(cam.pitch) < math.radians(3)
            else "camera tilted slightly down" if cam.pitch < 0 else "camera tilted slightly up")
    fin = view["finish"]
    out = [COMMON_LOOK + " " + fin["details"]]
    if not view.get("short_style"):
        out.append(concept["mood"])
    out.append("Camera: {} photo, {:.0f} mm full-frame-equivalent lens, camera height {} cm, {}.".format(
        R[4], cam.lens_mm, _cm(cam.z), tilt))
    out.append("Space: {}, {:.1f} m x {:.1f} m, ceiling {:.1f} m. Walls: {}. Floor: {}.".format(
        view["space"], (rx1 - rx0) / 1000.0, (ry1 - ry0) / 1000.0, C / 1000.0, fin["walls"], fin["floor"]))
    light = concept["light"]
    # 컨셉이 햇빛을 말해도 간유리 창의 빛은 퍼진 낮·저녁 빛이다. 이미 diffuse 인 문장은 그대로 둔다.
    if light_dir and "frosted glass" in light_dir and "diffuse" not in light.lower():
        light = light.rstrip(".") + ", diffuse through the frosted glass, no direct sun"
    if view.get("short_style"):
        out.append("Light: {}.".format(light_dir) if light_dir else "Light: soft daylight.")
    else:
        out.append("Light: {}. {}".format(light, light_dir) if light_dir else
                   "Light: soft even light from the LED ceiling light, with a little daylight from the opening.")
    out.append("View: {}.".format(kind_txt))
    rules, body = [], []
    for ln in lines:
        if ln.startswith("Layout: ") or ln.startswith("Exactly "):
            rules.append(ln)
        else:
            body.append(ln)
    if ops:
        out.append("In view: " + "; ".join(ops) + ".")
    if rules:
        # 개수·좌우는 가구 목록과 따로다. 한도로 줄이지 않는다.
        out.append(" ".join(rules))
    if view.get("kitchen"):
        out.append(view["kitchen"])
    if view.get("entry_floor"):
        out.append(view["entry_floor"])
    if view.get("towel"):
        # 낮·저녁이 같은 문장이다. 한도로 줄이지 않는다.
        out.append(view["towel"])
    out.append("Furniture in frame, left to right (position, depth; W x D x H). Draw exactly these, at true scale:")
    out.extend(body)
    # 소품은 적은 것만 놓인다. 「Small soft props only」 는 작은 소품을 더 지어 놓아도 된다는 말로 읽혀, 목록에 없는
    # 조명·상자가 수납장 위에 올라갔다(2026-11-13). 어느 방이든 받침 윗면과 바닥에는 적은 소품 말고는 아무것도 없다
    props = fin["props"] and fin["props"] + (", " + concept["plants"] if concept.get("plants") else "")
    guard = " Do not add a furniture run on a wall the sketch and list do not show."
    if view.get("short_style") or not props:
        out.append("Styling: nothing on any surface." + guard)
    else:
        out.append("Styling: {}; nothing else on any surface.{}".format(props, guard))
    for t in thru:
        out.append(t["head"])
        out.extend(t["short"] if view.get("short_through") else t["lines"])
    rt = []
    bidx = [i for i, ref in enumerate(refs, 1) if ref["role"] == "board"]
    mf = view.get("master_finish") or fin
    same = [k for k in ("walls", "floor") if fin[k] == mf[k]]
    for i, ref in enumerate(refs, 1):
        if ref.get("opposite_view"):
            rt.append("Reference image {0} is a photo looking the other way through this same opening. Do not copy its "
                      "left and right. Furniture that shares one wall in the plan stays on that wall; it swaps sides of "
                      "the frame in this view. Do not add a run of furniture on the side where that photo had it if this "
                      "shot's sketch and text place that wall on the other side. Match only the opening width, the shared "
                      "wall's finishes, and the light. This shot's massing sketch is the authority for left, right, depth "
                      "and how large the far wall is in the frame.".format(i))
        elif view.get("short_refs") and ref["role"] in ("master", "neighbor"):
            rt.append("Reference image {} matches finishes and light only, not the layout.".format(i))
        elif ref["role"] == "master" and ref.get("same_room"):
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
        elif ref["role"] == "sketch" and view.get("short_refs"):
            rt.append("Reference image {} is the massing sketch: left, right, and depth follow it{}.".format(
                i, "; the checkered floor is the entry tile" if TILE in view.get("colors", ()) else ""))
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
    if spec.get("for_room") and spec["for_room"] != sc.room["id"]:
        sub = sc.ctx.rooms[spec["for_room"]]
        here_en = KIND_EN.get(sc.room.get("kind"), "room")
        sub_en = KIND_EN.get(sub.get("kind"), "room")
        here_ko = P.KIND_KO.get(sc.room.get("kind") or "", "방")
        sub_ko = P.KIND_KO.get(sub.get("kind") or "", "방")
        return ("a wide shot standing in the {}, looking through the opening into the {}".format(here_en, sub_en),
                "{}에서 열린 문간으로 {} 쪽을 본다".format(here_ko, sub_ko))
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
        other = byid.get(m) if m else None
        # 서로 문간에 서서 상대 방을 찍는 두 컷은 서로의 대표를 기다리지 않는다
        if other and other.get("for_room") == s["room"] and s.get("for_room") == other.get("room"):
            m = None
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
        ready = [s for s in base if s["id"] not in done and need(s) <= done]
        if not ready:
            raise SystemExit("컷 순서를 정하지 못했다: " + ", ".join(
                "{} needs {}".format(s["id"], ",".join(need(s)) or "-") for s in base if s["id"] not in done))
        first_ready = ready[0]
        s = pick(first_ready, frozenset()) or first_ready
        out.append(s)
        done.add(s["id"])
    return out


def _yaw_opposite(a, b, tol=math.radians(40)):
    """두 시선이 약 180° 반대인지. 각은 ±180° 로 접고, abs(abs(차)−180°) ≤ tol."""
    d = math.atan2(math.sin(a - b), math.cos(a - b))
    return abs(abs(d) - math.pi) <= tol


def _same_opening(a, b):
    return bool(set(a.get("through_ops") or ()) & set(b.get("through_ops") or ()))


def _room_photo_ref(spec, by_spec, master_of_room, global_master, made):
    """같은 방 대표 사진. 같은 문간을 반대쪽에서 본 사진이면 같은 방 대표로 넣지 않고 opposite neighbor 로 돌린다.
    돌려주는 것: (refs, warnings)."""
    if spec["id"] == global_master:
        return [], []
    m = master_of_room.get(spec["room"])
    other = by_spec.get(m) if m and m != spec["id"] else None
    if other and _same_opening(spec, other) and _yaw_opposite(spec["yaw"], other["yaw"]):
        refs = []
        if m in made:
            refs.append(dict(role="neighbor", shot=m, opposite_view=True,
                             label="this opening", label_ko="같은 문간, 반대"))
        elif global_master not in (spec["id"], m):
            refs.append(dict(role="master", shot=global_master, same_room=False))
        return refs, ["반대 방향 참고 — `{}` 은 같은 문간을 반대쪽에서 본 사진이다. 같은 방 대표로 넣지 않는다. "
                      "좌우·깊이·먼 벽은 이 컷의 스케치가 정한다".format(m)]
    if m and m != spec["id"]:
        return [dict(role="master", shot=m, same_room=True)], []
    return [dict(role="master", shot=global_master, same_room=False)], []


def _fit_prompt(shot_id, build, view, thru):
    """한도를 넘으면 생김새·소품·레퍼런스 설명을 줄인다. 나란히·깊이·폭·벽이 이어진다는 문장은 남긴다.
    그래도 넘으면 그 문장을 빼지 않고 컷을 내지 않는다."""
    prompt = build()
    notes = []
    if len(prompt) > PROMPT_MAX and thru:
        view["short_through"] = True
        prompt = build()
        notes.append("프롬프트가 한도를 넘어 문간 너머 품목의 생김새를 뺐다(크기·자리만 적는다)")
    if len(prompt) > PROMPT_MAX:
        view["short_style"] = True
        prompt = build()
        notes.append("프롬프트가 한도를 넘어 소품 문장을 줄였다")
    if len(prompt) > PROMPT_MAX:
        view["short_refs"] = True
        prompt = build()
        notes.append("프롬프트가 한도를 넘어 레퍼런스 설명을 줄였다")
    if len(prompt) > PROMPT_MAX:
        structural = any("side by side" in (t.get("head") or "") for t in thru)
        why = ("나란히 선 가구 문장은 구조라 빼지 않는다. " if structural else
               "깊이·폭·벽이 이어진다는 문장은 구조라 빼지 않는다. ")
        if "top shows" in prompt:
            why += "받침 위 품목 문장(if the … top shows)도 구조라 빼지 않는다. "
        if "Towel bar:" in prompt:
            why += "수건걸이 자리 문장은 구조라 빼지 않는다. "
        raise SystemExit("컷 {} 의 프롬프트가 {:,}자로 한도({:,}자)를 넘는다. {}"
                         "look 을 줄이고 plan 을 다시 돌린다. 이 컷은 내지 않는다.".format(
                             shot_id, len(prompt), PROMPT_MAX, why))
    return prompt, notes


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
                          lens=m.get("lens", MAIN_LENS if m.get("kind", "wide") == "wide" else HERO_LENS),
                          kind=m.get("kind", "wide"), target=m.get("target"),
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
    unshot = []
    for room in rooms:
        if room["id"] in covered or room["id"] in skip:
            continue
        sc = Scene(ctx, room, ceil)
        pre = "" if len(rooms) == 1 else room["id"] + "-"
        wides = plan_wide(sc, ratio, cam_h, review)
        if not wides:
            unshot.append(room["id"])
        for k, s in enumerate(wides, 1):
            s["id"] = "{}wide-{}".format(pre, k)
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
    for s in sorted(specs, key=lambda x: (rank.get(x.get("for_room") or x["room"], 99), not x.get("window"))):
        # 문간 밖에서 찍은 전체 컷도 그 방(for_room)의 대표가 된다. 창이 보이는 컷을 먼저 고른다
        key = s.get("for_room") or s["room"]
        if s["kind"] == "wide" and key not in master_of_room:
            master_of_room[key] = s["id"]
            global_master = global_master or s["id"]
    global_master = global_master or specs[0]["id"]
    master_finish = room_finish(house, concept, ctx.rooms[next(s["room"] for s in specs if s["id"] == global_master)])
    has_ffmpeg = bool(shutil.which("ffmpeg"))
    seen_by = {}                                  # 컷 id → (스케치·글 재료)
    skipped = []                                  # 자동 제품 컷만 빼고 나머지는 계속 낸다
    for s in specs:
        room = ctx.rooms[s["room"]]
        sc = Scene(ctx, room, ceil)
        hfov = 2 * math.atan((sw / 2.0) / s["lens"])
        cam = Cam(s["x"], s["y"], s["z"], s["yaw"], s["pitch"], hfov, W, H, s["lens"], s.get("cyf", 0.5))
        cv = see_through(sc, cam, sc.render(cam))
        st = cv.stats()
        if s["kind"] == "wide":
            bad_cam = wide_faults(sc, cam, cv, st)
            if bad_cam and s.get("where") == "manual":
                s["cam_faults"] = bad_cam          # 직접 적은 자리는 경고로 남긴다. 자동 자리는 후보에서 이미 뺐다
            elif bad_cam:
                raise SystemExit("컷 {} 은 폰으로 찍을 수 없는 자리다:\n  {}".format(s["id"], "\n  ".join(bad_cam)))
        empty = void_faults(cv)
        if empty:
            raise SystemExit("컷 {} 의 스케치에 비어 있는 문간이 남았다. 이 컷은 내지 않는다:\n  {}".format(
                s["id"], "\n  ".join(empty)))
        blown = scale_faults(sc, cam, cv, st)
        if blown:
            # 직접 적은 컷은 멈추고, 자동 제품 컷 하나는 빼고 다음 컷을 계속 만든다
            if s["kind"] == "hero" and s.get("where") != "manual":
                skipped.append(dict(id=s["id"], why=blown))
                continue
            raise SystemExit("컷 {} 의 상자가 치수와 안 맞는다. 이 컷은 내지 않는다:\n  {}".format(
                s["id"], "\n  ".join(blown)))
        # 범례는 스케치에 실제로 칠해진 색만 적는다. 트인 문간은 너머 방이 그려져 짙은 회색이 남지 않는 일이 많다
        painted = set(zip(cv.px[0::3], cv.px[1::3], cv.px[2::3]))
        colors = {c for c, _ in OPENING_LEGEND if tuple(c) in painted}
        if TILE_ALT in painted:
            colors.add(TILE)                     # 바둑판의 다른 칸만 보여도 타일이 화면에 있다
        sketch = os.path.join("sketch", s["id"] + ".png")
        cv.png(os.path.join(out_dir, sketch))
        # 범례는 사람용이다. 모델에 넣는 레퍼런스는 위의 깨끗한 스케치다.
        write_legend(cv, os.path.join(out_dir, "sketch", s["id"] + "-legend.png"), _legend_entries(sc, cv, st, cam))
        s["through_ops"] = sorted((getattr(cv, "doorways", {}) or {}))
        seen_by[s["id"]] = (sc, cam, hfov, st, sketch, colors, describe(sc, cam, cv, st, house, rules))
        del cv
    specs = [s for s in specs if s["id"] in seen_by]
    looks = {sid: [t["room"] for t in sorted(v[6][7], key=lambda t: -t["share"]) if t["share"] >= NEIGHBOR_SHARE]
             for sid, v in seen_by.items()}
    shots, made = [], set()
    for s in shot_order(specs, global_master, master_of_room, looks):
        room = ctx.rooms[s["room"]]
        sc, cam, hfov, st, sketch, colors, (vis, lines, ops, checks, board, avoid, facts, thru) = seen_by[s["id"]]
        is_master = s["id"] == global_master
        refs, ref_warns = _room_photo_ref(s, {x["id"]: x for x in specs}, master_of_room, global_master, made)
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
        warns = list(ref_warns)
        if any(r.get("opposite_view") for r in refs):
            checks.append("반대 방향 참고 — 마감·빛·문간 폭만 맞추고, 좌우·깊이·먼 벽 크기는 이 컷의 스케치와 글을 따른다")
        for t in thru:
            for a in t.get("avoids") or []:
                if a not in avoid:
                    avoid.append(a)
            if t.get("shallow"):
                warns.append("얕은 너머 — {} 은 문간에서 {}cm. 복도처럼 깊게 그리지 않는다".format(
                    t["label_ko"], t["depth_cm"]))
        if any(t.get("shallow") or t.get("full_width") for t in thru):
            for a in (AVOID_SHALLOW, AVOID_JAMB, AVOID_SIDE):
                if a not in avoid:
                    avoid.append(a)
        for v in vis:                             # 리뷰 제품을 글로만 그리지 않는다(2026-11-13 침대를 ref:false 로 뺐다 — 사용자 지적)
            it, prod = v["it"], v["it"].get("product") or {}
            if P.reviewable(it) and (prod.get("ref") is False or not (prod.get("ref_image") or prod.get("image"))):
                warns.append("{}: 리뷰 제품인데 보드에 사진이 없어 글로만 그린다{}. 상세 이미지에서 그 제품만 찍힌 사진을 찾아 "
                             "product.ref_image·ref_crop 으로 넣는다".format(
                                 P.label_of(it), "(이 컷의 대상이다)" if it["id"] == s.get("target") else ""))
        for msg in s.get("cam_faults") or []:
            warns.append("카메라 — " + msg)
        if s.get("for_room") and s["for_room"] != s["room"]:
            sub = ctx.rooms[s["for_room"]]
            here = ctx.rooms[s["room"]]
            warns.append("{}은 좁아 {}에서 트인 문간으로 찍는다(화면에 들어온 가구까지 {:.0f}cm 이상)".format(
                P.KIND_KO.get(sub.get("kind") or "", sub["id"]),
                P.KIND_KO.get(here.get("kind") or "", here["id"]), NEAR_MIN / 10))
        if s["kind"] == "wide":
            for it, d, side in near_cuts(sc, cam, st):
                warns.append("{}: 카메라에서 {:.1f}m, 화면 {} 끝에 잘려 걸린다. 생성 모델이 실제보다 크게 그리기 쉽다. "
                             "photo.shots 로 카메라를 옮겨 화면 밖으로 빼거나 전체가 들어오게 한다".format(
                                 P.label_of(it), d / 1000.0, "왼쪽" if side == "left" else "오른쪽"))
        en, ko = _view_text(sc, cam, s, byid)
        light_en, light_ko = light_direction(sc, cam, st)
        view = dict(room=room, space=_room_space(house, room), finish=room_finish(house, concept, room),
                    master_finish=master_finish, colors=colors)
        kids = set()
        if room.get("kind") == "kitchen":
            kids.add(room["id"])
        for t in thru:
            tr = ctx.rooms.get(t["room"])
            if tr and tr.get("kind") == "kitchen":
                kids.add(t["room"])
        kline, kavoids = kitchen_line(house, kids)
        if kline:
            view["kitchen"] = kline
        for a in kavoids:
            if a not in avoid:
                avoid.append(a)
        eids = set()
        if room.get("kind") == "entrance":
            eids.add(room["id"])
        for t in thru:
            tr = ctx.rooms.get(t["room"])
            if tr and tr.get("kind") == "entrance":
                eids.add(t["room"])
        vids = {v["it"]["id"] for v in vis}
        for t in thru:
            for it in t.get("items") or []:
                vids.add(it["id"])
        fwords = {}
        for rid, r in ctx.rooms.items():
            fl = room_finish(house, concept, r)["floor"].lower()
            fwords[rid] = ("wood" if any(k in fl for k in ("oak", "wood", "laminate")) else
                           KIND_EN.get(r.get("kind"), "room"))
        tin = TILE in colors
        eline, eavoids = entry_floor_line(ctx, eids, vids, fwords, tin)
        if eline:
            view["entry_floor"] = eline        # 구조 문장이다. _fit_prompt 가 줄이지 않는다
            for a in eavoids:
                if a not in avoid:
                    avoid.append(a)
            checks.extend(entry_floor_checks(ctx, eids, vids, tin))
        brooms = []
        if room.get("kind") == "bathroom":
            brooms.append(room)
        for t in thru:
            tr = ctx.rooms.get(t["room"])
            if tr and tr.get("kind") == "bathroom" and all(tr["id"] != r["id"] for r in brooms):
                brooms.append(tr)
        ttext, tchecks, tavoids = towel_view(ctx, cam, brooms)
        if ttext:
            view["towel"] = ttext
            checks.extend(tchecks)
            for a in tavoids:
                if a not in avoid:
                    avoid.append(a)
        def _build():
            return build_prompt(house, concept, ratio, cam, en, view, lines, ops, board, refs, light_en, avoid, thru)
        prompt, fit_notes = _fit_prompt(s["id"], _build, view, thru)
        visible_ids = {v["it"]["id"] for v in vis}
        for t in thru:
            for it in t.get("items") or []:
                visible_ids.add(it["id"])
            for fid in t.get("far_ids") or ():
                visible_ids.add(fid)
        gaps = missing_stacked(prompt, ctx.items, visible_ids)
        if gaps:
            raise SystemExit("컷 {} 의 프롬프트에 화면에 있는 받침 위 품목이 없다: {}. "
                             "이 문장은 구조라 한도로 줄이지 않는다.".format(s["id"], ", ".join(gaps)))
        warns.extend(fit_notes)
        if light_ko:
            checks.append("빛 — " + light_ko)
        checks.append("목록·소품 밖 물건(가구·가전·조명·장식·러그·액자)이 없다")
        if board:
            checks.append("제품 모양·비율·색·광택이 보드와 같다 — 다르면 `shots.py fix` 로 그 제품만 고친다")
        if not is_master and not any(r.get("opposite_view") for r in refs):
            checks.append("벽지·바닥·창틀·커튼·빛이 대표 컷과 같다")
        shots.append(dict(
            id=s["id"], kind=s["kind"], room=s["room"], for_room=s.get("for_room") or s["room"],
            master=is_master, title=ko,
            camera=dict(x=int(round(s["x"])), y=int(round(s["y"])), height=int(round(s["z"])),
                        yaw_deg=round(math.degrees(s["yaw"]), 1), pitch_deg=round(math.degrees(s["pitch"]), 1),
                        lens_mm=s["lens"], hfov_deg=round(math.degrees(hfov), 1)),
            target=s.get("target"),
            items=[dict(id=v["it"]["id"], label=P.label_of(v["it"]), share=round(v["share"], 3),
                        x=round(v["hx"], 2), hidden=round(1 - v["frac"], 2), en=f) for v, f in zip(vis, facts)],
            through=[dict(room=t["room"], label=t["label_ko"], share=round(t["share"], 3), items=t["items"],
                          far_ids=t.get("far_ids") or []) for t in thru],
            refs=refs, prompt=prompt, prompt_chars=len(prompt), checks=checks, warnings=warns))
    order = shots                                 # shot_order 의 순서 = 만드는 순서
    seen = {i["id"] for sh in shots for i in sh["items"] + [j for t in sh["through"] for j in t["items"]]}
    no_look = [it["id"] for it in ctx.items if it["id"] in seen and not it.get("look")]
    claims = {it["id"]: m.group(0) for it in ctx.items if it["id"] in seen
              for m in [SIZE_CLAIM.search(it.get("look") or "")] if m}
    data = dict(house=house.get("name"), concept=concept["key"], concept_ko=concept["ko"], ratio=ratio, image_size=size,
                model=ph.get("model"), quality=ph.get("quality", "medium"),
                missing_look=no_look, size_claims=claims, unshot=unshot, skipped=skipped,
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
           "카메라 자리와 보는 방향: `shots.svg` · 모델에 넣는 스케치: `sketch/<컷>.png` · "
           "사람용 범례: `sketch/<컷>-legend.png` · 제품 보드: `boards/`(board 명령)",
           "이미지 모델 {} · 품질 {} — 견적과 제출에 같은 값을 싣는다".format(
               "`{}`".format(data["model"]) if data.get("model") else "DemoCut 기본", data.get("quality", "medium")), "",
           "만드는 순서: **아래 번호 순서대로** 만든다. 대표 컷을 먼저 만들고 확인한 뒤 그 그림을 나머지 컷의 레퍼런스 1번으로 "
           "넣는다. 레퍼런스에 다른 컷의 그림이 있으면 그 컷이 언제나 앞 번호다.",
           "이 사진은 빈 방이다. 나중에 사람이 앉는 컷의 레퍼런스로 쓸 때, 그 사진에 이미 있는 의자·침대처럼 사람이 앉거나 "
           "쓰는 가구를 소품으로 따로 적지 않는다. `{}` 처럼 같은 물건이라고 적는다"
           "(예의 이름은 그 사람의 이름이고, 가구 이름은 그 가구로 바꾼다). 그 컷의 프롬프트에 있는 Layout·Exactly 문장을 그대로 "
           "옮기고, 같은 사진을 쓰는 다른 컷에도 같은 문장을 넣는다.".format(
               person_same_furniture("chair", "Yeonjae")), ""]
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
            elif r["role"] == "neighbor" and r.get("opposite_view"):
                refs.append("{}) `{}` 에서 만든 그림(같은 문간, 반대 방향)".format(k, r["shot"]))
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


def stacked_check(house_path, prompt_path=None, shots_path=None, shot_id=None, visible=None):
    """최종 프롬프트에, 화면에 있는 받침의 `on` 품목이 다 적혀 있는지. 없으면 종료 코드 1.
    prompt_path 가 있으면 그 글(손으로 고친 것)을 보고, 없으면 shots.json 의 그 컷 프롬프트를 본다."""
    with open(house_path, encoding="utf-8") as f:
        house = json.load(f)
    visible_ids = {x.strip() for x in (visible or "").split(",") if x.strip()}
    prompt = ""
    if shots_path and shot_id and not visible_ids:
        with open(shots_path, encoding="utf-8") as f:
            data = json.load(f)
        shot = next((s for s in data.get("shots") or [] if s.get("id") == shot_id), None)
        if shot is None:
            raise SystemExit("컷이 없다: {}".format(shot_id))
        visible_ids = {i["id"] for i in shot.get("items") or []}
        for t in shot.get("through") or []:
            for i in t.get("items") or []:
                visible_ids.add(i["id"])
            for fid in t.get("far_ids") or []:
                visible_ids.add(fid)
        prompt = shot.get("prompt") or ""
    if prompt_path:
        with open(prompt_path, encoding="utf-8") as f:
            prompt = f.read()
    if not prompt:
        raise SystemExit("프롬프트가 없다. --prompt 또는 --shots 와 --shot 을 준다")
    gaps = missing_stacked(prompt, house.get("items") or [], visible_ids)
    if gaps:
        raise SystemExit("받침 위 품목이 프롬프트에 없다: {}".format(", ".join(gaps)))
    print("ok stacked")
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
    e = sub.add_parser("stacked", help="화면에 있는 받침의 올린 품목이 프롬프트에 있는지 확인")
    e.add_argument("house")
    e.add_argument("--prompt", help="확인할 프롬프트 파일. 없으면 --shots 의 그 컷 프롬프트")
    e.add_argument("--shots", help="plan 이 낸 shots.json. --shot 과 함께 보이던 품목 id 를 받침으로 쓴다")
    e.add_argument("--shot", help="shots.json 의 컷 id")
    e.add_argument("--visible", help="쉼표로 구분한 받침 id. 주면 --shot 의 목록 대신 이것을 쓴다")
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
        for sk in data.get("skipped") or []:
            print("  ⚠ {} — 자동 제품 컷을 빼 두었다. {}".format(sk["id"], " / ".join(sk["why"])))
        for rid in data.get("unshot") or []:
            print("  ⚠ {} — 전체 컷 없음. 폰 기본 렌즈로 {:.0f}cm 이상 물러설 자리가 방 안에도 트인 문간 너머에도 없다".format(
                rid, NEAR_MIN / 10))
        if data["missing_look"]:
            print("⚠ look 이 없는 품목: {} — 제품 사진을 보고 items[].look 에 영어 한 문장을 적은 뒤 plan 을 다시 돌린다"
                  "(없으면 상품명이 들어가 모양이 틀어진다)".format(", ".join(data["missing_look"])))
        if data["size_claims"]:
            print("⚠ look 에 크기 관계 말이 있다: {} — 크기·여백은 치수와 가구별 규칙이 정한다. 제품 사진이 고른 옵션과 "
                  "다른 크기일 수 있으니 그 말을 빼고 모양·색·재질만 적는다".format(
                      ", ".join("{}('{}')".format(k, v) for k, v in data["size_claims"].items())))
        return 0
    if args.cmd == "stacked":
        return stacked_check(args.house, args.prompt, args.shots, args.shot, args.visible)
    if args.cmd == "fetch":
        fetch(P.load(args.house), args.dest)
        return 0
    if args.cmd == "fix":
        return fix(args.shots, args.shot, args.items, args.images, args.scale, args.change)
    return board(args.shots, args.images, args.out)


if __name__ == "__main__":
    sys.exit(main())
