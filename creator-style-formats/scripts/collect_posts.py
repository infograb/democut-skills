#!/usr/bin/env python3
"""creator-style-formats: 공개 숏폼의 메타데이터를 한 표로 모은다.

영상 파일은 받지 않는다. yt-dlp 는 --skip-download 로 제목·캡션·길이·조회수 같은
공개 메타데이터만 읽고, 자막·썸네일은 옵션이다. 조회수가 없으면 0 으로 채우지 않고
순위에서도 뺀다. 같은 작성자 안에서 조회수 중앙값보다 높은 글을 상위로 표시한다.

표준 라이브러리만 쓴다(Python 3.8+). yt-dlp·ffmpeg 는 그 기능이 필요할 때만 PATH 에 있으면 된다.

  python3 collect_posts.py fetch URL [URL...] --out DIR [--limit 30] [--subs] [--thumbnails]
  python3 collect_posts.py normalize DUMP.json [DUMP.json...] --out DIR
  python3 collect_posts.py youtube-api TARGET --out DIR [--limit 30]
  python3 collect_posts.py oembed URL [URL...] --out DIR
  python3 collect_posts.py cues FILE.vtt [--to 6]
  python3 collect_posts.py frames VIDEO --out DIR [--every 1]

TARGET 은 @핸들, 채널 URL, 채널 id(UC…)다. 유튜브 데이터 API 키는 환경 변수
YOUTUBE_API_KEY 만 읽는다. 인자로 받지 않는다.

출력 디렉터리는 없거나 비어 있어야 한다. 받은 원문은 raw/ 에 두고, 표는 posts.json·posts.csv 다.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

SCHEMA = "creator-style-formats.posts.v1"
HIDDEN = {
    "private",
    "needs_auth",
    "subscriber_only",
    "premium_only",
    "unlisted",
    "login_required",
}
PAGE_HOSTS = ("youtube.com", "youtu.be", "instagram.com", "tiktok.com")
HASHTAG = re.compile(r"(?<![\w/])#([\w]+)", re.UNICODE)
ISO_DURATION = re.compile(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?$")
VTT_TIME = re.compile(
    r"(?:(\d+):)?(\d{2}):(\d{2})[.](\d{1,3})\s*-->\s*(?:(\d+):)?(\d{2}):(\d{2})[.](\d{1,3})"
)
YOUTUBE_API = "https://www.googleapis.com/youtube/v3"


def median(values):
    nums = sorted(values)
    n = len(nums)
    if n == 0:
        return None
    if n % 2 == 1:
        return nums[n // 2]
    return (nums[n // 2 - 1] + nums[n // 2]) / 2.0


def percentile(values, p):
    nums = sorted(values)
    n = len(nums)
    if n == 0:
        return None
    if n == 1:
        return nums[0]
    k = (n - 1) * (p / 100.0)
    lo = int(math.floor(k))
    hi = int(math.ceil(k))
    if lo == hi:
        return nums[lo]
    frac = k - lo
    return nums[lo] * (1 - frac) + nums[hi] * frac


def as_int(value):
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int):
        return value if value >= 0 else None
    if isinstance(value, float) and value >= 0 and value == int(value):
        return int(value)
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return None


def as_float(value):
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)) and value >= 0:
        return float(value)
    if isinstance(value, str):
        try:
            num = float(value)
        except ValueError:
            return None
        return num if num >= 0 else None
    return None


def hashtags(text):
    found = []
    seen = set()
    for tag in HASHTAG.findall(text or ""):
        key = tag.lower()
        if key in seen:
            continue
        seen.add(key)
        found.append(tag)
    return found


def merge_tags(text, tags):
    found = hashtags(text)
    seen = {tag.lower() for tag in found}
    for tag in tags or []:
        if not isinstance(tag, str):
            continue
        cleaned = tag.strip().lstrip("#")
        if not cleaned or cleaned.lower() in seen:
            continue
        seen.add(cleaned.lower())
        found.append(cleaned)
    return found


def platform_of(url, extractor):
    blob = "%s %s" % ((extractor or ""), (url or ""))
    low = blob.lower()
    if "youtube" in low or "youtu.be" in low:
        return "youtube"
    if "instagram" in low:
        return "instagram"
    if "tiktok" in low:
        return "tiktok"
    return "unknown"


def aspect_label(width, height):
    w = as_int(width)
    h = as_int(height)
    if not w or not h:
        return None
    ratio = w / float(h)
    known = (("9:16", 9 / 16.0), ("4:5", 4 / 5.0), ("1:1", 1.0), ("16:9", 16 / 9.0))
    for name, target in known:
        if abs(ratio - target) / target <= 0.04:
            return name
    g = math.gcd(w, h)
    return "%d:%d" % (w // g, h // g)


def short_form(url, width, height, platform):
    low = (url or "").lower()
    if "/shorts/" in low or "/reel/" in low or "/reels/" in low:
        return True
    if platform == "tiktok" or "tiktok.com" in low:
        return True
    w = as_int(width)
    h = as_int(height)
    if w and h and h > w * 1.2:
        return True
    if w and h and w > h * 1.2:
        return False
    return None


def iso_day(upload_date):
    if isinstance(upload_date, str) and re.fullmatch(r"\d{8}", upload_date):
        return "%s-%s-%s" % (upload_date[0:4], upload_date[4:6], upload_date[6:8])
    return None


def day_from_timestamp(timestamp):
    num = as_int(timestamp)
    if num is None:
        return None
    try:
        return datetime.fromtimestamp(num, timezone.utc).date().isoformat()
    except (OverflowError, OSError, ValueError):
        return None


def parse_iso8601_duration(text):
    if not text or not isinstance(text, str):
        return None
    match = ISO_DURATION.fullmatch(text.strip())
    if not match:
        return None
    hours = int(match.group(1) or 0)
    minutes = int(match.group(2) or 0)
    seconds = int(match.group(3) or 0)
    if match.group(1) is None and match.group(2) is None and match.group(3) is None:
        return None
    return hours * 3600 + minutes * 60 + seconds


def page_url(entry, platform):
    for key in ("webpage_url", "original_url"):
        value = entry.get(key)
        if isinstance(value, str) and value.startswith("http") and "googlevideo.com" not in value:
            return value
    value = entry.get("url")
    if isinstance(value, str) and value.startswith("http") and "googlevideo.com" not in value:
        if any(host in value for host in PAGE_HOSTS):
            return value
    video_id = entry.get("id")
    if platform == "youtube" and isinstance(video_id, str) and video_id:
        return "https://www.youtube.com/watch?v=" + video_id
    return None


def caption_of(entry):
    for key in ("description", "caption"):
        value = entry.get(key)
        if isinstance(value, str) and value.strip():
            text = value.strip()
            if len(text) > 8000:
                return text[:8000], True
            return text, False
    return "", False


def iter_entries(dump):
    if isinstance(dump, list):
        for item in dump:
            if isinstance(item, dict):
                yield item
        return
    if not isinstance(dump, dict):
        return
    entries = dump.get("entries")
    if isinstance(entries, list):
        for item in entries:
            if isinstance(item, dict):
                yield item
        return
    if dump.get("id") or dump.get("webpage_url") or dump.get("title"):
        yield dump


def normalize_entry(entry):
    extractor = entry.get("extractor_key") or entry.get("extractor") or entry.get("ie_key")
    url_hint = entry.get("webpage_url") or entry.get("original_url") or entry.get("url") or ""
    platform = platform_of(url_hint if isinstance(url_hint, str) else "", extractor)
    availability = entry.get("availability")
    if isinstance(availability, str) and availability.lower() in HIDDEN:
        return None, "hidden"
    url = page_url(entry, platform)
    width = as_int(entry.get("width"))
    height = as_int(entry.get("height"))
    caption, truncated = caption_of(entry)
    title = entry.get("title") if isinstance(entry.get("title"), str) else ""
    tags = entry.get("tags") if isinstance(entry.get("tags"), list) else []
    creator = entry.get("channel") or entry.get("uploader") or entry.get("creator") or ""
    if not isinstance(creator, str):
        creator = ""
    creator_id = entry.get("channel_id") or entry.get("uploader_id") or ""
    if not isinstance(creator_id, str):
        creator_id = ""
    upload = iso_day(entry.get("upload_date")) or day_from_timestamp(entry.get("timestamp"))
    subs = entry.get("subtitles") if isinstance(entry.get("subtitles"), dict) else {}
    auto = entry.get("automatic_captions") if isinstance(entry.get("automatic_captions"), dict) else {}
    post = {
        "platform": platform,
        "id": entry.get("id") if isinstance(entry.get("id"), str) else "",
        "url": url or "",
        "creator": creator,
        "creator_id": creator_id,
        "title": title,
        "caption": caption,
        "caption_truncated": truncated,
        "hashtags": merge_tags("%s\n%s" % (title, caption), tags),
        "duration_s": as_float(entry.get("duration")),
        "width": width,
        "height": height,
        "aspect": aspect_label(width, height),
        "view_count": as_int(entry.get("view_count")),
        "like_count": as_int(entry.get("like_count")),
        "comment_count": as_int(entry.get("comment_count")),
        "upload_date": upload,
        "thumbnail_url": entry.get("thumbnail") if isinstance(entry.get("thumbnail"), str) else "",
        "subtitle_langs": sorted(set(list(subs) + list(auto))),
        "is_short_form": short_form(url or "", width, height, platform),
        "availability": availability if isinstance(availability, str) else None,
    }
    return post, None


def creator_key(post):
    return "%s|%s" % (post["platform"], post["creator_id"] or post["creator"] or "unknown")


def rank_posts(posts):
    groups = {}
    for post in posts:
        groups.setdefault(creator_key(post), []).append(post)
    summaries = []
    for key, group in sorted(groups.items()):
        ranked = [p for p in group if p["view_count"] is not None]
        views = [p["view_count"] for p in ranked]
        durations = [p["duration_s"] for p in group if p["duration_s"] is not None]
        view_median = median(views)
        ordered = sorted(ranked, key=lambda p: (-p["view_count"], p["id"], p["url"]))
        place = {}
        for index, post in enumerate(ordered, start=1):
            place[id(post)] = index
        top = []
        for post in group:
            if post["view_count"] is None or view_median is None:
                post["rank"] = {
                    "view_median": view_median,
                    "views_over_median": None,
                    "band": "unranked",
                    "rank_in_creator": None,
                }
                continue
            if post["view_count"] > view_median:
                band = "above_median"
            elif post["view_count"] < view_median:
                band = "below_median"
            else:
                band = "at_median"
            ratio = None
            if view_median:
                ratio = round(post["view_count"] / float(view_median), 2)
            post["rank"] = {
                "view_median": view_median,
                "views_over_median": ratio,
                "band": band,
                "rank_in_creator": place[id(post)],
            }
            if band == "above_median":
                top.append(post)
        top.sort(key=lambda p: (-p["view_count"], p["id"]))
        sample = group[0]
        summaries.append({
            "platform": sample["platform"],
            "creator": sample["creator"],
            "creator_id": sample["creator_id"],
            "post_count": len(group),
            "ranked_count": len(ranked),
            "view_median": view_median,
            "view_p75": percentile(views, 75),
            "duration_median_s": median(durations),
            "top_posts": [
                {
                    "id": p["id"],
                    "url": p["url"],
                    "title": p["title"],
                    "view_count": p["view_count"],
                    "views_over_median": p["rank"]["views_over_median"],
                    "duration_s": p["duration_s"],
                }
                for p in top
            ],
        })
    return {
        "post_count": len(posts),
        "ranked_count": sum(1 for p in posts if p["view_count"] is not None),
        "creators": summaries,
    }


def combine_dumps(dumps):
    posts = []
    notes = []
    hidden = 0
    seen = set()
    for dump in dumps:
        for entry in iter_entries(dump):
            post, flag = normalize_entry(entry)
            if flag == "hidden":
                hidden += 1
                continue
            if post is None:
                continue
            if not post["id"] and not post["url"] and not post["title"]:
                continue
            key = (post["platform"], post["id"] or post["url"])
            if key in seen:
                notes.append("같은 글을 두 번 받아 한 번만 남겼다: %s" % (post["id"] or post["url"]))
                continue
            seen.add(key)
            posts.append(post)
    if hidden:
        notes.append("비공개·제한·일부 공개 %d건은 표에서 뺐다." % hidden)
    missing_views = sum(1 for p in posts if p["view_count"] is None)
    if missing_views:
        notes.append("조회수가 없는 %d건은 0 으로 넣지 않았고 중앙값 순위에서 뺐다." % missing_views)
    unknown_shape = sum(1 for p in posts if p["is_short_form"] is None)
    if unknown_shape:
        notes.append("세로인지 응답만으로 알 수 없는 글이 %d건이다. 숏폼 여부는 비워 두었다." % unknown_shape)
    return posts, notes


def document(posts, notes, errors, tool):
    return {
        "schema": SCHEMA,
        "collected_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "tool": tool,
        "notes": notes,
        "errors": errors,
        "summary": rank_posts(posts),
        "posts": posts,
    }


def write_table(doc, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    json_path = os.path.join(out_dir, "posts.json")
    csv_path = os.path.join(out_dir, "posts.csv")
    with open(json_path, "w", encoding="utf-8") as handle:
        json.dump(doc, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    columns = [
        "platform", "id", "url", "creator", "creator_id", "title", "duration_s",
        "view_count", "like_count", "comment_count", "upload_date", "width", "height",
        "aspect", "is_short_form", "view_median", "views_over_median", "band",
        "rank_in_creator", "hashtags", "thumbnail_url",
    ]
    with open(csv_path, "w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for post in doc["posts"]:
            rank = post.get("rank") or {}
            row = {key: post.get(key) for key in columns}
            row["view_median"] = rank.get("view_median")
            row["views_over_median"] = rank.get("views_over_median")
            row["band"] = rank.get("band")
            row["rank_in_creator"] = rank.get("rank_in_creator")
            row["hashtags"] = " ".join("#" + tag for tag in post.get("hashtags") or [])
            writer.writerow({key: "" if row[key] is None else row[key] for key in columns})
    return json_path, csv_path


def print_summary(doc, json_path, csv_path):
    summary = doc["summary"]
    print("글 %d · 조회수 있는 글 %d" % (summary["post_count"], summary["ranked_count"]))
    for creator in summary["creators"]:
        median_text = "없음" if creator["view_median"] is None else ("%g" % creator["view_median"])
        tops = creator["top_posts"][:5]
        top_text = ", ".join(
            "%s (%s배)" % (item["id"] or item["url"], item["views_over_median"])
            if item["views_over_median"] is not None
            else (item["id"] or item["url"])
            for item in tops
        ) or "없음"
        print("%s %s 조회수 중앙값 %s · 길이 중앙값 %s · 중앙값 초과 %s" % (
            creator["platform"],
            creator["creator"] or creator["creator_id"] or "(작성자 없음)",
            median_text,
            "없음" if creator["duration_median_s"] is None else ("%g초" % creator["duration_median_s"]),
            top_text,
        ))
    for note in doc["notes"]:
        print("참고: " + note)
    for error in doc["errors"]:
        print("오류: %s" % error.get("url", ""))
    print(json_path)
    print(csv_path)


def prepare_out(path):
    if not path:
        sys.exit("--out 디렉터리가 필요하다.")
    full = os.path.abspath(path)
    if os.path.exists(full):
        if not os.path.isdir(full) or os.listdir(full):
            sys.exit("출력 디렉터리가 비어 있지 않다. 새 디렉터리를 쓴다: " + full)
    else:
        os.makedirs(full)
    return full


def public_http_url(url):
    parsed = urllib.parse.urlparse(url or "")
    return parsed.scheme in ("http", "https") and bool(parsed.netloc)


def ytdlp_dump_argv(binary, url, limit, sleep_requests):
    if limit < 1 or limit > 50:
        raise ValueError("limit 은 1 이상 50 이하다.")
    if sleep_requests < 0:
        raise ValueError("sleep 은 0 이상이다.")
    return [
        binary,
        "--ignore-config",
        "--no-update",
        "--dump-single-json",
        "--skip-download",
        "--no-warnings",
        "--no-progress",
        "--sleep-requests",
        "%g" % sleep_requests,
        "--playlist-items",
        "1:%d" % limit,
        url,
    ]


def ytdlp_subs_argv(binary, url, limit, sleep_requests, sub_langs, out_dir):
    argv = ytdlp_dump_argv(binary, url, limit, sleep_requests)
    argv = [arg for arg in argv if arg != "--dump-single-json"]
    argv[1:1] = [
        "--write-subs",
        "--write-auto-subs",
        "--sub-langs",
        sub_langs,
        "--convert-subs",
        "vtt",
        "--output",
        os.path.join(out_dir, "subs", "%(id)s.%(ext)s"),
    ]
    return argv


def ytdlp_thumb_argv(binary, url, limit, sleep_requests, out_dir):
    argv = ytdlp_dump_argv(binary, url, limit, sleep_requests)
    argv = [arg for arg in argv if arg != "--dump-single-json"]
    argv[1:1] = [
        "--write-thumbnail",
        "--convert-thumbnails",
        "jpg",
        "--output",
        os.path.join(out_dir, "thumbs", "%(id)s.%(ext)s"),
    ]
    return argv


def default_runner(argv, timeout):
    proc = subprocess.run(argv, capture_output=True, timeout=timeout)
    stdout = proc.stdout.decode("utf-8", "replace")
    stderr = proc.stderr.decode("utf-8", "replace")
    return proc.returncode, stdout, stderr


def load_json(text, label):
    try:
        return json.loads(text), None
    except json.JSONDecodeError as exc:
        return None, "%s JSON 이 아니다: %s" % (label, exc)


def fetch_urls(urls, out, limit, sleep_requests, subs, sub_langs, thumbnails, timeout, runner, binary):
    for url in urls:
        if not public_http_url(url):
            sys.exit("http(s) 공개 주소만 받는다: " + url)
    out = prepare_out(out)
    raw = os.path.join(out, "raw")
    os.makedirs(raw)
    dumps = []
    errors = []
    for index, url in enumerate(urls):
        argv = ytdlp_dump_argv(binary, url, limit, sleep_requests)
        try:
            code, stdout, stderr = runner(argv, timeout)
        except subprocess.TimeoutExpired:
            code, stdout, stderr = 124, "", "시간 초과"
        with open(os.path.join(raw, "%d.json" % index), "w", encoding="utf-8") as handle:
            handle.write(stdout)
        with open(os.path.join(raw, "%d.err" % index), "w", encoding="utf-8") as handle:
            handle.write(stderr[-4000:])
        if code != 0 or not stdout.strip():
            tail = [line for line in stderr.strip().splitlines()[-5:] if line.strip()]
            errors.append({"url": url, "exit": code, "stderr": tail})
            continue
        dump, err = load_json(stdout, url)
        if err:
            errors.append({"url": url, "exit": code, "stderr": [err]})
            continue
        dumps.append(dump)
        if subs:
            os.makedirs(os.path.join(out, "subs"), exist_ok=True)
            extra = ytdlp_subs_argv(binary, url, limit, sleep_requests, sub_langs, out)
            try:
                code, _stdout, stderr = runner(extra, timeout)
            except subprocess.TimeoutExpired:
                code, stderr = 124, "시간 초과"
            if code != 0:
                errors.append({"url": url, "exit": code, "stderr": ["자막을 받지 못했다", stderr.strip()[-300:]]})
        if thumbnails:
            os.makedirs(os.path.join(out, "thumbs"), exist_ok=True)
            extra = ytdlp_thumb_argv(binary, url, limit, sleep_requests, out)
            try:
                code, _stdout, stderr = runner(extra, timeout)
            except subprocess.TimeoutExpired:
                code, stderr = 124, "시간 초과"
            if code != 0:
                errors.append({"url": url, "exit": code, "stderr": ["썸네일 파일을 받지 못했다", stderr.strip()[-300:]]})
    posts, notes = combine_dumps(dumps)
    notes.insert(0, "영상 파일은 받지 않았다. yt-dlp 는 --skip-download 로 메타데이터만 읽었다.")
    if not dumps:
        notes.append("메타데이터를 한 건도 받지 못했다. 스타일 프로파일을 이 표로 확정하지 않는다.")
    doc = document(posts, notes, errors, {"name": "yt-dlp", "mode": "dump-json"})
    json_path, csv_path = write_table(doc, out)
    print_summary(doc, json_path, csv_path)
    if not posts:
        return 1
    return 0


def normalize_files(paths, out):
    dumps = []
    errors = []
    for path in paths:
        with open(path, encoding="utf-8") as handle:
            dump, err = load_json(handle.read(), path)
        if err:
            errors.append({"url": path, "exit": 1, "stderr": [err]})
            continue
        dumps.append(dump)
    posts, notes = combine_dumps(dumps)
    notes.append("이 표는 이미 받아 둔 JSON 을 정규화한 것이다. 받는 시각의 원본은 raw 파일이 들고 있다.")
    doc = document(posts, notes, errors, {"name": "collect_posts.normalize", "mode": "file"})
    out = prepare_out(out)
    json_path, csv_path = write_table(doc, out)
    print_summary(doc, json_path, csv_path)
    return 0 if posts else 1


def parse_youtube_target(text):
    raw = (text or "").strip()
    shorts_tab = "/shorts" in raw
    if raw.startswith("@"):
        return {"handle": raw[1:], "shorts_tab": shorts_tab}
    handle = re.search(r"youtube\.com/@([^/?#]+)", raw)
    if handle:
        return {"handle": urllib.parse.unquote(handle.group(1)), "shorts_tab": shorts_tab}
    channel = re.search(r"youtube\.com/channel/(UC[\w-]+)", raw)
    if channel:
        return {"channel_id": channel.group(1), "shorts_tab": shorts_tab}
    if re.fullmatch(r"UC[\w-]{20,}", raw):
        return {"channel_id": raw, "shorts_tab": False}
    return None


def redact(text, secret):
    if text is None:
        return ""
    cleaned = str(text)
    if secret:
        cleaned = cleaned.replace(secret, "[key]")
    return re.sub(r"(key=)[^&\s]+", r"\1[key]", cleaned)


def api_get(opener, path, params, key, sleep_s):
    if sleep_s:
        time.sleep(sleep_s)
    query = dict(params)
    query["key"] = key
    url = YOUTUBE_API + path + "?" + urllib.parse.urlencode(query)
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with opener.open(request, timeout=30) as response:
            payload = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", "replace")
        raise RuntimeError(redact("HTTP %s %s" % (exc.code, body[:500]), key))
    except urllib.error.URLError as exc:
        raise RuntimeError(redact(str(exc.reason), key))
    data, err = load_json(payload, "youtube-api")
    if err:
        raise RuntimeError(err)
    if isinstance(data, dict) and data.get("error"):
        raise RuntimeError(redact(json.dumps(data["error"], ensure_ascii=False)[:500], key))
    return data


def youtube_collect(target_text, key, limit, opener, sleep_s):
    target = parse_youtube_target(target_text)
    if not target:
        raise RuntimeError("유튜브 채널 핸들·채널 URL·채널 id 만 받는다.")
    if limit < 1 or limit > 50:
        raise RuntimeError("limit 은 1 이상 50 이하다.")
    notes = []
    hidden = 0
    if "handle" in target:
        channel = api_get(opener, "/channels", {
            "part": "snippet,contentDetails",
            "forHandle": target["handle"],
        }, key, 0)
    else:
        channel = api_get(opener, "/channels", {
            "part": "snippet,contentDetails",
            "id": target["channel_id"],
        }, key, 0)
    items = channel.get("items") or []
    if not items:
        raise RuntimeError("채널을 찾지 못했다.")
    snippet = items[0].get("snippet") or {}
    related = (items[0].get("contentDetails") or {}).get("relatedPlaylists") or {}
    uploads = related.get("uploads")
    if not uploads:
        raise RuntimeError("업로드 재생목록 id 가 응답에 없다.")
    if target.get("shorts_tab"):
        notes.append("숏츠 탭 주소를 받았지만 데이터 API 업로드 목록은 숏츠만이 아니다. 세로 여부는 비운다.")
    playlist_items = []
    token = None
    while len(playlist_items) < limit:
        params = {
            "part": "snippet,contentDetails",
            "playlistId": uploads,
            "maxResults": min(50, limit - len(playlist_items)),
        }
        if token:
            params["pageToken"] = token
        page = api_get(opener, "/playlistItems", params, key, sleep_s if playlist_items else 0)
        playlist_items.extend(page.get("items") or [])
        token = page.get("nextPageToken")
        if not token:
            break
    ids = []
    for item in playlist_items:
        resource = ((item.get("snippet") or {}).get("resourceId") or {})
        content = item.get("contentDetails") or {}
        video_id = resource.get("videoId") or content.get("videoId")
        if video_id:
            ids.append(video_id)
    videos = []
    for start in range(0, len(ids), 50):
        chunk = ids[start:start + 50]
        page = api_get(opener, "/videos", {
            "part": "snippet,contentDetails,statistics,status",
            "id": ",".join(chunk),
        }, key, sleep_s)
        videos.extend(page.get("items") or [])
    by_id = {item.get("id"): item for item in videos}
    posts = []
    for video_id in ids:
        item = by_id.get(video_id)
        if not item:
            notes.append("동영상 목록 응답에 없는 id: " + video_id)
            continue
        snip = item.get("snippet") or {}
        stats = item.get("statistics") or {}
        details = item.get("contentDetails") or {}
        privacy = ((item.get("status") or {}).get("privacyStatus") or "").lower()
        if privacy in HIDDEN or privacy in ("private", "unlisted"):
            hidden += 1
            continue
        posts.append({
            "platform": "youtube",
            "id": video_id,
            "url": "https://www.youtube.com/watch?v=" + video_id,
            "creator": snippet.get("title") or snip.get("channelTitle") or "",
            "creator_id": items[0].get("id") or snip.get("channelId") or "",
            "title": snip.get("title") or "",
            "caption": (snip.get("description") or "")[:8000],
            "caption_truncated": len(snip.get("description") or "") > 8000,
            "hashtags": merge_tags(
                "%s\n%s" % (snip.get("title") or "", snip.get("description") or ""),
                snip.get("tags") or [],
            ),
            "duration_s": parse_iso8601_duration(details.get("duration")),
            "width": None,
            "height": None,
            "aspect": None,
            "view_count": as_int(stats.get("viewCount")),
            "like_count": as_int(stats.get("likeCount")),
            "comment_count": as_int(stats.get("commentCount")),
            "upload_date": (snip.get("publishedAt") or "")[:10] or None,
            "thumbnail_url": (((snip.get("thumbnails") or {}).get("high") or {}).get("url") or ""),
            "subtitle_langs": [],
            "is_short_form": None,
            "availability": privacy or None,
        })
    if hidden:
        notes.append("비공개·일부 공개 %d건은 표에서 뺐다." % hidden)
    notes.append("데이터 API 응답에는 세로·가로가 없다. 화면비와 숏폼 여부는 비운다. 썸네일 크기로 추정하지 않는다.")
    if any(post["view_count"] is None for post in posts):
        notes.append("조회수가 없는 글은 0 으로 넣지 않았고 순위에서 뺐다.")
    return document(posts, notes, [], {"name": "youtube-data-api", "mode": "videos.list"})


def oembed_request_url(page_url):
    if "tiktok.com" in page_url:
        return "https://www.tiktok.com/oembed?" + urllib.parse.urlencode({"url": page_url})
    if "youtube.com" in page_url or "youtu.be" in page_url:
        return "https://www.youtube.com/oembed?" + urllib.parse.urlencode({
            "url": page_url, "format": "json",
        })
    return None


def youtube_id_from_url(page_url):
    parsed = urllib.parse.urlparse(page_url)
    if parsed.netloc.endswith("youtu.be"):
        return parsed.path.strip("/").split("/")[0]
    if "/shorts/" in parsed.path:
        return parsed.path.strip("/").split("/")[-1]
    query = urllib.parse.parse_qs(parsed.query)
    if query.get("v"):
        return query["v"][0]
    return ""


def normalize_oembed(page_url, payload):
    platform = platform_of(page_url, "")
    title = payload.get("title") if isinstance(payload.get("title"), str) else ""
    creator = payload.get("author_name") if isinstance(payload.get("author_name"), str) else ""
    thumb = payload.get("thumbnail_url") if isinstance(payload.get("thumbnail_url"), str) else ""
    video_id = ""
    if platform == "youtube":
        video_id = youtube_id_from_url(page_url)
    elif platform == "tiktok":
        video_id = str(payload.get("embed_product_id") or "")
    return {
        "platform": platform,
        "id": video_id,
        "url": page_url,
        "creator": creator,
        "creator_id": "",
        "title": title,
        "caption": "",
        "caption_truncated": False,
        "hashtags": hashtags(title),
        "duration_s": None,
        "width": None,
        "height": None,
        "aspect": None,
        "view_count": None,
        "like_count": None,
        "comment_count": None,
        "upload_date": None,
        "thumbnail_url": thumb,
        "subtitle_langs": [],
        "is_short_form": True if platform == "tiktok" else short_form(page_url, None, None, platform),
        "availability": None,
    }


def oembed_collect(urls, opener):
    posts = []
    errors = []
    notes = [
        "oEmbed 는 제목·작성자·썸네일만 준다. 조회수·길이·업로드 시각은 없다.",
        "틱톡 주소는 숏폼으로 표시한다. 화면비 숫자는 비운다.",
        "oEmbed 의 width·height 는 임베드 크기라 영상 화면비로 쓰지 않는다. 2026-11-20 실측: 유튜브 공개 영상 한 건이 200×150, 틱톡 문서 예시가 325×578 이었다.",
    ]
    for page_url in urls:
        if not public_http_url(page_url):
            errors.append({"url": page_url, "exit": 1, "stderr": ["http(s) 주소가 아니다"]})
            continue
        endpoint = oembed_request_url(page_url)
        if not endpoint:
            errors.append({"url": page_url, "exit": 1, "stderr": ["유튜브·틱톡 oEmbed 만 호출한다. 인스타그램은 이번 작성에서 확인하지 않았다."]})
            continue
        request = urllib.request.Request(endpoint, headers={"Accept": "application/json"})
        try:
            with opener.open(request, timeout=30) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except Exception as exc:  # noqa: BLE001 — 주소별 실패를 표에 남긴다
            errors.append({"url": page_url, "exit": 1, "stderr": [str(exc)[:300]]})
            continue
        if not isinstance(payload, dict):
            errors.append({"url": page_url, "exit": 1, "stderr": ["oEmbed JSON 객체가 아니다"]})
            continue
        posts.append(normalize_oembed(page_url, payload))
    if posts:
        notes.append("조회수가 없어 중앙값 순위를 만들 수 없다. 이 표만으로 스타일 프로파일을 확정하지 않는다.")
    return document(posts, notes, errors, {"name": "oembed", "mode": "partial"})


def vtt_seconds(hours, minutes, seconds, millis):
    frac = millis
    width = len(millis)
    return int(hours or 0) * 3600 + int(minutes) * 60 + int(seconds) + int(frac) / float(10 ** width)


def vtt_cues(text, end_s=None):
    cleaned = text.replace("\r\n", "\n").replace("\r", "\n")
    cues = []
    for block in re.split(r"\n\s*\n", cleaned):
        match = None
        lines = []
        for line in block.split("\n"):
            found = VTT_TIME.search(line)
            if found and match is None:
                match = found
                continue
            if line.strip().startswith(("WEBVTT", "NOTE", "Kind:", "Language:", "STYLE", "X-TIMESTAMP")):
                continue
            if line.strip().isdigit() and not lines:
                continue
            if match is not None and line.strip():
                lines.append(line.strip())
        if not match or not lines:
            continue
        groups = match.groups()
        start = vtt_seconds(groups[0], groups[1], groups[2], groups[3])
        end = vtt_seconds(groups[4], groups[5], groups[6], groups[7])
        if end_s is not None and start >= end_s:
            continue
        spoken = re.sub(r"<[^>]+>", "", " ".join(lines))
        spoken = re.sub(r"\s+", " ", spoken).strip()
        if spoken:
            cues.append({"start_s": round(start, 3), "end_s": round(end, 3), "text": spoken})
    return cues


def frames_argv(ffmpeg, video, out, every):
    if every <= 0:
        raise ValueError("--every 는 0보다 커야 한다.")
    rate = "1" if every == 1 else ("1/%g" % every)
    return [
        ffmpeg, "-hide_banner", "-loglevel", "error", "-i", video,
        "-vf", "fps=" + rate, "-q:v", "3",
        os.path.join(out, "f-%03d.jpg"),
    ]


def local_video(path):
    if not path or "://" in path or path.lower().startswith("http"):
        sys.exit("URL 은 받지 않는다. 이미 가지고 있는 영상 파일만 키프레임으로 뽑는다.")
    full = os.path.abspath(path)
    if not os.path.isfile(full):
        sys.exit("영상 파일이 없다: " + full)
    return full


def cmd_fetch(args):
    binary = shutil.which("yt-dlp")
    if not binary:
        sys.exit("yt-dlp 가 PATH 에 없다. 없애면 사용자가 받아 둔 JSON 은 normalize 로 읽고, 유튜브 키가 있으면 youtube-api 를 쓴다.")
    return fetch_urls(
        args.urls, args.out, args.limit, args.sleep, args.subs, args.sub_langs,
        args.thumbnails, args.timeout, default_runner, binary,
    )


def cmd_normalize(args):
    return normalize_files(args.dumps, args.out)


def cmd_youtube_api(args):
    key = os.environ.get("YOUTUBE_API_KEY", "").strip()
    if not key:
        sys.exit("환경 변수 YOUTUBE_API_KEY 가 없다. 키를 명령 인자에 넣지 않는다.")
    try:
        doc = youtube_collect(args.target, key, args.limit, urllib.request.build_opener(), args.sleep)
    except RuntimeError as exc:
        sys.exit(redact(str(exc), key))
    out = prepare_out(args.out)
    raw = os.path.join(out, "raw")
    os.makedirs(raw)
    with open(os.path.join(raw, "youtube-api.json"), "w", encoding="utf-8") as handle:
        json.dump({"note": "정규화된 표만 남긴다. API 키와 원문 응답 전체는 저장하지 않는다."}, handle, ensure_ascii=False)
    json_path, csv_path = write_table(doc, out)
    print_summary(doc, json_path, csv_path)
    return 0 if doc["posts"] else 1


def cmd_oembed(args):
    doc = oembed_collect(args.urls, urllib.request.build_opener())
    out = prepare_out(args.out)
    json_path, csv_path = write_table(doc, out)
    print_summary(doc, json_path, csv_path)
    return 0 if doc["posts"] else 1


def cmd_cues(args):
    with open(args.file, encoding="utf-8") as handle:
        cues = vtt_cues(handle.read(), args.to)
    print(json.dumps(cues, ensure_ascii=False, indent=2))
    return 0


def cmd_frames(args):
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        sys.exit("ffmpeg 가 PATH 에 없다.")
    video = local_video(args.video)
    out = prepare_out(args.out)
    argv = frames_argv(ffmpeg, video, out, args.every)
    proc = subprocess.run(argv)
    if proc.returncode != 0:
        return proc.returncode
    print(out)
    return 0


def build_parser():
    parser = argparse.ArgumentParser(description="공개 숏폼 메타데이터를 모아 채널 중앙값과 비교한다.")
    sub = parser.add_subparsers(dest="cmd", required=True)

    fetch = sub.add_parser("fetch", help="yt-dlp 로 공개 메타데이터만 받는다")
    fetch.add_argument("urls", nargs="+")
    fetch.add_argument("--out", required=True)
    fetch.add_argument("--limit", type=int, default=30)
    fetch.add_argument("--sleep", type=float, default=1)
    fetch.add_argument("--timeout", type=int, default=120)
    fetch.add_argument("--subs", action="store_true")
    fetch.add_argument("--sub-langs", default="ko.*,en.*")
    fetch.add_argument("--thumbnails", action="store_true")
    fetch.set_defaults(func=cmd_fetch)

    norm = sub.add_parser("normalize", help="받아 둔 yt-dlp JSON 을 표로 만든다")
    norm.add_argument("dumps", nargs="+")
    norm.add_argument("--out", required=True)
    norm.set_defaults(func=cmd_normalize)

    api = sub.add_parser("youtube-api", help="유튜브 데이터 API 로 최근 업로드를 읽는다")
    api.add_argument("target")
    api.add_argument("--out", required=True)
    api.add_argument("--limit", type=int, default=30)
    api.add_argument("--sleep", type=float, default=0.2)
    api.set_defaults(func=cmd_youtube_api)

    embed = sub.add_parser("oembed", help="제목·작성자·썸네일만 받는다. 순위는 못 만든다")
    embed.add_argument("urls", nargs="+")
    embed.add_argument("--out", required=True)
    embed.set_defaults(func=cmd_oembed)

    cues = sub.add_parser("cues", help="VTT 자막에서 초 구간 대사를 뽑는다")
    cues.add_argument("file")
    cues.add_argument("--to", type=float, default=None)
    cues.set_defaults(func=cmd_cues)

    frames = sub.add_parser("frames", help="이미 있는 영상 파일에서 키프레임을 뽑는다")
    frames.add_argument("video")
    frames.add_argument("--out", required=True)
    frames.add_argument("--every", type=float, default=1)
    frames.set_defaults(func=cmd_frames)
    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        code = args.func(args)
    except ValueError as exc:
        sys.exit(str(exc))
    return code


if __name__ == "__main__":
    sys.exit(main() or 0)
