// Generator prompt ReelForge (versi situs, turunan V5.4) untuk ChatGPT dan Claude.
// Template prompt dibaca dari <textarea> di halaman (satu sumber, tetap terbaca tanpa JS).
// Tidak ada permintaan jaringan: isian hanya disimpan di localStorage browser ini agar
// terbawa antara halaman ChatGPT dan Claude. Fungsi murni diekspor untuk pengujian (Node).
(function () {
  var STORAGE_KEY = 'reelforge-prompt-v1';
  var FIELDS = ['topic', 'duration', 'description', 'facts', 'terms', 'audience', 'cta', 'style', 'caption', 'structure', 'hook'];
  var REQUIRED = ['topic', 'description'];
  var MAX_LENGTH = { topic: 120, duration: 3, description: 1000, facts: 1500, terms: 500, audience: 200, cta: 200, style: 300, caption: 10, structure: 10, hook: 10 };
  // Preset caption diadaptasi dari claude-shorts (MIT, Daniel Agrici); posisi disesuaikan dengan safe area Reels.
  var CAPTIONS = {
    bold: {
      name: 'Bold (kapital tegas, kata aktif disorot kuning)',
      spec: 'Bold. Huruf kapital, 2–3 kata per halaman (gabung kata dalam 800 ms), ±72 px, teks putih dengan kata aktif kuning #FFD700, outline hitam 3 px, posisi ±420 px dari bawah. Masuk dengan pop spring (mass 1, damping 12, stiffness 200). Font tebal dari design tokens.'
    },
    bounce: {
      name: 'Bounce (memantul, warna bergantian)',
      spec: 'Bounce. Huruf kapital, 1–2 kata per halaman (gabung kata dalam 600 ms), ±84 px, warna halaman bergantian dari palet aksen (atau cyan, magenta, lime, kuning, oranye, pink), outline hitam 4 px, posisi ±420 px dari bawah. Skala memantul 70% → ±120% → 100% (spring mass 1, damping 8, stiffness 180).'
    },
    clean: {
      name: 'Clean (minimalis, fade halus)',
      spec: 'Clean. Huruf asli (tanpa kapital paksa), 3–5 kata per halaman (gabung kata dalam 1500 ms), ±56 px, teks putih dengan kata aktif sedikit lebih redup (#E0E0E0), bayangan lembut, posisi ±420 px dari bawah. Muncul dengan fade 6 frame.'
    },
    auto: {
      name: 'dipilih Claude sesuai nada video (tegas, memantul, atau bersih)',
      spec: 'Pilih sendiri yang paling cocok dengan nada video: Bold (kapital, sorot kata aktif), Bounce (memantul, warna bergantian), atau Clean (minimalis, fade halus). Tetap di atas ±420 px dari bawah dan tidak menutupi teks layar.'
    }
  };

  // Struktur cerita dan jenis hook diadaptasi dari motion-skills (iart.ai, MIT).
  var STRUCTURES = {
    explainer: 'Edukasi (explainer): Problem ±20% (sebut masalah dengan bahasa penonton) → Stakes (kenapa penting) → Solusi ±15% (satu kalimat) → Cara kerja ±45% (1–3 langkah konkret, satu langkah per PART) → Payoff + CTA ±20%. Pilih SATU analogi dari dunia penonton dan pakai konsisten di VO dan visual.',
    retensi: 'Retensi: Hook (0–1 detik, membuka rasa penasaran) → Setup (alasan menonton, sampai ±4 detik) → Body (beberapa beat, satu ide per beat) → Payoff yang menjawab hook, atau loop kembali ke frame pertama.',
    auto: 'Pilih yang paling cocok dan sebutkan di BRIEF: Edukasi (Problem → Stakes → Solusi → Cara kerja 1–3 langkah → Payoff + CTA, dengan satu analogi) atau Retensi (Hook → Setup → Body beat → Payoff/loop).'
  };
  var HOOKS = {
    auto: 'Pilih satu jenis hook yang paling cocok dan sebutkan di BRIEF: open loop, janji langsung, negasi, taruhan, atau listicle.',
    openloop: 'Open loop, misalnya "Alasan sebenarnya kenapa …"; jawabannya baru diberikan di payoff.',
    janji: 'Janji langsung, misalnya "… dalam 30 detik, tanpa …"; sebut hasil dan batas waktunya.',
    negasi: 'Negasi, misalnya "Berhenti …" atau "Ternyata … itu keliru"; untuk sudut pandang tegas.',
    taruhan: 'Taruhan, misalnya "Kesalahan ini bikin … jangan diulangi"; tetap hanya memakai fakta yang diberikan.',
    listicle: 'Listicle, misalnya "3 … yang … (nomor 3 paling …)"; siapkan rujukan ke depan.'
  };

  // Acuan kecepatan bicara Cartesia (dari contoh tutorial: 92 kata ≈ 41 detik).
  var WORDS_PER_SECOND_LOW = 2.0;
  var WORDS_PER_SECOND_HIGH = 2.2;
  var EXAMPLE = {
    topic: 'CLI Proxy',
    duration: '20',
    description: 'CLI Proxy membantu menghubungkan terminal dengan layanan API melalui perantara yang terstruktur.',
    audience: 'Developer, programmer, pemula AI',
    cta: 'Follow untuk tutorial berikutnya',
    terms: 'CLI = si-el-ai, API = ei-pi-ai',
    style: 'Premium dark tech, neon cyan-violet, cinematic terminal UI'
  };

  function text(value) {
    return value == null ? '' : String(value).trim();
  }

  // Angka 5–180 dibulatkan; selain itu kembali ke 20 detik (sama dengan ReelForge).
  function seconds(value) {
    var s = Number(text(value));
    return isFinite(s) && s >= 5 && s <= 180 ? Math.round(s) : 20;
  }

  function durationLabel(value) {
    return seconds(value) + ' detik';
  }

  function wordBudget(value) {
    var s = seconds(value);
    return Math.round(s * WORDS_PER_SECOND_LOW) + '–' + Math.round(s * WORDS_PER_SECOND_HIGH) + ' kata';
  }

  // Nama file: huruf kecil, garis bawah, tanpa aksen; maksimal 40 karakter.
  function slug(value) {
    var s = text(value).toLowerCase();
    if (s.normalize) s = s.normalize('NFKD').replace(/[\u0300-\u036f]/g, '');
    s = s.replace(/[^a-z0-9]+/g, '_').replace(/^_+|_+$/g, '').slice(0, 40).replace(/_+$/, '');
    return s || 'video';
  }

  function values(raw) {
    raw = raw || {};
    return {
      topic: text(raw.topic) || '[ISI TOPIK]',
      description: text(raw.description) || '[ISI DESKRIPSI]',
      audience: text(raw.audience) || '[ISI AUDIENS]',
      cta: text(raw.cta) || '[ISI CTA]',
      facts: text(raw.facts) || '(tidak diisi)',
      terms: text(raw.terms) || '(tidak diisi)',
      duration: durationLabel(raw.duration),
      budget: wordBudget(raw.duration),
      slug: slug(raw.topic),
      style: text(raw.style) || 'modern premium',
      caption: CAPTIONS[text(raw.caption)] ? text(raw.caption) : 'bold',
      structure: STRUCTURES[text(raw.structure)] ? text(raw.structure) : 'explainer',
      hook: HOOKS[text(raw.hook)] ? text(raw.hook) : 'auto'
    };
  }

  var PLACEHOLDER = /\[(STRUKTUR|JENIS HOOK|GAYA CAPTION SINGKAT|GAYA CAPTION|ISI TOPIK|ISI DESKRIPSI|ISI FAKTA|ISI ISTILAH|ISI AUDIENS|ISI CTA|DURASI|ANGGARAN KATA|NAMA FILE|NAMA ZIP)\]/g;

  // Satu kali jalan dengan fungsi pengganti: teks pengguna tidak diganti ulang dan pola $ tidak ditafsirkan.
  function fillTemplate(template, v) {
    var map = {
      'ISI TOPIK': v.topic, 'ISI DESKRIPSI': v.description, 'ISI FAKTA': v.facts, 'ISI ISTILAH': v.terms,
      'ISI AUDIENS': v.audience, 'ISI CTA': v.cta, 'DURASI': v.duration, 'ANGGARAN KATA': v.budget,
      'STRUKTUR': STRUCTURES[v.structure], 'JENIS HOOK': HOOKS[v.hook],
      'GAYA CAPTION': CAPTIONS[v.caption].spec, 'GAYA CAPTION SINGKAT': CAPTIONS[v.caption].name,
      'NAMA FILE': 'motion_graphic_' + v.slug + '.txt', 'NAMA ZIP': 'remotion_reels_' + v.slug + '.zip'
    };
    return String(template).replace(PLACEHOLDER, function (_, key) { return map[key]; });
  }

  function buildPrompt(kind, template, raw) {
    var v = values(raw);
    var head = 'Topik: ' + v.topic + '\nDeskripsi: ' + v.description + '\nAudiens: ' + v.audience + '\nCTA: ' + v.cta + '\n';
    if (kind === 'gpt') {
      return 'KONFIGURASI VIDEO\n' + head + 'Durasi: ' + v.duration + ' (anggaran voice-over ' + v.budget + ')' +
        '\nGaya visual: ' + v.style + '\n\n' + fillTemplate(template, v);
    }
    return 'KONFIGURASI PROJECT (IKUTI TXT & AUDIO TERLAMPIR)\n' + head + 'Target durasi: ' + v.duration +
      '\nGaya visual: ' + v.style + '\n\n' + fillTemplate(template, v);
  }

  function missingRequired(raw) {
    return REQUIRED.filter(function (k) { return !text(raw && raw[k]); });
  }

  // Data dari localStorage tidak dipercaya: hanya string per field, dipotong sesuai batas.
  function sanitize(data) {
    var clean = {};
    if (!data || typeof data !== 'object') return clean;
    FIELDS.forEach(function (k) {
      if (typeof data[k] === 'string') clean[k] = data[k].slice(0, MAX_LENGTH[k]);
    });
    if (clean.caption && !CAPTIONS[clean.caption]) delete clean.caption;
    if (clean.structure && !STRUCTURES[clean.structure]) delete clean.structure;
    if (clean.hook && !HOOKS[clean.hook]) delete clean.hook;
    return clean;
  }

  // Gaya visual disimpan sebagai daftar dipisah koma; chip menambah atau menghapus satu gaya.
  function styleTokens(value) {
    return text(value).split(',').map(text).filter(Boolean);
  }

  function hasStyle(value, token) {
    var t = token.toLowerCase();
    return styleTokens(value).some(function (s) { return s.toLowerCase() === t; });
  }

  function toggleStyle(value, token) {
    var tokens = styleTokens(value);
    var t = token.toLowerCase();
    var kept = tokens.filter(function (s) { return s.toLowerCase() !== t; });
    if (kept.length === tokens.length) kept.push(token);
    return kept.join(', ');
  }

  var api = {
    durationLabel: durationLabel,
    wordBudget: wordBudget,
    slug: slug,
    buildPrompt: buildPrompt,
    missingRequired: missingRequired,
    sanitize: sanitize,
    toggleStyle: toggleStyle,
    hasStyle: hasStyle,
    EXAMPLE: EXAMPLE,
    CAPTIONS: CAPTIONS,
    STRUCTURES: STRUCTURES,
    HOOKS: HOOKS
  };

  if (typeof module === 'object' && module.exports) {
    module.exports = api;
    return;
  }

  var form = document.getElementById('prompt-form');
  var output = document.getElementById('prompt-output');
  if (!form || !output) return;

  var kind = form.getAttribute('data-kind') === 'claude' ? 'claude' : 'gpt';
  var template = output.defaultValue;
  var counter = document.getElementById('prompt-count');
  var durationHelp = document.getElementById('pf-duration-help');
  var status = document.getElementById('prompt-status');
  var copyBtn = document.getElementById('prompt-copy');
  var chips = Array.prototype.slice.call(form.querySelectorAll('[data-style]'));
  var copyLabel = copyBtn.textContent;
  var resetTimer = null;

  function field(k) { return form.elements[k]; }

  function current() {
    var data = {};
    FIELDS.forEach(function (k) { data[k] = field(k).value; });
    return data;
  }

  function load() {
    try { return sanitize(JSON.parse(window.localStorage.getItem(STORAGE_KEY) || 'null')); } catch (e) { return {}; }
  }

  function save(data) {
    try { window.localStorage.setItem(STORAGE_KEY, JSON.stringify(data)); } catch (e) { /* abaikan */ }
  }

  function forget() {
    try { window.localStorage.removeItem(STORAGE_KEY); } catch (e) { /* abaikan */ }
  }

  function say(message, isError) {
    status.textContent = message;
    status.classList.toggle('is-error', !!isError);
  }

  function markInvalid(keys) {
    REQUIRED.forEach(function (k) {
      field(k).setAttribute('aria-invalid', keys.indexOf(k) >= 0 ? 'true' : 'false');
    });
  }

  function render() {
    var data = current();
    output.value = buildPrompt(kind, template, data);
    counter.textContent = output.value.length.toLocaleString('id-ID') + ' karakter';
    if (durationHelp) durationHelp.textContent = '5–180 detik. Anggaran voice-over: ' + durationLabel(data.duration) + ' ≈ ' + wordBudget(data.duration) + '.';
    chips.forEach(function (chip) {
      chip.setAttribute('aria-pressed', hasStyle(data.style, chip.getAttribute('data-style')) ? 'true' : 'false');
    });
    if (form.querySelector('[aria-invalid="true"]')) markInvalid(missingRequired(data));
    return data;
  }

  function fill(data) {
    FIELDS.forEach(function (k) { if (typeof data[k] === 'string') field(k).value = data[k]; });
  }

  function copied() {
    copyBtn.textContent = '✓ Tersalin';
    say(kind === 'gpt'
      ? 'Prompt tersalin. Tempel di ChatGPT (Ctrl+V), lalu kirim.'
      : 'Prompt tersalin. Tempel di Claude, lampirkan file TXT dan audio, lalu kirim.');
    clearTimeout(resetTimer);
    resetTimer = setTimeout(function () { copyBtn.textContent = copyLabel; }, 2500);
  }

  function copyFallback() {
    output.focus();
    output.select();
    var ok = false;
    try { ok = document.execCommand('copy'); } catch (e) { ok = false; }
    if (ok) copied();
    else say('Teks prompt sudah dipilih. Tekan Ctrl+C (atau tahan lalu Salin di ponsel).', true);
  }

  form.addEventListener('input', function () { save(render()); });
  form.addEventListener('change', function () { save(render()); });
  form.addEventListener('submit', function (e) { e.preventDefault(); });

  chips.forEach(function (chip) {
    chip.addEventListener('click', function () {
      field('style').value = toggleStyle(field('style').value, chip.getAttribute('data-style'));
      save(render());
    });
  });

  document.getElementById('prompt-example').addEventListener('click', function () {
    fill(EXAMPLE);
    markInvalid([]);
    save(render());
    say('Contoh "CLI Proxy" dimuat. Ganti dengan topik Anda sendiri.');
  });

  document.getElementById('prompt-reset').addEventListener('click', function () {
    FIELDS.forEach(function (k) { field(k).value = k === 'duration' ? '20' : ({ caption: 'bold', structure: 'explainer', hook: 'auto' }[k] || ''); });
    forget();
    markInvalid([]);
    render();
    say('Isian dikosongkan dan dihapus dari browser ini.');
    field('topic').focus();
  });

  copyBtn.addEventListener('click', function () {
    var missing = missingRequired(current());
    if (missing.length) {
      markInvalid(missing);
      say('Isi Topik dan Deskripsi dulu agar prompt tidak berisi penanda [ISI ...].', true);
      field(missing[0]).focus();
      return;
    }
    var value = output.value;
    if (navigator.clipboard && window.isSecureContext) {
      navigator.clipboard.writeText(value).then(copied, copyFallback);
    } else {
      copyFallback();
    }
  });

  fill(load());
  render();
  Array.prototype.forEach.call(document.querySelectorAll('[data-js-only]'), function (el) { el.hidden = false; });
})();
