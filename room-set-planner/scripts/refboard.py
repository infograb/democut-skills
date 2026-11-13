#!/usr/bin/env python3
"""레퍼런스 사진 모으기·훑기·고르게 보여 주기.

  refboard.py pins EXTRACT.txt... --download DIR   # 핀터레스트 페이지에서 핀 사진 주소를 뽑아 새 빈 디렉터리에 받는다
  refboard.py sheet DIR -o OUT                      # 받은 사진을 번호 붙인 모음 시트(JPEG)로 — 훑어볼 때(Pillow 필요)
  refboard.py board CHOICES.json -o board.html     # 고를 선택지를 사진과 함께 HTML 한 장으로 — 사용자에게 보여 줄 때

pins 는 Tavily extract 결과를 저장한 텍스트에서 i.pinimg.com 주소를 찾는다. 같은 핀은 한 번만 받는다.
board 의 CHOICES.json 꼴은 references/style-research.md 「보여 주고 고르게 한다」.
"""
import argparse
import base64
import html
import json
import os
import re
import sys

PIN_RE = re.compile(r"https://i\.pinimg\.com/(?:\d+x|originals)/([0-9a-f]{2}/[0-9a-f]{2}/[0-9a-f]{2}/[0-9a-f]{32})\.(jpg|jpeg|png|webp)")
URL_LINE = re.compile(r"^URL:\s*(\S+)")
MIME = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp", ".gif": "image/gif"}


def find_pins(texts):
    """(핀 해시, 확장자, 그 핀이 나온 페이지 주소) 를 처음 나온 순서대로."""
    seen, out = set(), []
    for text in texts:
        page = ""
        for line in text.splitlines():
            m = URL_LINE.match(line.strip())
            if m:
                page = m.group(1)
            for h, ext in PIN_RE.findall(line):
                if h not in seen:
                    seen.add(h)
                    out.append((h, ext, page))
    return out


