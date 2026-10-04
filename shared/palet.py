# -*- coding: utf-8 -*-
"""Komut paleti — Ctrl+K / ⌘K / "/" ya da üst şeritteki "Ara" (Ekim 2026).

Sayfadan ayrılmadan ortada açılır. Gruplar: sayfalar · işlemler (tarayıcıda
anında süzülür) + ürünler · cariler · satışlar · ithalat · servis (veri araması,
shared.arama.ara — yazmayı bırakınca). Ok tuşları + Enter, Esc kapatır.

Parçacık (st.fragment) içinde çalışır: aramada yalnız palet yenilenir; bir
sayfaya gidince tüm uygulama yeniden çizilir.
"""
import streamlit as st

_CSS = r"""
:host{display:block}
.ac{display:inline-flex;align-items:center;gap:8px;height:34px;padding:0 10px 0 9px;border-radius:8px;cursor:pointer;
  border:0;background:transparent;color:var(--k-soluk);font:inherit;font-size:13px;white-space:nowrap}
.ac:hover{background:var(--k-ortu2);color:var(--k-metin)}
.ac kbd{font:inherit;font-size:11px;color:var(--k-silik);border:1px solid var(--k-kenar2);border-radius:5px;padding:1px 5px}
.mi{font-family:"Material Symbols Rounded";font-weight:normal;font-style:normal;font-size:18px;line-height:1;
  display:inline-block;letter-spacing:normal;text-transform:none;white-space:nowrap;-webkit-font-smoothing:antialiased}
.ort{position:fixed;inset:0;z-index:2147483647;background:rgba(2,6,23,.55);display:none;align-items:flex-start;justify-content:center;padding:10vh 12px 0}
.ort.acik{display:flex}
.kutu{width:620px;max-width:100%;max-height:70vh;display:flex;flex-direction:column;background:var(--k-yuzey1);
  border:1px solid var(--k-kenar2);border-radius:14px;box-shadow:0 24px 64px rgba(0,0,0,.45);overflow:hidden;color:var(--k-metin)}
.ust{display:flex;align-items:center;gap:10px;padding:12px 16px;border-bottom:1px solid var(--k-kenar)}
.ust .mi{color:var(--k-silik)}
.ust input{flex:1;min-width:0;border:0;outline:none;background:transparent;color:var(--k-metin);font:inherit;font-size:15px}
.ust kbd{font:inherit;font-size:11px;color:var(--k-silik);border:1px solid var(--k-kenar2);border-radius:5px;padding:1px 6px;cursor:pointer}
.liste{overflow:auto;padding:6px 0 8px}
.grup{font-size:11px;color:var(--k-silik);padding:10px 16px 4px}
.og{display:flex;align-items:center;gap:12px;padding:8px 16px;cursor:pointer;font-size:13.5px}
.og .mi{color:var(--k-soluk);font-size:19px;width:20px;text-align:center}
.og .ad{min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.og .yol{margin-left:auto;padding-left:12px;color:var(--k-silik);font-size:12px;white-space:nowrap}
.og.s{background:var(--k-vurgu)}
.og.s .mi{color:var(--k-mor2)}
.bilgi{padding:14px 16px;color:var(--k-silik);font-size:13px}
.alt{display:flex;gap:14px;padding:8px 16px;border-top:1px solid var(--k-kenar);font-size:11px;color:var(--k-silik)}
@media (max-width:640px){.ac kbd,.ac .yazi{display:none}.ort{padding:8px}.kutu{max-height:85vh}.alt{display:none}}
"""

