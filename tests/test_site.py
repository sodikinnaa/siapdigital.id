"""Validasi tautan dan struktur situs statis (hanya pustaka standar)."""

import hashlib
import json
import math
import unicodedata
import posixpath
import re
import shutil
import struct
import subprocess
import unittest
from html import unescape as html_unescape
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import quote, urlsplit

ROOT = Path(__file__).resolve().parent.parent

PAGES = [
    "index.html",
    "apps/index.html",
    "apps/jelajah-nusantara/index.html",
    "privacy/index.html",
    "terms/index.html",
    "panduan/index.html",
    "panduan/transfer-konten-google/index.html",
    "panduan/remotion-reelforge/index.html",
    "panduan/remotion-reelforge/prompt-chatgpt/index.html",
    "panduan/remotion-reelforge/prompt-claude/index.html",
]

# Target navigasi utama (relatif terhadap root) dan halaman yang seharusnya aria-current.
NAV_TARGETS = ["index.html", "apps/index.html", "panduan/index.html", "privacy/index.html", "terms/index.html"]
NAV_CURRENT = {
    "index.html": "index.html",
    "apps/index.html": "apps/index.html",
    "apps/jelajah-nusantara/index.html": "apps/index.html",
    "privacy/index.html": "privacy/index.html",
    "terms/index.html": "terms/index.html",
    # Setiap panduan berada di bawah item navigasi Panduan.
    "panduan/index.html": "panduan/index.html",
    "panduan/transfer-konten-google/index.html": "panduan/index.html",
    "panduan/remotion-reelforge/index.html": "panduan/index.html",
    "panduan/remotion-reelforge/prompt-chatgpt/index.html": "panduan/index.html",
    "panduan/remotion-reelforge/prompt-claude/index.html": "panduan/index.html",
}

WEB_URL = "https://eduquest.siapdigital.id/"
PLAY_TESTING_URL = "https://play.google.com/apps/testing/id.siapdigital.jelajahnusantara"
WA_DISPLAY = "088275426716"
WA_NUMBER = "6288275426716"
NOSCRIPT_WA_TEXT = (
    "Halo Admin Siap Digital, saya ingin mendaftar sebagai tester Android aplikasi "
    "Jelajah Nusantara di Google Play. Email akun Google saya: "
)


def encode_uri_component(text):
    """Padanan encodeURIComponent JavaScript."""
    return quote(text, safe="-_.!~*'()")


def wa_url(text):
    return "https://wa.me/" + WA_NUMBER + "?text=" + encode_uri_component(text)


NOSCRIPT_WA_URL = wa_url(NOSCRIPT_WA_TEXT)

GUIDE_PAGE = "panduan/transfer-konten-google/index.html"
GUIDE_IMG_DIR = "assets/img/panduan/transfer-konten-google"
GOOGLE_TRANSFER_URL = "https://takeout.google.com/transfer"
SITE_URL = "https://siapdigital.id/"
GUIDE_COVER = GUIDE_IMG_DIR + "/sampul-transfer-konten-google.jpg"
GEMINI_WA_TEXT = "Halo, saya ingin minta informasi terkait akun Gemini Pro selama 18 bulan."
GEMINI_WA_URL = "https://wa.me/62895353557327?text=" + encode_uri_component(GEMINI_WA_TEXT)

SITE_WA_TEXT = "Halo Admin Siap Digital, saya ingin informasi lebih lanjut terkait website siapdigital.id."
SITE_WA_URL = "https://wa.me/62895353557327?text=" + encode_uri_component(SITE_WA_TEXT)

GUIDE_HUB = "panduan/index.html"
REMOTION_PAGE = "panduan/remotion-reelforge/index.html"
REMOTION_IMG_DIR = "assets/img/panduan/remotion-reelforge"
REMOTION_COVER = REMOTION_IMG_DIR + "/sampul-remotion-reelforge.jpg"
REMOTION_SERVICE_URLS = {
    "https://nodejs.org/",
    "https://chatgpt.com/",
    "https://claude.ai/",
    "https://www.cartesia.ai/",
}

COLAB_NOTEBOOK_URL = "https://colab.research.google.com/drive/1jjNd_7Rx0eOxNXgsuxftZmg6bxrzBcDN?usp=sharing"

ALLOWED_EXTERNAL = REMOTION_SERVICE_URLS | {
    COLAB_NOTEBOOK_URL,
    "https://github.com/sodikinnaa/siapdigital.id/issues",
    GOOGLE_TRANSFER_URL,
    GEMINI_WA_URL,
    SITE_WA_URL,
    WEB_URL,
    PLAY_TESTING_URL,
    NOSCRIPT_WA_URL,
}

FORBIDDEN_SUBSTRINGS = [
    "mailto:", "<iframe", "@siapdigital", "apps.apple.com",
    # Tautan rilis GitHub privat dan klaim lama "belum tersedia di Google Play".
    "jelajahnusantara/releases", "belum tersedia di google play",
]

TESTER_PAGE = "apps/jelajah-nusantara/index.html"
TESTER_JS = "assets/js/tester.js"

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
        self.tags = []  # (tag, dict atribut) semua elemen
        self._in_nav_list = False

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        self.tags.append((tag, a))
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


def webp_chunks(data):
    """Daftar FourCC chunk di dalam berkas WebP (RIFF)."""
    chunks, i = [], 12
    while i + 8 <= len(data):
        length = struct.unpack("<I", data[i + 4:i + 8])[0]
        chunks.append(data[i:i + 4])
        i += 8 + length + (length & 1)
    return chunks


