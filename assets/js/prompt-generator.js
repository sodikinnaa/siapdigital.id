// Generator prompt ReelForge V5.4 untuk ChatGPT dan Claude.
// Template prompt dibaca dari <textarea> di halaman (satu sumber, tetap terbaca tanpa JS).
// Tidak ada permintaan jaringan: isian hanya disimpan di localStorage browser ini agar
// terbawa antara halaman ChatGPT dan Claude. Fungsi murni diekspor untuk pengujian (Node).
(function () {
  var STORAGE_KEY = 'reelforge-prompt-v1';
  var FIELDS = ['topic', 'duration', 'description', 'audience', 'cta', 'style'];
  var REQUIRED = ['topic', 'description'];
  var MAX_LENGTH = { topic: 120, duration: 3, description: 1000, audience: 200, cta: 200, style: 300 };
  var EXAMPLE = {
    topic: 'CLI Proxy',
    duration: '20',
    description: 'CLI Proxy membantu menghubungkan terminal dengan layanan API melalui perantara yang terstruktur.',
    audience: 'Developer, programmer, pemula AI',
    cta: 'Follow untuk tutorial berikutnya',
    style: 'Premium dark tech, neon cyan-violet, cinematic terminal UI'
  };

  function text(value) {
    return value == null ? '' : String(value).trim();
  }

  // Sama dengan ReelForge: angka 5–180 dibulatkan, selain itu kembali ke 20 detik.
  function durationLabel(value) {
    var seconds = Number(text(value));
    return isFinite(seconds) && seconds >= 5 && seconds <= 180 ? Math.round(seconds) + ' detik' : '20 detik';
  }

  function values(raw) {
    raw = raw || {};
    return {
      topic: text(raw.topic) || '[ISI TOPIK]',
      description: text(raw.description) || '[ISI DESKRIPSI]',
      audience: text(raw.audience) || '[ISI AUDIENS]',
      cta: text(raw.cta) || '[ISI CTA]',
      duration: durationLabel(raw.duration),
      style: text(raw.style) || 'modern premium'
    };
  }

  // split/join: mengganti semua kemunculan tanpa menafsirkan pola $ di teks pengguna.
  function replaceAll(source, find, replacement) {
    return source.split(find).join(replacement);
  }

  function buildPrompt(kind, template, raw) {
    var v = values(raw);
    var t = String(template);
    if (kind === 'gpt') {
      t = replaceAll(t, '[ISI TOPIK]', v.topic);
      t = replaceAll(t, '[ISI DESKRIPSI]', v.description);
      t = replaceAll(t, '[ISI AUDIENS]', v.audience);
      t = replaceAll(t, '[ISI CTA]', v.cta);
      t = replaceAll(t, '15-20 detik', v.duration);
      return 'KONFIGURASI VIDEO\nTopik: ' + v.topic + '\nDeskripsi: ' + v.description +
        '\nAudiens: ' + v.audience + '\nCTA: ' + v.cta + '\nDurasi: ' + v.duration +
        '\nGaya visual: ' + v.style + '\n\n' + t;
    }
    return 'KONFIGURASI PROJECT (IKUTI TXT & AUDIO TERLAMPIR)\nTopik: ' + v.topic +
      '\nDeskripsi: ' + v.description + '\nAudiens: ' + v.audience + '\nCTA: ' + v.cta +
      '\nTarget durasi: ' + v.duration + '\nGaya visual: ' + v.style + '\n\n' +
      replaceAll(t, '15-20 detik', v.duration);
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
    buildPrompt: buildPrompt,
    missingRequired: missingRequired,
    sanitize: sanitize,
    toggleStyle: toggleStyle,
    hasStyle: hasStyle,
    EXAMPLE: EXAMPLE
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
    FIELDS.forEach(function (k) { field(k).value = k === 'duration' ? '20' : ''; });
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