_JS = r"""
export default function(component){
  const {data, setTriggerValue, parentElement} = component;
  const P = parentElement.__p || (parentElement.__p = {q:"", s:0, acik:false, t:null});
  P.D = data || {};
  const es = s => String(s ?? "").replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;");
  const harf = {"ç":"c","ğ":"g","ı":"i","ö":"o","ş":"s","ü":"u","â":"a","î":"i","İ":"i","I":"i"};
  const sade = s => String(s||"").replace(/[çğıöşüâîİI]/g, c => harf[c] || c).toLowerCase();
  if (!P.kok){
    const k = document.createElement("div");
    const mac = /Mac|iPhone|iPad/.test(navigator.platform || "");
    k.innerHTML = '<button class="ac" type="button" aria-label="Ara"><span class="mi">search</span><span class="yazi">Ara</span><kbd>' + (mac ? "⌘K" : "Ctrl K") + '</kbd></button>';
    // Örtü sayfanın EN ÜST katmanında: üst şeridin içinde kalınca (sticky, z 999)
    // kenar çubuğu düğmesi gibi öğeler paletin üstünde görünüyordu.
    try { if (window.__kayranPaletHost) window.__kayranPaletHost.remove(); } catch (e) {}
    const host = document.createElement("div"); host.id = "kayran-palet";
    host.style.cssText = "position:relative;z-index:2147483647";      // kenar çubuğu düğmesinin de üstünde
    document.body.appendChild(host); window.__kayranPaletHost = host;
    const gk = host.attachShadow({mode: "open"});
    gk.innerHTML = '<style>' + (P.D.css || "") + '</style>' +
      '<div class="ort" role="dialog" aria-modal="true" aria-label="Komut paleti"><div class="kutu">' +
        '<div class="ust"><span class="mi">search</span><input type="text" autocomplete="off" spellcheck="false" ' +
        'placeholder="Sayfa, işlem, SKU, firma ya da soru: geçen ay en çok satan 5 ürün" aria-label="Ara"><kbd class="kapat">Esc</kbd></div>' +
        '<div class="liste" role="listbox"></div>' +
        '<div class="alt"><span>↑↓ seç</span><span>Enter git</span><span>Esc kapat</span></div>' +
      '</div></div>';
    parentElement.appendChild(k);
    P.kok = k; P.ort = gk.querySelector(".ort"); P.inp = gk.querySelector("input"); P.lst = gk.querySelector(".liste");
    const ac = () => { P.acik = true; P.ort.classList.add("acik"); P.inp.value = P.q; P.s = 0; ciz(); setTimeout(() => { P.inp.focus(); P.inp.select(); }, 0); };
    const kapa = () => { P.acik = false; P.ort.classList.remove("acik"); };
    P.kapa = kapa;
    window.__kayranPaletAc = ac;
    k.querySelector(".ac").addEventListener("click", ac);
    gk.querySelector(".kapat").addEventListener("click", kapa);
    P.ort.addEventListener("mousedown", e => { if (e.target === P.ort) kapa(); });
    P.inp.addEventListener("input", () => {
      P.q = P.inp.value; P.s = 0; ciz();
      clearTimeout(P.t);
      const q = P.q.trim();
      P.t = setTimeout(() => { if (q.length >= 2 && q !== P.sonIstek){ P.sonIstek = q; setTriggerValue("ara", q); } }, 300);
    });
    P.inp.addEventListener("keydown", e => {
      const n = P.gorunen ? P.gorunen.length : 0;
      if (e.key === "Escape"){ e.preventDefault(); kapa(); }
      else if (e.key === "ArrowDown"){ e.preventDefault(); if (n){ P.s = (P.s + 1) % n; ciz(true); } }
      else if (e.key === "ArrowUp"){ e.preventDefault(); if (n){ P.s = (P.s - 1 + n) % n; ciz(true); } }
      else if (e.key === "Enter"){ e.preventDefault(); if (n) git(P.gorunen[P.s]); }
    });
    P.lst.addEventListener("mousemove", e => { const o = e.target.closest(".og"); if (o && +o.dataset.n !== P.s){ P.s = +o.dataset.n; ciz(true); } });
    P.lst.addEventListener("click", e => { const o = e.target.closest(".og"); if (o) git(P.gorunen[+o.dataset.n]); });
  }
  function git(o){ if (!o) return; clearTimeout(P.t); P.kapa(); P.q = ""; P.sonIstek = null; setTriggerValue("sec", o.id); }
  function ciz(yalnizSecim){
    if (!P.acik) return;
    if (yalnizSecim && P.lst.children.length){
      P.lst.querySelectorAll(".og").forEach(x => x.classList.toggle("s", +x.dataset.n === P.s));
      const s = P.lst.querySelector(".og.s"); if (s) s.scrollIntoView({block: "nearest"});
      return;
    }
    const q = sade(P.q.trim()), parca = q.split(/\s+/).filter(Boolean);
    const D = P.D, sabit = D.ogeler || [];
    const uy = o => parca.every(p => o.ara.includes(p));
    // Sıra: adı aranan metinle başlayan → bir kelimesi başlayan → içeren (kararlı)
    const puan = o => { const a = sade(o.ad); if (a.startsWith(q)) return 0;
                        return a.split(/[\s/·-]+/).some(w => w.startsWith(parca[0] || "")) ? 1 : 2; };
    const sirala = l => l.map((o,i)=>[puan(o),i,o]).sort((x,y)=>x[0]-y[0]||x[1]-y[1]).map(x=>x[2]);
    let gr = [];
    if (!q){
      gr.push(["Sayfalar", sabit.filter(o => o.tur === "sayfa" && !o.yol).concat(sabit.filter(o => o.tur === "islem")).slice(0, 12)]);
    } else {
      const sy = sirala(sabit.filter(o => o.tur === "sayfa" && uy(o))).slice(0, 8);
      const isl = sirala(sabit.filter(o => o.tur === "islem" && uy(o))).slice(0, 5);
      if (D.sonuc_q && sade(D.sonuc_q) === q && (D.sonuc || []).some(o => o.tur === "soru")) gr.unshift(["Soru", (D.sonuc || []).filter(o => o.tur === "soru")]);
      if (sy.length) gr.push(["Sayfalar", sy]);
      if (isl.length) gr.push(["İşlemler", isl]);
      const ad = {urun:"Ürünler", cari:"Cariler", satis:"Satışlar", ithalat:"İthalat", servis:"Teknik servis"};
      if (D.sonuc_q && sade(D.sonuc_q) === q){
        for (const t of ["urun","cari","satis","ithalat","servis"]){
          const l = (D.sonuc || []).filter(o => o.tur === t);
          if (l.length) gr.push([ad[t], l]);
        }
      }
    }
    P.gorunen = []; let h = "";
    for (const [b, l] of gr){
      h += '<div class="grup">' + es(b) + '</div>';
      for (const o of l){
        const n = P.gorunen.length; P.gorunen.push(o);
        h += '<div class="og' + (n === P.s ? " s" : "") + '" role="option" data-n="' + n + '"><span class="mi">' + es(o.ikon) + '</span>' +
             '<span class="ad">' + es(o.ad) + '</span>' + (o.yol ? '<span class="yol">' + es(o.yol) + '</span>' : '') + '</div>';
      }
    }
    const bekliyor = q.length >= 2 && !(D.sonuc_q && sade(D.sonuc_q) === q);
    if (bekliyor) h += '<div class="bilgi">Verilerde aranıyor…</div>';
    else if (!P.gorunen.length) h += '<div class="bilgi">Sonuç yok. SKU, firma adı, sipariş ya da seri no deneyin.</div>';
    P.lst.innerHTML = h;
  }
  ciz();
}
"""

