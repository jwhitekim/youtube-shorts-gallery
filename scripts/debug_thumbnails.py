"""
썸네일 크기 디버깅 스크립트
Usage: python scripts/debug_thumbnails.py [video_id ...]
  예) python scripts/debug_thumbnails.py dQw4w9WgXcQ abc123
  인자 없이 실행하면 테스트용 ID 사용
"""
import sys
import requests
from PIL import Image
from io import BytesIO

SIZES = ["maxresdefault", "hqdefault", "mqdefault", "sddefault"]

def check_thumbnail(video_id: str):
    print(f"\n=== {video_id} ===")
    for size in SIZES:
        url = f"https://img.youtube.com/vi/{video_id}/{size}.jpg"
        try:
            resp = requests.get(url, timeout=5)
            img = Image.open(BytesIO(resp.content))
            w, h = img.size
            ratio = "9:16 (portrait)" if h > w else "16:9 (landscape)"
            print(f"  {size:18s}: {w}x{h}  → {ratio}")
        except Exception as e:
            print(f"  {size:18s}: 오류 - {e}")

if __name__ == "__main__":
    ids = sys.argv[1:] if len(sys.argv) > 1 else [
        # 테스트용 — Shorts ID와 일반 영상 ID를 직접 교체하세요
        "SHORTS_VIDEO_ID_HERE",
        "NORMAL_VIDEO_ID_HERE",
    ]
    for vid in ids:
        check_thumbnail(vid)
