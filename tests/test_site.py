"""Validasi tautan dan struktur situs statis (hanya pustaka standar)."""

import posixpath
import struct
import unittest
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent.parent

PAGES = [
    "index.html",
    "apps/index.html",
    "apps/jelajah-nusantara/index.html",
    "privacy/index.html",
    "terms/index.html",
]

# Target navigasi utama (relatif terhadap root) dan halaman yang seharusnya aria-current.
NAV_TARGETS = ["index.html", "apps/index.html", "privacy/index.html", "terms/index.html"]
NAV_CURRENT = {
    "index.html": "index.html",
    "apps/index.html": "apps/index.html",
    "apps/jelajah-nusantara/index.html": "apps/index.html",
    "privacy/index.html": "privacy/index.html",
    "terms/index.html": "terms/index.html",
}

ALLOWED_EXTERNAL = {
    "https://github.com/sodikinnaa/siapdigital.id/issues",
    "https://github.com/sodikinnaa/jelajahnusantara/releases/tag/v0.1.1",
}

FORBIDDEN_SUBSTRINGS = ["play.google.com", "mailto:", "<iframe", "@siapdigital", "apps.apple.com"]

APP_ICON = "assets/img/jelajah-nusantara-icon-512.png"
FEATURE_GRAPHIC = "assets/img/jelajah-nusantara-feature-graphic.jpg"


class PageParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = set()
        self.links = []  # (tag, attr, value)
        self.nav_links = []  # (href, aria-current)
        self.h1_count = 0
        self.html_lang = None
        self.imgs_without_alt = 0
        self.scripts = []
        self.imgs = []  # dict atribut per <img>
        self.icons = []  # href <link rel="icon">
        self._in_nav_list = False

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if "id" in a:
            self.ids.add(a["id"])
        if tag == "html":
            self.html_lang = a.get("lang")
        if tag == "h1":
            self.h1_count += 1
        if tag == "img":
            self.imgs.append(a)
            if "alt" not in a:
                self.imgs_without_alt += 1
        if tag == "link" and a.get("rel") == "icon":
            self.icons.append(a.get("href"))
        if tag == "script" and "src" in a:
            self.scripts.append(a["src"])
        if tag == "ul" and a.get("id") == "nav-links":
            self._in_nav_list = True
        for attr in ("href", "src"):
            if attr in a:
                self.links.append((tag, attr, a[attr]))
        if tag == "a" and self._in_nav_list:
            self.nav_links.append((a.get("href"), a.get("aria-current")))

    def handle_endtag(self, tag):
        if tag == "ul":
            self._in_nav_list = False


def parse(rel):
    p = PageParser()
    p.feed((ROOT / rel).read_text(encoding="utf-8"))
    return p


def resolve(page_rel, href):
    """Resolve href relatif ke path berkas (relatif root); None jika eksternal."""
    parts = urlsplit(href)
    if parts.scheme or parts.netloc:
        return None, parts.fragment
    if not parts.path:
        return page_rel, parts.fragment
    base = posixpath.dirname(page_rel)
    target = posixpath.normpath(posixpath.join(base, parts.path))
    if target == ".":
        target = ""
    if parts.path.endswith("/") or target == "" or (ROOT / target).is_dir():
        target = posixpath.join(target, "index.html") if target else "index.html"
    return target, parts.fragment


def image_size(path):
    """Dimensi intrinsik (lebar, tinggi) PNG/JPEG tanpa dependensi."""
    data = path.read_bytes()
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return struct.unpack(">II", data[16:24])
    if data.startswith(b"\xff\xd8"):
        i = 2
        while i < len(data):
            marker, length = data[i + 1], struct.unpack(">H", data[i + 2:i + 4])[0]
            if 0xC0 <= marker <= 0xCF and marker not in (0xC4, 0xC8, 0xCC):
                h, w = struct.unpack(">HH", data[i + 5:i + 9])
                return w, h
            i += 2 + length
    raise ValueError(f"format gambar tidak dikenal: {path}")


