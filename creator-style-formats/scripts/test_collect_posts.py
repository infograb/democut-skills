#!/usr/bin/env python3
"""collect_posts.py 정규화·순위. 네트워크는 호출하지 않는다.

  python3 test_collect_posts.py
"""
import io
import json
import os
import shutil
import sys
import tempfile
import urllib.error

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
import collect_posts as C  # noqa: E402


def check(cond, message):
    if not cond:
        raise SystemExit(message)


def test_median_and_rank():
    check(C.median([]) is None, "빈 중앙값")
    check(C.median([10, 30, 20]) == 20, "홀수 중앙값")
    check(C.median([10, 20, 30, 40]) == 25, "짝수 중앙값")
    check(C.percentile([10, 20, 30, 40], 75) == 32.5, "p75")
    check(C.parse_iso8601_duration("PT1H2M3S") == 3723, "시분초")
    check(C.parse_iso8601_duration("PT1M2S") == 62, "분초")
    check(C.parse_iso8601_duration("PT45S") == 45, "초")
    check(C.parse_iso8601_duration("P1D") is None, "날짜 기간은 길이가 아니다")
    check(C.hashtags("원룸 #자취템 끝 #자취템 #Honey") == ["자취템", "Honey"], "해시태그")
    check(C.aspect_label(1080, 1920) == "9:16", "세로")
    check(C.aspect_label(1920, 1080) == "16:9", "가로")
    check(C.short_form("https://www.youtube.com/shorts/abc", None, None, "youtube") is True, "숏츠 주소")
    check(C.short_form("https://www.youtube.com/watch?v=abc", 1920, 1080, "youtube") is False, "가로 영상")

    dump = {"entries": [
        {"id": "a", "webpage_url": "https://www.youtube.com/shorts/a", "extractor_key": "Youtube",
         "channel": "채널", "channel_id": "UC1", "title": "하나 #자취", "description": "설명",
         "duration": 20, "view_count": 10, "width": 1080, "height": 1920, "upload_date": "20261001",
         "availability": "public", "thumbnail": "https://i.ytimg.com/vi/a/hqdefault.jpg"},
        {"id": "b", "webpage_url": "https://www.youtube.com/shorts/b", "extractor_key": "Youtube",
         "channel": "채널", "channel_id": "UC1", "title": "둘", "duration": 30, "view_count": 20,
         "upload_date": "20261002", "availability": "public"},
        {"id": "c", "webpage_url": "https://www.youtube.com/shorts/c", "extractor_key": "Youtube",
         "channel": "채널", "channel_id": "UC1", "title": "셋", "duration": 40, "view_count": 30,
         "upload_date": "20261003", "availability": "public"},
        {"id": "d", "webpage_url": "https://www.youtube.com/shorts/d", "extractor_key": "Youtube",
         "channel": "채널", "channel_id": "UC1", "title": "넷", "duration": 50, "view_count": 40,
         "upload_date": "20261004", "availability": "public"},
        {"id": "e", "webpage_url": "https://www.youtube.com/shorts/e", "extractor_key": "Youtube",
         "channel": "채널", "channel_id": "UC1", "title": "조회수 없음", "duration": 12,
         "availability": "public"},
        {"id": "secret", "webpage_url": "https://www.youtube.com/watch?v=secret", "title": "비공개",
         "availability": "private", "view_count": 99999, "extractor_key": "Youtube"},
        {"id": "listed", "title": "일부공개", "availability": "unlisted", "view_count": 1,
         "extractor_key": "Youtube", "channel_id": "UC1"},
        {"id": "a", "webpage_url": "https://www.youtube.com/shorts/a", "extractor_key": "Youtube",
         "channel_id": "UC1", "title": "중복", "view_count": 10, "availability": "public"},
        None,
        {"id": "media", "webpage_url": "https://www.youtube.com/watch?v=media", "extractor_key": "Youtube",
         "channel": "채널", "channel_id": "UC1", "title": "주소", "view_count": 1, "availability": "public",
         "url": "https://rr.googlevideo.com/videoplayback?id=secret",
         "formats": [{"url": "https://rr.googlevideo.com/videoplayback?id=secret"}]},
    ]}
    posts, notes = C.combine_dumps([dump])
    ids = [post["id"] for post in posts]
    check(ids == ["a", "b", "c", "d", "e", "media"], "남긴 글 " + ",".join(ids))
    check(any("비공개" in note for note in notes), "비공개 메모")
    check(any("조회수" in note for note in notes), "조회수 메모")
    summary = C.rank_posts(posts)
    creator = summary["creators"][0]
    check(creator["view_median"] == 20, "중앙값 %s" % creator["view_median"])
    check([item["id"] for item in creator["top_posts"]] == ["d", "c"], "상위")
    by_id = {post["id"]: post for post in posts}
    check(by_id["d"]["rank"]["views_over_median"] == 2, "40/20")
    check(by_id["e"]["rank"]["band"] == "unranked", "조회수 없음은 순위 밖")
    check(by_id["e"]["view_count"] is None, "0 으로 채우지 않는다")
    check(by_id["a"]["aspect"] == "9:16" and by_id["a"]["is_short_form"] is True, "세로 숏")
    check("googlevideo" not in json.dumps(by_id["media"], ensure_ascii=False), "재생 주소를 표에 넣지 않는다")
    check(by_id["media"]["url"] == "https://www.youtube.com/watch?v=media", "페이지 주소")
    check(by_id["a"]["hashtags"] == ["자취"], "제목 해시태그")
    check(by_id["a"]["upload_date"] == "2026-10-01", "업로드 날짜")


