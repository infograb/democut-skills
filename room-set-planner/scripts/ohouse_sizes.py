#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""오늘의집 상품 페이지(Tavily extract 결과)에서 실측 후보와 리뷰용 정보를 뽑는다.

ohou.se 는 curl 같은 직접 요청을 막는다(Akamai 403). 그래서 페이지는 Tavily extract
(extract_depth=advanced)로 받고, 큰 결과가 파일로 저장되면 그 파일을 이 스크립트에 넘긴다.
표준 라이브러리만 쓴다.

  ohouse_sizes.py PAGE.txt                    페이지마다 요약(제목·브랜드·가격·평점·리뷰 수·대표 사진)
                                              + 실측 후보 줄 + 사이즈표로 보이는 상세 이미지 주소
  ohouse_sizes.py PAGE.txt --json             같은 내용을 JSON 으로
  ohouse_sizes.py PAGE.txt --download DIR     사이즈표 후보 이미지를 DIR(새 빈 디렉터리)에 받는다
        [--all-images]                        상세 이미지 전부를 받는다(사이즈표가 이름으로 안 잡힐 때)

뽑은 값은 후보일 뿐이다. 실측은 사람이 읽듯이 확인한다: 옵션 이름 · 상품정보 표 · 상세 이미지
(사이즈표) · Q&A 답변 순으로 보고, 침대는 매트리스가 아니라 프레임 바깥 치수를 쓴다.
"""
import argparse
import json
import os
import re
import sys

SKIP_SECTIONS = ("유저들의 스타일링샷", "함께 둘러보면 좋아요", "배송", "교환/환불", "판매자 정보",
                 "반품/교환", "이런 상품은 어때요", "다른 고객이 함께 본 상품")
DIM_PATTERNS = [
    re.compile(r"\d{2,4}(?:\.\d)?\s*[x×X*]\s*\d{2,4}(?:\.\d)?(?:\s*[x×X*]\s*\d{2,4}(?:\.\d)?)?\s*(?:mm|cm|㎜|㎝)?"),
    re.compile(r"(?:가로|세로|폭|너비|깊이|높이|길이|지름|직경|W|D|H)\s*[:：]?\s*\d{2,4}(?:\.\d)?\s*(?:mm|cm|㎜|㎝)?"),
    re.compile(r"\d{2,4}(?:\.\d)?\s*(?:mm|cm|㎜|㎝)\b"),
]
SIZE_WORDS = ("사이즈", "치수", "크기", "규격", "실측", "가로", "세로", "높이", "깊이", "폭", "너비")
# 페이지의 큰 갈래. 상세 설명 안의 '## FRAME SIZE' 같은 소제목은 갈래를 바꾸지 않는다.
TOP_SECTION = re.compile(r"^(상품정보|리뷰\s*[\d,]*|문의\s*[\d,]*|배송|교환/환불|판매자 정보|유저들의 스타일링샷.*|함께 둘러보면 좋아요|추천)$")
SIZE_URL_HINT = re.compile(r"size|사이즈|치수|규격|spec|info|dimension", re.I)
SIZE_HEAD_HINT = re.compile(r"size|사이즈|치수|규격|spec|dimension|제품 ?정보", re.I)
SIZE_ALT_HINT = re.compile(r"치수|규격|사이즈표|실측|size ?chart", re.I)
IMG_RE = re.compile(r"!\[([^\]]*)\]\((https?://[^)\s]+)\)")


def split_pages(text):
    """Tavily extract 텍스트를 페이지 단위로 나눈다. JSON 으로 저장된 결과도 받는다."""
    t = text.lstrip()
    if t.startswith("{") or t.startswith("["):
        try:
            data = json.loads(t)
            res = data.get("results", data) if isinstance(data, dict) else data
            return [(r.get("url", ""), r.get("title", ""), r.get("raw_content") or r.get("content") or "", 0) for r in res]
        except ValueError:
            pass
    pages = []
    for m in re.finditer(r"^Title: (.*)\nURL: (.*)\n(?:Content: .*\n)?(?:Raw Content: )?", text, re.M):
        pages.append([m.group(2).strip(), m.group(1).strip(), m.start(), m.end()])
    out = []
    for i, (url, title, head, start) in enumerate(pages):
        end = pages[i + 1][2] if i + 1 < len(pages) else len(text)
        # 줄 번호를 파일 기준으로 맞춘다(grep·Read 로 바로 찾아가게)
        out.append((url, title, text[start:end], text[:start].count("\n")))
    return out


def num(s):
    try:
        return int(s.replace(",", ""))
    except ValueError:
        return None


def summarize(url, page_title, body, base=0):
    lines = body.split("\n")
    info = {"url": url, "page_title": page_title, "title": None, "brand": None, "price": None,
            "rating": None, "review_count": None, "image": None, "category": [], "spec_table": {},
            "options": [], "dim_lines": [], "qna_lines": [], "detail_images": [], "size_images": []}
    # 제목: 본문의 첫 '# ' 줄
    ti = next((i for i, l in enumerate(lines) if l.startswith("# ")), None)
    if ti is not None:
        info["title"] = lines[ti][2:].strip()
        for l in reversed(lines[max(0, ti - 4):ti]):  # 제목 바로 위 브랜드 줄
            l = l.strip()
            if not l:
                continue
            m = re.match(r"\[([^\]]+)\]\(https://store\.ohou\.se/brands/", l)
            if m:
                info["brand"] = m.group(1).strip()
            elif not l.startswith(("!", "*", "[", "|")):
                info["brand"] = l
            break
        for l in lines[ti + 1:ti + 20]:
            m = re.match(r"^\s*\[?([\d,]+) 개 리뷰", l)
            if m and info["review_count"] is None:
                info["review_count"] = num(m.group(1))
            m = re.match(r"^\s*([\d,]+) ?원\s*$", l)
            if m and info["price"] is None:
                info["price"] = num(m.group(1))
    # 분류
    for l in lines[:ti or 60]:
        m = re.match(r"^\s*\d+\.\s+\[([^\]]+)\]\(https://ohou\.se/store/category", l)
        if m:
            info["category"].append(m.group(1))
    # 대표 사진: 대체 텍스트가 '브랜드 제목' 이고 '사진 n' 이 붙지 않은 640px 이미지
    for alt, src in IMG_RE.findall(body[:body.find("# ")] if ti is not None else body[:4000]):
        a = alt.split(":", 1)[-1].strip()
        if info["title"] and a.endswith(info["title"]) and "w=640" in src:
            info["image"] = src
            break
    # 섹션을 따라가며 상품정보 표·리뷰 평점·실측 후보·Q&A 를 모은다
    section, sub = "", ""
    after_review_head = 0
    for i, l in enumerate(lines):
        s = l.strip()
        ln = base + i + 1
        if s.startswith("## ") or s.startswith("### "):
            h = s.lstrip("#").strip()
            if s.startswith("## ") and TOP_SECTION.match(h):
                section, sub = h, ""
                m = re.match(r"리뷰\s+([\d,]+)", section)
                if m:
                    info["review_count"] = info["review_count"] or num(m.group(1))
                    after_review_head = 6
            else:
                sub = h
            continue
        if after_review_head:
            after_review_head -= 1
            if re.match(r"^[1-5](?:\.\d)?$", s) and info["rating"] is None:
                info["rating"] = float(s)
                after_review_head = 0
        if any(section.startswith(k) for k in SKIP_SECTIONS):
            continue
        if s.startswith("|") and section.startswith("상품정보"):
            cells = [c.strip() for c in s.strip("|").split("|")]
            if len(cells) >= 2 and cells[0] and not set(cells[0]) <= set("- "):
                info["spec_table"][cells[0]] = cells[1]
        if section.startswith("상품정보"):
            for alt, src in IMG_RE.findall(l):
                if "판매자 공지" in alt or src in info["detail_images"]:
                    continue
                info["detail_images"].append(src)
                if SIZE_URL_HINT.search(src.split("?")[0]) or SIZE_HEAD_HINT.search(sub) or SIZE_ALT_HINT.search(alt):
                    info["size_images"].append(src)
        text = IMG_RE.sub("", s)
        if not text:
            continue
        if section.startswith("문의"):
            if any(w in text for w in SIZE_WORDS) or any(p.search(text) for p in DIM_PATTERNS):
                info["qna_lines"].append({"line": ln, "text": text[:240]})
            continue
        hits = [m.group(0).strip() for p in DIM_PATTERNS for m in p.finditer(text)]
        if hits:
            info["dim_lines"].append({"line": ln, "section": (section or "머리") + (" > " + sub if sub else ""), "text": text[:240]})
    # 옵션 이름: 머리 영역에서 사이즈 낱말이 든 짧은 줄(옵션 셀렉트 제목)
    if ti is not None:
        for l in lines[ti:ti + 60]:
            s = l.strip()
            if s.startswith("## "):
                break
            if 0 < len(s) < 60 and any(w in s for w in ("사이즈", "옵션", "규격", "크기")) and not s.startswith(("[", "!", "*", "#")):
                info["options"].append(s)
    return info


def fmt_page(p):
    out = ["## {}".format(p["title"] or p["page_title"]), "- 주소: {}".format(p["url"])]
    if p["category"]:
        out.append("- 분류: {}".format(" > ".join(p["category"])))
    out.append("- 브랜드: {}".format(p["brand"] or "미상"))
    out.append("- 가격: {}".format("{:,}원".format(p["price"]) if p["price"] is not None else "미상"))
    out.append("- 평점: {} · 리뷰 {}".format(p["rating"] if p["rating"] is not None else "미상",
                                         "{:,}".format(p["review_count"]) if p["review_count"] is not None else "미상"))
    out.append("- 대표 사진: {}".format(p["image"] or "못 찾음"))
    if p["options"]:
        out.append("- 옵션 제목: " + " / ".join(p["options"]))
    if p["spec_table"]:
        for k in ("품명", "모델명", "크기", "치수", "규격", "사이즈"):
            if k in p["spec_table"]:
                out.append("- 상품정보 표 [{}]: {}".format(k, p["spec_table"][k]))
    out.append("\n### 실측 후보 줄 ({}개)".format(len(p["dim_lines"])))
    for d in p["dim_lines"][:60]:
        out.append("- L{} [{}] {}".format(d["line"], d["section"], d["text"]))
    if len(p["dim_lines"]) > 60:
        out.append("- … {}줄 더 (--json 으로 전부 본다)".format(len(p["dim_lines"]) - 60))
    out.append("\n### Q&A 중 크기 언급 ({}개)".format(len(p["qna_lines"])))
    for d in p["qna_lines"][:30]:
        out.append("- L{} {}".format(d["line"], d["text"]))
    out.append("\n### 사이즈표로 보이는 상세 이미지 ({} / 상세 이미지 {}장)".format(len(p["size_images"]), len(p["detail_images"])))
    for u in p["size_images"]:
        out.append("- " + u)
    if not p["size_images"] and p["detail_images"]:
        out.append("- (이름으로는 못 찾았다 — --all-images 로 받아 직접 본다)")
    return "\n".join(out)


def download(urls, dest, limit=8000000):
    import urllib.request
    if os.path.exists(dest) and os.listdir(dest):
        raise SystemExit("{} 가 비어 있지 않다 — 내려받기는 새 빈 디렉터리에만 한다".format(dest))
    os.makedirs(dest, exist_ok=True)
    saved = []
    for n, u in enumerate(urls, 1):
        if not u.startswith("https://"):
            continue
        req = urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"})
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                ct = r.headers.get_content_type()
                data = r.read(limit + 1)
        except Exception as e:
            sys.stderr.write("실패 {}: {}\n".format(e.__class__.__name__, u))
            continue
        if not ct.startswith("image/") or ct == "image/svg+xml" or len(data) > limit:
            sys.stderr.write("건너뜀({} · {}바이트): {}\n".format(ct, len(data), u))
            continue
        ext = {"image/jpeg": ".jpg", "image/png": ".png", "image/gif": ".gif", "image/webp": ".webp"}.get(ct, ".img")
        path = os.path.join(dest, "{:02d}{}".format(n, ext))
        with open(path, "wb") as f:
            f.write(data)
        saved.append((path, u))
    return saved


def main(argv=None):
    ap = argparse.ArgumentParser(description="오늘의집 상품 페이지에서 실측 후보·리뷰 정보 뽑기")
    ap.add_argument("page", help="Tavily extract 결과를 저장한 파일")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--download", metavar="DIR", help="사이즈표 후보 이미지를 받을 새 빈 디렉터리")
    ap.add_argument("--all-images", action="store_true", help="상세 이미지 전부를 받는다")
    a = ap.parse_args(argv)
    with open(a.page, encoding="utf-8", errors="replace") as f:
        text = f.read()
    pages = [summarize(*p) for p in split_pages(text)]
    if not pages:
        raise SystemExit("페이지를 못 찾았다 — Tavily extract 결과 파일인지 확인한다")
    if a.json:
        print(json.dumps(pages, ensure_ascii=False, indent=2))
    else:
        print("\n\n".join(fmt_page(p) for p in pages))
    if a.download:
        urls = []
        for p in pages:
            for u in (p["detail_images"] if a.all_images else p["size_images"]):
                if u not in urls:
                    urls.append(u)
        if not urls:
            print("\n받을 이미지가 없다" + ("" if a.all_images else " — --all-images 를 붙여 본다"))
            return 0
        saved = download(urls, a.download)
        print("\n받은 이미지 {}장 → {}".format(len(saved), a.download))
        for path, u in saved:
            print("- {}  ← {}".format(path, u))
    return 0


if __name__ == "__main__":
    sys.exit(main())
