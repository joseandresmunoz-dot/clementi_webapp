(function () {
  var VAPID_PUBLIC_KEY = "BIp6NZxaw76Opgi_kgdnyaA9zL5yE6Ac_DrZENmte7Po5ag_rvkkzncRpVH3n76AOktzQAEwFR9g7MQH3mi0KRw";
  var SW_PATH = "/sw.js";
  var SAVE_URL = "/save_information";

  var toggle = document.getElementById("pushToggle");
  var statusEl = document.getElementById("pushStatus");
  if (!toggle) return;

  function urlBase64ToUint8Array(base64String) {
    var padding = "=".repeat((4 - (base64String.length % 4)) % 4);
    var base64 = (base64String + padding).replace(/-/g, "+").replace(/_/g, "/");
    var raw = atob(base64);
    var arr = new Uint8Array(raw.length);
    for (var i = 0; i < raw.length; i++) arr[i] = raw.charCodeAt(i);
    return arr;
  }

  function setState(on, disabled, text) {
    toggle.checked = !!on;
    toggle.disabled = !!disabled;
    if (text && statusEl) statusEl.textContent = text;
  }

  async function registerSW() {
    if (!("serviceWorker" in navigator)) throw new Error("sin soporte");
    var reg = await navigator.serviceWorker.register(SW_PATH);
    await navigator.serviceWorker.ready;
    return reg;
  }

  async function getExisting(reg) {
    try {
      return await reg.pushManager.getSubscription();
    } catch (e) {
      return null;
    }
  }

  async function saveOnServer(subscription, status_type) {
    var res = await fetch(SAVE_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        subscription: subscription.toJSON ? subscription.toJSON() : subscription,
        status_type: status_type,
        browser: (navigator.userAgent.match(/chrome|firefox|safari|edg|opr/i) || ["unknown"])[0],
        user_agent: navigator.userAgent,
      }),
    });
    if (!res.ok) throw new Error("save failed");
    return res;
  }

  async function enable() {
    setState(true, true, "Solicitando permiso…");
    try {
      if (!("Notification" in window)) throw new Error("sin soporte");
      if (Notification.permission === "denied") {
        setState(false, true, "Notificaciones bloqueadas en tu navegador.");
        return;
      }
      var perm = await Notification.requestPermission();
      if (perm !== "granted") {
        setState(false, false, "No autorizaste las notificaciones.");
        return;
      }
      var reg = await registerSW();
      var sub = await getExisting(reg);
      if (!sub) {
        sub = await reg.pushManager.subscribe({
          userVisibleOnly: true,
          applicationServerKey: urlBase64ToUint8Array(VAPID_PUBLIC_KEY),
        });
      }
      await saveOnServer(sub, "subscribe");
      setState(true, false, "Notificaciones activadas. Te avisaremos cuando la Dra. suba documentos para vos.");
    } catch (err) {
      console.error("push-subscribe:", err);
      setState(false, false, "No se pudo activar. Probá de nuevo en un rato.");
    }
  }

  async function disable() {
    setState(false, true, "Desactivando…");
    try {
      var reg = await navigator.serviceWorker.ready;
      var sub = await getExisting(reg);
      if (sub) {
        await saveOnServer(sub, "unsubscribe").catch(function () {});
        await sub.unsubscribe().catch(function () {});
      }
      setState(false, false, "Notificaciones desactivadas.");
    } catch (e) {
      setState(true, false, "No se pudo desactivar.");
    }
  }

  toggle.addEventListener("change", function () {
    if (toggle.checked) enable();
    else disable();
  });

  (async function init() {
    if (!("serviceWorker" in navigator) || !("Notification" in window) || !("PushManager" in window)) {
      setState(false, true, "Tu navegador no soporta notificaciones push.");
      return;
    }
    if (Notification.permission === "denied") {
      setState(false, true, "Notificaciones bloqueadas en tu navegador.");
      return;
    }
    try {
      var reg = await navigator.serviceWorker.ready;
      var sub = await getExisting(reg);
      setState(!!sub, false, sub ? "Notificaciones activadas." : "Recibí un aviso cuando la Dra. suba documentos nuevos.");
    } catch (e) {
      setState(false, false, "Recibí un aviso cuando la Dra. suba documentos nuevos.");
    }
  })();
})();