def download(pins, dest, size, limit=4000000):
    import urllib.request
    if os.path.exists(dest) and os.listdir(dest):
        raise SystemExit("{} 가 비어 있지 않다 — 내려받기는 새 빈 디렉터리에만 한다".format(dest))
    os.makedirs(dest, exist_ok=True)
    index = []
    for n, (h, ext, page) in enumerate(pins, 1):
        pid = "P{:03d}".format(n)
        url = "https://i.pinimg.com/{}/{}.{}".format(size, h, ext)
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                ct = r.headers.get_content_type()
                data = r.read(limit + 1)
        except Exception as e:
            sys.stderr.write("실패 {} {}: {}\n".format(pid, e.__class__.__name__, url))
            continue
        if ct not in MIME.values() or len(data) > limit:
            sys.stderr.write("건너뜀 {}({} · {}바이트): {}\n".format(pid, ct, len(data), url))
            continue
        fname = pid + {v: k for k, v in MIME.items() if k != ".jpeg"}[ct]
        with open(os.path.join(dest, fname), "wb") as f:
            f.write(data)
        index.append({"id": pid, "file": fname, "image": "https://i.pinimg.com/736x/{}.{}".format(h, ext), "page": page})
    with open(os.path.join(dest, "index.json"), "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=1)
    return index


def cmd_pins(a):
    texts = []
    for p in a.extract:
        with open(p, encoding="utf-8", errors="replace") as f:
            texts.append(f.read())
    pins = find_pins(texts)
    if not pins:
        raise SystemExit("핀 사진 주소(i.pinimg.com)를 못 찾았다 — Tavily extract 를 include_images 로 받았는지 본다")
    pages = {}
    for _, _, page in pins:
        pages[page] = pages.get(page, 0) + 1
    print("핀 {}개 · 페이지 {}개".format(len(pins), len(pages)))
    for page, n in pages.items():
        print("  {:3d}  {}".format(n, page or "(페이지 주소 없음)"))
    if a.download:
        index = download(pins[: a.max], a.download, a.size)
        print("받음 {}개 → {} (index.json 에 번호·원래 주소·페이지)".format(len(index), a.download))


def cmd_sheet(a):
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        raise SystemExit("Pillow 가 없다 — 모음 시트 대신 사진을 하나씩 Read 로 본다(474px 이면 한 장에 작다)")
    files = sorted(f for f in os.listdir(a.dir) if os.path.splitext(f)[1].lower() in MIME)
    if not files:
        raise SystemExit("{} 에 사진이 없다".format(a.dir))
    os.makedirs(a.out, exist_ok=True)
    W, H, C = 250, 330, 6
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 26)
    except Exception:
        font = ImageFont.load_default()
    for s in range(0, len(files), a.per):
        chunk = files[s : s + a.per]
        rows = (len(chunk) + C - 1) // C
        sheet = Image.new("RGB", (C * W, rows * H), "white")
        d = ImageDraw.Draw(sheet)
        for k, fname in enumerate(chunk):
            try:
                im = Image.open(os.path.join(a.dir, fname)).convert("RGB")
            except Exception:
                continue
            im.thumbnail((W - 6, H - 6))
            x, y = (k % C) * W, (k // C) * H
            sheet.paste(im, (x + 3, y + 3))
            label = os.path.splitext(fname)[0]
            d.rectangle([x + 3, y + 3, x + 84, y + 34], fill="black")
            d.text((x + 7, y + 5), label, fill="yellow", font=font)
        p = os.path.join(a.out, "sheet{}.jpg".format(s // a.per + 1))
        sheet.save(p, quality=80)
        print(p, len(chunk))


def _img_src(path):
    ext = os.path.splitext(path)[1].lower()
    if ext not in MIME or not os.path.isfile(path):
        return None
    with open(path, "rb") as f:
        return "data:{};base64,{}".format(MIME[ext], base64.b64encode(f.read()).decode())


def cmd_board(a):
    with open(a.choices, encoding="utf-8") as f:
        spec = json.load(f)
    base = os.path.dirname(os.path.abspath(a.choices))
    root = spec.get("images_dir")
    root = os.path.join(base, root) if root and not os.path.isabs(root) else (root or base)
    e = html.escape
    parts = []
    missing = []
    for g in spec.get("groups", []):
        cells = []
        for im in g.get("images", []):
            src = _img_src(os.path.join(root, im["file"]))
            if src is None:
                missing.append(im["file"])
                continue
            cap = e(im.get("caption", ""))
            link = im.get("link")
            cap = '<a href="{}" target="_blank" rel="noopener">{}</a>'.format(e(link), cap or "원본") if link else cap
            cells.append('<figure><img src="{}" alt=""><figcaption>{}</figcaption></figure>'.format(src, cap))
        text = "".join("<li>{}</li>".format(e(t)) for t in g.get("text", []))
        parts.append('<section><h2>{}</h2>{}<div class="grid">{}</div></section>'.format(
            e(g.get("name", "")), "<ul>{}</ul>".format(text) if text else "", "".join(cells)))
    doc = """<!doctype html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>{title}</title>
<style>
:root {{ --bg:#fafaf8; --fg:#222; --muted:#666; --line:#e4e2dc; }}
@media (prefers-color-scheme: dark) {{ :root {{ --bg:#1b1b1a; --fg:#eee; --muted:#aaa; --line:#333; }} }}
body {{ margin:0; padding:24px 16px 48px; background:var(--bg); color:var(--fg);
  font:15px/1.6 -apple-system, "Apple SD Gothic Neo", "Noto Sans KR", sans-serif; }}
main {{ max-width:1100px; margin:0 auto; }}
h1 {{ font-size:22px; margin:0 0 4px; }} .intro {{ color:var(--muted); margin:0 0 24px; white-space:pre-line; }}
section {{ border-top:1px solid var(--line); padding:20px 0; }} h2 {{ font-size:18px; margin:0 0 8px; }}
ul {{ margin:0 0 12px; padding-left:20px; }}
.grid {{ display:grid; grid-template-columns:repeat(auto-fill, minmax(180px, 1fr)); gap:10px; }}
figure {{ margin:0; }} img {{ width:100%; aspect-ratio:3/4; object-fit:cover; border-radius:6px; display:block; }}
figcaption {{ font-size:12px; color:var(--muted); margin-top:4px; }} a {{ color:inherit; }}
</style></head><body><main><h1>{title}</h1><p class="intro">{intro}</p>{body}</main></body></html>""".format(
        title=e(spec.get("title", "고를 선택지")), intro=e(spec.get("intro", "")), body="".join(parts))
    with open(a.out, "w", encoding="utf-8") as f:
        f.write(doc)
    print("{} 저장 · 묶음 {}개".format(a.out, len(spec.get("groups", []))))
    if missing:
        sys.stderr.write("못 찾은 사진: {}\n".format(", ".join(missing)))


def main(argv=None):
    ap = argparse.ArgumentParser(description="레퍼런스 사진 모으기·훑기·고르게 보여 주기")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("pins", help="Tavily extract 결과에서 핀 사진을 뽑아 받는다")
    p.add_argument("extract", nargs="+", help="Tavily extract 결과를 저장한 파일(여럿 가능)")
    p.add_argument("--download", metavar="DIR", help="받을 새 빈 디렉터리")
    p.add_argument("--size", default="474x", help="받을 크기(236x·474x·736x, 기본 474x)")
    p.add_argument("--max", type=int, default=120, help="받을 핀 수 상한(기본 120)")
    p.set_defaults(fn=cmd_pins)
    p = sub.add_parser("sheet", help="받은 사진을 번호 붙인 모음 시트로(Pillow 필요)")
    p.add_argument("dir")
    p.add_argument("-o", "--out", required=True)
    p.add_argument("--per", type=int, default=24)
    p.set_defaults(fn=cmd_sheet)
    p = sub.add_parser("board", help="선택지를 사진과 함께 HTML 한 장으로")
    p.add_argument("choices", help="선택지 JSON")
    p.add_argument("-o", "--out", required=True)
    p.set_defaults(fn=cmd_board)
    a = ap.parse_args(argv)
    a.fn(a)


if __name__ == "__main__":
    main()
