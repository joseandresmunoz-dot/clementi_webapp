(function () {
  var btn = document.getElementById('pwa-install-btn');
  if (!btn) return;

  var isStandalone =
    window.matchMedia('(display-mode: standalone)').matches ||
    window.navigator.standalone === true;

  var KEY = 'pwa-install-dismissed';
  var DISMISS_MS = 30 * 24 * 3600 * 1000; // 30 días

  function hide() {
    btn.setAttribute('hidden', '');
  }

  // Ya instalada como app: no mostrar nada
  if (isStandalone) return;

  // Si el usuario la descartó recientemente, no molestar
  var dismissed = parseInt(localStorage.getItem(KEY) || '0', 10);
  if (dismissed && Date.now() - dismissed < DISMISS_MS) return;

  var deferredPrompt = null;

  window.addEventListener('beforeinstallprompt', function (e) {
    e.preventDefault();
    deferredPrompt = e;
    btn.removeAttribute('hidden');
  });

  btn.addEventListener('click', function () {
    hide();
    if (!deferredPrompt) return;
    deferredPrompt.prompt();
    deferredPrompt.userChoice.then(function () {
      localStorage.setItem(KEY, String(Date.now()));
      deferredPrompt = null;
    });
  });

  window.addEventListener('appinstalled', function () {
    localStorage.setItem(KEY, String(Date.now()));
    hide();
  });

  // Recargar una sola vez cuando un nuevo service worker toma el control
  if ('serviceWorker' in navigator) {
    var refreshing = false;
    navigator.serviceWorker.addEventListener('controllerchange', function () {
      if (refreshing) return;
      refreshing = true;
      location.reload();
    });
  }
})();
