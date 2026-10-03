"""Finish-photo companion tool.

Assigns photos to bib numbers via OCR (two passes: full image + detected bright bib cards),
downsizes them (long edge ~1600 px, EXIF stripped), uploads to `{prefix}/{hash}/` where
`hash = HMAC-SHA256(seed, bib)[:40]`, and writes an `index.html` gallery per folder.
Objects are uploaded public-read; the bucket must NOT allow public listing, so folders are only
reachable through the manage page link.

Usage:
    python -m tools.finishphotos.cli --photos ./fotos --seed $SEED --bucket bibby-prod-finish-photos \
        --prefix stadtlauf-2026 --endpoint https://s3.fr-par.scw.cloud --bib-min 1 --bib-max 2000 \
        [--year 2026] [--dry-run] [--review ./review]

Credentials for S3: AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY (or Scaleway equivalents) via env.
Optional dependencies: `uv sync --extra photos` (pytesseract + boto3) and the tesseract binary.
Idempotent: already uploaded objects (same key + size) are skipped.
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import html
import io
import json
import re
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image, ImageOps

LONG_EDGE = 1600
IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp"}


def bib_folder(seed: str, bib: int) -> str:
    return hmac.new(seed.encode(), str(bib).encode(), hashlib.sha256).hexdigest()[:40]


# ---------------------------------------------------------------- OCR -----


@dataclass
class Detection:
    bib: int
    confidence: float
    source: str


def plausible_numbers(text: str, bib_min: int, bib_max: int, year: int | None) -> list[int]:
    """Filters OCR tokens: within the bib range, not a year number, 1–5 digits."""
    out: list[int] = []
    for tok in re.findall(r"\d{1,5}", text):
        n = int(tok)
        if year and n == year:
            continue
        if 1900 <= n <= 2100 and len(tok) == 4 and year is not None:
            continue
        if bib_min <= n <= bib_max:
            out.append(n)
    return out


def find_bright_cards(img: Image.Image) -> list[tuple[int, int, int, int]]:
    """Heuristic: bright, roughly rectangular regions of plausible relative size (bib cards)."""
    gray = ImageOps.autocontrast(img.convert("L"))
    small = gray.resize((max(1, gray.width // 8), max(1, gray.height // 8)))
    w, h = small.size
    px = small.load()
    visited = [[False] * w for _ in range(h)]
    boxes: list[tuple[int, int, int, int]] = []
    for y in range(h):
        for x in range(w):
            if visited[y][x] or px[x, y] < 200:
                continue
            stack = [(x, y)]
            xs: list[int] = []
            ys: list[int] = []
            while stack:
                cx, cy = stack.pop()
                if cx < 0 or cy < 0 or cx >= w or cy >= h or visited[cy][cx] or px[cx, cy] < 200:
                    continue
                visited[cy][cx] = True
                xs.append(cx)
                ys.append(cy)
                stack.extend(((cx + 1, cy), (cx - 1, cy), (cx, cy + 1), (cx, cy - 1)))
            if not xs:
                continue
            bw, bh = max(xs) - min(xs) + 1, max(ys) - min(ys) + 1
            area_ratio = (bw * bh) / (w * h)
            fill = len(xs) / (bw * bh)
            if 0.002 < area_ratio < 0.2 and 0.6 < fill and 0.8 < bw / max(bh, 1) < 3.0:
                boxes.append((min(xs) * 8, min(ys) * 8, (max(xs) + 1) * 8, (max(ys) + 1) * 8))
    return boxes


def ocr_text(img: Image.Image) -> str:
    try:
        import pytesseract
    except ImportError:
        print("pytesseract not installed – run `uv sync --extra photos`", file=sys.stderr)
        sys.exit(2)
    return pytesseract.image_to_string(img, config="--psm 6 -c tessedit_char_whitelist=0123456789")


def detect_bibs(img: Image.Image, bib_min: int, bib_max: int, year: int | None) -> list[Detection]:
    found: dict[int, Detection] = {}
    for n in plausible_numbers(ocr_text(img), bib_min, bib_max, year):
        found.setdefault(n, Detection(n, 0.5, "full"))
    for box in find_bright_cards(img):
        crop = img.crop(box)
        crop = crop.resize((crop.width * 2, crop.height * 2))
        for n in plausible_numbers(ocr_text(crop), bib_min, bib_max, year):
            det = found.get(n)
            if det:
                det.confidence = min(1.0, det.confidence + 0.4)
                det.source = "both"
            else:
                found[n] = Detection(n, 0.7, "card")
    return sorted(found.values(), key=lambda d: -d.confidence)


# ------------------------------------------------------------ images -----


def downsize(path: Path) -> bytes:
    img = Image.open(path)
    img = ImageOps.exif_transpose(img) or img
    img = img.convert("RGB")
    img.thumbnail((LONG_EDGE, LONG_EDGE))
    out = io.BytesIO()
    img.save(out, format="JPEG", quality=85, optimize=True)  # no EXIF written
    return out.getvalue()


def gallery_html(bib: int, filenames: list[str]) -> str:
    items = "".join(
        f'<a href="{html.escape(f)}" target="_blank"><img src="{html.escape(f)}" loading="lazy" alt="Zielfoto"></a>'
        for f in filenames
    )
    return f"""<!doctype html><html lang="de"><head><meta charset="utf-8"><meta name="robots" content="noindex">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Zielfotos Startnummer {bib}</title>
