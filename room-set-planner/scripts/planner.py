#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""room-set-planner — 오늘의집 제품으로 방을 꾸미는 배치도 플래너.
집 구조(house.json)를 만들고, 검사하고, 평면도 + 리뷰용 인벤토리 HTML 한 장으로 그린다.

표준 라이브러리만 쓴다(Python 3.8+). 단위는 전부 mm, 좌표는 도면 왼쪽 위가 원점이고
x 는 오른쪽, y 는 아래로 커진다. 벽 이름 n/s/w/e 는 방위가 아니라 도면의 위/아래/왼/오른쪽이다.

  planner.py shell spec.json -o house.json      평면 틀(방 한 칸·원룸형·아파트형)로 집 구조 만들기
  planner.py check house.json [--json]          겹침·여유 공간·문·동선·실측 검사 (오류가 있으면 종료 코드 1)
  planner.py walls house.json ROOM_ID           방의 벽별 빈 구간(가구를 붙일 자리) 보기
  planner.py inventory house.json               방별 인벤토리·합계(마크다운)
  planner.py render house.json -o plan.html     평면도 + 검사 결과 + 인벤토리 + 리뷰 카드 HTML 한 장
                [--embed-images]                제품 사진을 내려받아 HTML 안에 넣는다(공유용)
"""
import argparse
import datetime
import html as _html
import json
import math
import os
import sys
from collections import deque

OPP = {"n": "s", "s": "n", "e": "w", "w": "e"}
SIDE_KO = {"n": "위쪽", "s": "아래쪽", "w": "왼쪽", "e": "오른쪽"}
KIND_KO = {
    "bedroom": "침실", "living": "거실", "kitchen": "주방", "bathroom": "화장실",
    "entrance": "현관", "hall": "복도", "dressroom": "드레스룸", "utility": "다용도실",
}
TYPE_KO = {"room": "방 한 칸", "oneroom": "원룸형", "apartment": "아파트형"}

# 품목별 사용성 규칙. front/sides/seats = (최소, 권장) mm.
#   front: 정면에 비워 둘 깊이. spot 이 있으면 그 폭의 한 자리만 있으면 된다(의자 자리 등).
#   sides: 침대 양옆(머리맡 600 은 협탁 자리로 빼고 잰다). seats: 식탁 의자 쪽.
#   wall: 등을 벽에 붙이는 품목. floor: 바닥에 깔려 걸리지 않는 품목.
# 근거는 references/clearances.md.
CAT = {
    "bed": dict(label="침대", wall=True, sides=(500, 650)),
    "wardrobe": dict(label="옷장", wall=True, front=(750, 900)),
    "dresser": dict(label="서랍장", wall=True, front=(750, 900)),
    "bookshelf": dict(label="책장", wall=True, front=(600, 750)),
    "storage": dict(label="수납장", wall=True, front=(600, 750)),
    "nightstand": dict(label="협탁", wall=True),
    "desk": dict(label="책상", front=(750, 900), spot=700),
    "vanity": dict(label="화장대", wall=True, front=(700, 800), spot=600),
    "sofa": dict(label="소파", front=(450, 600)),
    "coffee_table": dict(label="거실 테이블"),
    "tv_stand": dict(label="TV장", wall=True, front=(450, 600)),
    "dining_table": dict(label="식탁", seats=(750, 900)),
    "kitchen_counter": dict(label="주방 상판", wall=True, front=(900, 1100)),
    "fridge": dict(label="냉장고", wall=True, front=(800, 1000)),
    "washer": dict(label="세탁기", wall=True, front=(600, 800)),
    "dryer": dict(label="건조기", wall=True, front=(600, 800)),
    "shoe_cabinet": dict(label="신발장", wall=True, front=(600, 750)),
    "toilet": dict(label="변기", wall=True, front=(600, 700)),
    "washbasin": dict(label="세면대", wall=True, front=(600, 750)),
    "shower": dict(label="샤워부스", front=(600, 700)),
    "bathtub": dict(label="욕조", wall=True, front=(600, 700)),
    "chair": dict(label="의자"),
    "rug": dict(label="러그", floor=True),
    "lamp": dict(label="조명"),
    "plant": dict(label="화분"),
    "tv": dict(label="TV"),
    "mirror": dict(label="거울", wall=True),
    "appliance": dict(label="가전", front=(600, 750)),
    "other": dict(label="기타"),
}

DIMS_SOURCE = {
    "spec_table": "상품정보고시",
    "option_text": "옵션명",
    "detail_text": "상세 설명 글",
    "detail_image": "상세 이미지 치수표",
    "qna": "판매자 Q&A",
    "review": "구매 후기",
    "user": "사용자 실측",
    "standard": "표준 규격",
}
WEAK_SOURCES = ("review", "standard")

CELL = 50          # 동선 격자 한 칸(mm)
PATH_KS = (5, 7)   # 지나갈 수 있는 통로: k=5 → 약 550mm 이상, k=7 → 약 750mm 이상
APPROACH = 500     # 문 앞에 비워 둘 깊이
WINDOW_BAND = 300  # 창 앞 이 깊이 안의 높은 가구는 창을 가린다
WALL_MOUNT_Z = 1200  # 이 높이 이상에 매단 것은 바닥 장애물이 아니다


# ----------------------------------------------------------------------------- 기하

def rr(room):
    x, y, w, d = room["rect"]
    return (x, y, x + w, y + d)


def inter(a, b):
    """두 사각형의 겹친 사각형(없으면 None)."""
    x0, y0 = max(a[0], b[0]), max(a[1], b[1])
    x1, y1 = min(a[2], b[2]), min(a[3], b[3])
    if x1 - x0 > 1 and y1 - y0 > 1:
        return (x0, y0, x1, y1)
    return None


def inside(a, outer, tol=1):
    return (a[0] >= outer[0] - tol and a[1] >= outer[1] - tol
            and a[2] <= outer[2] + tol and a[3] <= outer[3] + tol)


def hits_quarter(rect, center, quad, radius):
    """rect 가 문이 쓸고 지나가는 사분원(중심 center, 그 사분면 사각형 quad)과 겹치나."""
    c = inter(rect, quad)
    if not c:
        return False
    cx, cy = center
    nx = min(max(cx, c[0]), c[2])
    ny = min(max(cy, c[1]), c[3])
    return (nx - cx) ** 2 + (ny - cy) ** 2 < (radius - 1) ** 2


def fmt(n):
    return "{:,}".format(int(round(n)))


def area_txt(w, d):
    m2 = w * d / 1e6
    return "{:.1f}㎡ ({:.1f}평)".format(m2, m2 / 3.3058)


# ----------------------------------------------------------------------------- 해석

class Ctx:
    """house.json 을 읽어 방·문·가구의 절대 좌표를 계산하고 문제를 모은다."""

    def __init__(self, house):
        self.h = house
        self.wall = house.get("wall", 100)
        self.rooms = {}
        self.issues = []
        self.ops = []
        self.items = []
        self.geo = {}
        for r in house.get("rooms", []):
            if r.get("id") in self.rooms:
                self.add("error", "room_dup", "방 id 가 겹친다: {}".format(r.get("id")))
            self.rooms[r["id"]] = r
        for op in house.get("openings", []):
            res = self._opening(op)
            if res:
                self.ops.append(res)
        ids = set()
        for it in house.get("items", []):
            if it.get("id") in ids:
                self.add("error", "item_dup", "가구 id 가 겹친다: {}".format(it.get("id")))
            ids.add(it.get("id"))
            g = self._item(it)
            if g:
                self.items.append(it)
                self.geo[it["id"]] = g

    def add(self, level, code, msg, ids=()):
        self.issues.append({"level": level, "code": code, "msg": msg, "ids": [i for i in ids if i]})

    def rname(self, rid):
        r = self.rooms.get(rid)
        return "{}({})".format(r.get("name") or KIND_KO.get(r.get("kind"), rid), rid) if r else str(rid)

    def iname(self, it):
        return "{}({})".format(label_of(it), it["id"])

    # -- 문·창
    def _opening(self, op):
        oid = op.get("id", "?")
        R = self.rooms.get(op.get("room"))
        wall = op.get("wall")
        if not R or wall not in OPP:
            self.add("error", "opening_bad", "{}: room/wall 이 잘못됐다".format(oid), [oid])
            return None
        x0, y0, x1, y1 = rr(R)
        if wall in "ns":
            axis, start, end, line = "x", x0, x1, (y0 if wall == "n" else y1)
        else:
            axis, start, end, line = "y", y0, y1, (x0 if wall == "w" else x1)
        width = op.get("width", 900)
        off = op.get("offset", 0)
        if off == "center":
            off = (end - start - width) / 2
        a, b = start + off, start + off + width
        out = -1 if wall in "nw" else 1
        typ = op.get("type", "door")
        res = dict(op=op, id=oid, type=typ, room=R["id"], wall=wall, axis=axis, a=a, b=b,
                   line=line, out=out, width=width)
        if a < start - 1 or b > end + 1:
            self.add("error", "opening_span", "{}: {} {} 길이({}mm)를 벗어난다".format(
                oid, self.rname(R["id"]), SIDE_KO[wall] + " 벽", fmt(end - start)), [oid])
        if typ == "window":
            res["sill"] = op.get("sill", 900)
            return res
        to = op.get("to")
        if to == "outside":
            res.update(to="outside", gap=self.wall, other_line=line + out * self.wall)
        else:
            O = self.rooms.get(to)
            if not O:
                self.add("error", "opening_to", "{}: 반대편 방 '{}' 이 없다".format(oid, to), [oid])
                return None
            ox0, oy0, ox1, oy1 = rr(O)
            oline = {"n": oy0, "s": oy1, "w": ox0, "e": ox1}[OPP[wall]]
            gap = (oline - line) * out
            ospan = (ox0, ox1) if axis == "x" else (oy0, oy1)
            if not (20 <= gap <= 400) or ospan[0] > a + 1 or ospan[1] < b - 1:
                self.add("error", "opening_wall",
                         "{}: {} 와 {} 사이 벽에 있지 않다(두 방의 마주 보는 벽이 문 폭만큼 겹쳐야 한다)".format(
                             oid, self.rname(R["id"]), self.rname(to)), [oid])
                return None
            res.update(to=to, gap=gap, other_line=oline)
        if typ == "door":
            swing = op.get("swing", "in")
            hinge = op.get("hinge", "start")
            hp, other = (a, b) if hinge == "start" else (b, a)
            if swing == "in":
                sline, sdir, sroom = line, -out, R["id"]
            else:
                sline, sdir, sroom = res["other_line"], out, res["to"]
            lo, hi = sorted((hp, other))
            p0, p1 = sorted((sline, sline + sdir * width))
            if axis == "x":
                quad, hpt = (lo, p0, hi, p1), (hp, sline)
                otip, ctip = (hp, sline + sdir * width), (other, sline)
            else:
                quad, hpt = (p0, lo, p1, hi), (sline, hp)
                otip, ctip = (sline + sdir * width, hp), (sline, other)
            res.update(swing=swing, swing_room=sroom, quad=quad, hinge_pt=hpt,
                       open_tip=otip, closed_tip=ctip)
        return res

    def carve(self, o):
        """문·개구부가 벽을 뚫는 사각형."""
        l0, l1 = sorted((o["line"], o["other_line"]))
        return (o["a"], l0, o["b"], l1) if o["axis"] == "x" else (l0, o["a"], l1, o["b"])

    def approaches(self, o):
        """문 양쪽(방 안쪽)에 비워 둘 사각형 [(room_id, rect)]."""
        out = []
        sides = [(o["room"], o["line"], -o["out"])]
        if o.get("to") not in (None, "outside"):
            sides.append((o["to"], o["other_line"], o["out"]))
        for rid, line, d in sides:
            p0, p1 = sorted((line, line + d * APPROACH))
            rect = (o["a"], p0, o["b"], p1) if o["axis"] == "x" else (p0, o["a"], p1, o["b"])
            out.append((rid, rect))
        return out

    # -- 가구
    def _item(self, it):
        iid = it.get("id", "?")
        R = self.rooms.get(it.get("room"))
        size = it.get("size") or {}
        if not R:
            self.add("error", "item_room", "{}: 방 '{}' 이 없다".format(iid, it.get("room")), [iid])
            return None
        if not (size.get("w", 0) > 0 and size.get("d", 0) > 0):
            self.add("error", "item_size", "{}: size.w/size.d 가 없다".format(iid), [iid])
            return None
        w, d = size["w"], size["d"]
        p = it.get("place") or {}
        x0, y0, x1, y1 = rr(R)
        wall = p.get("wall")
        if wall is not None and wall not in OPP:
            self.add("error", "item_place", "{}: place.wall 은 n/s/w/e 중 하나".format(iid), [iid])
            return None
        facing = OPP[wall] if wall else p.get("facing", "s")
        if facing not in OPP:
            self.add("error", "item_place", "{}: place.facing 은 n/s/w/e 중 하나".format(iid), [iid])
            return None
        fw, fd = (w, d) if facing in "ns" else (d, w)
        if wall:
            gap = p.get("gap", 0)
            along = (x1 - x0) if wall in "ns" else (y1 - y0)
            span = fw if wall in "ns" else fd
            if "offset_end" in p:
                off = along - span - p["offset_end"]
            else:
                off = p.get("offset", 0)
                if off == "center":
                    off = (along - span) / 2
            if wall == "n":
                X, Y = x0 + off, y0 + gap
            elif wall == "s":
                X, Y = x0 + off, y1 - gap - fd
            elif wall == "w":
                X, Y = x0 + gap, y0 + off
            else:
                X, Y = x1 - gap - fw, y0 + off
        else:
            X, Y = x0 + p.get("x", 0), y0 + p.get("y", 0)
        return dict(rect=(X, Y, X + fw, Y + fd), facing=facing, h=size.get("h", 0), z=it.get("z", 0))


def label_of(it):
    return it.get("label") or CAT.get(it.get("category"), CAT["other"])["label"]


def is_obstacle(it):
    if it.get("on") or it.get("with"):
        return False
    if CAT.get(it.get("category"), {}).get("floor"):
        return False
    return it.get("z", 0) < WALL_MOUNT_Z


def side_axis(rect, side):
    """사각형의 한 변: (변을 따라가는 축, 시작, 끝, 변 좌표, 바깥 방향 부호)."""
    x0, y0, x1, y1 = rect
    return {"s": ("x", x0, x1, y1, 1), "n": ("x", x0, x1, y0, -1),
            "e": ("y", y0, y1, x1, 1), "w": ("y", y0, y1, x0, -1)}[side]


def depth_profile(room_rect, rect, side, obstacles, span=None, step=50):
    """rect 의 side 변에서 바깥으로 막힘 없이 비어 있는 깊이를 변을 따라 step 마다 잰다.
    obstacles: [(rect, 이름)]. 반환 [(위치, 깊이, 막는 것)]."""
    axis, a0, a1, edge, sign = side_axis(rect, side)
    s0, s1 = span if span else (a0, a1)
    rx0, ry0, rx1, ry1 = room_rect
    if axis == "x":
        bound = (ry1 - edge) if sign > 0 else (edge - ry0)
    else:
        bound = (rx1 - edge) if sign > 0 else (edge - rx0)
    out = []
    t = s0 + step / 2.0
    while t < s1:
        dmin, who = max(bound, 0), "벽"
        for o, name in obstacles:
            ox0, oy0, ox1, oy1 = o
            if axis == "x":
                if not (ox0 < t < ox1):
                    continue
                near, far = (oy0, oy1) if sign > 0 else (-oy1, -oy0)
            else:
                if not (oy0 < t < oy1):
                    continue
                near, far = (ox0, ox1) if sign > 0 else (-ox1, -ox0)
            e = edge * sign
            if far <= e + 1:
                continue
            dist = max(near - e, 0)
            if dist < dmin:
                dmin, who = dist, name
        out.append((t, dmin, who))
        t += step
    return out


def zone_depth(samples, mode, spot):
    """full: 변 전체에서 가장 얕은 깊이. spot: 폭 spot 짜리 자리 중 가장 깊은 자리의 깊이."""
    if not samples:
        return 0, "벽"
    if mode == "full" or spot <= 0:
        d, who = min(((s[1], s[2]) for s in samples), key=lambda x: x[0])
        return d, who
    n = max(1, int(math.ceil(spot / 50.0)))
    if n >= len(samples):
        d, who = min(((s[1], s[2]) for s in samples), key=lambda x: x[0])
        return d, who
    best, bwho = -1, "벽"
    for i in range(len(samples) - n + 1):
        win = samples[i:i + n]
        d, who = min(((s[1], s[2]) for s in win), key=lambda x: x[0])
        if d > best:
            best, bwho = d, who
    return best, bwho


def zones_for(it, g):
    """품목이 요구하는 빈 자리 목록."""
    if it.get("on") or it.get("with"):
        return []
    cat = CAT.get(it.get("category"), CAT["other"])
    cl = it.get("clearance") or {}
    f = g["facing"]
    x0, y0, x1, y1 = g["rect"]
    zs = []
    if "sides" in cat or "side" in cl:
        mn, rec = cl.get("side", cat.get("sides", (500, 650)))
        longs = ("w", "e") if f in "ns" else ("n", "s")
        span = {"s": (y0 + 600, y1), "n": (y0, y1 - 600), "e": (x0 + 600, x1), "w": (x0, x1 - 600)}[f]
        for s in longs:
            zs.append(dict(side=s, min=mn, rec=rec, mode="spot", spot=600, span=span,
                           kind="bed_side", label="{} 옆".format(SIDE_KO[s])))
    elif "seats" in cat or "seat" in cl:
        mn, rec = cl.get("seat", cat.get("seats", (750, 900)))
        sides = it.get("seat_sides") or (("n", "s") if (x1 - x0) >= (y1 - y0) else ("w", "e"))
        for s in sides:
            zs.append(dict(side=s, min=mn, rec=rec, mode="full", spot=0, span=None,
                           kind="seat", label="{} 의자 자리".format(SIDE_KO[s])))
    elif "front" in cat or "front" in cl:
        mn, rec = cl.get("front", cat.get("front"))
        if it.get("category") == "wardrobe" and it.get("door") == "sliding" and "front" not in cl:
            mn, rec = 500, 600
        spot = cat.get("spot", 0)
        zs.append(dict(side=f, min=mn, rec=rec, mode="spot" if spot else "full", spot=spot, span=None,
                       kind="front", label="앞"))
    return zs


def zone_rect(g, z, depth):
    """빈 자리를 사각형으로(그림·동선 검사용)."""
    axis, a0, a1, edge, sign = side_axis(g["rect"], z["side"])
    s0, s1 = z["span"] if z.get("span") else (a0, a1)
    p0, p1 = sorted((edge, edge + sign * depth))
    return (s0, p0, s1, p1) if axis == "x" else (p0, s0, p1, s1)


# ----------------------------------------------------------------------------- 동선 격자

class Grid:
    def __init__(self, ctx):
        self.ctx = ctx
        xs, ys = [], []
        for r in ctx.rooms.values():
            x0, y0, x1, y1 = rr(r)
            xs += [x0, x1]
            ys += [y0, y1]
        m = 1800
        self.ox = (math.floor((min(xs) - m) / CELL)) * CELL
        self.oy = (math.floor((min(ys) - m) / CELL)) * CELL
        self.nx = int(math.ceil((max(xs) + m - self.ox) / CELL))
        self.ny = int(math.ceil((max(ys) + m - self.oy) / CELL))
        N = self.nx * self.ny
        self.free = bytearray(N)
        self.carved = bytearray(N)
        self.start = bytearray(N)
        self.obst = bytearray(N)
        self.rid = [None] * N
        for r in ctx.rooms.values():
            for i in self.cells(rr(r)):
                self.free[i] = 1
                self.rid[i] = r["id"]
        for o in ctx.ops:
            if o["type"] == "window":
                continue
            c = ctx.carve(o)
            for i in self.cells(c):
                self.free[i] = 1
                self.carved[i] = 1
            if o.get("to") == "outside":
                ln = o["other_line"]
                p0, p1 = sorted((ln, ln + o["out"] * 1000))
                land = (o["a"] - 600, p0, o["b"] + 600, p1) if o["axis"] == "x" else (p0, o["a"] - 600, p1, o["b"] + 600)
                for i in self.cells(land):
                    self.free[i] = 1
                    self.carved[i] = 1
                    self.start[i] = 1
        for it in ctx.items:
            if is_obstacle(it):
                for i in self.cells(ctx.geo[it["id"]]["rect"]):
                    self.obst[i] = 1
        self.reach, self.dist, self.blocked = {}, {}, {}
        for k in PATH_KS:
            self.reach[k], self.dist[k], self.blocked[k] = self._bfs(k)

    def cells(self, rect):
        x0, y0, x1, y1 = rect
        i0 = max(0, int(math.ceil((x0 - self.ox) / CELL - 0.5)))
        i1 = min(self.nx - 1, int(math.floor((x1 - self.ox) / CELL - 0.5 - 1e-9)))
        j0 = max(0, int(math.ceil((y0 - self.oy) / CELL - 0.5)))
        j1 = min(self.ny - 1, int(math.floor((y1 - self.oy) / CELL - 0.5 - 1e-9)))
        for j in range(j0, j1 + 1):
            base = j * self.nx
            for i in range(i0, i1 + 1):
                yield base + i

    def _dilate(self, mask, k):
        nx, ny = self.nx, self.ny
        W = nx + 1
        P = [0] * ((ny + 1) * W)
        for j in range(ny):
            row = 0
            base, prev, off = (j + 1) * W, j * W, j * nx
            for i in range(nx):
                row += mask[off + i]
                P[base + i + 1] = P[prev + i + 1] + row
        out = bytearray(nx * ny)
        for j in range(ny):
            j0, j1 = max(0, j - k), min(ny, j + k + 1)
            for i in range(nx):
                i0, i1 = max(0, i - k), min(nx, i + k + 1)
                if P[j1 * W + i1] - P[j0 * W + i1] - P[j1 * W + i0] + P[j0 * W + i0]:
                    out[j * nx + i] = 1
        return out

    def _bfs(self, k):
        N = self.nx * self.ny
        near_door = self._dilate(self.carved, k + 1)
        src = bytearray(N)
        for i in range(N):
            if self.obst[i] or (not self.free[i] and not near_door[i]):
                src[i] = 1
        dil = self._dilate(src, k)
        blocked = bytearray(N)
        for i in range(N):
            if dil[i] or self.obst[i] or not self.free[i]:
                blocked[i] = 1
        seen = bytearray(N)
        dist = [-1] * N
        q = deque()
        for i in range(N):
            if self.start[i] and not blocked[i]:
                seen[i] = 1
                dist[i] = 0
                q.append(i)
        nx = self.nx
        while q:
            i = q.popleft()
            x = i % nx
            for n in ((i - 1) if x > 0 else -1, (i + 1) if x < nx - 1 else -1, i - nx, i + nx):
                if 0 <= n < N and not seen[n] and not blocked[n]:
                    seen[n] = 1
                    dist[n] = dist[i] + 1
                    q.append(n)
        return seen, dist, blocked

    def reachable(self, rect, k):
        r = self.reach[k]
        return any(r[i] for i in self.cells(rect))

    def chokes(self):
        """병목 찾기. 넓은 길(k1)이 들어갈 만한 구역인데 좁은 길(k0)을 지나야만 닿는 곳이 병목 너머다.
        벽 옆 띠나 침대 옆 틈처럼 원래 좁은 곳은 넓은 길이 들어갈 자리가 아니라서 걸리지 않는다.
        반환: 구역마다 (병목 출구 좌표 (x, y), 출구가 있는 방 id, 그 구역이 걸친 방 id 목록).
        출구는 그 구역에서 현관에 가장 가까운 칸이다."""
        k0, k1 = PATH_KS
        d0, r1, b1 = self.dist[k0], self.reach[k1], self.blocked[k1]
        nx, N = self.nx, self.nx * self.ny
        beyond = bytearray(N)
        for i in range(N):
            if d0[i] >= 0 and not r1[i] and not b1[i]:
                beyond[i] = 1
        seen = bytearray(N)
        out = []
        for s0 in range(N):
            if not beyond[s0] or seen[s0]:
                continue
            seen[s0] = 1
            q = deque([s0])
            best, rooms = s0, []
            while q:
                i = q.popleft()
                if d0[i] < d0[best]:
                    best = i
                rid = self.rid[i]
                if rid and rid not in rooms:
                    rooms.append(rid)
                x = i % nx
                for n in ((i - 1) if x > 0 else -1, (i + 1) if x < nx - 1 else -1, i - nx, i + nx):
                    if 0 <= n < N and beyond[n] and not seen[n]:
                        seen[n] = 1
                        q.append(n)
            out.append(((self.ox + (best % nx + 0.5) * CELL, self.oy + (best // nx + 0.5) * CELL), self.rid[best], rooms))
        return out


# ----------------------------------------------------------------------------- 검사

def check(house):
    ctx = Ctx(house)
    H = house
    htype = H.get("type", "apartment")
    rooms = list(ctx.rooms.values())

    # 방끼리
    for i in range(len(rooms)):
        for j in range(i + 1, len(rooms)):
            a, b = rr(rooms[i]), rr(rooms[j])
            if inter(a, b):
                ctx.add("error", "room_overlap", "{} 와 {} 가 겹친다".format(
                    ctx.rname(rooms[i]["id"]), ctx.rname(rooms[j]["id"])))
                continue
            gx = max(b[0] - a[2], a[0] - b[2])
            gy = max(b[1] - a[3], a[1] - b[3])
            if max(gx, gy) < 50 and min(gx, gy) < 0:
                ctx.add("error", "room_nowall", "{} 와 {} 사이에 벽 두께가 없다(최소 50mm 떨어뜨린다)".format(
                    ctx.rname(rooms[i]["id"]), ctx.rname(rooms[j]["id"])))

    entries = [r for r in rooms if r.get("kind") == "entrance"]
    if not entries and htype != "room":
        ctx.add("error", "no_entrance", "현관(kind=entrance)이 없다")
    if not any(o.get("to") == "outside" and o["type"] != "window" for o in ctx.ops):
        ctx.add("error", "no_front_door", "바깥으로 나가는 문(to=outside)이 없다 — 동선 검사를 할 수 없다")

    # 문 종류
    by_room = {}
    for o in ctx.ops:
        if o["type"] == "window":
            continue
        for rid in (o["room"], o.get("to")):
            by_room.setdefault(rid, []).append(o)
    for r in rooms:
        ops = by_room.get(r["id"], [])
        kinds = set(o["type"] for o in ops)
        if r.get("kind") == "bathroom" and not (kinds & {"door", "sliding"}):
            ctx.add("error", "bath_nodoor", "{} 에 문이 없다(트인 개구부만 있다)".format(ctx.rname(r["id"])))
        if r.get("kind") == "bedroom" and htype == "apartment" and ops and not (kinds & {"door", "sliding"}):
            ctx.add("warning", "bed_nodoor", "{} 에 문이 없다".format(ctx.rname(r["id"])))
    for o in ctx.ops:
        if o["type"] not in ("door", "sliding"):
            continue
        kinds = {ctx.rooms[o["room"]].get("kind")}
        if o.get("to") in ctx.rooms:
            kinds.add(ctx.rooms[o["to"]].get("kind"))
        w = o["width"]
        if o.get("to") == "outside" and w < 850:
            ctx.add("warning", "door_narrow", "{}({}) 폭 {}mm — 가구 반입에 850mm 이상이 안전하다".format(
                "출입문" if htype == "room" else "현관문", o["id"], fmt(w)), [o["id"]])
        elif "bathroom" in kinds and w < 650:
            ctx.add("warning", "door_narrow", "화장실 문({}) 폭 {}mm (보통 700~800)".format(o["id"], fmt(w)), [o["id"]])
        elif "bedroom" in kinds and w < 750:
            ctx.add("warning", "door_narrow", "방문({}) 폭 {}mm — 침대·옷장 반입이 빠듯하다(보통 800~900)".format(o["id"], fmt(w)), [o["id"]])

    obstacles = [(it, ctx.geo[it["id"]]) for it in ctx.items if is_obstacle(it)]

    # 가구 하나씩
    for it in ctx.items:
        g = ctx.geo[it["id"]]
        R = ctx.rooms[it["room"]]
        Rr = rr(R)
        nm = ctx.iname(it)
        if not inside(g["rect"], Rr):
            ctx.add("error", "item_outside", "{} 가 {} 밖으로 나간다".format(nm, ctx.rname(R["id"])), [it["id"]])
        # 실측
        if it.get("placeholder"):
            ctx.add("warning", "placeholder", "{}: 제품 미정 — 자리만 잡아 둔 가상 크기다".format(nm), [it["id"]])
        else:
            prod = it.get("product") or {}
            src = prod.get("dims_source") or ("user" if it.get("owned") else None)
            if not it.get("owned") and not prod.get("url"):
                ctx.add("error", "no_product", "{}: 제품 링크(product.url)가 없다".format(nm), [it["id"]])
            if src not in DIMS_SOURCE or prod.get("verified") is False:
                ctx.add("error", "dims_unverified", "{}: 실측 미확인 — 실측을 확인하기 전에는 배치하지 않는다".format(nm), [it["id"]])
            elif src in WEAK_SOURCES:
                ctx.add("warning", "dims_weak", "{}: 실측 근거가 약하다({}) — 상세 이미지·Q&A 로 확인하면 좋다".format(
                    nm, DIMS_SOURCE[src]), [it["id"]])
        # 올려 둔 것
        if it.get("on"):
            parent = ctx.geo.get(it["on"])
            if not parent:
                ctx.add("error", "on_missing", "{}: 올려 둘 가구 '{}' 가 없다".format(nm, it["on"]), [it["id"]])
            elif not inside(g["rect"], parent["rect"], tol=50):
                ctx.add("warning", "on_overhang", "{}: {} 밖으로 삐져나온다".format(nm, it["on"]), [it["id"]])
        # 벽에 붙이는 품목
        cat = CAT.get(it.get("category"), CAT["other"])
        if cat.get("wall") and is_obstacle(it):
            back = OPP[g["facing"]]
            axis, a0, a1, edge, sign = side_axis(g["rect"], back)
            if axis == "x":
                dist = (Rr[3] - edge) if sign > 0 else (edge - Rr[1])
            else:
                dist = (Rr[2] - edge) if sign > 0 else (edge - Rr[0])
            if dist > 100:
                ctx.add("warning", "off_wall", "{}: 등을 벽에 붙이는 품목인데 벽에서 {}mm 떨어져 있다(앞이 {} 을 향한다)".format(
                    nm, fmt(dist), SIDE_KO[g["facing"]]), [it["id"]])

    # 겹침
    for i in range(len(obstacles)):
        for j in range(i + 1, len(obstacles)):
            a, ga = obstacles[i]
            b, gb = obstacles[j]
            c = inter(ga["rect"], gb["rect"])
            if c:
                ctx.add("error", "overlap", "{} 와 {} 가 겹친다({}×{}mm)".format(
                    ctx.iname(a), ctx.iname(b), fmt(c[2] - c[0]), fmt(c[3] - c[1])), [a["id"], b["id"]])

    # 문
    for o in ctx.ops:
        if o["type"] == "window":
            for it, g in obstacles:
                if it["room"] != o["room"] or g["h"] <= o["sill"] + 100:
                    continue
                band_lo, band_hi = sorted((o["line"], o["line"] - o["out"] * WINDOW_BAND))
                band = (o["a"], band_lo, o["b"], band_hi) if o["axis"] == "x" else (band_lo, o["a"], band_hi, o["b"])
                if inter(g["rect"], band):
                    ctx.add("warning", "blocks_window", "{} (높이 {}) 가 창 {}(턱 {}) 을 가린다".format(
                        ctx.iname(it), fmt(g["h"]), o["id"], fmt(o["sill"])), [it["id"], o["id"]])
            continue
        if o["type"] == "door" and o.get("swing_room") not in (None, "outside"):
            for it, g in obstacles:
                if hits_quarter(g["rect"], o["hinge_pt"], o["quad"], o["width"]):
                    ctx.add("error", "blocks_swing", "문 {} 가 다 열리지 않는다 — {} 에 걸린다".format(
                        o["id"], ctx.iname(it)), [o["id"], it["id"]])
        if o["type"] == "opening" and o["width"] >= 1200:
            continue  # 넓게 트인 곳은 문 앞 검사 대신 동선 검사가 본다
        for rid, rect in ctx.approaches(o):
            for it, g in obstacles:
                if it["room"] == rid and inter(g["rect"], rect):
                    ctx.add("warning", "blocks_approach", "{} 가 문 {} 앞 {}mm 안에 있다 — 드나들 때 걸린다".format(
                        ctx.iname(it), o["id"], APPROACH), [it["id"], o["id"]])

    # 빈 자리(사용성)
    zone_results = {}
    for it in ctx.items:
        g = ctx.geo[it["id"]]
        zs = zones_for(it, g)
        if not zs:
            continue
        Rr = rr(ctx.rooms[it["room"]])
        obs = [(gg["rect"], ctx.iname(o)) for o, gg in obstacles
               if o["id"] != it["id"] and o.get("room") == it["room"]]
        res = []
        for z in zs:
            samples = depth_profile(Rr, g["rect"], z["side"], obs, span=z.get("span"))
            d, who = zone_depth(samples, z["mode"], z.get("spot", 0))
            res.append(dict(z, depth=d, who=who))
        zone_results[it["id"]] = res
        nm = ctx.iname(it)
        if res[0]["kind"] == "bed_side":
            best = max(res, key=lambda r: r["depth"])
            worst = min(res, key=lambda r: r["depth"])
            bw = (g["rect"][2] - g["rect"][0]) if g["facing"] in "ns" else (g["rect"][3] - g["rect"][1])
            if best["depth"] < best["min"]:
                ctx.add("error", "bed_access", "{}: 올라갈 자리가 없다 — 양옆 여유 {}, {}mm (한쪽은 {}mm 이상)".format(
                    nm, fmt(res[0]["depth"]), fmt(res[1]["depth"]), best["min"]), [it["id"]])
            elif best["depth"] < best["rec"]:
                ctx.add("warning", "bed_access", "{}: 옆 여유가 {}mm 뿐이다(권장 {}mm)".format(
                    nm, fmt(best["depth"]), best["rec"]), [it["id"]])
            if bw >= 1300 and worst["depth"] < worst["min"] and best["depth"] >= best["min"]:
                ctx.add("warning", "bed_one_side", "{}: 2인용인데 {} 여유가 {}mm — 한 사람은 침대를 넘어 다녀야 한다".format(
                    nm, worst["label"], fmt(worst["depth"])), [it["id"]])
        else:
            for r in res:
                where = "{} 여유 {}mm".format(r["label"], fmt(r["depth"]))
                blocker = " (막는 것: {})".format(r["who"]) if r["depth"] < r["rec"] else ""
                if r["depth"] < r["min"]:
                    ctx.add("error", "clearance", "{}: {} — 최소 {}mm 필요{}".format(nm, where, r["min"], blocker), [it["id"]])
                elif r["depth"] < r["rec"]:
                    ctx.add("warning", "clearance", "{}: {} — 권장 {}mm{}".format(nm, where, r["rec"], blocker), [it["id"]])

    # 동선
    grid = None
    has_front = any(o.get("to") == "outside" and o["type"] != "window" for o in ctx.ops)
    if has_front and rooms:
        grid = Grid(ctx)
        k0, k1 = PATH_KS
        for r in rooms:
            if not grid.reachable(rr(r), k0):
                ctx.add("error", "room_unreachable", "{} 에 현관에서 걸어 들어갈 수 없다(문이 없거나 통로가 막혔다)".format(
                    ctx.rname(r["id"])))
        blocked_front = set(i["ids"][0] for i in ctx.issues
                            if i["level"] == "error" and i["code"] in ("clearance", "bed_access") and i["ids"])
        for it in ctx.items:
            res = zone_results.get(it["id"])
            if not res or it["id"] in blocked_front:
                continue
            g = ctx.geo[it["id"]]
            rects = [zone_rect(g, z, max(z["rec"], 300)) for z in res]
            if not any(grid.reachable(rc, k0) for rc in rects):
                ctx.add("error", "unreachable", "{}: 쓰는 자리까지 걸어갈 길이 없다(약 550mm 통로가 이어지지 않는다)".format(
                    ctx.iname(it)), [it["id"]])
        for (px, py), at, rids in grid.chokes():
            near, nd = None, 900
            for it, g in obstacles:
                x0, y0, x1, y1 = g["rect"]
                d = math.hypot(max(x0 - px, 0, px - x1), max(y0 - py, 0, py - y1))
                if d < nd:
                    near, nd = it, d
            rest = [r for r in rids if r != at]
            ctx.add("warning", "narrow_path", "{} 에서 통로가 약 550~750mm 로 좁아진다{} — 그 너머{}는 이 좁은 길로만 닿는다".format(
                ctx.rname(at) if at else "방 사이", " (가까운 가구: {})".format(ctx.iname(near)) if near else "",
                "({})".format("·".join(ctx.rname(r) for r in rest)) if rest else ""),
                [near["id"]] if near else [])

    order = {"error": 0, "warning": 1, "info": 2}
    ctx.issues.sort(key=lambda x: order.get(x["level"], 3))
    return ctx, zone_results


LEVEL_KO = {"error": "오류", "warning": "주의", "info": "정보"}


def cmd_check(args):
    house = load(args.house)
    ctx, _ = check(house)
    errs = [i for i in ctx.issues if i["level"] == "error"]
    warns = [i for i in ctx.issues if i["level"] == "warning"]
    if args.json:
        print(json.dumps({"errors": len(errs), "warnings": len(warns), "issues": ctx.issues}, ensure_ascii=False, indent=2))
    else:
        for i in ctx.issues:
            print("[{}] {}".format(LEVEL_KO[i["level"]], i["msg"]))
        print("요약: 오류 {} · 주의 {} · 방 {} · 가구 {}".format(len(errs), len(warns), len(ctx.rooms), len(ctx.items)))
    return 1 if errs else 0


# ----------------------------------------------------------------------------- 벽별 빈 구간

def subtract(intervals, lo, hi):
    out = []
    for a, b in intervals:
        if hi <= a or lo >= b:
            out.append((a, b))
            continue
        if lo > a:
            out.append((a, lo))
        if hi < b:
            out.append((hi, b))
    return out


def cmd_walls(args):
    house = load(args.house)
    ctx = Ctx(house)
    R = ctx.rooms.get(args.room)
    if not R:
        print("방 '{}' 이 없다. 있는 방: {}".format(args.room, ", ".join(ctx.rooms)))
        return 2
    Rr = rr(R)
    W, D = Rr[2] - Rr[0], Rr[3] - Rr[1]
    band = args.depth
    print("{} — 실내 {}×{}mm · {}".format(ctx.rname(R["id"]), fmt(W), fmt(D), area_txt(W, D)))
    print("오프셋은 각 벽의 시작점에서 잰다: 위·아래 벽은 왼쪽 끝, 왼쪽·오른쪽 벽은 위쪽 끝. 벽에서 {}mm 깊이 안을 본다.".format(band))
    for wall in ("n", "s", "w", "e"):
        axis, a0, a1, edge, sign = side_axis(Rr, wall)
        inward = -sign
        p0, p1 = sorted((edge, edge + inward * band))
        def to_band(lo, hi):
            return (lo, p0, hi, p1) if axis == "x" else (p0, lo, p1, hi)
        length = a1 - a0
        free = [(0, length)]
        notes = []
        blocks = []
        for o in ctx.ops:
            on_this = (o["room"] == R["id"] and o["wall"] == wall) or (o.get("to") == R["id"] and OPP[o["wall"]] == wall)
            if o["type"] == "window":
                if o["room"] == R["id"] and o["wall"] == wall:
                    notes.append("창 {}~{} (폭 {}, 턱 높이 {}) — 턱보다 높은 가구는 창을 가린다".format(
                        fmt(o["a"] - a0), fmt(o["b"] - a0), fmt(o["width"]), fmt(o["sill"])))
                continue
            rects = []
            if on_this:
                kind = {"door": "문", "sliding": "미닫이문", "opening": "개구부"}[o["type"]]
                extra = ""
                if o["type"] == "door":
                    extra = ", {}".format("이 방 쪽으로 열림" if o.get("swing_room") == R["id"] else "반대쪽으로 열림")
                notes.append("{} {} {}~{} (폭 {}{})".format(kind, o["id"], fmt(o["a"] - a0), fmt(o["b"] - a0), fmt(o["width"]), extra))
            if o["type"] == "door" and o.get("swing_room") == R["id"]:
                rects.append(("문 {} 열림 범위".format(o["id"]), o["quad"]))
            for rid, rc in ctx.approaches(o):
                if rid == R["id"]:
                    rects.append(("문 {} 앞".format(o["id"]), rc))
            for why, rc in rects:
                c = inter(rc, to_band(a0, a1))
                if c:
                    lo, hi = (c[0], c[2]) if axis == "x" else (c[1], c[3])
                    free = subtract(free, lo - a0, hi - a0)
                    blocks.append("{} {}~{}".format(why, fmt(lo - a0), fmt(hi - a0)))
        for it in ctx.items:
            if it["room"] != R["id"] or not is_obstacle(it):
                continue
            g = ctx.geo[it["id"]]
            c = inter(g["rect"], to_band(a0, a1))
            if c:
                lo, hi = (c[0], c[2]) if axis == "x" else (c[1], c[3])
                free = subtract(free, lo - a0, hi - a0)
                blocks.append("{} {}~{}".format(ctx.iname(it), fmt(lo - a0), fmt(hi - a0)))
        print("\n[{} 벽] 길이 {}".format(SIDE_KO[wall], fmt(length)))
        for n in notes:
            print("  - {}".format(n))
        for b in blocks:
            print("  - 막힘: {}".format(b))
        fr = [(a, b) for a, b in free if b - a >= 100]
        if fr:
            print("  - 빈 구간: " + ", ".join("{}~{} ({}mm)".format(fmt(a), fmt(b), fmt(b - a)) for a, b in fr))
        else:
            print("  - 빈 구간: 없음")
    return 0


# ----------------------------------------------------------------------------- 인벤토리

def price_of(it):
    p = (it.get("product") or {}).get("price")
    if p is None or it.get("owned") or it.get("placeholder"):
        return None
    return p * it.get("qty", 1)


def rating_txt(prod):
    r, n = prod.get("rating"), prod.get("review_count")
    if r is None and n is None:
        return ""
    out = "★{:.1f}".format(r) if r is not None else "★-"
    if n is not None:
        out += " ({})".format(fmt(n))
    return out


def reviewable(it):
    """리뷰 카드에 올릴 품목: 오늘의집 제품으로 정해진 것(보유·자리만 잡은 것은 뺀다)."""
    return not it.get("owned") and not it.get("placeholder") and (it.get("product") or {}).get("url")


def inventory_rows(house):
    ctx = Ctx(house)
    rows = {}
    n = 0
    for it in ctx.items:
        n += 1
        rows.setdefault(it["room"], []).append((n, it))
    return ctx, rows


def cmd_inventory(args):
    house = load(args.house)
    ctx, rows = inventory_rows(house)
    total, unknown, count = 0, 0, 0
    print("# {} 인벤토리\n".format(house.get("name", "우리집")))
    for rid, r in ctx.rooms.items():
        items = rows.get(rid, [])
        x0, y0, x1, y1 = rr(r)
        print("## {} — {}×{}mm · {}".format(ctx.rname(rid), fmt(x1 - x0), fmt(y1 - y0), area_txt(x1 - x0, y1 - y0)))
        if not items:
            print("\n(비어 있음)\n")
            continue
        print("\n| # | 품목 | 제품 | 옵션 | 실측 W×D×H (mm) | 실측 출처 | 평점(리뷰) | 수량 | 가격 |")
        print("|---|---|---|---|---|---|---|---|---|")
        sub = 0
        for n, it in items:
            prod = it.get("product") or {}
            s = it.get("size", {})
            dims = "{}×{}×{}".format(fmt(s.get("w", 0)), fmt(s.get("d", 0)), fmt(s.get("h", 0)))
            if it.get("owned"):
                name, src = it.get("name", "보유 가구"), "보유 · " + DIMS_SOURCE.get(prod.get("dims_source", "user"), "사용자 실측")
            elif it.get("placeholder"):
                name, src = "(제품 미정)", "가상 크기"
            else:
                nm = (it.get("name") or prod.get("title") or "제품").replace("|", "/")
                name = "[{}]({})".format(nm, prod["url"]) if prod.get("url") else nm
                src = DIMS_SOURCE.get(prod.get("dims_source"), "**미확인**")
            p = price_of(it)
            ptxt = "{}원".format(fmt(p)) if p is not None else ("-" if (it.get("owned") or it.get("placeholder")) else "미상")
            if p is not None:
                sub += p
            elif not it.get("owned") and not it.get("placeholder"):
                unknown += 1
            count += 1
            print("| {} | {} | {} | {} | {} | {} | {} | {} | {} |".format(
                n, label_of(it), name, (prod.get("option") or "").replace("|", "/"), dims, src,
                rating_txt(prod) or "-", it.get("qty", 1), ptxt))
        total += sub
        print("\n소계: {}원\n".format(fmt(sub)))
    budget = house.get("budget")
    line = "**합계: 품목 {}개 · {}원**".format(count, fmt(total))
    if unknown:
        line += " (가격 미상 {}개 제외)".format(unknown)
    if budget:
        line += " · 예산 {}원 대비 {}".format(fmt(budget), ("{}원 남음".format(fmt(budget - total)) if budget >= total else "{}원 초과".format(fmt(total - budget))))
    print(line)
    return 0


# ----------------------------------------------------------------------------- 평면 틀

DEFAULTS = {
    "oneroom": {"entrance": (1200, 1200), "bathroom": (1500, 2000), "kitchen": (2400, 1500)},
    "apartment": {"entrance": (1500, 1600), "bathroom": (1600, 2200), "kitchen": (2800, 2600), "living": (4000, 4500)},
}


def _rooms_by_kind(spec, typ, notes):
    by = {}
    for r in spec.get("rooms", []):
        k = r.get("kind")
        if k not in KIND_KO:
            raise SystemExit("알 수 없는 방 종류: {} (쓸 수 있는 것: {})".format(k, ", ".join(KIND_KO)))
        by.setdefault(k, []).append(dict(r))
    for k in ("entrance", "bathroom", "kitchen") + (("living",) if typ == "apartment" else ()):
        if k not in by:
            w, d = DEFAULTS[typ][k]
            by[k] = [dict(kind=k, w=w, d=d)]
            notes.append("{} 크기가 없어 {}×{}mm 로 가정했다".format(KIND_KO[k], fmt(w), fmt(d)))
    for k, lst in by.items():
        for r in lst:
            if not (r.get("w") and r.get("d")):
                w, d = DEFAULTS[typ].get(k, (3000, 3000))
                r["w"], r["d"] = w, d
                notes.append("{} 크기가 없어 {}×{}mm 로 가정했다".format(r.get("name") or KIND_KO[k], fmt(w), fmt(d)))
    if not by.get("bedroom"):
        raise SystemExit("침실(kind=bedroom)이 하나 이상 있어야 한다")
    return by


def _name(r, default):
    return r.get("name") or default


def shell(spec):
    typ = spec.get("type", "apartment")
    if typ not in TYPE_KO:
        raise SystemExit("type 은 room(방 한 칸) · oneroom(원룸형) · apartment(아파트형) 중 하나")
    wall = spec.get("wall", 100)
    notes = []
    if typ == "room":
        rooms, ops = _shell_room(spec, notes)
        source = "room"
    else:
        by = _rooms_by_kind(spec, typ, notes)
        beds = sorted(by["bedroom"], key=lambda r: r["w"] * r["d"], reverse=True)
        if typ == "oneroom" and len(beds) == 1 and not by.get("living"):
            rooms, ops = _shell_studio(beds[0], by, wall, notes)
            source = "studio"
        else:
            rooms, ops = _shell_rows(typ, beds, by, wall, spec.get("hall", 1200), notes)
            source = "rows"
    minx = min(r["rect"][0] for r in rooms)
    miny = min(r["rect"][1] for r in rooms)
    for r in rooms:
        r["rect"] = [int(round(r["rect"][0] - minx)), int(round(r["rect"][1] - miny)),
                     int(round(r["rect"][2])), int(round(r["rect"][3]))]
    for o in ops:
        if o["offset"] != "center":
            o["offset"] = int(round(o["offset"]))
        o["width"] = int(round(o["width"]))
    house = {
        "version": 1,
        "name": spec.get("name", "우리집"),
        "type": typ,
        "units": "mm",
        "wall": wall,
        "budget": spec.get("budget"),
        "household": spec.get("household"),
        "meta": {"source": "template:" + source, "notes": notes},
        "rooms": rooms,
        "openings": ops,
        "items": [],
    }
    if house["budget"] is None:
        del house["budget"]
    if house["household"] is None:
        del house["household"]
    return house


def _room(rid, kind, name, x, y, w, d):
    return {"id": rid, "kind": kind, "name": name, "rect": [x, y, w, d]}


def _shell_room(spec, notes):
    """방 한 칸(촬영 세트처럼 매번 바뀌는 방): 바깥으로 나가는 문 하나와 창.

    spec.door = {wall, offset, width, swing, hinge}, spec.windows = [{wall, offset|"center", width, sill}].
    주지 않으면 문은 아래쪽 벽 오른쪽 끝(안으로 열림), 창은 위쪽 벽 가운데에 둔다.
    """
    rs = spec.get("rooms", [])
    if len(rs) != 1:
        raise SystemExit("type=room 은 방을 하나만 받는다(지금 {}개)".format(len(rs)))
    r = rs[0]
    kind = r.get("kind", "bedroom")
    if kind not in KIND_KO:
        raise SystemExit("알 수 없는 방 종류: {} (쓸 수 있는 것: {})".format(kind, ", ".join(KIND_KO)))
    W, D = r.get("w"), r.get("d")
    if not (W and D):
        raise SystemExit("방 크기 w, d 를 mm 로 준다")
    rid = r.get("id", "room")
    rooms = [_room(rid, kind, _name(r, KIND_KO[kind]), 0, 0, W, D)]
    ds = dict(spec.get("door") or {})
    dwall = ds.get("wall", "s")
    if dwall not in OPP:
        raise SystemExit("door.wall 은 n/s/w/e 중 하나")
    span = W if dwall in "ns" else D
    dw = ds.get("width", 900 if span >= 1300 else span - 300)
    doff = ds.get("offset", span - dw - 150)
    ops = [dict(id="d_room", type="door", room=rid, wall=dwall, offset=doff, width=dw, to="outside",
                swing=ds.get("swing", "in"), hinge=ds.get("hinge", "end"))]
    if "door" not in spec:
        notes.append("문 자리를 받지 않아 아래쪽 벽 오른쪽 끝에 폭 {}mm 문을 두었다(방 안으로 열림)".format(fmt(dw)))
    wins = spec.get("windows")
    if wins is None:
        ww = max(900, int(W * 0.6 / 100) * 100)
        wins = [dict(wall="n", offset=(W - ww) / 2, width=ww)]
        notes.append("창 자리를 받지 않아 위쪽 벽 가운데에 폭 {}mm 창을 두었다".format(fmt(ww)))
    for i, w in enumerate(wins):
        ops.append(dict(id="w{}".format(i + 1), type="window", room=rid, wall=w.get("wall", "n"),
                        offset=w.get("offset", "center"), width=w["width"], sill=w.get("sill", 900)))
    return rooms, ops


def _shell_studio(bed, by, wall, notes):
    """원룸(방 1): 위에 방, 아래 줄에 [화장실 | 주방(복도 겸) | 현관]."""
    W, D = bed["w"], bed["d"]
    bath, ent = by["bathroom"][0], by["entrance"][0]
    kit = by["kitchen"][0]
    rooms = [_room("room", "bedroom", _name(bed, "방"), 0, 0, W, D)]
    y = D + wall
    kd = kit["d"]
    kw = kit["w"] if kit.get("_given") else W - bath["w"] - ent["w"] - 2 * wall
    stacked = False
    if not kit.get("_given") and kw < 1500 and W - bath["w"] - wall >= max(1500, ent["w"]):
        # 폭이 모자라면 [화장실 | 주방 복도] 아래에 현관을 둔다(좁은 원룸에 흔한 꼴)
        stacked = True
        kw = W - bath["w"] - wall
        notes.append("방 가로({})가 좁아 현관을 주방 복도 아래에 두었다".format(fmt(W)))
    elif kw < 1500:
        notes.append("방 가로({})가 좁아 주방 가로를 1500mm 로 잡았다 — 아래 줄이 방보다 {}mm 넓다".format(
            fmt(W), fmt(1500 - kw)))
        kw = 1500
    rooms.append(_room("bath1", "bathroom", _name(bath, "화장실"), 0, y, bath["w"], bath["d"]))
    kx = bath["w"] + wall
    rooms.append(_room("kitchen", "kitchen", _name(kit, "주방"), kx, y, kw, kd))
    if stacked:
        rooms.append(_room("entry", "entrance", _name(ent, "현관"), kx, y + kd + wall, ent["w"], ent["d"]))
    else:
        rooms.append(_room("entry", "entrance", _name(ent, "현관"), kx + kw + wall, y, ent["w"], ent["d"]))
    ops = []
    fw = 900 if ent["w"] >= 1100 else ent["w"] - 200
    ops.append(dict(id="front", type="door", room="entry", wall="s", offset=(ent["w"] - fw) / 2, width=fw,
                    to="outside", swing="out", hinge="start"))
    if stacked:
        ops.append(dict(id="o_entry", type="opening", room="entry", wall="n", offset=100,
                        width=max(min(ent["w"], kw) - 200, 600), to="kitchen"))
    else:
        ov = min(ent["d"], kd)
        ops.append(dict(id="o_entry", type="opening", room="entry", wall="w", offset=100, width=max(ov - 200, 600), to="kitchen"))
    ovx = min(kx + kw, W) - kx
    if ovx >= 800:
        ops.append(dict(id="o_kitchen", type="opening", room="kitchen", wall="n", offset=100, width=ovx - 200, to="room"))
    else:
        notes.append("주방이 방과 맞닿는 폭이 {}mm 뿐이라 트인 개구부를 만들지 못했다".format(fmt(ovx)))
    ovb = min(bath["d"], kd)
    if ovb >= 950:
        ops.append(dict(id="d_bath", type="door", room="bath1", wall="e", offset=100, width=750, to="kitchen",
                        swing="in", hinge="start"))
    else:
        ops.append(dict(id="d_bath", type="door", room="bath1", wall="n", offset=max((bath["w"] - 750) / 2, 0),
                        width=min(750, bath["w"] - 100), to="room", swing="in", hinge="start"))
    ww = max(900, int(W * 0.6 / 100) * 100)
    ops.append(dict(id="w_room", type="window", room="room", wall="n", offset=(W - ww) / 2, width=ww, sill=900))
    return rooms, ops


def _shell_rows(typ, beds, by, wall, hall, notes):
    """두 줄 + 가운데 복도. 위 줄(창 쪽)에 [침실 | 중심 공간 | 안방], 아래 줄에 [나머지 방·화장실·현관 | 주방 | 안방 쪽 화장실].
    중심 공간(아파트형=거실, 원룸형 투룸 이상=주방 겸 거실)은 복도 깊이만큼 아래로 이어져 동선의 중심이 된다."""
    rooms, ops = [], []
    named = []
    for i, b in enumerate(beds):
        default = ("안방" if (typ == "apartment" and len(beds) >= 2 and i == 0) else "침실{}".format(i + 1))
        named.append(dict(b, id="bed{}".format(i + 1), kind="bedroom", name=_name(b, default)))
    baths = [dict(b, id="bath{}".format(i + 1), kind="bathroom",
                  name=_name(b, "화장실" if len(by["bathroom"]) == 1 else ("공용 화장실" if i == 0 else "화장실{}".format(i + 1))))
             for i, b in enumerate(by["bathroom"])]
    ent = dict(by["entrance"][0], id="entry", kind="entrance", name=_name(by["entrance"][0], "현관"))
    kit = dict(by["kitchen"][0], id="kitchen", kind="kitchen", name=_name(by["kitchen"][0], "주방"))
    extras = []
    for k in ("dressroom", "utility"):
        for i, r in enumerate(by.get(k, [])):
            extras.append(dict(r, id="{}{}".format(k, i + 1), kind=k, name=_name(r, KIND_KO[k])))
    if typ == "apartment":
        lv = by["living"][0]
        core = dict(lv, id="living", kind="living", name=_name(lv, "거실"))
        anchor = kit
    else:
        core = dict(kit, id="kitchen", kind="kitchen", name=_name(kit, "주방 겸 거실"))
        if not kit.get("_given"):
            core["w"], core["d"] = 3000, 3000
            notes.append("주방 겸 거실 크기가 없어 3,000×3,000mm 로 가정했다")
        anchor = None
    s_right = [named[0]]
    s_left = [named[1]] if len(named) >= 2 else []
    n_left = [ent, baths[0]] + named[2:] + extras
    n_right = baths[1:]
    placed = {}
    x = 0
    s_rooms = s_left + [core] + s_right
    yb = max(r["d"] for r in s_rooms)
    for r in s_rooms:
        placed[r["id"]] = [x, yb - r["d"], r["w"], r["d"]]
        x += r["w"] + wall
    cx, cy, cw, cd = placed[core["id"]]
    placed[core["id"]][3] = cd + wall + hall
    notes.append("{} 은 복도 폭 {}mm 를 겸해 깊이가 {}mm 로 늘었다".format(core["name"], fmt(hall), fmt(cd + wall + hall)))
    hy = yb + wall
    ny = hy + hall + wall
    if anchor:
        placed[anchor["id"]] = [cx, ny, anchor["w"], anchor["d"]]
        xr = cx + anchor["w"] + wall
    else:
        xr = cx
    xl = cx - wall
    for r in n_right:
        placed[r["id"]] = [xr, ny, r["w"], r["d"]]
        xr += r["w"] + wall
    for r in n_left:
        xl -= r["w"]
        placed[r["id"]] = [xl, ny, r["w"], r["d"]]
        xl -= wall
    minx = min(p[0] for p in placed.values())
    maxx = max(p[0] + p[2] for p in placed.values())
    halls = []
    if cx - wall - minx >= 300:
        halls.append(dict(id="hallL", kind="hall", name="복도", rect=[minx, hy, cx - wall - minx, hall]))
    if maxx - (cx + cw + wall) >= 300:
        halls.append(dict(id="hallR", kind="hall", name="복도", rect=[cx + cw + wall, hy, maxx - (cx + cw + wall), hall]))
    allrooms = s_rooms + ([anchor] if anchor else []) + n_right + n_left
    for r in allrooms:
        rooms.append(_room(r["id"], r["kind"], r["name"], *placed[r["id"]]))
    for h in halls:
        rooms.append(_room(h["id"], "hall", h["name"], *h["rect"]))
        side = "e" if h["id"] == "hallL" else "w"
        ops.append(dict(id="o_" + h["id"], type="opening", room=h["id"], wall=side, offset=0, width=hall, to=core["id"]))

    def above(rx, rw):
        cands = [(core["id"], cx, cx + cw)]
        for h in halls:
            hx, _, hw, _ = h["rect"]
            cands.append((h["id"], hx, hx + hw))
        best = None
        for cid, a, b in cands:
            lo, hi = max(a, rx), min(b, rx + rw)
            if hi - lo > 0 and (best is None or hi - lo > best[2] - best[1]):
                best = (cid, lo, hi)
        return best

    def below(rx, rw):
        for h in halls:
            hx, _, hw, _ = h["rect"]
            lo, hi = max(hx, rx), min(hx + hw, rx + rw)
            if hi - lo >= 900:
                return h["id"], lo, hi
        return None

    for r in s_left + s_right:
        x0 = placed[r["id"]][0]
        tgt = below(x0, r["w"])
        if not tgt:
            notes.append("{} 아래에 복도가 없어 문을 만들지 못했다".format(r["name"]))
            continue
        hid, lo, hi = tgt
        dw = 900
        if r in s_left:
            off, hinge = (hi - x0) - dw - 150, "end"
        else:
            off, hinge = (lo - x0) + 150, "start"
        ops.append(dict(id="d_" + r["id"], type="door", room=r["id"], wall="s", offset=off, width=dw,
                        to=hid, swing="in", hinge=hinge))
    for r in ([anchor] if anchor else []) + n_right + n_left:
        x0 = placed[r["id"]][0]
        tgt = above(x0, r["w"])
        if not tgt:
            notes.append("{} 위로 이어질 공간이 없어 문을 만들지 못했다".format(r["name"]))
            continue
        cid, lo, hi = tgt
        span = hi - lo
        if r["kind"] in ("kitchen", "entrance"):
            if span < 800:
                notes.append("{} 이 위 공간과 맞닿는 폭이 {}mm 뿐이다".format(r["name"], fmt(span)))
            w = min(span - 200, 1200 if r["kind"] == "entrance" else span - 200)
            ops.append(dict(id="o_" + r["id"], type="opening", room=r["id"], wall="n",
                            offset=(lo - x0) + (span - w) / 2, width=max(w, 600), to=cid))
        else:
            dw = 750 if r["kind"] == "bathroom" else 900
            if span < dw + 200:
                notes.append("{} 의 문이 들어갈 폭이 {}mm 뿐이다".format(r["name"], fmt(span)))
            ops.append(dict(id="d_" + r["id"], type="door", room=r["id"], wall="n",
                            offset=(lo - x0) + max((span - dw) / 2, 0), width=dw, to=cid, swing="in", hinge="start"))
    ew = placed["entry"][2]
    fw = 900 if ew >= 1100 else ew - 200
    ops.append(dict(id="front", type="door", room="entry", wall="s", offset=(ew - fw) / 2, width=fw,
                    to="outside", swing="out", hinge="start"))
    for r in s_rooms:
        w = r["w"]
        if r is core and core["kind"] == "living":
            ww, sill = max(w - 600, 1200), 0
        elif r is core:
            ww, sill = 1200, 1000
        else:
            ww, sill = max(900, int(w * 0.6 / 100) * 100), 900
        ops.append(dict(id="w_" + r["id"], type="window", room=r["id"], wall="n", offset=(w - ww) / 2, width=ww, sill=sill))
    for r in named[2:] + ([anchor] if anchor else []):
        w = r["w"]
        ww, sill = (1200, 1000) if r["kind"] == "kitchen" else (max(900, int(w * 0.5 / 100) * 100), 900)
        ww = min(ww, w - 200)
        ops.append(dict(id="w_" + r["id"], type="window", room=r["id"], wall="s", offset=(w - ww) / 2, width=ww, sill=sill))
    return rooms, ops


def cmd_shell(args):
    spec = load(args.spec)
    for r in spec.get("rooms", []):
        if r.get("kind") == "kitchen" and r.get("w"):
            r["_given"] = True
    house = shell(spec)
    for r in house["rooms"]:
        r.pop("_given", None)
    save(args.out, house)
    ctx, _ = check(house)
    xs = [rr(r) for r in house["rooms"]]
    W = max(x[2] for x in xs) - min(x[0] for x in xs)
    D = max(x[3] for x in xs) - min(x[1] for x in xs)
    total = sum((x[2] - x[0]) * (x[3] - x[1]) for x in xs)
    print("{} ({}) → {}".format(house["name"], TYPE_KO[house["type"]], args.out))
    print("외곽 {}×{}mm · 실내 면적 합 {}".format(fmt(W), fmt(D), area_txt(total, 1)))
    for r in house["rooms"]:
        x, y, w, d = r["rect"]
        print("  {:<10} {:<8} x={:>6} y={:>6}  {}×{}".format(r["id"], r["name"], fmt(x), fmt(y), fmt(w), fmt(d)))
    for n in house["meta"]["notes"]:
        print("  * " + n)
    errs = [i for i in ctx.issues if i["level"] == "error"]
    for i in ctx.issues:
        print("[{}] {}".format(LEVEL_KO[i["level"]], i["msg"]))
    return 1 if errs else 0


# ----------------------------------------------------------------------------- 렌더

ZONE_KINDS = ("front", "bed_side", "seat")


def _esc(s):
    return _html.escape(str(s), quote=True)


def fetch_image(url, limit=3000000):
    """제품 사진을 data URI 로. 실패하면 None(원래 주소를 그대로 쓴다)."""
    import base64
    import urllib.request
    if not str(url).startswith("https://"):
        return None
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            ct = r.headers.get_content_type()
            if not ct.startswith("image/") or ct == "image/svg+xml":
                return None
            data = r.read(limit + 1)
    except Exception as e:  # 네트워크 실패는 렌더를 막지 않는다
        sys.stderr.write("사진을 못 받았다({}): {}\n".format(e.__class__.__name__, url))
        return None
    if len(data) > limit:
        return None
    return "data:{};base64,{}".format(ct, base64.b64encode(data).decode("ascii"))


# ----------------------------------------------------------------------------- 도면 기호

def _band(rect, side, depth):
    """사각형의 한 변에 붙은 띠."""
    x0, y0, x1, y1 = rect
    return {"n": (x0, y0, x1, y0 + depth), "s": (x0, y1 - depth, x1, y1),
            "w": (x0, y0, x0 + depth, y1), "e": (x1 - depth, y0, x1, y1)}[side]


def _inset(rect, d):
    x0, y0, x1, y1 = rect
    return (x0 + d, y0 + d, x1 - d, y1 - d)


def _split(rect, facing, n, gap):
    """가구 폭 방향(정면과 나란한 축)으로 n 등분."""
    x0, y0, x1, y1 = rect
    out = []
    if facing in "ns":
        w = (x1 - x0 - gap * (n - 1)) / float(n)
        for i in range(n):
            a = x0 + i * (w + gap)
            out.append((a, y0, a + w, y1))
    else:
        h = (y1 - y0 - gap * (n - 1)) / float(n)
        for i in range(n):
            a = y0 + i * (h + gap)
            out.append((x0, a, x1, a + h))
    return out


def _svg_rect(r, rx=0):
    x0, y0, x1, y1 = r
    if x1 - x0 < 20 or y1 - y0 < 20:
        return ""
    return '<rect class="sym" x="{:.0f}" y="{:.0f}" width="{:.0f}" height="{:.0f}" rx="{:.0f}"/>'.format(
        x0, y0, x1 - x0, y1 - y0, min(rx, (x1 - x0) / 2.0, (y1 - y0) / 2.0))


def _svg_ellipse(r):
    x0, y0, x1, y1 = r
    if x1 - x0 < 20 or y1 - y0 < 20:
        return ""
    return '<ellipse class="sym" cx="{:.0f}" cy="{:.0f}" rx="{:.0f}" ry="{:.0f}"/>'.format(
        (x0 + x1) / 2.0, (y0 + y1) / 2.0, (x1 - x0) / 2.0, (y1 - y0) / 2.0)


def _svg_line(a, b):
    return '<line class="sym" x1="{:.0f}" y1="{:.0f}" x2="{:.0f}" y2="{:.0f}"/>'.format(a[0], a[1], b[0], b[1])


def _inner_edge(rect, side):
    """띠의 안쪽 변(가구 가운데 쪽) 양 끝점."""
    x0, y0, x1, y1 = rect
    return {"n": ((x0, y1), (x1, y1)), "s": ((x0, y0), (x1, y0)),
            "w": ((x1, y0), (x1, y1)), "e": ((x0, y0), (x0, y1))}[side]


def furniture_symbol(it, g):
    """평면도에서 품목을 알아보게 하는 기호. 기호가 없는 품목은 빈 목록."""
    cat = it.get("category")
    rect, f = g["rect"], g["facing"]
    back = OPP[f]
    x0, y0, x1, y1 = rect
    W, H = x1 - x0, y1 - y0
    wide = W if f in "ns" else H    # 정면 폭
    deep = H if f in "ns" else W    # 깊이
    lat = ("w", "e") if f in "ns" else ("n", "s")
    m = min(W, H)
    out = []
    if cat == "bed":
        head = _band(rect, back, min(500, deep * 0.22))
        for p in _split(_inset(head, 70), f, 2 if wide >= 1300 else 1, 90):
            out.append(_svg_rect(p, 70))
        out.append(_svg_line(*_inner_edge(_band(rect, back, deep * 0.4), back)))
    elif cat == "sofa":
        out.append(_svg_rect(_band(rect, back, min(260, deep * 0.3))))
        for sd in lat:
            out.append(_svg_rect(_band(rect, sd, min(200, wide * 0.15))))
    elif cat == "chair":
        out.append(_svg_rect(_band(rect, back, min(120, deep * 0.25))))
    elif cat == "toilet":
        out.append(_svg_rect(_inset(_band(rect, back, deep * 0.3), 25), 20))
        out.append(_svg_ellipse(_inset(_band(rect, f, deep * 0.72), 40)))
    elif cat == "washbasin":
        out.append(_svg_ellipse(_inset(rect, m * 0.15)))
    elif cat == "bathtub":
        out.append(_svg_rect(_inset(rect, 70), 180))
    elif cat in ("washer", "dryer"):
        out.append(_svg_ellipse(_inset(rect, m * 0.15)))
    elif cat in ("lamp", "plant"):
        c = ((x0 + x1) / 2.0, (y0 + y1) / 2.0)
        r = m * 0.42
        out.append(_svg_ellipse((c[0] - r, c[1] - r, c[0] + r, c[1] + r)))
        if cat == "lamp":
            out.append(_svg_line((c[0] - r * 0.7, c[1] - r * 0.7), (c[0] + r * 0.7, c[1] + r * 0.7)))
            out.append(_svg_line((c[0] - r * 0.7, c[1] + r * 0.7), (c[0] + r * 0.7, c[1] - r * 0.7)))
    elif cat == "wardrobe":
        a, b = _inner_edge(_band(rect, back, deep * 0.5), back)   # 옷걸이 봉
        out.append(_svg_line(a, b))
        n = max(2, int(wide // 300))
        for i in range(1, n):
            t = i / float(n)
            px, py = a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t
            d = deep * 0.18
            out.append(_svg_line((px - d, py - d), (px + d, py + d)) if f in "ns" else _svg_line((px - d, py + d), (px + d, py - d)))
    elif cat == "kitchen_counter":
        a, b = _inner_edge(_band(rect, back, deep * 0.12), back)     # 상판 뒤 턱
        out.append(_svg_line(a, b))
        sink = _split(_inset(rect, deep * 0.18), f, 3, deep * 0.1)[0]
        out.append(_svg_rect(sink, 60))
    elif cat == "shower":
        out.append(_svg_line((x0, y0), (x1, y1)))
        c = ((x0 + x1) / 2.0, (y0 + y1) / 2.0)
        out.append(_svg_ellipse((c[0] - 50, c[1] - 50, c[0] + 50, c[1] + 50)))
    elif cat == "fridge":
        out.append(_svg_line((x0, y0), (x1, y1)))
        out.append(_svg_line((x0, y1), (x1, y0)))
    return [x for x in out if x]


def review_cards(ctx, rows, num, bad, embed=False):
    out = []
    for rid, r in ctx.rooms.items():
        items = [it for _, it in rows.get(rid, []) if reviewable(it)]
        if not items:
            continue
        out.append('<h3>{}</h3><div class="cards">'.format(_esc(r.get("name") or rid)))
        for it in items:
            prod = it["product"]
            img = prod.get("image")
            if img and embed:
                img = fetch_image(img) or img
            thumb = ('<div class="thumb"><img src="{}" alt="{}" loading="lazy" referrerpolicy="no-referrer"></div>'.format(
                _esc(img), _esc(prod.get("title") or it.get("name") or "")) if img else '<div class="thumb none">사진 없음</div>')
            title = prod.get("title") or it.get("name") or label_of(it)
            meta = " · ".join(_esc(x) for x in (prod.get("brand"), prod.get("option")) if x)
            p = price_of(it)
            price = "{}원".format(fmt(p)) if p is not None else "가격 미상"
            if it.get("qty", 1) > 1:
                price += ' <small class="muted">({}개)</small>'.format(it["qty"])
            rt = rating_txt(prod)
            kp = prod.get("key_points") or []
            sz = it["size"]
            dims = "{}×{}×{}mm · {}".format(fmt(sz["w"]), fmt(sz["d"]), fmt(sz.get("h", 0)),
                                         DIMS_SOURCE.get(prod.get("dims_source"), "실측 미확인"))
            cls = "card" + (" " + bad[it["id"]] if it["id"] in bad else "")
            out.append(
                '<article class="{cls}" data-ref="{id}" data-id="{id}">{thumb}<div class="cbody">'
                '<div class="cno">{n} · {lab}</div>'
                '<h4><a href="{url}" target="_blank" rel="noopener">{title}</a></h4>'
                '{meta}<p class="price">{price}{rt}</p>{kp}<p class="cdim">{dims}{chk}</p></div></article>'.format(
                    cls=cls, id=_esc(it["id"]), thumb=thumb, n=num[it["id"]], lab=_esc(label_of(it)),
                    url=_esc(prod["url"]), title=_esc(title),
                    meta='<p class="cmeta">{}</p>'.format(meta) if meta else "",
                    price=price, rt=' <span class="rating">{}</span>'.format(_esc(rt)) if rt else "",
                    kp=('<ul class="kp">' + "".join("<li>{}</li>".format(_esc(k)) for k in kp) + "</ul>") if kp else "",
                    dims=_esc(dims),
                    chk=" · {} 조회".format(_esc(prod["checked"])) if prod.get("checked") else ""))
        out.append("</div>")
    if not out:
        return '<p class="muted">아직 오늘의집 제품으로 정한 품목이 없다</p>'
    return "\n".join(out)


def _text_w(t, size):
    return sum(1.0 if ord(ch) > 0x1100 else 0.62 for ch in t) * size


def _area(a, b):
    c = inter(a, b)
    return (c[2] - c[0]) * (c[3] - c[1]) if c else 0


def room_label_spot(ctx, zones, room, name, dims, fs):
    """방 이름표(이름 + 크기 두 줄)의 왼쪽 위. 가구·비울 자리·문 열림과 덜 겹치는 모서리를 고른다."""
    x0, y0, x1, y1 = rr(room)
    bw = max(_text_w(name, fs), _text_w(dims, fs * 0.75)) + fs * 0.4
    bh = fs * 2.3
    pad = fs * 0.4
    cands = [(x0 + pad, y0 + pad), (x1 - pad - bw, y0 + pad), (x0 + pad, y1 - pad - bh),
             (x1 - pad - bw, y1 - pad - bh), ((x0 + x1 - bw) / 2.0, (y0 + y1 - bh) / 2.0)]
    obst = []
    for it in ctx.items:
        if it["room"] != room["id"]:
            continue
        g = ctx.geo[it["id"]]
        obst.append((g["rect"], 1 if CAT.get(it.get("category"), {}).get("floor") else 4))
        for z in zones.get(it["id"], []):
            obst.append((zone_rect(g, z, z["rec"]), 1))
    for o in ctx.ops:
        if o["type"] == "door" and room["id"] in (o["room"], o.get("to")):
            pts = (o["hinge_pt"], o["open_tip"], o["closed_tip"])
            obst.append(((min(p[0] for p in pts), min(p[1] for p in pts), max(p[0] for p in pts), max(p[1] for p in pts)), 2))
    best, score = cands[0], None
    for cx, cy in cands:
        if cx < x0 or cy < y0:
            continue
        box = (cx, cy, cx + bw, cy + bh)
        sc = sum(_area(box, ob) * w for ob, w in obst)
        if score is None or sc < score:
            best, score = (cx, cy), sc
        if sc == 0:
            break
    return best


def render(house, embed=False):
    ctx, zones = check(house)
    wall = ctx.wall
    rooms = list(ctx.rooms.values())
    rects = [rr(r) for r in rooms]
    minx = min(r[0] for r in rects) - wall
    miny = min(r[1] for r in rects) - wall
    maxx = max(r[2] for r in rects) + wall
    maxy = max(r[3] for r in rects) + wall
    W, H = maxx - minx, maxy - miny
    fs = max(W, H) / 62.0
    M = fs * 4.5
    bx0, by0, bx1, by1 = minx, miny, maxx, maxy     # 바깥으로 열리는 문까지 넣은 테두리
    for o in ctx.ops:
        if o["type"] == "door":
            for px, py in (o["hinge_pt"], o["open_tip"], o["closed_tip"]):
                bx0, by0, bx1, by1 = min(bx0, px), min(by0, py), max(bx1, px), max(by1, py)
    vb = (bx0 - M, by0 - M, bx1 - bx0 + 2 * M, by1 - by0 + 2 * M)
    bad = {}
    for i in ctx.issues:
        for iid in i["ids"]:
            if i["level"] == "error" or bad.get(iid) != "error":
                bad[iid] = i["level"] if bad.get(iid) != "error" else "error"
    num = {}
    n = 0
    for it in ctx.items:
        n += 1
        num[it["id"]] = n

    s = []
    s.append('<svg viewBox="{:.0f} {:.0f} {:.0f} {:.0f}" role="img" aria-label="평면도" xmlns="http://www.w3.org/2000/svg">'.format(*vb))
    s.append('<defs><pattern id="hatch" width="{0:.0f}" height="{0:.0f}" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">'
             '<line x1="0" y1="0" x2="0" y2="{0:.0f}" class="hatch"/></pattern></defs>'.format(fs * 0.9))
    for r in rooms:
        x0, y0, x1, y1 = rr(r)
        s.append('<rect class="floor k-{}" x="{}" y="{}" width="{}" height="{}"/>'.format(r.get("kind"), x0, y0, x1 - x0, y1 - y0))
    for it in ctx.items:
        g = ctx.geo[it["id"]]
        for z in zones.get(it["id"], []):
            zr = zone_rect(g, z, z["rec"])
            c = inter(zr, rr(ctx.rooms[it["room"]]))
            if c:
                s.append('<rect class="zone" data-id="{}" x="{:.0f}" y="{:.0f}" width="{:.0f}" height="{:.0f}"/>'.format(
                    _esc(it["id"]), c[0], c[1], c[2] - c[0], c[3] - c[1]))
    for r in rooms:
        x0, y0, x1, y1 = rr(r)
        s.append('<rect class="wall" x="{}" y="{}" width="{}" height="{}" stroke-width="{}"/>'.format(
            x0 - wall / 2.0, y0 - wall / 2.0, x1 - x0 + wall, y1 - y0 + wall, wall))
    for o in ctx.ops:
        if o["type"] == "window":
            ln = o["line"]
            l0, l1 = sorted((ln, ln + o["out"] * wall))
            rc = (o["a"], l0, o["b"], l1) if o["axis"] == "x" else (l0, o["a"], l1, o["b"])
            s.append('<rect class="win" x="{:.0f}" y="{:.0f}" width="{:.0f}" height="{:.0f}"/>'.format(rc[0], rc[1], rc[2] - rc[0], rc[3] - rc[1]))
            mid = (l0 + l1) / 2.0
            if o["axis"] == "x":
                s.append('<line class="winline" x1="{:.0f}" y1="{:.0f}" x2="{:.0f}" y2="{:.0f}"/>'.format(o["a"], mid, o["b"], mid))
            else:
                s.append('<line class="winline" x1="{:.0f}" y1="{:.0f}" x2="{:.0f}" y2="{:.0f}"/>'.format(mid, o["a"], mid, o["b"]))
            continue
        c = ctx.carve(o)
        kind = ctx.rooms[o["room"]].get("kind")
        s.append('<rect class="floor k-{}" x="{:.0f}" y="{:.0f}" width="{:.0f}" height="{:.0f}"/>'.format(kind, c[0], c[1], c[2] - c[0], c[3] - c[1]))
        if o["type"] == "door":
            hx, hy = o["hinge_pt"]
            ox, oy = o["open_tip"]
            cx2, cy2 = o["closed_tip"]
            z = (ox - hx) * (cy2 - hy) - (oy - hy) * (cx2 - hx)
            sweep = 1 if z > 0 else 0
            s.append('<g class="door" data-id="{}"><line x1="{:.0f}" y1="{:.0f}" x2="{:.0f}" y2="{:.0f}"/>'
                     '<path d="M{:.0f},{:.0f} A{:.0f},{:.0f} 0 0 {} {:.0f},{:.0f}"/></g>'.format(
                         _esc(o["id"]), hx, hy, ox, oy, ox, oy, o["width"], o["width"], sweep, cx2, cy2))
        elif o["type"] == "sliding":
            mid = (c[1] + c[3]) / 2.0 if o["axis"] == "x" else (c[0] + c[2]) / 2.0
            a, b = o["a"], o["b"]
            half = (b - a) / 2.0
            if o["axis"] == "x":
                s.append('<g class="door"><line x1="{:.0f}" y1="{:.0f}" x2="{:.0f}" y2="{:.0f}"/><line x1="{:.0f}" y1="{:.0f}" x2="{:.0f}" y2="{:.0f}"/></g>'.format(
                    a, mid - wall * 0.2, a + half + 50, mid - wall * 0.2, b - half - 50, mid + wall * 0.2, b, mid + wall * 0.2))
            else:
                s.append('<g class="door"><line x1="{:.0f}" y1="{:.0f}" x2="{:.0f}" y2="{:.0f}"/><line x1="{:.0f}" y1="{:.0f}" x2="{:.0f}" y2="{:.0f}"/></g>'.format(
                    mid - wall * 0.2, a, mid - wall * 0.2, a + half + 50, mid + wall * 0.2, b - half - 50, mid + wall * 0.2, b))
    order = sorted(ctx.items, key=lambda it: (0 if CAT.get(it.get("category"), {}).get("floor") else (2 if (it.get("on") or it.get("with")) else 1)))
    for it in order:
        g = ctx.geo[it["id"]]
        x0, y0, x1, y1 = g["rect"]
        cls = ["item"]
        if CAT.get(it.get("category"), {}).get("floor"):
            cls.append("rug")
        if it.get("on") or it.get("with") or it.get("z", 0) >= WALL_MOUNT_Z:
            cls.append("light")
        if it.get("placeholder"):
            cls.append("ph")
        if bad.get(it["id"]) == "error":
            cls.append("err")
        elif bad.get(it["id"]) == "warning":
            cls.append("warn")
        s.append('<g class="{}" data-id="{}" data-ref="{}"><title>{}</title>'.format(" ".join(cls), _esc(it["id"]), _esc(it["id"]), _esc(
            "{}. {} — {}×{}×{}mm".format(num[it["id"]], it.get("name") or label_of(it), it["size"]["w"], it["size"]["d"], it["size"].get("h", 0)))))
        s.append('<rect x="{:.0f}" y="{:.0f}" width="{:.0f}" height="{:.0f}"/>'.format(x0, y0, x1 - x0, y1 - y0))
        s.extend(furniture_symbol(it, g))
        if zones.get(it["id"]) or CAT.get(it.get("category"), {}).get("wall"):
            axis, a0, a1, edge, sign = side_axis(g["rect"], g["facing"])
            if axis == "x":
                s.append('<line class="front" x1="{:.0f}" y1="{:.0f}" x2="{:.0f}" y2="{:.0f}"/>'.format(a0, edge, a1, edge))
            else:
                s.append('<line class="front" x1="{:.0f}" y1="{:.0f}" x2="{:.0f}" y2="{:.0f}"/>'.format(edge, a0, edge, a1))
        txt = "{} {}".format(num[it["id"]], label_of(it))
        iw, ih = x1 - x0, y1 - y0
        f = min(fs * 0.85, ih * 0.42, iw * 0.42)
        if len(txt) * f * 0.62 > iw * 0.92:
            txt = str(num[it["id"]])
            f = min(fs * 0.85, ih * 0.6, iw * 0.6)
        s.append('<text class="ilbl" x="{:.0f}" y="{:.0f}" font-size="{:.0f}">{}</text></g>'.format(
            (x0 + x1) / 2.0, (y0 + y1) / 2.0 + f * 0.35, max(f, fs * 0.45), _esc(txt)))
    for r in rooms:
        x0, y0, x1, y1 = rr(r)
        name = r.get("name") or KIND_KO.get(r.get("kind"), r["id"])
        dims = "{}×{}".format(fmt(x1 - x0), fmt(y1 - y0))
        lx, ly = room_label_spot(ctx, zones, r, name, dims, fs)
        s.append('<text class="rlbl" x="{:.0f}" y="{:.0f}" font-size="{:.0f}">{}</text>'.format(lx, ly + fs * 0.95, fs, _esc(name)))
        s.append('<text class="rdim" x="{:.0f}" y="{:.0f}" font-size="{:.0f}">{}</text>'.format(
            lx, ly + fs * 2.0, fs * 0.75, dims))
    ty = by0 - M * 0.45
    s.append('<g class="dim"><line x1="{:.0f}" y1="{:.0f}" x2="{:.0f}" y2="{:.0f}"/>'
             '<line x1="{:.0f}" y1="{:.0f}" x2="{:.0f}" y2="{:.0f}"/><line x1="{:.0f}" y1="{:.0f}" x2="{:.0f}" y2="{:.0f}"/>'
             '<text x="{:.0f}" y="{:.0f}" font-size="{:.0f}">{}</text></g>'.format(
                 minx, ty, maxx, ty, minx, ty - fs * 0.4, minx, ty + fs * 0.4, maxx, ty - fs * 0.4, maxx, ty + fs * 0.4,
                 (minx + maxx) / 2.0, ty - fs * 0.35, fs * 0.8, fmt(W)))
    tx = bx0 - M * 0.45
    s.append('<g class="dim"><line x1="{:.0f}" y1="{:.0f}" x2="{:.0f}" y2="{:.0f}"/>'
             '<line x1="{:.0f}" y1="{:.0f}" x2="{:.0f}" y2="{:.0f}"/><line x1="{:.0f}" y1="{:.0f}" x2="{:.0f}" y2="{:.0f}"/>'
             '<text x="{:.0f}" y="{:.0f}" font-size="{:.0f}" transform="rotate(-90 {:.0f} {:.0f})">{}</text></g>'.format(
                 tx, miny, tx, maxy, tx - fs * 0.4, miny, tx + fs * 0.4, miny, tx - fs * 0.4, maxy, tx + fs * 0.4, maxy,
                 tx - fs * 0.35, (miny + maxy) / 2.0, fs * 0.8, tx - fs * 0.35, (miny + maxy) / 2.0, fmt(H)))
    sx, sy = bx1 - 1000, by1 + M * 0.5
    s.append('<g class="dim"><line x1="{:.0f}" y1="{:.0f}" x2="{:.0f}" y2="{:.0f}" class="scale"/>'
             '<text x="{:.0f}" y="{:.0f}" font-size="{:.0f}">1m</text></g>'.format(sx, sy, sx + 1000, sy, sx + 500, sy - fs * 0.4, fs * 0.7))
    s.append("</svg>")
    svg = "\n".join(s)
    # 도면만 담은 SVG 파일(이미지로 열리고, 다른 문서·영상에 넣을 수 있다)
    top = fs * 3.2
    svb = (vb[0], vb[1] - top, vb[2], vb[3] + top)
    k = 1400.0 / max(svb[2], svb[3])    # 긴 변 1400px
    head = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="{:.0f} {:.0f} {:.0f} {:.0f}" width="{}" height="{}" '
            'role="img" aria-label="평면도">'.format(svb[0], svb[1], svb[2], svb[3], int(round(svb[2] * k)), int(round(svb[3] * k))))
    plan_title = '<text class="ttl" x="{:.0f}" y="{:.0f}" font-size="{:.0f}">{}</text>'.format(
        bx0, svb[1] + fs * 1.5, fs * 1.25, _esc(house.get("name", "우리집") + " 평면도"))
    plan_sub = '<text class="tsub" x="{:.0f}" y="{:.0f}" font-size="{:.0f}">{}</text>'.format(
        bx0, svb[1] + fs * 2.55, fs * 0.72, _esc("단위 mm · 파란 점선 = 비워 둘 자리 · 파란 굵은 선 = 가구 앞면 · 빨강 = 오류 · 노랑 = 주의"))
    standalone = "\n".join([head, "<style>" + SVG_CSS + "</style>",
                            '<rect x="{:.0f}" y="{:.0f}" width="{:.0f}" height="{:.0f}" fill="#ffffff"/>'.format(*svb),
                            plan_title, plan_sub] + s[1:])

    errs = [i for i in ctx.issues if i["level"] == "error"]
    warns = [i for i in ctx.issues if i["level"] == "warning"]
    issue_html = []
    if not ctx.issues:
        issue_html.append('<p class="ok">✓ 오류·주의 없음</p>')
    for i in ctx.issues:
        ref = i["ids"][0] if i["ids"] else ""
        issue_html.append('<li class="{}" data-ref="{}"><span class="tag">{}</span> {}</li>'.format(
            i["level"], _esc(ref), LEVEL_KO[i["level"]], _esc(i["msg"])))
    if ctx.issues:
        issue_html = ['<ul class="issues">'] + issue_html + ["</ul>"]

    _, rows = inventory_rows(house)
    inv = []
    total, unknown, count = 0, 0, 0
    for rid, r in ctx.rooms.items():
        items = rows.get(rid, [])
        x0, y0, x1, y1 = rr(r)
        inv.append('<section class="room"><h3>{} <small>{}×{}mm · {}</small></h3>'.format(
            _esc(r.get("name") or rid), fmt(x1 - x0), fmt(y1 - y0), area_txt(x1 - x0, y1 - y0)))
        if not items:
            inv.append('<p class="muted">가구 없음</p></section>')
            continue
        inv.append('<div class="tw"><table><thead><tr><th>#</th><th>품목</th><th>제품</th><th>실측 W×D×H</th><th>실측 출처</th><th class="num">가격</th></tr></thead><tbody>')
        sub = 0
        for n, it in items:
            prod = it.get("product") or {}
            sz = it["size"]
            if it.get("owned"):
                pname = _esc(it.get("name") or "보유 가구") + ' <span class="pill">보유</span>'
                src = DIMS_SOURCE.get(prod.get("dims_source", "user"), "사용자 실측")
            elif it.get("placeholder"):
                pname = '<span class="muted">제품 미정</span>'
                src = "가상 크기"
            else:
                nm = _esc(it.get("name") or prod.get("title") or "제품")
                pname = '<a href="{}" target="_blank" rel="noopener">{}</a>'.format(_esc(prod["url"]), nm) if prod.get("url") else nm
                if prod.get("option"):
                    pname += '<br><small class="muted">{}</small>'.format(_esc(prod["option"]))
                src = DIMS_SOURCE.get(prod.get("dims_source"), "미확인")
                if prod.get("dims_note"):
                    src += '<br><small class="muted">{}</small>'.format(_esc(prod["dims_note"]))
            p = price_of(it)
            if p is not None:
                sub += p
                ptxt = "{}원".format(fmt(p))
            else:
                ptxt = "-" if (it.get("owned") or it.get("placeholder")) else "미상"
                if not it.get("owned") and not it.get("placeholder"):
                    unknown += 1
            count += 1
            q = " ×{}".format(it["qty"]) if it.get("qty", 1) > 1 else ""
            st = ' class="{}"'.format(bad[it["id"]]) if it["id"] in bad else ""
            inv.append('<tr data-ref="{0}" data-id="{0}"{1}><td>{2}</td><td>{3}{4}</td><td>{5}</td><td class="nowrap">{6}×{7}×{8}</td><td>{9}</td><td class="num nowrap">{10}</td></tr>'.format(
                _esc(it["id"]), st, n, _esc(label_of(it)), q, pname, fmt(sz["w"]), fmt(sz["d"]), fmt(sz.get("h", 0)), src, ptxt))
        total += sub
        inv.append('</tbody><tfoot><tr><td colspan="5">소계</td><td class="num nowrap">{}원</td></tr></tfoot></table></div></section>'.format(fmt(sub)))
    budget = house.get("budget")
    tot = "{}원".format(fmt(total))
    if unknown:
        tot += " (가격 미상 {}개 제외)".format(unknown)
    btxt = ""
    if budget:
        btxt = " · 예산 {}원 대비 {}".format(fmt(budget), "{}원 남음".format(fmt(budget - total)) if budget >= total else "{}원 초과".format(fmt(total - budget)))
    cards = review_cards(ctx, rows, num, bad, embed)
    area = sum((r[2] - r[0]) * (r[3] - r[1]) for r in rects)
    notes = (house.get("meta") or {}).get("notes") or []
    if house.get("type") == "room":
        kinds = "{}".format(KIND_KO.get(rooms[0].get("kind"), "") if rooms else "")
    else:
        kinds = "침실 {}개".format(sum(1 for r in rooms if r.get("kind") == "bedroom"))
    title = "{} 배치도".format(house.get("name", "우리집"))
    now = datetime.date.today().isoformat()
    return HTML_TMPL.format(
        title=_esc(title),
        name=_esc(house.get("name", "우리집")),
        sub=_esc("{} · {} · 실내 면적 {} · 품목 {}점".format(
            TYPE_KO.get(house.get("type"), ""), kinds, area_txt(area, 1), count)),
        svg=svg,
        n_err=len(errs), n_warn=len(warns),
        issues="\n".join(issue_html),
        inv="\n".join(inv),
        cards=cards,
        total=_esc(tot + btxt),
        notes="".join("<li>{}</li>".format(_esc(n)) for n in notes) or "<li>없음</li>",
        date=now,
    ), standalone


SVG_CSS = (
    "text{font-family:-apple-system,BlinkMacSystemFont,'Apple SD Gothic Neo','Pretendard','Noto Sans KR','Malgun Gothic',sans-serif}"
    ".floor{stroke:none}.k-bedroom{fill:#f2e8d5}.k-living{fill:#e9efe0}.k-kitchen{fill:#e3ebf3}.k-bathroom{fill:#dcecef}"
    ".k-entrance{fill:#ebe4da}.k-hall{fill:#efede7}.k-dressroom{fill:#efe5ea}.k-utility{fill:#e6e6e6}"
    ".wall{fill:none;stroke:#2c2c2c}.win{fill:#ffffff;stroke:#3b9bd6;stroke-width:14}.winline{stroke:#3b9bd6;stroke-width:14}"
    ".door line,.door path{fill:none;stroke:#1d1f22;stroke-width:18}.door path{stroke-dasharray:40 30;stroke-width:12}"
    ".zone{fill:rgba(47,129,247,.10);stroke:rgba(47,129,247,.55);stroke-width:10;stroke-dasharray:50 40}.hatch{stroke:rgba(47,129,247,.55);stroke-width:6}"
    ".item rect{fill:#ffffff;stroke:#3d4045;stroke-width:16}.item.rug rect{fill:none;stroke-dasharray:60 40;stroke-width:10}"
    ".item.light rect{fill:none;stroke-dasharray:30 30;stroke-width:10}.item.ph rect{stroke-dasharray:80 50}"
    ".item.err rect{stroke:#cf222e;stroke-width:34}.item.warn rect{stroke:#b07800;stroke-width:26}"
    ".item .sym,.item rect.sym{fill:none;stroke:#3d4045;stroke-width:9;stroke-dasharray:none}"
    ".item .front{stroke:#2f6fde;stroke-width:40}"
    ".ilbl{fill:#1d1f22;text-anchor:middle;paint-order:stroke;stroke:#ffffff;stroke-width:14;font-weight:600}"
    ".rlbl{fill:#1d1f22;font-weight:700;paint-order:stroke;stroke:#ffffff;stroke-width:22}"
    ".rdim{fill:#6a6f76;paint-order:stroke;stroke:#ffffff;stroke-width:18}"
    ".dim line{stroke:#6a6f76;stroke-width:10}.dim line.scale{stroke:#1d1f22;stroke-width:30}.dim text{fill:#6a6f76;text-anchor:middle}"
    ".ttl{fill:#1d1f22;font-weight:700}.tsub{fill:#6a6f76}"
)


HTML_TMPL = """<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
:root {{
  --bg:#f7f6f2; --panel:#ffffff; --ink:#1d1f22; --muted:#6a6f76; --line:#d9d6cf;
  --wall:#2c2c2c; --halo:#f7f6f2;
  --k-bedroom:#f2e8d5; --k-living:#e9efe0; --k-kitchen:#e3ebf3; --k-bathroom:#dcecef;
  --k-entrance:#ebe4da; --k-hall:#efede7; --k-dressroom:#efe5ea; --k-utility:#e6e6e6;
  --item:#ffffff; --item-stroke:#3d4045; --err:#cf222e; --warn:#b07800;
  --zone:rgba(47,129,247,.10); --zone-line:rgba(47,129,247,.55); --win:#3b9bd6; --accent:#2f6fde;
}}
@media (prefers-color-scheme: dark) {{
  :root:not([data-theme="light"]) {{
    --bg:#16181b; --panel:#1e2125; --ink:#e7e7e4; --muted:#9aa0a6; --line:#33373c;
    --wall:#d6d4cf; --halo:#16181b;
    --k-bedroom:#3a3326; --k-living:#2c3426; --k-kitchen:#26303b; --k-bathroom:#22353a;
    --k-entrance:#352f28; --k-hall:#2a2a27; --k-dressroom:#352a30; --k-utility:#2c2c2c;
    --item:#2a2e33; --item-stroke:#c9ccd0; --err:#ff6b6b; --warn:#e3b341;
    --zone:rgba(88,166,255,.14); --zone-line:rgba(88,166,255,.6); --win:#58a6ff; --accent:#6ea8fe;
  }}
}}
:root[data-theme="dark"] {{
  --bg:#16181b; --panel:#1e2125; --ink:#e7e7e4; --muted:#9aa0a6; --line:#33373c;
  --wall:#d6d4cf; --halo:#16181b;
  --k-bedroom:#3a3326; --k-living:#2c3426; --k-kitchen:#26303b; --k-bathroom:#22353a;
  --k-entrance:#352f28; --k-hall:#2a2a27; --k-dressroom:#352a30; --k-utility:#2c2c2c;
  --item:#2a2e33; --item-stroke:#c9ccd0; --err:#ff6b6b; --warn:#e3b341;
  --zone:rgba(88,166,255,.14); --zone-line:rgba(88,166,255,.6); --win:#58a6ff; --accent:#6ea8fe;
}}
* {{ box-sizing:border-box; }}
body {{ margin:0; background:var(--bg); color:var(--ink);
  font:15px/1.55 -apple-system,BlinkMacSystemFont,"Apple SD Gothic Neo","Pretendard","Noto Sans KR","Malgun Gothic",sans-serif; }}
