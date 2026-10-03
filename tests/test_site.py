"""Validasi tautan dan struktur situs statis (hanya pustaka standar)."""

import json
import posixpath
import re
import shutil
import struct
import subprocess
import unittest
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

ALLOWED_EXTERNAL = {
    "https://github.com/sodikinnaa/siapdigital.id/issues",
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

    def test_external_urls_exact(self):
        # Hanya URL pengujian Play dan nomor WhatsApp yang diberikan; tanpa varian lain.
        for rel in PAGES:
            text = (ROOT / rel).read_text(encoding="utf-8")
            with self.subTest(page=rel):
                for url in re.findall(r'https?://[^\s"<>]*play\.google\.com[^\s"<>]*', text):
                    self.assertEqual(url, PLAY_TESTING_URL)
                for url in re.findall(r'https?://[^\s"<>]*wa\.me[^\s"<>]*', text):
                    self.assertEqual(url, NOSCRIPT_WA_URL)
                for url in re.findall(r'https?://[^\s"<>]+', text):
                    if urlsplit(url).netloc.endswith("siapdigital.id"):
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