def image_size(path):
    """Dimensi intrinsik (lebar, tinggi) PNG/JPEG/WebP tanpa dependensi."""
    data = path.read_bytes()
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return struct.unpack(">II", data[16:24])
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        kind = data[12:16]
        if kind == b"VP8 ":
            w, h = struct.unpack("<HH", data[26:30])
            return w & 0x3FFF, h & 0x3FFF
        if kind == b"VP8L":
            bits = int.from_bytes(data[21:25], "little")
            return (bits & 0x3FFF) + 1, ((bits >> 14) & 0x3FFF) + 1
        if kind == b"VP8X":
            return int.from_bytes(data[24:27], "little") + 1, int.from_bytes(data[27:30], "little") + 1
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

    def test_floating_whatsapp_button_on_every_page(self):
        for rel, p in self.parsed.items():
            with self.subTest(page=rel):
                floats = [a for t, a in p.tags if t == "a" and "wa-float" in a.get("class", "").split()]
                self.assertEqual(len(floats), 1)
                [a] = floats
                self.assertEqual(a.get("href"), SITE_WA_URL)
                self.assertEqual(a.get("rel"), "noopener")
                self.assertTrue(a.get("aria-label", "").strip(), "label untuk tampilan ikon saja")

    def test_admin_whatsapp_number_not_shown_as_text(self):
        # Nomor admin hanya ada di dalam tautan tombol, tidak ditampilkan di halaman.
        for rel in PAGES:
            html = (ROOT / rel).read_text(encoding="utf-8")
            visible = re.sub(r'href="[^"]*"', "", html)
            with self.subTest(page=rel):
                self.assertIsNone(re.search(r"0?895[\s.-]*3535[\s.-]*57327|62895353557327", visible))

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
                self.assertEqual(current, [NAV_CURRENT[rel]] if NAV_CURRENT[rel] else [])

    def test_document_basics(self):
        for rel, p in self.parsed.items():
            with self.subTest(page=rel):
                self.assertEqual(p.html_lang, "id")
                self.assertEqual(p.h1_count, 1)
                self.assertEqual(p.imgs_without_alt, 0)
                self.assertIn("konten", p.ids, "target skip-link #konten")

    def test_external_urls_exact(self):
        # Hanya URL pengujian Play dan nomor WhatsApp yang diberikan; tanpa varian lain.
        for rel in PAGES:
            text = (ROOT / rel).read_text(encoding="utf-8")
            with self.subTest(page=rel):
                for url in re.findall(r'https?://[^\s"<>]*play\.google\.com[^\s"<>]*', text):
                    self.assertEqual(url, PLAY_TESTING_URL)
                for url in re.findall(r'https?://[^\s"<>]*wa\.me[^\s"<>]*', text):
                    self.assertIn(url, (NOSCRIPT_WA_URL, GEMINI_WA_URL, SITE_WA_URL))
                for url in re.findall(r'https?://[^\s"<>]+', text):
                    if urlsplit(url).netloc.endswith("siapdigital.id"):
                        if url.startswith(SITE_URL):
                            # URL absolut situs sendiri (og:url/og:image) harus menunjuk berkas yang ada.
                            local = url[len(SITE_URL):]
                            self.assertTrue((ROOT / local).is_file()
                                            or (ROOT / local / "index.html").is_file(), url)
                        else:
                            self.assertEqual(url, WEB_URL)
                self.assertNotIn("market://", text)

    def test_primary_ctas_play_web_and_tester_signup(self):
        for rel, signup in (("index.html", "apps/jelajah-nusantara/index.html"),
                            ("apps/index.html", "apps/jelajah-nusantara/index.html"),
                            (TESTER_PAGE, TESTER_PAGE)):
            p = self.parsed[rel]
            with self.subTest(page=rel):
                primaries = [a.get("href") for t, a in p.tags
                             if t == "a" and "btn-primary" in a.get("class", "").split()]
                self.assertIn(WEB_URL, primaries)
                targets = [resolve(rel, h) for _, _, h in p.links]
                self.assertIn((signup, "daftar-tester"), targets)
        detail_hrefs = [h for _, _, h in self.parsed[TESTER_PAGE].links]
        self.assertIn(PLAY_TESTING_URL, detail_hrefs)
        text = (ROOT / TESTER_PAGE).read_text(encoding="utf-8")
        self.assertIn("Main versi web", text)
        self.assertIn("khusus tester terdaftar", text)

    def test_no_empty_or_placeholder_links(self):
        for rel, p in self.parsed.items():
            for tag, attr, href in p.links:
                with self.subTest(page=rel, href=href):
                    self.assertTrue(href.strip())
                    self.assertNotIn(href.strip(), ("#", "javascript:void(0)"))
                    self.assertFalse(href.lower().startswith("javascript:"))

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