main {{ max-width:1120px; margin:0 auto; padding:24px 16px 48px; }}
h1 {{ font-size:26px; margin:0 0 4px; letter-spacing:-.01em; }}
h2 {{ font-size:18px; margin:32px 0 12px; }}
h3 {{ font-size:16px; margin:20px 0 8px; }}
h3 small {{ font-weight:400; color:var(--muted); font-size:13px; margin-left:6px; }}
.sub {{ color:var(--muted); margin:0; }}
.muted {{ color:var(--muted); }}
figure {{ margin:20px 0 8px; background:var(--panel); border:1px solid var(--line); border-radius:10px; padding:12px; }}
svg {{ width:100%; height:auto; display:block; }}
.floor {{ stroke:none; }}
.k-bedroom {{ fill:var(--k-bedroom); }} .k-living {{ fill:var(--k-living); }} .k-kitchen {{ fill:var(--k-kitchen); }}
.k-bathroom {{ fill:var(--k-bathroom); }} .k-entrance {{ fill:var(--k-entrance); }} .k-hall {{ fill:var(--k-hall); }}
.k-dressroom {{ fill:var(--k-dressroom); }} .k-utility {{ fill:var(--k-utility); }}
.wall {{ fill:none; stroke:var(--wall); }}
.win {{ fill:var(--panel); stroke:var(--win); stroke-width:14; }}
.winline {{ stroke:var(--win); stroke-width:14; }}
.door line, .door path {{ fill:none; stroke:var(--ink); stroke-width:18; }}
.door path {{ stroke-dasharray:40 30; stroke-width:12; }}
.zone {{ fill:var(--zone); stroke:var(--zone-line); stroke-width:10; stroke-dasharray:50 40; }}
.hatch {{ stroke:var(--zone-line); stroke-width:6; }}
.item rect {{ fill:var(--item); stroke:var(--item-stroke); stroke-width:16; }}
.item.rug rect {{ fill:none; stroke-dasharray:60 40; stroke-width:10; }}
.item.light rect {{ fill:none; stroke-dasharray:30 30; stroke-width:10; }}
.item.ph rect {{ stroke-dasharray:80 50; }}
.item.err rect {{ stroke:var(--err); stroke-width:34; }}
.item.warn rect {{ stroke:var(--warn); stroke-width:26; }}
.item .sym, .item rect.sym {{ fill:none; stroke:var(--item-stroke); stroke-width:9; stroke-dasharray:none; }}
.item .front {{ stroke:var(--accent); stroke-width:40; }}
.item.hl rect, tr.hl, li.hl {{ outline:none; }}
.item.hl rect:not(.sym) {{ stroke:var(--accent); stroke-width:44; }}
.zone.hl {{ fill:rgba(47,129,247,.28); }}
.ilbl {{ fill:var(--ink); text-anchor:middle; paint-order:stroke; stroke:var(--item); stroke-width:14; font-weight:600; }}
.rlbl {{ fill:var(--ink); font-weight:700; paint-order:stroke; stroke:var(--halo); stroke-width:22; }}
.rdim {{ fill:var(--muted); paint-order:stroke; stroke:var(--halo); stroke-width:18; }}
.dim line {{ stroke:var(--muted); stroke-width:10; }}
.dim line.scale {{ stroke:var(--ink); stroke-width:30; }}
.dim text {{ fill:var(--muted); text-anchor:middle; }}
.legend {{ display:flex; flex-wrap:wrap; gap:6px 18px; font-size:13px; color:var(--muted); margin:6px 2px 0; }}
.legend i {{ display:inline-block; width:22px; height:10px; vertical-align:middle; margin-right:6px; border-radius:2px; }}
.lg-zone {{ background:var(--zone); border:1px dashed var(--zone-line); }}
.lg-front {{ background:var(--accent); height:4px !important; }}
.lg-err {{ border:2px solid var(--err); }}
.lg-warn {{ border:2px solid var(--warn); }}
.counts {{ display:flex; gap:10px; flex-wrap:wrap; }}
.badge {{ border-radius:999px; padding:2px 10px; font-size:13px; border:1px solid var(--line); background:var(--panel); }}
.badge.e {{ color:var(--err); border-color:var(--err); }} .badge.w {{ color:var(--warn); border-color:var(--warn); }}
ul.issues {{ list-style:none; padding:0; margin:10px 0 0; }}
ul.issues li {{ padding:7px 10px; border-bottom:1px solid var(--line); cursor:default; }}
ul.issues li.hl {{ background:var(--zone); }}
.tag {{ font-size:12px; font-weight:700; border-radius:4px; padding:1px 6px; margin-right:6px; }}
li.error .tag {{ color:var(--err); border:1px solid var(--err); }}
li.warning .tag {{ color:var(--warn); border:1px solid var(--warn); }}
.ok {{ color:var(--accent); }}
.tw {{ overflow-x:auto; border:1px solid var(--line); border-radius:8px; background:var(--panel); }}
table {{ border-collapse:collapse; width:100%; font-size:14px; }}
th, td {{ text-align:left; padding:8px 10px; border-bottom:1px solid var(--line); vertical-align:top; }}
th {{ font-size:12px; color:var(--muted); font-weight:600; }}
tfoot td {{ font-weight:700; border-bottom:none; }}
tr.hl {{ background:var(--zone); }}
tr.error td:first-child {{ box-shadow:inset 3px 0 0 var(--err); }}
tr.warning td:first-child {{ box-shadow:inset 3px 0 0 var(--warn); }}
td.num, th.num {{ text-align:right; }}
.nowrap {{ white-space:nowrap; }}
.pill {{ font-size:11px; border:1px solid var(--line); border-radius:999px; padding:0 6px; color:var(--muted); }}
a {{ color:var(--accent); }}
.total {{ font-size:17px; font-weight:700; margin:20px 0 0; }}
.cards {{ display:grid; grid-template-columns:repeat(auto-fill,minmax(230px,1fr)); gap:12px; }}
.card {{ background:var(--panel); border:1px solid var(--line); border-radius:10px; overflow:hidden; display:flex; flex-direction:column; }}
.card.hl {{ border-color:var(--accent); box-shadow:0 0 0 2px var(--accent); }}
.card.error {{ border-color:var(--err); }} .card.warning {{ border-color:var(--warn); }}
.thumb {{ aspect-ratio:1/1; background:#fff; display:flex; align-items:center; justify-content:center; border-bottom:1px solid var(--line); }}
.thumb img {{ width:100%; height:100%; object-fit:contain; }}
.thumb.none {{ background:var(--bg); color:var(--muted); font-size:13px; }}
.cbody {{ padding:10px 12px 12px; }}
.cbody p {{ margin:2px 0; }}
.cno {{ font-size:12px; color:var(--muted); font-weight:600; }}
.card h4 {{ font-size:14px; line-height:1.4; margin:2px 0 4px; }}
.card h4 a {{ color:var(--ink); text-decoration:none; }}
.card h4 a:hover {{ text-decoration:underline; }}
.cmeta {{ font-size:12px; color:var(--muted); }}
.price {{ font-weight:700; }}
.rating {{ font-weight:600; color:var(--warn); font-size:13px; margin-left:4px; }}
.kp {{ margin:6px 0 4px; padding-left:16px; font-size:13px; }}
.kp li {{ margin:1px 0; }}
.cdim {{ font-size:12px; color:var(--muted); }}
footer {{ color:var(--muted); font-size:12px; margin-top:28px; }}
</style>
</head>
<body>
<main>
<h1>{name}</h1>
<p class="sub">{sub}</p>
<figure>
{svg}
<div class="legend">
<span><i class="lg-zone"></i>비워 둘 자리(권장 깊이)</span>
<span><i class="lg-front"></i>가구 앞면</span>
<span><i class="lg-err"></i>오류</span>
<span><i class="lg-warn"></i>주의</span>
<span>점선 사각형 = 러그·올려 둔 것·벽에 단 것</span>
</div>
</figure>
<h2>검사 결과</h2>
<div class="counts"><span class="badge e">오류 {n_err}</span><span class="badge w">주의 {n_warn}</span></div>
{issues}
<h2>방별 인벤토리</h2>
{inv}
<p class="total">합계 {total}</p>
<h2>리뷰 카드</h2>
<p class="muted">카드에 마우스를 올리면 평면도에서 그 제품 자리가 보인다</p>
{cards}
<h2>가정·메모</h2>
<ul>{notes}</ul>
<footer>{date} 생성 · 가격·평점·리뷰 수는 조회 시점 기준이며 바뀔 수 있다 · 치수 단위 mm · 벽 이름(위/아래/왼/오른)은 도면 기준이고 방위가 아니다</footer>
</main>
<script>
(function(){{
  function hl(id,on){{ if(!id) return; document.querySelectorAll('[data-id="'+id+'"]').forEach(function(e){{ e.classList.toggle('hl',on); }}); }}
  document.querySelectorAll('[data-ref]').forEach(function(el){{
    el.addEventListener('mouseenter',function(){{ hl(el.getAttribute('data-ref'),true); }});
    el.addEventListener('mouseleave',function(){{ hl(el.getAttribute('data-ref'),false); }});
  }});
}})();
</script>
</body>
</html>
"""


def cmd_render(args):
    house = load(args.house)
    out, svg = render(house, embed=args.embed_images)
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(out)
    svg_path = os.path.splitext(args.out)[0] + ".svg"
    with open(svg_path, "w", encoding="utf-8") as f:
        f.write(svg)
    ctx, _ = check(house)
    errs = sum(1 for i in ctx.issues if i["level"] == "error")
    warns = sum(1 for i in ctx.issues if i["level"] == "warning")
    print("{} · {} 저장 · 오류 {} · 주의 {}".format(args.out, svg_path, errs, warns))
    return 0


# ----------------------------------------------------------------------------- 입출력

def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def main(argv=None):
    ap = argparse.ArgumentParser(description="room-set-planner — 오늘의집 제품 배치도 플래너")
    sub = ap.add_subparsers(dest="cmd")
    p = sub.add_parser("shell", help="평면 틀로 집 구조 만들기")
    p.add_argument("spec")
    p.add_argument("-o", "--out", default="house.json")
    p.set_defaults(fn=cmd_shell)
    p = sub.add_parser("check", help="검사")
    p.add_argument("house")
    p.add_argument("--json", action="store_true")
    p.set_defaults(fn=cmd_check)
    p = sub.add_parser("walls", help="방의 벽별 빈 구간")
    p.add_argument("house")
    p.add_argument("room")
    p.add_argument("--depth", type=int, default=600)
    p.set_defaults(fn=cmd_walls)
    p = sub.add_parser("inventory", help="방별 인벤토리")
    p.add_argument("house")
    p.set_defaults(fn=cmd_inventory)
    p = sub.add_parser("render", help="HTML 평면도")
    p.add_argument("house")
    p.add_argument("-o", "--out", default="plan.html")
    p.add_argument("--embed-images", action="store_true", help="제품 사진을 내려받아 HTML 안에 넣는다")
    p.set_defaults(fn=cmd_render)
    args = ap.parse_args(argv)
    if not getattr(args, "fn", None):
        ap.print_help()
        return 2
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