def test_argv_and_files():
    argv = C.ytdlp_dump_argv("yt-dlp", "https://www.youtube.com/@x/shorts", 30, 1)
    check("--skip-download" in argv and "--dump-single-json" in argv, "메타데이터만")
    check("--playlist-items" in argv and "1:30" in argv, "개수 제한")
    check("-f" not in argv and not any("cookie" in arg.lower() for arg in argv), "영상·쿠키 없음")
    subs = C.ytdlp_subs_argv("yt-dlp", "https://www.youtube.com/@x/shorts", 5, 1, "ko.*", "/tmp/out")
    check("--skip-download" in subs and "--dump-single-json" not in subs, "자막도 영상은 안 받는다")
    check("--write-subs" in subs and "--write-auto-subs" in subs, "자막 옵션")
    try:
        C.ytdlp_dump_argv("yt-dlp", "https://example.com", 51, 1)
    except ValueError:
        pass
    else:
        raise SystemExit("limit 상한이 없다")

    root = tempfile.mkdtemp()
    try:
        out = os.path.join(root, "empty")
        os.makedirs(out)
        seen = []

        def runner(cmd, timeout):
            seen.append(cmd)
            dump = {"id": "z", "title": "하나", "webpage_url": "https://www.tiktok.com/@a/video/1",
                    "extractor_key": "TikTok", "channel": "a", "view_count": 3, "duration": 9,
                    "availability": "public"}
            return 0, json.dumps(dump), ""

        code = C.fetch_urls(
            ["https://www.tiktok.com/@a/video/1"], out, 10, 1, False, "ko.*", False,
            30, runner, "yt-dlp",
        )
        check(code == 0, "fetch 실패")
        check("--skip-download" in seen[0], "실행 인자")
        saved = json.load(open(os.path.join(out, "posts.json"), encoding="utf-8"))
        check(saved["posts"][0]["platform"] == "tiktok", "틱톡")
        check(saved["posts"][0]["is_short_form"] is True, "틱톡은 숏폼")
        check(os.path.isfile(os.path.join(out, "posts.csv")), "csv")
        try:
            C.prepare_out(out)
        except SystemExit as exc:
            check("비어 있지 않다" in str(exc), "비운 디렉터리만")
        else:
            raise SystemExit("비어 있지 않은 디렉터리를 허용했다")
    finally:
        shutil.rmtree(root)