class GuidePageTests(unittest.TestCase):
    def setUp(self):
        self.page = parse(GUIDE_PAGE)
        self.html = (ROOT / GUIDE_PAGE).read_text(encoding="utf-8")

    def test_every_page_links_to_guide_hub_in_footer(self):
        for rel in PAGES:
            footer = (ROOT / rel).read_text(encoding="utf-8").split('<footer class="site-footer">', 1)[1]
            p = PageParser()
            p.feed(footer)
            with self.subTest(page=rel):
                self.assertIn(GUIDE_HUB, [resolve(rel, h)[0] for _, _, h in p.links])

    def test_hub_and_home_link_every_guide(self):
        for rel in (GUIDE_HUB, "index.html"):
            targets = [resolve(rel, h)[0] for _, _, h in parse(rel).links]
            for guide in (GUIDE_PAGE, REMOTION_PAGE):
                with self.subTest(page=rel, guide=guide):
                    self.assertIn(guide, targets)

    def test_ten_numbered_steps_each_with_screenshot(self):
        for n in range(1, 11):
            with self.subTest(step=n):
                self.assertIn(f"langkah-{n}", self.page.ids)
        srcs = sorted(resolve(GUIDE_PAGE, i["src"])[0] for i in self.page.imgs
                      if i["src"].endswith(".png"))
        files = sorted(f"{GUIDE_IMG_DIR}/{f.name}" for f in (ROOT / GUIDE_IMG_DIR).glob("*.png"))
        self.assertEqual(len(srcs), 10)
        self.assertEqual(srcs, files, "setiap tangkapan layar dipakai tepat sekali")

    def test_no_personal_data_in_markup(self):
        # Panduan tidak boleh memuat alamat email asli atau token apa pun.
        self.assertEqual(re.findall(r"[\w.+-]+@[\w-]+\.[\w.]+", self.html), [])
        self.assertNotRegex(self.html, r"get-code/|pwd\?TL=|#inbox/")

    def test_screenshots_carry_no_metadata_chunks(self):
        # Hanya chunk gambar inti; tanpa EXIF, teks, atau profil ICC dari sumber.
        allowed = {b"IHDR", b"IDAT", b"IEND"}
        for f in (ROOT / GUIDE_IMG_DIR).glob("*.png"):
            data, i, chunks = f.read_bytes(), 8, set()
            while i < len(data):
                length = struct.unpack(">I", data[i:i + 4])[0]
                chunks.add(data[i + 4:i + 8])
                i += 12 + length
            with self.subTest(image=f.name):
                self.assertLessEqual(chunks, allowed)

    def test_states_independence_and_safety(self):
        for phrase in ("Jangan bagikan kode",
                       "accounts.google.com", "sudah kami buramkan"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, self.html)
        self.assertIn(GOOGLE_TRANSFER_URL, [h for _, _, h in self.page.links])

    def meta(self, key):
        return [a.get("content") for t, a in self.page.tags
                if t == "meta" and (a.get("property") == key or a.get("name") == key)]

    def test_cover_used_as_thumbnail_and_og_image(self):
        self.assertIn(GUIDE_COVER, [resolve(GUIDE_PAGE, i["src"])[0] for i in self.page.imgs])
        self.assertEqual(self.meta("og:image"), [SITE_URL + GUIDE_COVER])
        self.assertEqual(self.meta("twitter:image"), [SITE_URL + GUIDE_COVER])
        self.assertEqual(self.meta("twitter:card"), ["summary_large_image"])
        self.assertEqual(self.meta("og:url"), [SITE_URL + "panduan/transfer-konten-google/"])
        w, h = image_size(ROOT / GUIDE_COVER)
        self.assertEqual(self.meta("og:image:width"), [str(w)])
        self.assertEqual(self.meta("og:image:height"), [str(h)])
        for key in ("og:title", "og:description", "og:image:alt"):
            with self.subTest(key=key):
                self.assertTrue(self.meta(key) and self.meta(key)[0].strip())

    def test_ad_popup_and_static_fallback(self):
        hrefs = [a.get("href") for t, a in self.page.tags if t == "a"]
        self.assertEqual(hrefs.count(GEMINI_WA_URL), 2, "popup + bagian statis")
        [dialog] = [a for t, a in self.page.tags if t == "dialog"]
        self.assertEqual(dialog.get("id"), "promo-gemini")
        self.assertNotIn("open", dialog)
        for ref in (dialog["aria-labelledby"], dialog["aria-describedby"]):
            self.assertIn(ref, self.page.ids)
        self.assertIn('aria-label="Tutup iklan"', self.html)
        self.assertEqual(self.html.count(">Iklan</span>"), 2, "iklan diberi label jelas")
        # Pemilik situs meminta catatan pihak ketiga dan catatan afiliasi tidak ditampilkan.
        for removed in ("pihak ketiga", "berafiliasi", "Oktober 2026"):
            with self.subTest(removed=removed):
                self.assertNotIn(removed, self.html)
        self.assertIn('value="nanti"', self.html, "tombol Nanti saja menutup popup")
        self.assertIn("../../assets/js/promo.js", self.page.scripts)
        for t, a in self.page.tags:
            if t == "a" and a.get("href") == GEMINI_WA_URL:
                self.assertEqual(a.get("rel"), "noopener")
        js = (ROOT / "assets/js/promo.js").read_text(encoding="utf-8")
        self.assertIn("showModal", js)
        for bad in ("innerHTML", "fetch(", "eval(", "http"):
            with self.subTest(bad=bad):
                self.assertNotIn(bad, js)

    def test_ad_only_on_guide_page(self):
        for rel in PAGES:
            if rel != GUIDE_PAGE:
                with self.subTest(page=rel):
                    self.assertFalse(any(x.endswith("promo.js") for x in parse(rel).scripts))
                    self.assertNotIn("Gemini", (ROOT / rel).read_text(encoding="utf-8"))


