/* ============================================================
   ESPECIALIDADES — Filtrado por categorías + flipbox táctil
   Vanilla JS, sin dependencias
   ============================================================ */
(function () {
  'use strict';

  var grid = document.getElementById('mi-grid');
  if (!grid) return;

  var cards = Array.prototype.slice.call(grid.querySelectorAll('.mi-card'));
  var filters = Array.prototype.slice.call(
    document.querySelectorAll('.mi-filter')
  );

  /* ---------- Filtrado con animación ---------- */
  function reveal(card, delay) {
    card.classList.remove('is-hidden', 'is-hiding');
    card.classList.add('is-enter');
    card.style.animationDelay = delay + 'ms';
    // limpiar la clase al terminar para permitir re-animaciones
    setTimeout(function () {
      card.classList.remove('is-enter');
      card.style.animationDelay = '';
    }, 520 + delay);
  }

  function hide(card) {
    if (card.classList.contains('is-hidden') || card.classList.contains('is-hiding')) return;
    card.classList.add('is-hiding');
    setTimeout(function () {
      card.classList.add('is-hidden');
      card.classList.remove('is-hiding');
    }, 350);
  }

  function applyFilter(filter) {
    var visibleIndex = 0;
    cards.forEach(function (card) {
      var match = filter === 'todos' || card.getAttribute('data-category') === filter;
      if (match) {
        reveal(card, visibleIndex * 60);
        visibleIndex++;
      } else {
        hide(card);
      }
    });
  }

  filters.forEach(function (btn) {
    btn.addEventListener('click', function () {
      filters.forEach(function (b) { b.classList.remove('is-active'); });
      btn.classList.add('is-active');
      applyFilter(btn.getAttribute('data-filter'));
    });
  });

  /* ---------- Flipbox en móviles (tap) ---------- */
  var finePointer = window.matchMedia('(hover: hover) and (pointer: fine)').matches;

  function toggleFlip(card) {
    // nunca interferir con el CTA de la cara trasera
    if (card.classList.contains('is-flipped')) {
      card.classList.remove('is-flipped');
    } else {
      card.classList.add('is-flipped');
    }
  }

  cards.forEach(function (card) {
    if (!finePointer) {
      // en táctil: un tap gira, otro tap devuelve; el CTA navega
      card.addEventListener('click', function (e) {
        if (e.target.closest('.mi-cta')) return;
        toggleFlip(card);
      });
    }

    // accesibilidad: Enter/Espacio para girar desde el teclado
    card.addEventListener('keydown', function (e) {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        toggleFlip(card);
      }
    });
  });

  /* cerrar la tarjeta girada al hacer click fuera (móviles) */
  document.addEventListener('click', function (e) {
    if (finePointer) return;
    cards.forEach(function (card) {
      if (!card.classList.contains('is-flipped')) return;
      if (!card.contains(e.target)) card.classList.remove('is-flipped');
    });
  });

  /* ---------- Init ---------- */
  applyFilter('todos');
})();