<style>body{{font-family:sans-serif;margin:16px;background:#111;color:#eee}}
.g{{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:12px}}img{{width:100%;border-radius:6px}}</style>
</head><body><h1>Zielfotos – Startnummer {bib}</h1><div class="g">{items}</div></body></html>"""


# ------------------------------------------------------------- upload -----


class Uploader:
    def __init__(self, bucket: str, endpoint: str, dry_run: bool) -> None:
        self.bucket = bucket
        self.dry_run = dry_run
        self.existing: dict[str, int] = {}
        if dry_run:
            self.s3 = None
            return
        try:
            import boto3
        except ImportError:
            print("boto3 not installed – run `uv sync --extra photos`", file=sys.stderr)
            sys.exit(2)
        self.s3 = boto3.client("s3", endpoint_url=endpoint)

    def load_existing(self, prefix: str) -> None:
        if self.s3 is None:
            return
        paginator = self.s3.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=self.bucket, Prefix=prefix):
            for obj in page.get("Contents", []):
                self.existing[obj["Key"]] = obj["Size"]

    def put(self, key: str, data: bytes, content_type: str) -> bool:
        if self.existing.get(key) == len(data):
            return False  # idempotent: unchanged object
        if self.s3 is not None:
            self.s3.put_object(
                Bucket=self.bucket,
                Key=key,
                Body=data,
                ContentType=content_type,
                ACL="public-read",
                CacheControl="public, max-age=86400",
            )
        self.existing[key] = len(data)
        return True


@dataclass
class Plan:
    assignments: dict[int, list[Path]] = field(default_factory=dict)
    unassigned: list[Path] = field(default_factory=list)
    ambiguous: dict[Path, list[int]] = field(default_factory=dict)


def build_plan(
    photos: Path, bib_min: int, bib_max: int, year: int | None, max_per_photo: int
) -> Plan:
    plan = Plan()
    for path in sorted(p for p in photos.rglob("*") if p.suffix.lower() in IMAGE_EXT):
        img = ImageOps.exif_transpose(Image.open(path)) or Image.open(path)
        dets = detect_bibs(img, bib_min, bib_max, year)
        bibs = [d.bib for d in dets if d.confidence >= 0.5][:max_per_photo]
        if not bibs:
            plan.unassigned.append(path)
            continue
        if len(bibs) > 1:
            plan.ambiguous[path] = bibs
        for b in bibs:
            plan.assignments.setdefault(b, []).append(path)
        print(f"{path.name}: {', '.join(str(b) for b in bibs)}")
    return plan


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--photos", required=True, type=Path)
    ap.add_argument("--seed", required=True, help="HMAC seed of the event (keep secret)")
    ap.add_argument("--bucket", required=True)
    ap.add_argument("--prefix", required=True)
    ap.add_argument("--endpoint", default="https://s3.fr-par.scw.cloud")
    ap.add_argument("--bib-min", type=int, default=1)
    ap.add_argument("--bib-max", type=int, default=9999)
    ap.add_argument(
        "--year", type=int, default=None, help="event year (filtered out of OCR results)"
    )
    ap.add_argument("--max-per-photo", type=int, default=4)
    ap.add_argument(
        "--review", type=Path, default=None, help="folder receiving unassigned/ambiguous photos"
    )
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    plan = build_plan(args.photos, args.bib_min, args.bib_max, args.year, args.max_per_photo)
    print(
        f"assigned bibs: {len(plan.assignments)}, unassigned photos: {len(plan.unassigned)}, ambiguous: {len(plan.ambiguous)}"
    )
    if args.review:
        (args.review / "unassigned").mkdir(parents=True, exist_ok=True)
        (args.review / "ambiguous").mkdir(parents=True, exist_ok=True)
        for p in plan.unassigned:
            shutil.copy2(p, args.review / "unassigned" / p.name)
        for p, bibs in plan.ambiguous.items():
            shutil.copy2(p, args.review / "ambiguous" / f"{'-'.join(map(str, bibs))}_{p.name}")
        (args.review / "plan.json").write_text(
            json.dumps({str(k): [str(x) for x in v] for k, v in plan.assignments.items()}, indent=1)
        )

    up = Uploader(args.bucket, args.endpoint, args.dry_run)
    prefix = args.prefix.strip("/")
    up.load_existing(prefix + "/")
    uploaded = skipped = 0
    for bib, paths in sorted(plan.assignments.items()):
        folder = f"{prefix}/{bib_folder(args.seed, bib)}"
        names = []
        for p in paths:
            data = downsize(p)
            name = f"{hashlib.sha1(data).hexdigest()[:12]}.jpg"
            names.append(name)
            if up.put(f"{folder}/{name}", data, "image/jpeg"):
                uploaded += 1
            else:
                skipped += 1
        up.put(
            f"{folder}/index.html", gallery_html(bib, names).encode(), "text/html; charset=utf-8"
        )
    print(f"{'DRY RUN – ' if args.dry_run else ''}uploaded={uploaded} skipped(unchanged)={skipped}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
