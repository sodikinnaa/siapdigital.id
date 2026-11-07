# Siap Digital

Situs resmi Siap Digital: katalog aplikasi, informasi produk, panduan bergambar, Kebijakan Privasi, dan Ketentuan Layanan.

## Halaman

- Beranda: `index.html`
- Katalog aplikasi: `apps/`
- Jelajah Nusantara: `apps/jelajah-nusantara/`
- Kebijakan Privasi: `privacy/`
- Ketentuan Layanan: `terms/`
- Katalog panduan: `panduan/`
- Panduan transfer akun kampus ke Gmail: `panduan/transfer-konten-google/`
- Tutorial Remotion (ChatGPT → Cartesia → Claude → MP4/ZIP): `panduan/remotion-reelforge/`
- Generator prompt ChatGPT: `panduan/remotion-reelforge/prompt-chatgpt/`
- Generator prompt Claude: `panduan/remotion-reelforge/prompt-claude/`
- Tutorial Hermes Agent (Codespace AI Lab → Tailscale → CLIProxyAPI → Hermes): `panduan/hermes-agent/`

Website: https://sodikinnaa.github.io/siapdigital.id/

## Pengujian

```bash
python3 -m unittest discover -s tests
```

Tes memeriksa tautan internal, navigasi, dimensi gambar (PNG/JPEG/WebP), metadata tangkapan layar, konten wajib tiap halaman, serta template dan logika generator prompt (dijalankan di Node bila tersedia).
