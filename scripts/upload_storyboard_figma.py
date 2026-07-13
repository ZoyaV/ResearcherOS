#!/usr/bin/env python3
"""Upload storyboard PNGs to Figma MCP submit URLs."""
import json
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / ".figma-storyboard" / "manifest.json"
URLS_FILE = ROOT / ".figma-storyboard" / "upload-urls.json"


def upload_one(path: Path, url: str) -> dict:
    data = path.read_bytes()
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "image/png"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        body = resp.read().decode("utf-8")
    return {"file": path.name, "response": json.loads(body) if body else {}}


def main() -> None:
    manifest = json.loads(MANIFEST.read_text())
    urls = json.loads(URLS_FILE.read_text())["uploads"]
    files = [Path(p) for p in manifest["files"]]
    if len(files) != len(urls):
        raise SystemExit(f"Mismatch: {len(files)} files vs {len(urls)} urls")

    results = []
    with ThreadPoolExecutor(max_workers=8) as pool:
        futs = [
            pool.submit(upload_one, f, u["submitUrl"])
            for f, u in zip(files, urls)
        ]
        for fut in as_completed(futs):
            results.append(fut.result())
            print("uploaded", results[-1]["file"])

    out = ROOT / ".figma-storyboard" / "upload-results.json"
    out.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"Done → {out}")


if __name__ == "__main__":
    main()
