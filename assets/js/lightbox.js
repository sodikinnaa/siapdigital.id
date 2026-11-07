// Penampil gambar tutorial: klik tangkapan layar untuk membuka popup, lalu geser
// (swipe), tekan panah kiri/kanan, atau pakai tombol untuk pindah gambar.
// Tanpa JS atau tanpa <dialog>, tautan tetap membuka gambar ukuran penuh.
(function () {
  if (typeof HTMLDialogElement !== 'function') return;
  var links = Array.prototype.slice.call(document.querySelectorAll('.guide-shot a'))
    .filter(function (a) { return a.querySelector('img'); });
  if (!links.length) return;

  var items = links.map(function (a) {
    var img = a.querySelector('img');
    var fig = a.closest('figure');
    var cap = fig && fig.querySelector('figcaption');
    var step = a.closest('.guide-step');
    var no = step && step.querySelector('.step-no');
    var title = step && step.querySelector('h3');
    return {
      link: a,
      src: a.getAttribute('href'),
      alt: img.getAttribute('alt') || '',
      w: img.getAttribute('width'),
      h: img.getAttribute('height'),
      caption: cap ? cap.textContent.trim() : '',
      step: (no ? 'Langkah ' + no.textContent.trim() : '') + (title ? (no ? ': ' : '') + title.textContent.trim() : '')
    };
  });

  function el(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text) n.textContent = text;
    return n;
  }
  function iconButton(cls, label, path) {
    var b = el('button', 'lightbox-btn ' + cls);
    b.type = 'button';
    b.setAttribute('aria-label', label);
    var svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    svg.setAttribute('viewBox', '0 0 24 24');
    svg.setAttribute('aria-hidden', 'true');
    var p = document.createElementNS('http://www.w3.org/2000/svg', 'path');
    p.setAttribute('d', path);
    svg.appendChild(p);
    b.appendChild(svg);
    return b;
  }

  var dialog = el('dialog', 'lightbox');
  dialog.setAttribute('aria-label', 'Penampil gambar tutorial');
  var bar = el('div', 'lightbox-bar');
  var counter = el('p', 'lightbox-counter');
  counter.setAttribute('aria-live', 'polite');
  var full = el('a', 'lightbox-full', 'Ukuran penuh ↗');
  full.target = '_blank';
  full.rel = 'noopener';
  var closeBtn = iconButton('lightbox-close', 'Tutup', 'M6 6l12 12M18 6L6 18');
  bar.appendChild(counter);
  bar.appendChild(full);
  bar.appendChild(closeBtn);

  var stage = el('div', 'lightbox-stage');
  var img = el('img', 'lightbox-img');
  img.decoding = 'async';
  img.draggable = false;
  var prev = iconButton('lightbox-prev', 'Gambar sebelumnya', 'M15 5l-7 7 7 7');
  var next = iconButton('lightbox-next', 'Gambar berikutnya', 'M9 5l7 7-7 7');
  stage.appendChild(img);
  stage.appendChild(prev);
  stage.appendChild(next);

  var info = el('div', 'lightbox-info');
  var stepText = el('p', 'lightbox-step');
  var capText = el('p', 'lightbox-caption');
  var hint = el('p', 'lightbox-hint', 'Geser atau tekan ← → untuk pindah gambar');
  info.appendChild(stepText);
  info.appendChild(capText);
  info.appendChild(hint);

  dialog.appendChild(bar);
  dialog.appendChild(stage);
  dialog.appendChild(info);
  document.body.appendChild(dialog);

  var index = 0;
  var opener = null;
  var reduce = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  function preload(i) {
    if (i >= 0 && i < items.length) { var p = new Image(); p.src = items[i].src; }
  }

  function show(i, dir) {
    if (i < 0 || i >= items.length) return;
    index = i;
    var it = items[i];
    img.src = it.src;
    img.alt = it.alt;
    if (it.w && it.h) { img.width = +it.w; img.height = +it.h; }
    counter.textContent = (i + 1) + ' / ' + items.length;
    stepText.textContent = it.step;
    stepText.hidden = !it.step;
    capText.textContent = it.caption;
    full.href = it.src;
    prev.disabled = i === 0;
    next.disabled = i === items.length - 1;
    img.style.transform = '';
    if (dir && !reduce) {
      img.classList.remove('slide-next', 'slide-prev');
      void img.offsetWidth; // mulai ulang animasi
      img.classList.add(dir > 0 ? 'slide-next' : 'slide-prev');
    }
    preload(i + 1);
    preload(i - 1);
  }

  function open(i) {
    opener = items[i].link;
    show(i, 0);
    document.documentElement.classList.add('lightbox-open');
    dialog.showModal();
    closeBtn.focus();
  }

  links.forEach(function (a, i) {
    a.addEventListener('click', function (e) {
      if (e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
      e.preventDefault();
      open(i);
    });
  });

  prev.addEventListener('click', function () { show(index - 1, -1); });
  next.addEventListener('click', function () { show(index + 1, 1); });
  closeBtn.addEventListener('click', function () { dialog.close(); });
  dialog.addEventListener('close', function () {
    document.documentElement.classList.remove('lightbox-open');
    // Kembalikan fokus ke gambar terakhir yang dilihat, bukan hanya gambar pembuka.
    var target = items[index] ? items[index].link : opener;
    if (target) {
      target.focus({ preventScroll: true });
      target.scrollIntoView({ block: 'center', behavior: reduce ? 'auto' : 'smooth' });
    }
  });
  // Klik area gelap di luar gambar menutup popup.
  dialog.addEventListener('click', function (e) {
    if (Math.abs(dx) > 10) { dx = 0; return; } // akhir gerakan swipe, bukan klik
    if (e.target === dialog || e.target === stage) dialog.close();
  });
  dialog.addEventListener('keydown', function (e) {
    if (e.key === 'ArrowRight') { e.preventDefault(); show(index + 1, 1); }
    else if (e.key === 'ArrowLeft') { e.preventDefault(); show(index - 1, -1); }
    else if (e.key === 'Home') { e.preventDefault(); show(0, -1); }
    else if (e.key === 'End') { e.preventDefault(); show(items.length - 1, 1); }
  });

  // Swipe: gambar mengikuti jari, lalu pindah bila digeser cukup jauh.
  var startX = null, startY = 0, dx = 0, pid = null;
  stage.addEventListener('pointerdown', function (e) {
    if (e.pointerType === 'mouse' || e.target.closest('button')) return;
    startX = e.clientX; startY = e.clientY; dx = 0; pid = e.pointerId;
  });
  stage.addEventListener('pointermove', function (e) {
    if (startX === null || e.pointerId !== pid) return;
    dx = e.clientX - startX;
    if (Math.abs(dx) > Math.abs(e.clientY - startY)) {
      var atEdge = (dx > 0 && index === 0) || (dx < 0 && index === items.length - 1);
      img.style.transform = 'translateX(' + (atEdge ? dx / 4 : dx) + 'px)';
    }
  });
  function endSwipe(e) {
    if (startX === null || e.pointerId !== pid) return;
    var limit = Math.min(80, stage.clientWidth / 5);
    startX = null;
    if (dx <= -limit && index < items.length - 1) show(index + 1, 1);
    else if (dx >= limit && index > 0) show(index - 1, -1);
    else img.style.transform = '';
  }
  stage.addEventListener('pointerup', endSwipe);
  stage.addEventListener('pointercancel', endSwipe);
})();