_BILESEN = None


def _bilesen():
    global _BILESEN
    if _BILESEN is None:
        import streamlit.components.v2 as _v2
        _BILESEN = _v2.component("kayran_palet", css=_CSS, js=_JS)
    return _BILESEN


def git(oge_id):
    """Paletten seçilen öğeye git. Sayfa: oturuma yaz + uygulamayı yeniden çiz.
    Ürün: stok kartını aç (bulunduğun sayfada kalır)."""
    if str(oge_id or "").startswith("soru:"):
        from shared.soru_ekran import sor
        sor(str(oge_id)[5:])
        st.rerun(scope="app")
        return
    from shared.gezinme import hedef
    h = hedef(oge_id)
    if not h:
        st.toast("Bu sayfa bulunamadı.")
        return
    if "stok_karti" in h:
        try:
            from kayranpm.stok_karti import goster
            goster(h["stok_karti"])
            return
        except Exception:
            h = {"modul": "kayranpm", "anahtar": None, "secenek": None}
    st.session_state.aktif_uygulama = h["modul"]
    if h.get("anahtar") and h.get("secenek"):
        st.session_state[h["anahtar"]] = h["secenek"]
    st.rerun(scope="app")


@st.fragment
def palet(yetkiler, ozel, kullanici, kosul):
    """Üst şeritteki "Ara" düğmesi + ortada açılan palet."""
    from shared.gezinme import palet_ogeleri, arama_ogeleri
    q = st.session_state.get("_palet_q", "")
    sonuc = []
    if len(q.strip()) >= 2:
        try:
            from shared.arama import ara
            sonuc = arama_ogeleri(ara(q))
        except Exception:
            sonuc = []
        try:                                   # soru gibi okunuyorsa en üstte "Sor" (shared/soru_ekran)
            from shared.soru_ekran import anlasilir_mi
            if anlasilir_mi(q):
                sonuc = [{"tur": "soru", "id": "soru:" + q.strip(), "ad": "Sor: " + q.strip(),
                          "yol": "cevap programın hesaplarından", "ikon": "forum"}] + sonuc
        except Exception:  # noqa: BLE001
            pass
    veri = {"css": _CSS, "ogeler": palet_ogeleri(yetkiler, ozel, kullanici, kosul),
            "sonuc": sonuc, "sonuc_q": q if len(q.strip()) >= 2 else ""}
    r = _bilesen()(key="kayran_palet", data=veri, default={}, height="content",
                   on_ara_change=lambda: None, on_sec_change=lambda: None)
    # Önce seçim: aynı anda gelen bir arama isteği seçimi yutmasın
    sec = getattr(r, "sec", None)
    if sec:
        st.session_state["_palet_q"] = ""
        git(sec)
        return
    yeni_q = getattr(r, "ara", None)
    if yeni_q is not None and yeni_q != q:
        st.session_state["_palet_q"] = yeni_q
        st.rerun(scope="fragment")
