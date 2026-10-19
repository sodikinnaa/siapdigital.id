// Popup iklan Gemini Pro: muncul sekali per sesi, beberapa detik setelah halaman dibuka.
// Tanpa JS (atau tanpa dukungan <dialog>), iklan tetap tersedia sebagai bagian statis di halaman.
(function () {
  var dialog = document.getElementById('promo-gemini');
  if (!dialog || typeof dialog.showModal !== 'function') return;

  var KEY = 'promo-gemini-ditutup';
  function dismissed() {
    try { return window.sessionStorage.getItem(KEY) === '1'; } catch (e) { return false; }
  }
  function remember() {
    try { window.sessionStorage.setItem(KEY, '1'); } catch (e) { /* abaikan */ }
  }

  dialog.addEventListener('close', remember);

  // Klik di luar kotak (pada backdrop) menutup popup.
  dialog.addEventListener('click', function (e) {
    if (e.target === dialog) dialog.close();
  });

  // Setelah tombol WhatsApp diklik, popup tidak perlu tampil lagi.
  dialog.querySelectorAll('a').forEach(function (a) {
    a.addEventListener('click', function () { dialog.close(); });
  });

  if (dismissed()) return;
  window.setTimeout(function () {
    if (!dialog.open && !document.querySelector('dialog[open]')) dialog.showModal();
  }, 4000);
})();
