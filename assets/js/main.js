// Navigasi seluler: tanpa JS, menu tetap tampil terbuka (progressive enhancement).
(function () {
  document.documentElement.classList.add('js');
  var toggle = document.querySelector('.nav-toggle');
  var links = document.getElementById('nav-links');
  if (!toggle || !links) return;

  function close() {
    links.classList.remove('open');
    toggle.setAttribute('aria-expanded', 'false');
  }

  toggle.addEventListener('click', function () {
    var open = links.classList.toggle('open');
    toggle.setAttribute('aria-expanded', String(open));
  });

  // Tutup menu setelah tautan dipilih (penting untuk tautan #anchor di halaman yang sama).
  links.addEventListener('click', function (e) {
    if (e.target.closest('a')) close();
  });

  // Tutup saat klik di luar header.
  document.addEventListener('click', function (e) {
    if (links.classList.contains('open') && !e.target.closest('.site-header')) close();
  });

  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape' && links.classList.contains('open')) {
      close();
      toggle.focus();
    }
  });
})();