class RemotionTutorialTests(unittest.TestCase):
    def setUp(self):
        self.page = parse(REMOTION_PAGE)
        self.html = (ROOT / REMOTION_PAGE).read_text(encoding="utf-8")

    def meta(self, key):
        return [a.get("content") for t, a in self.page.tags
                if t == "meta" and (a.get("property") == key or a.get("name") == key)]

    def test_numbered_steps_in_eight_sections(self):
        for n in range(1, 35):
            with self.subTest(step=n):
                self.assertIn(f"langkah-{n}", self.page.ids)
        self.assertNotIn("langkah-35", self.page.ids)
        sections = ("chatgpt", "claude", "cartesia", "naskah", "voice", "video", "render-lokal", "render-colab")
        toc = [h for t, a in self.page.tags if t == "a" for h in [a.get("href", "")] if h.startswith("#")]
        for sec in sections:
            with self.subTest(section=sec):
                self.assertIn(sec, self.page.ids)
                self.assertIn("#" + sec, toc, "daftar isi menautkan setiap bagian")

    def test_colab_is_an_optional_alternative_to_local_export(self):
        # Tutorial memakai nama "Render Studio"; ReelForge dan tunnel mentah tidak muncul di teks.
        for bad in ("ReelForge", "trycloudflare"):
            with self.subTest(bad=bad):
                self.assertNotIn(bad, self.html)
        self.assertIn("Render Studio Siap Digital", self.html)
        for name in ("05-reelforge-studio", "27-reelforge-master-prompt", "36-reelforge-prompt-claude", "42-reelforge-video-siap"):
            with self.subTest(image=name):
                self.assertFalse((ROOT / REMOTION_IMG_DIR / f"{name}.webp").exists())
        # Satu-satunya tautan Drive/Colab spesifik adalah notebook resmi, selalu dibuka di tab baru.
        drive_links = re.findall(r'https://colab\.research\.google\.com/drive/[^"\s<]*', self.html)
        self.assertTrue(drive_links)
        self.assertEqual(set(drive_links), {COLAB_NOTEBOOK_URL})
        for a in (a for t, a in self.page.tags if t == "a" and a.get("href") == COLAB_NOTEBOOK_URL):
            self.assertEqual((a.get("target"), a.get("rel")), ("_blank", "noopener"))
        # Opsi B: enam langkah (29-34), dibuka dengan tombol notebook, ditutup dengan unduhan MP4.
        step29 = self.html.split('id="langkah-29"', 1)[1].split("</li>", 1)[0]
        self.assertIn(">Buka notebook Render Studio</a>", step29)
        self.assertIn("GPU T4", step29)
        step34 = self.html.split('id="langkah-34"', 1)[1].split("</li>", 1)[0]
        self.assertIn("Unduh MP4", step34)
        step23 = self.html.split('id="langkah-23"', 1)[1].split("</li>", 1)[0]
        self.assertIn("langkah 24–28", step23)
        self.assertIn("langkah 29–34", step23)

    def test_generator_steps_and_output_choice(self):
        targets = [resolve(REMOTION_PAGE, h)[0] for _, _, h in self.page.links]
        for slug in ("prompt-chatgpt", "prompt-claude"):
            with self.subTest(slug=slug):
                self.assertIn(f"panduan/remotion-reelforge/{slug}/index.html", targets)
        step21 = self.html.split('id="langkah-21"', 1)[1].split("</li>", 1)[0]
        for phrase in ("Output dari Claude", "MP4 + ZIP", "MP4 saja", "ZIP project saja"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, step21)
        for cmd in ("npm install", "npx remotion still src/index.ts MainReel", "--timeout=120000",
                    "npx remotion render src/index.ts MainReel out.mp4"):
            with self.subTest(cmd=cmd):
                self.assertIn(cmd, self.html)
        self.assertEqual(self.html.count('<pre class="code-block">'), 4)
        # Bagian ekspor dibuka dengan contoh respons Claude yang hanya memberi ZIP.
        step24 = self.html.split('id="langkah-24"', 1)[1].split("</li>", 1)[0]
        self.assertIn("45-claude-tidak-bisa-render.webp", step24)
        self.assertIn("46-claude-zip-dan-instruksi.webp", step24)

    def test_every_screenshot_used_exactly_once(self):
        srcs = [resolve(REMOTION_PAGE, i["src"])[0] for i in self.page.imgs if i["src"].endswith(".webp")]
        files = sorted(f"{REMOTION_IMG_DIR}/{f.name}" for f in (ROOT / REMOTION_IMG_DIR).glob("*.webp"))
        self.assertEqual(len(files), 43)
        self.assertEqual(sorted(srcs), files)
        # Setiap tangkapan layar dapat dibuka dalam ukuran penuh.
        hrefs = {resolve(REMOTION_PAGE, h)[0] for t, a, h in self.page.links if t == "a"}
        self.assertLessEqual(set(srcs), hrefs)

    def test_no_personal_data_in_markup(self):
        self.assertEqual(re.findall(r"[\w.+-]+@[\w-]+\.[\w.]+", self.html), [])
        # Nama akun di tangkapan layar ("sodikin"/"sodikinn"), bukan nama pemilik repo GitHub.
        for bad in (r"semeruexpose", r"\bsodikinn?\b", r"aguzza"):
            with self.subTest(bad=bad):
                self.assertIsNone(re.search(bad, self.html))
        self.assertIn("sudah kami buramkan", self.html)

    def test_screenshots_carry_no_metadata_chunks(self):
        for f in (ROOT / REMOTION_IMG_DIR).glob("*.webp"):
            with self.subTest(image=f.name):
                self.assertEqual(webp_chunks(f.read_bytes()), [b"VP8 "])
                self.assertEqual(image_size(f)[0], 1400)

    def test_cover_used_as_thumbnail_and_og_image(self):
        self.assertIn(REMOTION_COVER, [resolve(REMOTION_PAGE, i["src"])[0] for i in self.page.imgs])
        self.assertEqual(self.meta("og:image"), [SITE_URL + REMOTION_COVER])
        self.assertEqual(self.meta("twitter:image"), [SITE_URL + REMOTION_COVER])
        self.assertEqual(self.meta("og:url"), [SITE_URL + "panduan/remotion-reelforge/"])
        w, h = image_size(ROOT / REMOTION_COVER)
        self.assertEqual((w, h), (1200, 675))
        self.assertEqual(self.meta("og:image:width"), [str(w)])
        self.assertEqual(self.meta("og:image:height"), [str(h)])
        for key in ("og:title", "og:description", "og:image:alt", "twitter:card"):
            with self.subTest(key=key):
                self.assertTrue(self.meta(key) and self.meta(key)[0].strip())

    def test_service_links_open_safely(self):
        external = [a for t, a in self.page.tags if t == "a" and a.get("href") in REMOTION_SERVICE_URLS]
        self.assertEqual({a["href"] for a in external}, REMOTION_SERVICE_URLS)
        for a in external:
            with self.subTest(href=a["href"]):
                self.assertEqual(a.get("target"), "_blank")
                self.assertEqual(a.get("rel"), "noopener")

    def test_safety_warnings_kept(self):
        for phrase in ("batas penggunaan per 5 jam", "1080×1920", "<code>npm install</code> menjalankan kode",
                       "tetap memberi ZIP", "Siapa pun yang memiliki URL studio", "Tetap jalankan"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, self.html)
        self.assertEqual(self.html.count('class="callout warn"'), 4)


PROMPT_PAGES = {
    "gpt": "panduan/remotion-reelforge/prompt-chatgpt/index.html",
    "claude": "panduan/remotion-reelforge/prompt-claude/index.html",
}
PROMPT_JS = "assets/js/prompt-generator.js"
# SHA-256 template prompt versi situs (turunan ReelForge V5.4); berubah hanya jika template sengaja diganti.
PROMPT_TEMPLATE_SHA256 = {
    "gpt": "2b3199c455173ae21173664c87136744a63b39a51864b668e2615b396c522720",
    "claude": "d645fe2115922be6f64bdcbc8cd26baf5713b4d61dbd1a6462e2725da152c475",
}


def prompt_template(rel):
    raw = re.search(r'<textarea class="prompt-text" id="prompt-output"[^>]*>(.*?)</textarea>',
                    (ROOT / rel).read_text(encoding="utf-8"), re.S).group(1)
    return html_unescape(raw)


def py_seconds(value):
    """Padanan seconds(): Number() JS, rentang 5–180, Math.round (setengah ke atas), selain itu 20."""
    s = value.strip()
    try:
        x = float(s) if s else 0.0
    except ValueError:
        return 20
    return math.floor(x + 0.5) if math.isfinite(x) and 5 <= x <= 180 else 20


def py_slug(value):
    s = unicodedata.normalize("NFKD", value.strip().lower())
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = re.sub(r"[^a-z0-9]+", "_", s).strip("_")[:40].rstrip("_")
    return s or "video"


