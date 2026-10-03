from app.core.security import hmac_hex
from tools.finishphotos.cli import bib_folder, gallery_html, plausible_numbers


def test_folder_hash_matches_backend():
    assert bib_folder("seed", 42) == hmac_hex("seed", "42")
    assert len(bib_folder("seed", 42)) == 40


def test_plausibility_filter():
    assert plausible_numbers("Start 2026 Nr 123 und 99999 sowie 7", 1, 500, 2026) == [123, 7]
    assert plausible_numbers("1999", 1, 5000, 2026) == []  # year-like numbers are dropped
    assert plausible_numbers("1999", 1, 5000, None) == [1999]


def test_gallery_escapes():
    page = gallery_html(5, ["a.jpg", '"x.jpg'])
    assert "Startnummer 5" in page and "&quot;x.jpg" in page and "noindex" in page