def test_youtube_api_and_oembed():
    check(C.parse_youtube_target("https://www.youtube.com/@Demo/shorts")["shorts_tab"] is True, "숏츠 탭")
    check(C.parse_youtube_target("UC" + "a" * 22)["channel_id"].startswith("UC"), "채널 id")

    class Response:
        def __init__(self, payload):
            self.payload = payload

        def read(self):
            return json.dumps(self.payload).encode("utf-8")

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

    class Opener:
        def open(self, request, timeout=30):
            url = request.full_url
            check("SECRET" in url, "키는 쿼리에만")
            if "/channels?" in url:
                return Response({"items": [{
                    "id": "UCtest",
                    "snippet": {"title": "채널"},
                    "contentDetails": {"relatedPlaylists": {"uploads": "UUtest"}},
                }]})
            if "/playlistItems?" in url:
                return Response({"items": [
                    {"snippet": {"resourceId": {"videoId": "aaa"}}},
                    {"snippet": {"resourceId": {"videoId": "bbb"}}},
                    {"snippet": {"resourceId": {"videoId": "ccc"}}},
                ]})
            if "/videos?" in url:
                return Response({"items": [
                    {"id": "aaa", "snippet": {
                        "title": "첫째 #자취", "description": "본문", "publishedAt": "2026-10-01T00:00:00Z",
                        "tags": ["호빵"], "thumbnails": {"high": {"url": "https://i.ytimg.com/vi/aaa/hqdefault.jpg"}},
                    }, "contentDetails": {"duration": "PT45S"}, "statistics": {
                        "viewCount": "100", "likeCount": "1", "commentCount": "2",
                    }, "status": {"privacyStatus": "public"}},
                    {"id": "bbb", "snippet": {
                        "title": "둘째", "description": "", "publishedAt": "2026-10-02T00:00:00Z",
                    }, "contentDetails": {"duration": "PT1M2S"}, "statistics": {"viewCount": "10"},
                     "status": {"privacyStatus": "public"}},
                    {"id": "ccc", "snippet": {"title": "비공개", "description": ""},
                     "statistics": {"viewCount": "9"}, "status": {"privacyStatus": "private"}},
                ]})
            raise SystemExit("모르는 경로 " + url)

    doc = C.youtube_collect("https://www.youtube.com/@Demo/shorts", "SECRET", 10, Opener(), 0)
    blob = json.dumps(doc, ensure_ascii=False)
    check("SECRET" not in blob, "키를 결과에 남겼다")
    check(doc["posts"][0]["view_count"] == 100, "조회수")
    check(doc["posts"][0]["duration_s"] == 45, "길이")
    check(doc["posts"][1]["view_count"] == 10, "둘째 조회수")
    check(doc["posts"][0]["is_short_form"] is None, "API 는 세로를 모른다")
    check(doc["posts"][0]["aspect"] is None, "썸네일로 화면비를 추정하지 않는다")
    check("호빵" in doc["posts"][0]["hashtags"] and "자취" in doc["posts"][0]["hashtags"], "태그")
    check(any("숏츠 탭" in note for note in doc["notes"]), "숏츠 탭 메모")
    by_id = {post["id"]: post for post in doc["posts"]}
    check(by_id["aaa"]["rank"]["band"] == "above_median", "100 > 중앙값")
    check(by_id["bbb"]["rank"]["band"] == "below_median", "10 < 중앙값")
    check("ccc" not in by_id, "비공개는 표에서 뺀다")
    check(any("비공개" in note for note in doc["notes"]), "비공개 메모")

    class Boom:
        def open(self, request, timeout=30):
            raise urllib.error.HTTPError(
                request.full_url, 400, "bad", {}, io.BytesIO(b'{"error":"no"}'),
            )

    try:
        C.youtube_collect("@Demo", "SECRET", 5, Boom(), 0)
    except RuntimeError as exc:
        check("SECRET" not in str(exc), "오류에 키가 남았다")
    else:
        raise SystemExit("API 오류를 삼켰다")

    payload = {
        "title": "Me at the zoo", "author_name": "jawed",
        "thumbnail_url": "https://i.ytimg.com/vi/jNQXAC9IVRw/hqdefault.jpg",
        "width": 200, "height": 150,
    }
    post = C.normalize_oembed("https://www.youtube.com/watch?v=jNQXAC9IVRw", payload)
    check(post["title"] == "Me at the zoo" and post["creator"] == "jawed", "oEmbed 제목")
    check(post["width"] is None and post["view_count"] is None and post["duration_s"] is None, "임베드 크기를 화면비로 쓰지 않는다")
    check(post["id"] == "jNQXAC9IVRw", "영상 id")
    shorts = C.normalize_oembed("https://www.youtube.com/shorts/abc", {"title": "s"})
    check(shorts["is_short_form"] is True, "숏츠 oEmbed")
    tiktok = C.normalize_oembed(
        "https://www.tiktok.com/@scout2015/video/6718335390845095173",
        {"embed_product_id": "6718335390845095173", "width": "325", "height": "578"},
    )
    check(tiktok["id"] == "6718335390845095173" and tiktok["title"] == "", "틱톡 oEmbed 에는 제목이 없을 수 있다")
    check(tiktok["width"] is None and tiktok["is_short_form"] is True, "틱톡 화면비는 비운다")


def test_cues_and_frames():
    text = """WEBVTT

00:00:00.000 --> 00:00:01.500
안녕하세요

00:00:01.500 --> 00:00:04.000 align:start position:0%
<c>제품</c> 이름

00:00:06.000 --> 00:00:07.000
끝
"""
    early = C.vtt_cues(text, 6)
    check([cue["text"] for cue in early] == ["안녕하세요", "제품 이름"], "6초 이전")
    check(early[0]["end_s"] == 1.5, "끝 시각")
    check(C.vtt_cues(text, None)[-1]["text"] == "끝", "전체")
    argv = C.frames_argv("ffmpeg", "/tmp/a.mp4", "/tmp/frames", 1)
    check("fps=1" in argv and "-i" in argv, "키프레임")
    try:
        C.local_video("https://example.com/a.mp4")
    except SystemExit as exc:
        check("URL" in str(exc), "주소로 키프레임을 받지 않는다")
    else:
        raise SystemExit("URL 을 허용했다")


def main():
    test_median_and_rank()
    test_argv_and_files()
    test_youtube_api_and_oembed()
    test_cues_and_frames()
    print("ok")


if __name__ == "__main__":
    main()