def py_build_prompt(kind, template, raw, captions, structures, hooks, outputs):
    """Implementasi acuan buildPrompt (generator versi situs). captions: preset {kunci: {name, spec}}."""
    g = lambda k: str(raw.get(k, "")).strip()
    sec = py_seconds(g("duration"))
    v = {"ISI TOPIK": g("topic") or "[ISI TOPIK]", "ISI DESKRIPSI": g("description") or "[ISI DESKRIPSI]",
         "ISI FAKTA": g("facts") or "(tidak diisi)", "ISI ISTILAH": g("terms") or "(tidak diisi)",
         "ISI AUDIENS": g("audience") or "[ISI AUDIENS]", "ISI CTA": g("cta") or "[ISI CTA]",
         "DURASI": f"{sec} detik",
         "ANGGARAN KATA": f"{math.floor(sec * 2.0 + 0.5)}–{math.floor(sec * 2.2 + 0.5)} kata"}
    slug = py_slug(g("topic"))
    v["NAMA FILE"] = f"motion_graphic_{slug}.txt"
    v["NAMA ZIP"] = f"remotion_reels_{slug}.zip"
    v["NAMA MP4"] = f"reels_{slug}.mp4"
    template = template.replace("[OUTPUT]", outputs[g("output") if g("output") in outputs else "both"])
    cap = g("caption") if g("caption") in captions else "bold"
    v["GAYA CAPTION SINGKAT"] = captions[cap]["name"]
    v["GAYA CAPTION"] = captions[cap]["spec"]
    v["STRUKTUR"] = structures[g("structure") if g("structure") in structures else "explainer"]
    v["JENIS HOOK"] = hooks[g("hook") if g("hook") in hooks else "auto"]
    style = g("style") or "modern premium"
    keys = sorted(v, key=len, reverse=True)
    body = re.sub(r"\[(" + "|".join(map(re.escape, keys)) + r")\]", lambda m: v[m.group(1)], template)
    head = (f"Topik: {v['ISI TOPIK']}\nDeskripsi: {v['ISI DESKRIPSI']}\nAudiens: {v['ISI AUDIENS']}\nCTA: {v['ISI CTA']}\n")
    if kind == "gpt":
        return (f"KONFIGURASI VIDEO\n{head}Durasi: {v['DURASI']} (anggaran voice-over {v['ANGGARAN KATA']})\n"
                f"Gaya visual: {style}\n\n{body}")
    return f"KONFIGURASI PROJECT (IKUTI TXT & AUDIO TERLAMPIR)\n{head}Target durasi: {v['DURASI']}\nGaya visual: {style}\n\n{body}"


