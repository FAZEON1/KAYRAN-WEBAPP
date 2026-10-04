# -*- coding: utf-8 -*-
"""Takılı kalan ipucu (tooltip) kutularını gizler (Ekim 2026).

Sorun: Streamlit 1.65'te `help=` verilmiş bir düğmeye tıklanınca sayfa yeniden çizilir; o anda
açık olan ipucu kutusu sahipsiz kalır ve fare çekilse de ekranda durur. Üst menüde birkaç modül
gezilince "Muhasebe", "Depo", "Satış" kutuları birikiyor, açılan pencerenin (st.dialog) bile
ÜSTÜNDE görünüyordu (ipucu katmanı pencereden bir üstte).

Çözüm: bir ipucu kutusu yalnız kendi hedefi üzerindeyken (fare üstünde ya da klavyeyle odakta)
görünür; hedefi etkin olmayan kutu gizlenir. Kutu SİLİNMEZ (Streamlit'in kendi düğümü), yalnız
görünmez yapılır; aynı hedefin üstüne gelince yeniden görünür.
"""

_JS = """
export default function(component) {
  if (window.__kayranIpucu) return;
  window.__kayranIpucu = true;
  const HEDEF = '[data-testid="stTooltipHoverTarget"]';
  const ICERIK = '[data-testid="stTooltipContent"]';
  const etkin = (h) => {
    try { return h.matches(':hover') || h.matches(':focus-visible') || !!h.querySelector(':focus-visible'); }
    catch (e) { return h.matches(':hover'); }
  };
  // ipucu kutusu hedefin hemen üstünde/altında ve yatayda onunla çakışık mı
  const yakin = (k, h) => {
    const a = k.getBoundingClientRect(), b = h.getBoundingClientRect();
    if (!a.width || !b.width) return false;
    const yatay = a.left <= b.right + 12 && a.right >= b.left - 12;
    const dikey = Math.max(b.top - a.bottom, a.top - b.bottom);
    return yatay && dikey <= 28;
  };
  function denetle() {
    const kutular = document.querySelectorAll(ICERIK);
    if (!kutular.length) return;
    const hedefler = Array.from(document.querySelectorAll(HEDEF)).filter(etkin);
    const ks = Array.from(kutular).map((ic) => ic.parentElement || ic);
    // her etkin hedef için YALNIZ en yakın kutu görünür (yan düğmenin bayat kutusu değil)
    const goster = new Set();
    hedefler.forEach((h) => {
      const b = h.getBoundingClientRect(), hx = (b.left + b.right) / 2;
      let en = null, enMesafe = Infinity;
      ks.forEach((k) => {
        if (!yakin(k, h)) return;
        const a = k.getBoundingClientRect(), m = Math.abs((a.left + a.right) / 2 - hx);
        if (m < enMesafe) { enMesafe = m; en = k; }
      });
      if (en) goster.add(en);
    });
    ks.forEach((k) => {
      const v = goster.has(k) ? '' : 'hidden';
      if (k.style.visibility !== v) k.style.visibility = v;
    });
  }
  let planli = false;
  const planla = () => {
    if (planli) return;
    planli = true;
    requestAnimationFrame(() => { planli = false; denetle(); });
  };
  ['pointermove', 'pointerdown', 'focusin', 'keyup'].forEach((o) =>
    document.addEventListener(o, planla, true));
  window.addEventListener('scroll', planla, true);
  // yeni ipucu ya da yeniden çizim: hemen ve konumlandıktan sonra bir kez daha
  new MutationObserver(() => { planla(); setTimeout(denetle, 220); })
    .observe(document.body, {childList: true, subtree: true});
}
"""

_BILESEN = None


def kur():
    """app.py her çalıştırmada bir kez çağırır; kurulamazsa sessiz geçer (eski davranış)."""
    global _BILESEN
    try:
        if _BILESEN is None:
            import streamlit.components.v2 as _v2
            _BILESEN = _v2.component("kayran_ipucu", js=_JS)
        _BILESEN(key="kayran_ipucu")
    except Exception:  # noqa: BLE001
        pass