class SiteTests(unittest.TestCase):
    def setUp(self):
        self.parsed = {rel: parse(rel) for rel in PAGES}

    def test_required_pages_exist(self):
        for rel in PAGES:
            self.assertTrue((ROOT / rel).is_file(), rel)

    def test_internal_links_and_fragments_resolve(self):
        for rel, p in self.parsed.items():
            for tag, attr, href in p.links:
                target, frag = resolve(rel, href)
                if target is None:
                    continue
                with self.subTest(page=rel, href=href):
                    self.assertFalse(target.startswith(".."), "tautan keluar dari root situs")
                    self.assertTrue((ROOT / target).is_file(), f"{target} tidak ada")
                    if frag:
                        ids = self.parsed[target].ids if target in self.parsed else parse(target).ids
                        self.assertIn(frag, ids, f"#{frag} tidak ada di {target}")

    def test_no_absolute_root_paths(self):
        # Tautan relatif agar situs bisa disajikan dari subpath.
        for rel, p in self.parsed.items():
            for _, _, href in p.links:
                with self.subTest(page=rel, href=href):
                    self.assertFalse(href.startswith("/"), href)

    def test_external_links_allowlisted(self):
        for rel, p in self.parsed.items():
            for _, _, href in p.links:
                if urlsplit(href).scheme:
                    with self.subTest(page=rel, href=href):
                        self.assertIn(href, ALLOWED_EXTERNAL)

    def test_forbidden_content_absent(self):
        for rel in PAGES:
            text = (ROOT / rel).read_text(encoding="utf-8").lower()
            for bad in FORBIDDEN_SUBSTRINGS:
                with self.subTest(page=rel, bad=bad):
                    self.assertNotIn(bad, text)

    def test_scripts_are_local(self):
        for rel, p in self.parsed.items():
            for src in p.scripts:
                with self.subTest(page=rel, src=src):
                    self.assertIsNone(urlsplit(src).scheme or None)

    def test_main_navigation_consistent(self):
        for rel, p in self.parsed.items():
            with self.subTest(page=rel):
                targets = [resolve(rel, href)[0] for href, _ in p.nav_links]
                self.assertEqual(targets, NAV_TARGETS)
                current = [resolve(rel, href)[0] for href, cur in p.nav_links if cur == "page"]
                self.assertEqual(current, [NAV_CURRENT[rel]])

    def test_document_basics(self):
        for rel, p in self.parsed.items():
            with self.subTest(page=rel):
                self.assertEqual(p.html_lang, "id")
                self.assertEqual(p.h1_count, 1)
                self.assertEqual(p.imgs_without_alt, 0)
                self.assertIn("konten", p.ids, "target skip-link #konten")

    def test_release_link_points_to_v0_1_1(self):
        p = self.parsed["apps/jelajah-nusantara/index.html"]
        hrefs = [h for _, _, h in p.links]
        self.assertIn("https://github.com/sodikinnaa/jelajahnusantara/releases/tag/v0.1.1", hrefs)

    def test_images_have_dimensions_matching_aspect_and_alt(self):
        for rel, p in self.parsed.items():
            for img in p.imgs:
                with self.subTest(page=rel, src=img.get("src")):
                    self.assertTrue(img.get("alt", "").strip(), "alt kosong")
                    w, h = int(img["width"]), int(img["height"])
                    iw, ih = image_size(ROOT / resolve(rel, img["src"])[0])
                    self.assertAlmostEqual(w / h, iw / ih, places=2)

    def test_jelajah_nusantara_uses_released_app_icon(self):
        for rel in ("index.html", "apps/index.html", "apps/jelajah-nusantara/index.html"):
            with self.subTest(page=rel):
                p = self.parsed[rel]
                srcs = [resolve(rel, i["src"])[0] for i in p.imgs]
                self.assertIn(APP_ICON, srcs)
                self.assertNotIn(">JN<", (ROOT / rel).read_text(encoding="utf-8"))
        self.assertEqual(image_size(ROOT / APP_ICON), (512, 512))

    def test_detail_page_shows_feature_graphic_and_app_favicon(self):
        rel = "apps/jelajah-nusantara/index.html"
        p = self.parsed[rel]
        self.assertIn(FEATURE_GRAPHIC, [resolve(rel, i["src"])[0] for i in p.imgs])
        self.assertEqual([resolve(rel, h)[0] for h in p.icons], [APP_ICON])

    def test_studio_branding_stays_distinct(self):
        # Ikon aplikasi tidak menggantikan identitas Siap Digital di halaman lain.
        for rel in PAGES:
            if rel == "apps/jelajah-nusantara/index.html":
                continue
            with self.subTest(page=rel):
                self.assertEqual([resolve(rel, h)[0] for h in self.parsed[rel].icons], ["assets/img/favicon.svg"])
        for rel in PAGES:
            with self.subTest(page=rel):
                self.assertIn('<span class="brand-mark" aria-hidden="true">S</span>Siap Digital', (ROOT / rel).read_text(encoding="utf-8"))

    def test_legal_pages_marked_draft_and_contact_unresolved(self):
        for rel in ("privacy/index.html", "terms/index.html"):
            text = (ROOT / rel).read_text(encoding="utf-8")
            with self.subTest(page=rel):
                self.assertIn("Status: draf", text)
                self.assertIn("belum tersedia", text)


if __name__ == "__main__":
    unittest.main()
