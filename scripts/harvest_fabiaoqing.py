"""Harvest 斗图 memes straight from 发表情 (fabiaoqing.com) search pages.

Search engines are noisy for Chinese meme queries; 发表情 has a searchable library whose result
pages list the original artwork.  This tool walks those pages and records both the preview and
the large image URL, so only selected candidates need the heavy download.

    python scripts/harvest_fabiaoqing.py list   --out /tmp/fbq --keywords 电视 手机 --pages 6
    python scripts/harvest_fabiaoqing.py thumbs --out /tmp/fbq
    python scripts/harvest_fabiaoqing.py large  --out /tmp/fbq --pick 0 2 3

Notes
-----
* 发表情 answers plain ``requests`` with an SSL handshake failure, so page fetches shell out to
  ``curl``.  Image CDN (img.soutula.com) is fine with ``requests``.
* Result pages are ``/search/bqb/keyword/<kw>/type/bq/page/<n>.html`` and hold 15 hits each.
* Posting the same keyword too fast gets an empty page; the fetcher retries with a backoff.
"""

import argparse
import json
import re
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import quote

import requests

BASE = "https://www.fabiaoqing.com/search/bqb/keyword/{keyword}/type/bq/page/{page}.html"
UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)
HEADERS = {"User-Agent": UA, "Accept-Language": "zh-CN,zh;q=0.9"}
IMAGE = re.compile(r'data-original="(https?://[^"]+)"')


def curl(url):
    """发表情 uses a TLS profile that requests cannot negotiate; shell out to curl."""
    result = subprocess.run(
        [
            "curl",
            "-sS",
            "--compressed",
            "-m",
            "30",
            "-A",
            UA,
            "-H",
            "Accept-Language: zh-CN,zh;q=0.9",
            url,
        ],
        capture_output=True,
    )
    if result.returncode != 0:
        return ""
    return result.stdout.decode("utf-8", errors="ignore")


def page_images(keyword, page, attempts=3):
    url = BASE.format(keyword=quote(keyword), page=page)
    html = ""
    for attempt in range(attempts):
        html = curl(url)
        if html and "data-original" in html:
            break
        time.sleep(2.5 + attempt * 3)
    if not html:
        return [], url
    found = []
    for raw in IMAGE.findall(html):
        large = raw.replace("/bmiddle/", "/large/")
        found.append({"thumb": raw, "large": large})
    return found, url


def crawl(keyword, pages, delay):
    items, seen = [], set()
    for page in range(1, pages + 1):
        found, url = page_images(keyword, page)
        if not found:
            break
        for entry in found:
            if entry["thumb"] in seen:
                continue
            seen.add(entry["thumb"])
            items.append(
                {
                    "thumb": entry["thumb"],
                    "large": entry["large"],
                    "query": keyword,
                    "page_url": url,
                }
            )
        time.sleep(delay)
    return items


def fetch(url, target, referer="https://www.fabiaoqing.com/"):
    try:
        response = requests.get(url, headers={**HEADERS, "Referer": referer}, timeout=25)
        if response.status_code != 200 or len(response.content) < 2500:
            return False
    except requests.RequestException:
        return False
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(response.content)
    return True


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)

    list_parser = sub.add_parser("list")
    list_parser.add_argument("--out", default="/tmp/fbq")
    list_parser.add_argument("--keywords", nargs="+", required=True)
    list_parser.add_argument("--pages", type=int, default=6)
    list_parser.add_argument("--delay", type=float, default=0.9)

    thumbs_parser = sub.add_parser("thumbs")
    thumbs_parser.add_argument("--out", default="/tmp/fbq")

    large_parser = sub.add_parser("large")
    large_parser.add_argument("--out", default="/tmp/fbq")
    large_parser.add_argument("--pick", nargs="+", type=int, required=True)

    args = parser.parse_args()
    out = Path(args.out)
    index_path = out / "index.json"

    if args.command == "list":
        index = json.loads(index_path.read_text(encoding="utf-8")) if index_path.exists() else []
        known = {item["thumb"] for item in index}
        for keyword in args.keywords:
            found = [
                item for item in crawl(keyword, args.pages, args.delay) if item["thumb"] not in known
            ]
            print(f"{keyword}: {len(found)} new")
            known.update(item["thumb"] for item in found)
            index.extend(found)
            index_path.write_text(json.dumps(index, ensure_ascii=False, indent=1), encoding="utf-8")
        print("indexed", len(index))
        return

    index = json.loads(index_path.read_text(encoding="utf-8"))

    if args.command == "thumbs":
        folder = out / "thumb"

        def work(pair):
            position, item = pair
            suffix = Path(item["thumb"].split("?")[0]).suffix.lower() or ".jpg"
            target = folder / f"{position:05d}{suffix}"
            if target.exists():
                item["thumb_file"] = str(target)
                return target
            if fetch(item["thumb"], target):
                item["thumb_file"] = str(target)
                return target
            return None

        with ThreadPoolExecutor(max_workers=16) as executor:
            list(executor.map(work, enumerate(index)))
        index_path.write_text(json.dumps(index, ensure_ascii=False, indent=1), encoding="utf-8")
        print("thumbs", len(list(folder.glob("*"))) if folder.exists() else 0)

    if args.command == "large":
        folder = out / "original"

        def work(number):
            if not 0 <= number < len(index):
                return None
            item = index[number]
            suffix = Path(item["large"].split("?")[0]).suffix.lower() or ".jpg"
            target = folder / f"L{number:05d}{suffix}"
            if target.exists():
                item["large_file"] = str(target)
                return target
            if fetch(item["large"], target) or fetch(item["thumb"], target):
                item["large_file"] = str(target)
                return target
            return None

        with ThreadPoolExecutor(max_workers=10) as executor:
            list(executor.map(work, args.pick))
        index_path.write_text(json.dumps(index, ensure_ascii=False, indent=1), encoding="utf-8")
        print("large", len(list(folder.glob("*"))) if folder.exists() else 0)


if __name__ == "__main__":
    sys.exit(main())
