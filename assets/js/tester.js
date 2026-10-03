// Formulir pendaftaran tester: menyusun tautan wa.me berisi pesan siap kirim.
// Tidak ada permintaan jaringan dari situs ini; pesan hanya terkirim jika pengguna
// sendiri menekan Kirim di WhatsApp. Fungsi murni diekspor untuk pengujian (Node).
(function () {
  var EMAIL_MAX = 254;
  var MESSAGE_MAX = 500;

  // Nomor lokal Indonesia (08xx) → format internasional wa.me (628xx), hanya digit.
  function toWhatsAppNumber(local) {
    var digits = String(local).replace(/\D/g, '');
    if (digits.charAt(0) === '0') return '62' + digits.slice(1);
    return digits;
  }

  function isValidEmail(value) {
    var v = String(value).trim();
    return v.length > 0 && v.length <= EMAIL_MAX && /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(v);
  }

  // Normalisasi baris baru, buang karakter kontrol (kecuali baris baru), batasi panjang.
  function cleanMessage(value) {
    return String(value)
      .replace(/\r\n?/g, '\n')
      .replace(/[\u0000-\u0009\u000B-\u001F\u007F]/g, '')
      .trim()
      .slice(0, MESSAGE_MAX);
  }

  function buildMessage(app, email, message) {
    var note = cleanMessage(message);
    return 'Halo Admin Siap Digital, saya ingin mendaftar sebagai tester Android aplikasi ' + app + ' di Google Play.\n\n' +
      'Email akun Google: ' + String(email).trim() + '\n' +
      'Pesan: ' + (note || '-') + '\n\n' +
      'Saya memahami email ini ditambahkan secara manual ke daftar tester Google Play dan permintaan belum tentu disetujui.';
  }

  function buildWhatsAppUrl(number, text) {
    return 'https://wa.me/' + number + '?text=' + encodeURIComponent(text);
  }

  var api = {
    EMAIL_MAX: EMAIL_MAX,
    MESSAGE_MAX: MESSAGE_MAX,
    toWhatsAppNumber: toWhatsAppNumber,
    isValidEmail: isValidEmail,
    cleanMessage: cleanMessage,
    buildMessage: buildMessage,
    buildWhatsAppUrl: buildWhatsAppUrl
  };

  if (typeof module === 'object' && module.exports) {
    module.exports = api;
    return;
  }

  var form = document.getElementById('form-tester');
  if (!form) return;
  var email = form.elements.email;
  var message = form.elements.pesan;
  var emailError = document.getElementById('tester-email-error');
  var status = document.getElementById('tester-status');
  var number = toWhatsAppNumber(form.getAttribute('data-wa-phone'));
  var app = form.getAttribute('data-app');

  // Validasi ditampilkan sendiri agar pesan galat konsisten dan terbaca pembaca layar.
  form.noValidate = true;

  function setEmailError(text) {
    emailError.textContent = text;
    emailError.hidden = !text;
    email.setAttribute('aria-invalid', text ? 'true' : 'false');
  }

  email.addEventListener('input', function () {
    if (email.getAttribute('aria-invalid') === 'true' && isValidEmail(email.value)) setEmailError('');
  });

  form.addEventListener('submit', function (e) {
    e.preventDefault();
    var value = email.value.trim();
    if (!value) {
      setEmailError('Email wajib diisi.');
      email.focus();
      return;
    }
    if (!isValidEmail(value) || !email.validity.valid) {
      setEmailError('Format email belum benar. Contoh: nama@gmail.com');
      email.focus();
      return;
    }
    setEmailError('');

    var url = buildWhatsAppUrl(number, buildMessage(app, value, message.value));

    // Tautan cadangan jika jendela baru diblokir. Disusun lewat DOM dan textContent, bukan string HTML.
    status.textContent = '';
    var p = document.createElement('p');
    p.textContent = 'Pesan belum terkirim sampai Anda menekan Kirim di WhatsApp. Jika WhatsApp tidak terbuka otomatis, gunakan tautan ini: ';
    var link = document.createElement('a');
    link.href = url;
    link.rel = 'noopener noreferrer';
    link.textContent = 'Buka WhatsApp';
    p.appendChild(link);
    status.appendChild(p);

    window.open(url, '_blank', 'noopener,noreferrer');
  });

  form.hidden = false;
  var fallback = document.getElementById('tester-fallback');
  if (fallback) fallback.hidden = true;
})();
