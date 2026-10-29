(function () {
  "use strict";
  var grilla = document.getElementById("grilla");
  var estadoWs = document.getElementById("estado-ws");
  var plantilla = document.getElementById("tpl-tarjeta");
  var tarjetas = {};
  var MAX_PASOS = 30;

  function tarjeta(ev) {
    var t = tarjetas[ev.ejecucion_id];
    if (t) return t;
    var el = plantilla.content.firstElementChild.cloneNode(true);
    t = tarjetas[ev.ejecucion_id] = {
      el: el,
      canvas: el.querySelector("canvas"),
      lista: el.querySelector(".razonamiento"),
      tsFrame: null,
      punto: null,
      puntoT: 0,
      img: null,
    };
    el.addEventListener("click", function () {
      var ya = el.classList.contains("ampliada");
      cerrarAmpliadas();
      if (!ya) el.classList.add("ampliada");
    });
    grilla.appendChild(el);
    return t;
  }

  function cerrarAmpliadas() {
    Object.keys(tarjetas).forEach(function (k) {
      tarjetas[k].el.classList.remove("ampliada");
    });
  }

  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape") cerrarAmpliadas();
  });

  function dibujar(t) {
    var ctx = t.canvas.getContext("2d");
    if (t.img) ctx.drawImage(t.img, 0, 0, t.canvas.width, t.canvas.height);
    var edad = performance.now() - t.puntoT;
    if (t.punto && edad < 1000 && t.img) {
      var sx = t.canvas.width / t.img.naturalWidth;
      var sy = t.canvas.height / t.img.naturalHeight;
      ctx.globalAlpha = 1 - edad / 1000;
      ctx.strokeStyle = "#ef4444";
      ctx.lineWidth = 4;
      ctx.beginPath();
      ctx.arc(t.punto[0] * sx, t.punto[1] * sy, 24, 0, 2 * Math.PI);
      ctx.stroke();
      ctx.globalAlpha = 1;
      requestAnimationFrame(function () { dibujar(t); });
    }
  }

  function texto(t, clase, valor) {
    t.el.querySelector("." + clase).textContent = valor;
  }

  function recibir(ev) {
    var t = tarjeta(ev);
    if (ev.persona) texto(t, "persona", ev.persona);
    if (ev.escenario) texto(t, "escenario", ev.escenario);
    if (ev.tipo === "paso") {
      texto(t, "paso", "paso " + ev.n_paso);
      var li = document.createElement("li");
      li.textContent = ev.paso_contrato + " → " + ev.accion + " → " + ev.razonamiento;
      t.lista.insertBefore(li, t.lista.firstChild);
      while (t.lista.children.length > MAX_PASOS) t.lista.removeChild(t.lista.lastChild);
      if (ev.punto) {
        t.punto = ev.punto;
        t.puntoT = performance.now();
        dibujar(t);
      }
    } else if (ev.tipo === "frame" && ev.frame_jpeg_b64) {
      var img = new Image();
      img.onload = function () { t.img = img; dibujar(t); };
      img.src = "data:image/jpeg;base64," + ev.frame_jpeg_b64;
      t.tsFrame = new Date(ev.ts).getTime();
    } else if (ev.tipo === "fin") {
      texto(t, "resultado", "resultado: " + (ev.resultado || "—"));
    }
  }

  setInterval(function () {
    Object.keys(tarjetas).forEach(function (k) {
      var t = tarjetas[k];
      if (t.tsFrame) texto(t, "latencia", "latencia " + Math.max(0, Date.now() - t.tsFrame) + " ms");
    });
  }, 500);

  function conectar() {
    var ws = new WebSocket((location.protocol === "https:" ? "wss://" : "ws://") + location.host + "/ws");
    ws.onopen = function () { estadoWs.textContent = "Conectado"; };
    ws.onmessage = function (m) { recibir(JSON.parse(m.data)); };
    ws.onclose = function () {
      estadoWs.textContent = "Reconectando…";
      setTimeout(conectar, 1000);
    };
  }
  conectar();
})();