class PromptGeneratorTests(unittest.TestCase):
    def setUp(self):
        self.pages = {k: parse(rel) for k, rel in PROMPT_PAGES.items()}
        self.html = {k: (ROOT / rel).read_text(encoding="utf-8") for k, rel in PROMPT_PAGES.items()}
        self.js = (ROOT / PROMPT_JS).read_text(encoding="utf-8")

    def test_templates_are_current_version(self):
        for kind, rel in PROMPT_PAGES.items():
            tpl = prompt_template(rel)
            with self.subTest(kind=kind):
                self.assertEqual(hashlib.sha256(tpl.encode("utf-8")).hexdigest(), PROMPT_TEMPLATE_SHA256[kind])
        gpt, claude = prompt_template(PROMPT_PAGES["gpt"]), prompt_template(PROMPT_PAGES["claude"])
        for marker in ("[ISI TOPIK]", "[ISI FAKTA]", "[ISI ISTILAH]", "[ANGGARAN KATA]", "[NAMA FILE]",
                       "ATURAN FAKTA", "=== C. SEGMEN VOICE-OVER ===", "=== K. CHECKLIST ===", "Gunakan Python",
                       "[GAYA CAPTION SINGKAT]", "HookOverlay, Captions, ProgressBar", "ATURAN CERITA",
                       "[STRUKTUR]", "[JENIS HOOK]", "BEAT:", "INTERRUPT:", "sejak frame pertama"):
            with self.subTest(marker=marker):
                self.assertIn(marker, gpt)
        for marker in ("CARA MEMBACA TXT", "[OUTPUT]", "KOMPATIBILITAS RENDER", "[ISI FAKTA]", "src/data/captions.ts", "MainReel",
                       "CAPTION & ELEMEN PENDUKUNG (rekomendasi", "[GAYA CAPTION]", "createTikTokStyleCaptions",
                       "calculateMetadata", "HookOverlay", "ProgressBar", "TEKNIK ANIMASI", "useCurrentFrame()",
                       "jangan mengarang hash", "README.md", "still:hook",
                       "JANGAN memanggil delayRender() atau loadFont()", "useFontsReady()",
                       "useState(() => delayRender(",
                       "CSS transition/animation", "mask reveal", "stroke-dashoffset", "npx remotion still", "900×1400",
                       "ATURAN WAJIB STABILITAS FONT"):
            with self.subTest(marker=marker):
                self.assertIn(marker, claude)
        # Template lama memakai "15-20 detik" sebagai penanda durasi; versi ini memakai [DURASI].
        self.assertNotIn("15-20 detik", gpt + claude)
        for bad in ("ReelForge", "Colab"):
            with self.subTest(bad=bad):
                self.assertNotIn(bad, gpt + claude)
        # Pola lama yang menyebabkan timeout font tidak boleh dianjurkan lagi.
        self.assertNotIn("registrasi font yang deterministik sekali di tingkat modul", claude)

    def test_form_and_output_markup(self):
        for kind, p in self.pages.items():
            tags = {a.get("id"): (t, a) for t, a in p.tags if a.get("id")}
            with self.subTest(kind=kind):
                tag, form = tags["prompt-form"]
                self.assertEqual((tag, form.get("data-kind")), ("form", kind))
                self.assertNotIn("action", form)
                # Tanpa JS: form dan tombol salin tersembunyi, template tetap bisa disalin manual.
                for el in ("prompt-form", "prompt-copy"):
                    self.assertIn("hidden", tags[el][1])
                    self.assertIn("data-js-only", tags[el][1])
                self.assertIn("readonly", tags["prompt-output"][1])
                self.assertIn("<noscript>", self.html[kind])
                self.assertEqual(tags["prompt-status"][1].get("role"), "status")
                for name in ("topic", "duration", "description", "facts", "terms", "audience", "cta", "style"):
                    [field] = [a for t, a in p.tags if a.get("name") == name and t in ("input", "textarea")]
                    self.assertEqual(len([1 for t, a in p.tags if t == "label" and a.get("for") == field["id"]]), 1)
                [sel] = [a for t, a in p.tags if t == "select" and a.get("name") == "caption"]
                options = [a.get("value") for t, a in p.tags if t == "option"]
                if kind == "claude":
                    self.assertEqual(options[:3], ["both", "mp4", "zip"])
                    options = options[3:]
                self.assertEqual(options, ["explainer", "retensi", "auto", "auto", "openloop", "janji", "negasi",
                                           "taruhan", "listicle", "bold", "bounce", "clean", "auto"])
                self.assertIn("motion-skills (iart.ai, MIT)", self.html[kind])
                self.assertIn("claude-shorts (MIT)", self.html[kind])
                for name in ("topic", "description"):
                    self.assertIn("required", [a for t, a in p.tags if a.get("name") == name and t != "meta"][0])

    def test_pages_link_each_other_tutorial_and_ai(self):
        other = {"gpt": PROMPT_PAGES["claude"], "claude": PROMPT_PAGES["gpt"]}
        ai = {"gpt": "https://chatgpt.com/", "claude": "https://claude.ai/"}
        for kind, rel in PROMPT_PAGES.items():
            targets = [resolve(rel, h)[0] for _, _, h in self.pages[kind].links]
            with self.subTest(kind=kind):
                self.assertIn(other[kind], targets)
                self.assertIn(REMOTION_PAGE, targets)
                [a] = [a for t, a in self.pages[kind].tags if t == "a" and a.get("href") == ai[kind]]
                self.assertEqual((a.get("target"), a.get("rel")), ("_blank", "noopener"))
        for rel in (REMOTION_PAGE, GUIDE_HUB, "index.html"):
            targets = [resolve(rel, h)[0] for _, _, h in parse(rel).links]
            with self.subTest(page=rel):
                self.assertIn(PROMPT_PAGES["gpt"], targets)
        tutorial_targets = [resolve(REMOTION_PAGE, h)[0] for _, _, h in parse(REMOTION_PAGE).links]
        self.assertIn(PROMPT_PAGES["claude"], tutorial_targets)

    def test_thumbnails_on_hub_and_as_og_image(self):
        hub = parse(GUIDE_HUB)
        hub_imgs = [resolve(GUIDE_HUB, i["src"])[0] for i in hub.imgs]
        hub_links = [resolve(GUIDE_HUB, h)[0] for _, _, h in hub.links]
        self.assertIn("generator-prompt", hub.ids)
        for kind, slug in (("gpt", "chatgpt"), ("claude", "claude")):
            thumb = f"{REMOTION_IMG_DIR}/thumb-prompt-{slug}.jpg"
            meta = lambda key: [a.get("content") for t, a in self.pages[kind].tags
                                if t == "meta" and (a.get("property") == key or a.get("name") == key)]
            with self.subTest(kind=kind):
                self.assertEqual(image_size(ROOT / thumb), (1200, 675))
                self.assertIn(thumb, hub_imgs)
                self.assertIn(PROMPT_PAGES[kind], hub_links)
                self.assertEqual(meta("og:image"), [SITE_URL + thumb])
                self.assertEqual(meta("twitter:image"), [SITE_URL + thumb])
                self.assertEqual((meta("og:image:width"), meta("og:image:height")), (["1200"], ["675"]))
                self.assertTrue(meta("og:image:alt")[0].startswith("Thumbnail generator prompt"))

    def test_claude_page_offers_laptop_and_colab_for_zip(self):
        rel = PROMPT_PAGES["claude"]
        self.assertIn("ekspor-zip", self.pages["claude"].ids)
        links = [(resolve(rel, h), h) for _, _, h in self.pages["claude"].links]
        targets = [(r[0], r[1]) for r, _ in links]
        self.assertIn((REMOTION_PAGE, "render-lokal"), targets)
        self.assertIn((REMOTION_PAGE, "render-colab"), targets)
        tutorial_ids = parse(REMOTION_PAGE).ids
        self.assertLessEqual({"render-lokal", "render-colab"}, tutorial_ids)
        [a] = [a for t, a in self.pages["claude"].tags if t == "a" and a.get("href") == COLAB_NOTEBOOK_URL]
        self.assertEqual((a.get("target"), a.get("rel")), ("_blank", "noopener"))
        # Halaman ChatGPT tidak membahas ekspor ZIP.
        self.assertNotIn("ekspor-zip", self.pages["gpt"].ids)

    def test_script_only_on_generator_pages(self):
        for rel in PAGES:
            has = any(s.endswith("prompt-generator.js") for s in parse(rel).scripts)
            with self.subTest(page=rel):
                self.assertEqual(has, rel in PROMPT_PAGES.values())

    def test_js_static_safety(self):
        for bad in ("innerHTML", "outerHTML", "insertAdjacentHTML", "document.write", "fetch(",
                    "XMLHttpRequest", "sendBeacon", "sessionStorage", "document.cookie", "eval(", "http"):
            with self.subTest(bad=bad):
                self.assertNotIn(bad, self.js)
        # localStorage hanya disentuh di dalam try/catch.
        for line in self.js.splitlines():
            if "localStorage" in line and not line.lstrip().startswith("//"):
                with self.subTest(line=line.strip()):
                    self.assertIn("try {", line)

    @unittest.skipUnless(shutil.which("node"), "node tidak tersedia")
    def test_js_matches_reference_in_node(self):
        cases = [
            {},
            {"topic": "CLI Proxy", "duration": "18.4", "description": "Deskripsi", "audience": "Dev",
             "cta": "Follow", "style": "Line Art"},
            {"topic": "  Remotion  ", "duration": "4", "description": "x"},
            {"topic": "A", "duration": "181", "description": "B", "audience": "C", "cta": "D", "style": "E"},
            {"topic": "A", "duration": "abc", "description": "B"},
            {"topic": "A", "duration": "45", "description": "B"},
            {"topic": "A", "duration": "", "description": "B"},
            {"topic": "Hermes Agent", "duration": "50", "description": "Pengenalan",
             "facts": "- Fakta 1\n- Fakta 2 [ISI CTA]", "terms": "agentic = e-jen-tik", "cta": "Kunjungi profil"},
            {"topic": "Café Ünïcode!!", "duration": "12.6", "description": "x", "caption": "bounce"},
            {"topic": "A", "description": "B", "caption": "clean"},
            {"topic": "A", "description": "B", "caption": "auto"},
            {"topic": "A", "description": "B", "caption": "evil"},
            {"topic": "A", "description": "B", "structure": "retensi", "hook": "negasi"},
            {"topic": "A", "description": "B", "structure": "auto", "hook": "listicle"},
            {"topic": "A", "description": "B", "structure": "zzz", "hook": "zzz"},
            {"topic": "Hermes Agent", "description": "B", "output": "mp4"},
            {"topic": "Hermes Agent", "description": "B", "output": "zip"},
            {"topic": "Hermes Agent", "description": "B", "output": "[ISI CTA]"},
        ]
        templates = {k: prompt_template(rel) for k, rel in PROMPT_PAGES.items()}
        script = (
            "const g = require(process.argv[1]); const d = JSON.parse(process.argv[2]);"
            "const out = {};"
            "for (const k of ['gpt','claude']) out[k] = d.cases.map(c => g.buildPrompt(k, d.templates[k], c));"
            "out.dollar = g.buildPrompt('gpt', d.templates.gpt, {topic: 'Rp $& 10', description: 'x'});"
            "out.extra = [g.wordBudget('50'), g.wordBudget('x'), g.slug('  Hermes Agent! '), g.slug('***')];"
            "out.toggle = [g.toggleStyle('', 'Line Art'), g.toggleStyle('Line Art, Neon', 'line art'),"
            " g.hasStyle('Premium dark tech, neon', 'premium DARK tech')];"
            "out.missing = [g.missingRequired({}), g.missingRequired({topic: ' ', description: 'x'})];"
            "out.sanitize = g.sanitize({topic: 5, description: 'y'.repeat(2000), evil: 'x'});"
            "out.captions = g.CAPTIONS; out.structures = g.STRUCTURES; out.hooks = g.HOOKS; out.outputs = g.OUTPUTS;"
            "out.badcap = g.sanitize({caption: 'x', topic: 't'});"
            "console.log(JSON.stringify(out));"
        )
        payload = json.dumps({"cases": cases, "templates": templates})
        res = subprocess.run(["node", "-e", script, str(ROOT / PROMPT_JS), payload],
                             capture_output=True, text=True, check=True, timeout=30)
        r = json.loads(res.stdout)
        for kind in ("gpt", "claude"):
            for i, c in enumerate(cases):
                with self.subTest(kind=kind, case=i):
                    self.assertEqual(r[kind][i], py_build_prompt(kind, templates[kind], c, r["captions"], r["structures"], r["hooks"], r["outputs"]))
        self.assertEqual(sorted(r["captions"]), ["auto", "bold", "bounce", "clean"])
        self.assertIn("#FFD700", r["captions"]["bold"]["spec"])
        self.assertEqual(r["badcap"], {"topic": "t"})
        self.assertEqual(sorted(r["structures"]), ["auto", "explainer", "retensi"])
        self.assertEqual(sorted(r["outputs"]), ["both", "mp4", "zip"])
        out_zip = r["claude"][cases.index({"topic": "Hermes Agent", "description": "B", "output": "zip"})]
        out_mp4 = r["claude"][cases.index({"topic": "Hermes Agent", "description": "B", "output": "mp4"})]
        self.assertIn("remotion_reels_hermes_agent.zip", out_zip)
        self.assertNotIn(" reels_hermes_agent.mp4", out_zip)
        self.assertIn(" reels_hermes_agent.mp4", out_mp4)
        self.assertEqual(sorted(r["hooks"]), ["auto", "janji", "listicle", "negasi", "openloop", "taruhan"])
        self.assertIn("Topik: Rp $& 10", r["dollar"], "pola $ dari pengguna tidak ditafsirkan")
        self.assertEqual(r["extra"], ["100–110 kata", "40–44 kata", "hermes_agent", "video"])
        self.assertEqual(r["toggle"], ["Line Art", "Neon", True])
        self.assertEqual(r["missing"], [["topic", "description"], ["topic"]])
        self.assertEqual(r["sanitize"], {"description": "y" * 1000})


