# siapdigital.id — situs studio Siap Digital

Situs statis (HTML/CSS/JS tanpa dependensi, tanpa build step) untuk studio Siap Digital dan
katalog aplikasinya.

| Halaman | Berkas |
| --- | --- |
| Beranda | `index.html` |
| Katalog aplikasi | `apps/index.html` |
| Jelajah Nusantara | `apps/jelajah-nusantara/index.html` |
| Kebijakan Privasi | `privacy/index.html` |
| Ketentuan Layanan | `terms/index.html` |

Semua tautan internal bersifat relatif, sehingga situs bisa disajikan dari root domain maupun subpath.

## Pratinjau lokal

```bash
python3 -m http.server 8000   # lalu buka http://localhost:8000/
```

## Tes

Validasi tautan dan struktur (hanya pustaka standar Python):

```bash
python3 -m unittest discover -s tests -v
```

Tes memeriksa: semua halaman wajib ada, tautan internal dan `#fragment` dapat di-resolve, navigasi
utama seragam dengan `aria-current` yang benar, satu `<h1>` per halaman, `lang="id"`, tautan eksternal
hanya ke domain yang diizinkan, serta tidak ada tautan Play Store, `mailto:`, `iframe`, atau skrip
pihak ketiga.

## Sumber kanonik dan ekspor

Sumber kanonik: `/home/dev/workspace/sodikin/game/landing-page` (diabaikan oleh repo game).
Repositori publikasi: <https://github.com/sodikinnaa/siapdigital.id>.

```bash
python3 scripts/export_site.py /path/ke/clone/siapdigital.id
```

Skrip menyalin pohon situs ke clone tujuan (tanpa menyentuh `.git`), menghapus berkas basi, lalu
memverifikasi kesetaraan byte (SHA-256) kedua arah.

## Status data & keputusan yang belum selesai

Fakta di situs bersumber dari dokumen repo aplikasi (PRD, catatan rilis v0.1.1) dan metadata rilis
GitHub (`aapt2 dump badging` di `signing-verification.txt`: APK v0.1.1 tidak meminta izin `INTERNET`).

**Belum terselesaikan — perlu keputusan pemilik:**

- [ ] **Kontak resmi pemilik** (email/alamat) — **belum ada**. Halaman privasi & ketentuan menyatakan
      hal ini secara terbuka dan mengarahkan ke GitHub Issues sementara. Jangan isi dengan alamat
      karangan.
- [ ] **Identitas hukum** (nama entitas/badan usaha, alamat terdaftar) — belum diketahui; tidak dicantumkan.
- [ ] **Hukum yang berlaku / yurisdiksi** di Ketentuan Layanan — sengaja belum ditulis.
- [ ] **Tinjauan hukum** Kebijakan Privasi & Ketentuan Layanan — keduanya berstatus *draf*, belum
      ditinjau penasihat hukum. Tidak ada klaim sertifikasi/kepatuhan.
- [ ] **Penyedia hosting & domain** — belum diputuskan. Belum ada DNS, GitHub Pages, atau deployment
      produksi (memerlukan otorisasi pemilik). Setelah dipilih, perbarui bagian log hosting di halaman privasi
      bila perlu.
- [ ] **Ikon aplikasi** — tidak dipakai di situs; lisensi aset desain/ikon belum dikonfirmasi
      (lihat catatan rilis v0.1.1). Situs memakai monogram "JN" berbasis CSS.
- [ ] **Tautan rilis** v0.1.1 mengarah ke repo aplikasi yang **privat**; pengunjung umum akan
      mendapat 404 sampai repo/rilis dibuat publik. Tidak ada tautan Google Play karena aplikasi belum
      diunggah ke Play.
- [ ] **Tinjauan konten sejarah** oleh ahli — masih tertunda (ditandai di situs).
