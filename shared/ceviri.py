# -*- coding: utf-8 -*-
"""Streamlit'in kendi İngilizce yazıları → Türkçe (Ekim 2026, görünüm birliği #1, #2).

Dosya yükleme kutusu ("Upload", "200MB per file • XLSX") ve seçim kutuları ("Choose options")
Streamlit'in içinden gelir; Python'dan değiştirilemez. Bu bileşen sayfada bir kez kurulur
(app.py) ve YALNIZ bu kalıp yazıları çevirir: metin düğümünün TAMAMI aşağıdaki listedeki bir
kalıba uymalı. Kullanıcı verisine (ürün adı, açıklama) dokunmaz.
"""
import json

# Tam eşleşme (baştaki/sondaki boşluk yok sayılır)
SOZLUK = {
    "Upload": "Dosya seç",
    "Browse files": "Dosya seç",
    "Drag and drop file here": "Dosyayı buraya sürükle",
    "Drag and drop files here": "Dosyaları buraya sürükle",
    "Choose options": "Seç…",
    "Choose an option": "Seç…",
    "No options to select.": "Seçenek yok",
    "No results": "Sonuç yok",
    "Add multiple files": "Dosya ekle",
}
# Kalıp: "200MB per file • XLSX, XLS" → "Dosya başına en fazla 200 MB • XLSX, XLS"
KALIPLAR = [
    (r"^(\d+)\s*MB per file(.*)$", "Dosya başına en fazla $1 MB$2"),
    (r"^Limit (\d+)\s*MB per file(.*)$", "Dosya başına en fazla $1 MB$2"),
]

_JS = """
export default function(component) {
  if (window.__kayranCeviri) return;
  window.__kayranCeviri = true;
  const S = __SOZLUK__, K = __KALIP__.map(([d, y]) => [new RegExp(d), y]);
  function cevir(t) {
    const s = t.trim();
    if (!s) return null;
    if (Object.prototype.hasOwnProperty.call(S, s)) return t.replace(s, S[s]);
    for (const [d, y] of K) { if (d.test(s)) return t.replace(s, s.replace(d, y)); }
    return null;
  }
  function dugum(n) {
    if (n.nodeType === 3) {
      const y = cevir(n.nodeValue);
      if (y !== null && y !== n.nodeValue) n.nodeValue = y;
      return;
    }
    if (n.nodeType !== 1) return;
    if (n.placeholder) { const y = cevir(n.placeholder); if (y !== null) n.placeholder = y; }
    const w = document.createTreeWalker(n, NodeFilter.SHOW_TEXT);
    let t; while ((t = w.nextNode())) { const y = cevir(t.nodeValue); if (y !== null && y !== t.nodeValue) t.nodeValue = y; }
    n.querySelectorAll && n.querySelectorAll('input[placeholder]').forEach(i => {
      const y = cevir(i.placeholder); if (y !== null) i.placeholder = y; });
  }
  dugum(document.body);
  new MutationObserver(ms => { for (const m of ms) {
    if (m.type === 'characterData') dugum(m.target);
    else m.addedNodes.forEach(dugum);
  } }).observe(document.body, {childList: true, subtree: true, characterData: true});
}
"""


def _js():
    return (_JS.replace("__SOZLUK__", json.dumps(SOZLUK, ensure_ascii=False))
            .replace("__KALIP__", json.dumps(KALIPLAR, ensure_ascii=False)))


_BILESEN = None


def kur():
    """app.py her çalıştırmada bir kez çağırır; kurulamazsa sessiz geçer (yazılar İngilizce kalır)."""
    global _BILESEN
    try:
        if _BILESEN is None:
            import streamlit.components.v2 as _v2
            _BILESEN = _v2.component("kayran_ceviri", js=_js())
        _BILESEN(key="kayran_ceviri")
    except Exception:  # noqa: BLE001
        pass