def to_whatsapp_number(local):
    digits = re.sub(r"\D", "", local)
    return "62" + digits[1:] if digits.startswith("0") else digits


class TesterFormTests(unittest.TestCase):
    def setUp(self):
        self.page = parse(TESTER_PAGE)
        self.html = (ROOT / TESTER_PAGE).read_text(encoding="utf-8")
        self.js = (ROOT / TESTER_JS).read_text(encoding="utf-8")

    def elements(self, tag, **attrs):
        return [a for t, a in self.page.tags
                if t == tag and all(a.get(k) == v for k, v in attrs.items())]

    def test_section_anchor_and_script_only_on_detail_page(self):
        self.assertIn("daftar-tester", self.page.ids)
        self.assertIn("../../" + TESTER_JS, self.page.scripts)
        for rel in PAGES:
            if rel != TESTER_PAGE:
                with self.subTest(page=rel):
                    self.assertFalse(any(s.endswith("tester.js") for s in parse(rel).scripts))

    def test_form_has_no_submission_target_and_is_hidden_without_js(self):
        [form] = self.elements("form", id="form-tester")
        self.assertNotIn("action", form)
        self.assertNotIn("method", form)
        self.assertIn("hidden", form, "tanpa JS formulir tidak boleh bisa dikirim ke situs")
        self.assertEqual(form.get("data-wa-phone"), WA_DISPLAY)
        self.assertEqual(form.get("data-app"), "Jelajah Nusantara")

    def test_whatsapp_number_conversion(self):
        self.assertEqual(to_whatsapp_number(WA_DISPLAY), WA_NUMBER)
        self.assertEqual(to_whatsapp_number("0882-7542-6716"), WA_NUMBER)
        self.assertIn(WA_DISPLAY, self.html)

    def test_email_field_required_and_labelled(self):
        [email] = self.elements("input", id="tester-email")
        self.assertEqual(email.get("type"), "email")
        self.assertEqual(email.get("name"), "email")
        self.assertIn("required", email)
        self.assertEqual(email.get("autocomplete"), "email")
        self.assertEqual(email.get("maxlength"), "254")
        self.assertNotIn("pattern", email, "akun Google apa pun, bukan hanya Gmail")
        self.assertEqual(len(self.elements("label", **{"for": "tester-email"})), 1)
        for ref in email["aria-describedby"].split():
            self.assertIn(ref, self.page.ids)
        self.assertRegex(self.html, r'<label for="tester-email">Email akun Google <span class="req">\(wajib\)</span></label>')

    def test_message_field_optional_with_maxlength(self):
        [msg] = self.elements("textarea", id="tester-pesan")
        self.assertEqual(msg.get("name"), "pesan")
        self.assertNotIn("required", msg)
        self.assertEqual(msg.get("maxlength"), "500")
        self.assertEqual(len(self.elements("label", **{"for": "tester-pesan"})), 1)
        for ref in msg["aria-describedby"].split():
            self.assertIn(ref, self.page.ids)

    def test_submit_button_and_live_status(self):
        self.assertIn('<button class="btn btn-primary" type="submit">Kirim permintaan lewat WhatsApp</button>', self.html)
        [status] = self.elements("div", id="tester-status")
        self.assertEqual(status.get("role"), "status")
        self.assertEqual(status.get("aria-live"), "polite")

    def test_explains_manual_unguaranteed_access(self):
        for phrase in ("secara manual", "belum tentu disetujui", "akun Google yang sama",
                       "menekan Kirim di WhatsApp", PLAY_TESTING_URL):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, self.html)

    def test_noscript_fallback_link(self):
        # Di luar <noscript> agar tetap tampil jika tester.js gagal dimuat; JS menyembunyikannya.
        block = re.search(r'<div class="callout" id="tester-fallback">(.*?)</div>', self.html, re.S).group(1)
        self.assertIn("<noscript>", block)
        self.assertIn('href="' + NOSCRIPT_WA_URL + '"', block)
        self.assertIn(WA_DISPLAY, block)
        self.assertIn("tekan Kirim sendiri", block)
        self.assertIn("getElementById('tester-fallback')", self.js)

    def test_js_static_safety(self):
        self.assertIn("'https://wa.me/' + number + '?text=' + encodeURIComponent(text)", self.js)
        self.assertIn("textContent", self.js)
        for bad in ("innerHTML", "outerHTML", "insertAdjacentHTML", "document.write", "fetch(",
                    "XMLHttpRequest", "sendBeacon", "localStorage", "sessionStorage",
                    "document.cookie", ".submit()", "eval(", "http://"):
            with self.subTest(bad=bad):
                self.assertNotIn(bad, self.js)
        self.assertEqual(re.findall(r"https?://[^'\"\s]+", self.js), ["https://wa.me/"])

    @unittest.skipUnless(shutil.which("node"), "node tidak tersedia")
    def test_js_behaviour_in_node(self):
        script = (
            "const t = require(process.argv[1]);"
            "const msg = t.buildMessage('Jelajah Nusantara', ' a.b+tag@example.co.id ', 'Halo & #1\\r\\nHP: Pixel 7?\\u0007');"
            "console.log(JSON.stringify({"
            " number: t.toWhatsAppNumber('088275426716'),"
            " valid: ['nama@gmail.com', 'a.b+tag@example.co.id', ' x@y.id '].map(t.isValidEmail),"
            " invalid: ['', '   ', 'nama', 'nama@', '@gmail.com', 'a b@gmail.com', 'a@b', 'x'.repeat(250) + '@g.co'].map(t.isValidEmail),"
            " msg: msg,"
            " url: t.buildWhatsAppUrl(t.toWhatsAppNumber('088275426716'), msg),"
            " empty: t.buildMessage('Jelajah Nusantara', 'x@y.id', '   '),"
            " long: t.cleanMessage('a'.repeat(900)).length"
            "}));"
        )
        out = subprocess.run(["node", "-e", script, str(ROOT / TESTER_JS)],
                             capture_output=True, text=True, check=True, timeout=30)
        r = json.loads(out.stdout)
        self.assertEqual(r["number"], WA_NUMBER)
        self.assertEqual(r["valid"], [True, True, True])
        self.assertEqual(r["invalid"], [False] * 8)
        expected_msg = (
            "Halo Admin Siap Digital, saya ingin mendaftar sebagai tester Android aplikasi Jelajah Nusantara di Google Play.\n\n"
            "Email akun Google: a.b+tag@example.co.id\n"
            "Pesan: Halo & #1\nHP: Pixel 7?\n\n"
            "Saya memahami email ini ditambahkan secara manual ke daftar tester Google Play dan permintaan belum tentu disetujui."
        )
        self.assertEqual(r["msg"], expected_msg)
        self.assertEqual(r["url"], wa_url(expected_msg))
        self.assertTrue(r["url"].startswith("https://wa.me/6288275426716?text=Halo%20Admin"))
        for raw in ("\n", " ", "&", "#", "+", "?"):
            self.assertNotIn(raw, r["url"].split("?text=", 1)[1])
        self.assertIn("%0A", r["url"])
        self.assertIn("a.b%2Btag%40example.co.id", r["url"])
        self.assertIn("Pesan: -", r["empty"])
        self.assertEqual(r["long"], 500)


class LegalTesterDisclosureTests(unittest.TestCase):
    def test_privacy_describes_whatsapp_tester_processing(self):
        text = (ROOT / "privacy/index.html").read_text(encoding="utf-8")
        p = parse("privacy/index.html")
        self.assertIn("tester", p.ids)
        for phrase in ("WhatsApp (Meta)", "Google Play", "secara manual", "belum tentu disetujui",
                       WA_DISPLAY, "tidak mengirim isian formulir", "hanya untuk mengelola tester",
                       "belum ditetapkan"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)
        # Pengungkapan data lokal dan cadangan Android tetap ada.
        for phrase in ("disimpan secara lokal di perangkat Anda", "Cadangan bawaan Android",
                       "Kami tidak menyimpan cadangan data Anda", "tidak meminta izin akses internet"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)

    def test_terms_reflect_test_access_limits(self):
        text = (ROOT / "terms/index.html").read_text(encoding="utf-8")
        for phrase in ("pengujian tertutup di Google Play", "secara manual", "tidak dijamin diterima",
                       "akun Google yang sudah terdaftar sebagai tester"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)


if __name__ == "__main__":
    unittest.main()
