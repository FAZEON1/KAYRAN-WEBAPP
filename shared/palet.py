# -*- coding: utf-8 -*-
"""Komut paleti — Ctrl+K / ⌘K / "/" ya da üst şeritteki "Ara" (Ekim 2026).

Stok kartı (Ekim 2026, kullanıcı seçimi "A"): üst şeritte "Stok kartı" düğmesi ve Ürün Yönetimi'ndeki geniş
kutu paleti ÜRÜN kipinde açar. Ürünler tarayıcıda, yazarken anında süzülür; her satırda stok ve "kaç gün
yeter" (kural stok kartıyla aynı: kayranpm/stok_karti_palet.py). Boşken son açılan kartlar ve sipariş zamanı
gelenler. Ctrl+K'daki genel aramada da ürünler en üstte, aynı satırlarla.

Sayfadan ayrılmadan ortada açılır. Gruplar: sayfalar · işlemler (tarayıcıda
anında süzülür) + ürünler · cariler · satışlar · ithalat · servis (veri araması,
shared.arama.ara — yazmayı bırakınca). Ok tuşları + Enter, Esc kapatır.

Parçacık (st.fragment) içinde çalışır: aramada yalnız palet yenilenir; bir
sayfaya gidince tüm uygulama yeniden çizilir.
"""
import streamlit as st
from shared.kayit import sessiz

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
.og .sku{font-family:ui-monospace,Menlo,Consolas,monospace;font-size:12.5px;color:var(--k-metin);white-space:nowrap;flex:none}
.og .ad.u{color:var(--k-soluk);font-size:13px}
.og .sag{margin-left:auto;display:flex;gap:6px;padding-left:10px;flex:none}
.cip{font-size:11px;font-weight:600;padding:1px 8px;border-radius:999px;white-space:nowrap;font-variant-numeric:tabular-nums}
.cip.g,.cip.yok{background:var(--k-ortu2);color:var(--k-soluk)}
.cip.siparis{background:color-mix(in srgb,var(--k-kirmizi) 16%,transparent);color:var(--k-kirmizi)}
.cip.yeter{background:color-mix(in srgb,var(--k-yesil) 15%,transparent);color:var(--k-yesil)}
.cip.satissiz{background:color-mix(in srgb,var(--k-amber) 16%,transparent);color:var(--k-amber)}
.dugmeler{display:inline-flex;align-items:center;gap:2px}
.og.s .mi{color:var(--k-mor2)}
.bilgi{padding:14px 16px;color:var(--k-silik);font-size:13px}
.alt{display:flex;gap:14px;padding:8px 16px;border-top:1px solid var(--k-kenar);font-size:11px;color:var(--k-silik)}
@media (max-width:640px){.ac kbd,.ac .yazi{display:none}.ort{padding:8px}.kutu{max-height:85vh}.alt{display:none}.og .stokc{display:none}}
"""

_JS = r"""
export default function(component){
  const {data, setTriggerValue, parentElement} = component;
  const P = parentElement.__p || (parentElement.__p = {q:"", s:0, acik:false, t:null});
  P.D = data || {};
  const es = s => String(s ?? "").replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;");
  const harf = {"ç":"c","ğ":"g","ı":"i","ö":"o","ş":"s","ü":"u","â":"a","î":"i","İ":"i","I":"i"};
  const sade = s => String(s||"").replace(/[çğıöşüâîİI]/g, c => harf[c] || c).toLowerCase();
  // Sayı kutusu tekerleği yutmasın (Ekim 2026): fare odakta olmayan bir sayı kutusunun üstündeyken Streamlit
  // tekerleği kilitliyor, sayfa kaymıyordu (Yurt içi alış, Yeni ithalat, telefonda Hesap makinesi). Kutuyu içeren
  // kaydırılabilir alan (sayfa ya da açık pencere) kaydırılır; kutunun değeri değişmez. Palet her sayfada var:
  // dinleyici pencereye bir kez kurulur.
  if (!window.__kayranTeker){
    window.__kayranTeker = true;
    window.addEventListener("wheel", ev => {
      const t = ev.target && ev.target.closest ? ev.target.closest('input[type="number"], [data-testid="stNumberInput"] input') : null;
      if (!t || t === document.activeElement) return;
      let a = t.parentElement;
      while (a && a !== document.body){
        const o = getComputedStyle(a).overflowY;
        if ((o === "auto" || o === "scroll") && a.scrollHeight > a.clientHeight + 1) break;
        a = a.parentElement;
      }
      const kap = (a && a !== document.body) ? a : (document.querySelector('[data-testid="stMain"]') || document.scrollingElement);
      ev.preventDefault(); ev.stopPropagation();
      kap.scrollBy({top: ev.deltaY, left: ev.deltaX});
    }, {capture: true, passive: false});
  }
  if (!P.kok){
    const k = document.createElement("div");
    const mac = /Mac|iPhone|iPad/.test(navigator.platform || "");
    k.innerHTML = '<span class="dugmeler"><button class="ac sk" type="button" aria-label="Stok kartı aç"><span class="mi">inventory_2</span><span class="yazi">Stok kartı</span></button>' +
      '<button class="ac ara" type="button" aria-label="Ara"><span class="mi">search</span><span class="yazi">Ara</span><kbd>' + (mac ? "⌘K" : "Ctrl K") + '</kbd></button></span>';
    // Örtü sayfanın EN ÜST katmanında: üst şeridin içinde kalınca (sticky, z 999)
    // kenar çubuğu düğmesi gibi öğeler paletin üstünde görünüyordu.
    try { if (window.__kayranPaletHost) window.__kayranPaletHost.remove(); } catch (e) {}
    const host = document.createElement("div"); host.id = "kayran-palet";
    host.style.cssText = "position:relative;z-index:2147483647";      // kenar çubuğu düğmesinin de üstünde
    document.body.appendChild(host); window.__kayranPaletHost = host;
    // Açık bir pencerenin (st.dialog, ör. stok kartı) odak kilidi, paleti açınca odağı geri çekiyordu: kart
    // açıkken Ctrl+K'ya yazılan harfler arama kutusuna gitmiyordu (Ekim 2026). Palet açıkken, odağın palete
    // girip çıkmasıyla ilgili olayları kilit görmeden (pencere düzeyinde, yakalama aşamasında) durdur.
    if (!window.__kayranPaletOdak){
      window.__kayranPaletOdak = true;
      const bizde = e => { const h = window.__kayranPaletHost; if (!h || !h.__acik || !h.__acik()) return false;
        const yol = e.composedPath ? e.composedPath() : [];
        return yol.includes(h) || e.relatedTarget === h; };
      for (const t of ["focusin", "focusout"]) window.addEventListener(t, e => { if (bizde(e)) e.stopImmediatePropagation(); }, true);
    }
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
    host.__acik = () => P.acik;
    // Açık pencere (st.dialog) sayfadaki diğer her şeyi "inert" yapıyor (react-aria): palet de tıklanamaz ve
    // yazılamaz oluyordu. Palet açıkken bu işaret kaldırılır, pencere yeniden koyarsa yine kaldırılır.
    const serbest = () => { if (P.acik && (host.inert || host.hasAttribute("aria-hidden"))){ host.inert = false; host.removeAttribute("inert"); host.removeAttribute("aria-hidden"); } };
    new MutationObserver(serbest).observe(host, {attributes: true, attributeFilter: ["inert", "aria-hidden"]});
    P.serbest = serbest;
    const YER = {urun: "Stok kartı aç · SKU, model ya da ürün adı",
                 "": "Sayfa, işlem, SKU, firma ya da soru: geçen ay en çok satan 5 ürün"};
    const ac = (mod) => { P.mod = mod === "urun" ? "urun" : ""; P.inp.placeholder = YER[P.mod];
                          P.acik = true; if (P.serbest) P.serbest(); P.ort.classList.add("acik"); P.inp.value = P.q; P.s = 0; ciz();
                          setTimeout(() => { P.inp.focus(); P.inp.select(); }, 0); };
    const kapa = () => { P.acik = false; P.ort.classList.remove("acik"); };
    P.kapa = kapa;
    window.__kayranPaletAc = ac;
    k.querySelector(".ac.ara").addEventListener("click", () => ac(""));
    k.querySelector(".ac.sk").addEventListener("click", () => ac("urun"));
    gk.querySelector(".kapat").addEventListener("click", kapa);
    P.ort.addEventListener("mousedown", e => { if (e.target === P.ort) kapa(); });
    P.inp.addEventListener("input", () => {
      P.q = P.inp.value; P.s = 0; ciz();
      clearTimeout(P.t);
      const q = P.q.trim();
      if (P.mod === "urun" && (P.D.urunler || []).length) return;     // ürün kipi: sunucuya gerek yok
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
    // Ürünler (tarayıcıda süzülür): bir kez hazırlanır
    if (P.uKaynak !== D.urunler){
      P.uKaynak = D.urunler;
      P.U = (D.urunler || []).map(u => ({tur: "urun", urun: true, id: "urun:" + u.sku, sku: u.sku, ad: u.ad,
                                          stok: u.stok, gun: u.gun, durum: u.durum, ara: sade(u.sku + " " + u.ad)}));
      P.Uk = {}; for (const u of P.U) P.Uk[u.sku] = u;
    }
    const U = P.U, urunVar = U.length > 0;
    const son = (D.son || []).map(k => P.Uk[k] || {tur: "urun", urun: true, id: "urun:" + k, sku: k, ad: "", durum: ""});
    const urunBul = () => {
      const l = U.filter(o => parca.every(p => o.ara.includes(p)));
      const ks = sade(q.replace(/\s+/g, ""));
      const p = o => { const k = sade(o.sku).replace(/\s+/g, ""); return k === ks ? 0 : k.startsWith(ks) ? 1 : k.includes(ks) ? 2 : 3; };
      return l.map((o, i) => [p(o), i, o]).sort((x, y) => x[0] - y[0] || x[1] - y[1]).map(x => x[2]);
    };
    const uy = o => parca.every(p => o.ara.includes(p));
    // Sıra: adı aranan metinle başlayan → bir kelimesi başlayan → içeren (kararlı)
    const puan = o => { const a = sade(o.ad); if (a.startsWith(q)) return 0;
                        return a.split(/[\s/·-]+/).some(w => w.startsWith(parca[0] || "")) ? 1 : 2; };
    const sirala = l => l.map((o,i)=>[puan(o),i,o]).sort((x,y)=>x[0]-y[0]||x[1]-y[1]).map(x=>x[2]);
    let gr = [];
    if (P.mod === "urun" && urunVar){
      if (!q){
        if (son.length) gr.push(["Son açılan stok kartları", son]);
        const sp = U.filter(o => o.durum === "siparis").slice(0, 6);
        if (sp.length) gr.push(["Sipariş zamanı gelenler", sp]);
        if (!gr.length) gr.push(["Ürünler", U.slice(0, 8)]);
      } else {
        const l = urunBul();
        gr.push(["Ürünler · " + l.length.toLocaleString("tr-TR") + " sonuç", l.slice(0, 40)]);
      }
    } else if (!q){
      if (son.length) gr.push(["Son açılan stok kartları", son.slice(0, 4)]);
      gr.push(["Sayfalar", sabit.filter(o => o.tur === "sayfa" && !o.yol).concat(sabit.filter(o => o.tur === "islem")).slice(0, 12)]);
    } else {
      const sy = sirala(sabit.filter(o => o.tur === "sayfa" && uy(o))).slice(0, 8);
      const isl = sirala(sabit.filter(o => o.tur === "islem" && uy(o))).slice(0, 5);
      if (D.sonuc_q && sade(D.sonuc_q) === q && (D.sonuc || []).some(o => o.tur === "soru")) gr.unshift(["Soru", (D.sonuc || []).filter(o => o.tur === "soru")]);
      const ul = urunVar ? urunBul().slice(0, 6) : [];
      if (ul.length) gr.push(["Ürünler", ul]);
      if (sy.length) gr.push(["Sayfalar", sy]);
      if (isl.length) gr.push(["İşlemler", isl]);
      const ad = {urun:"Ürünler", cari:"Cariler", satis:"Satışlar", ithalat:"İthalat", servis:"Teknik servis"};
      if (D.sonuc_q && sade(D.sonuc_q) === q){
        for (const t of (urunVar ? ["cari","satis","ithalat","servis"] : ["urun","cari","satis","ithalat","servis"])){
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
        if (o.urun){
          const tr = n => Number(n || 0).toLocaleString("tr-TR");
          const gun = o.durum === "satissiz" ? "satış yok" : o.durum === "yok" ? "stok yok"
                    : (o.gun === null || o.gun === undefined) ? "" : tr(o.gun) + " gün";
          const ipucu = o.durum === "siparis" ? "Sipariş zamanı (stok + yolda, tedarik süresince yetmiyor)"
                      : o.durum === "yeter" ? "Son 90 günün satış hızıyla" : "";
          h += '<div class="og' + (n === P.s ? " s" : "") + '" role="option" data-n="' + n + '"><span class="mi">inventory_2</span>' +
               '<span class="sku">' + es(o.sku) + '</span><span class="ad u">' + es(o.ad) + '</span><span class="sag">' +
               (o.durum ? '<span class="cip g stokc">' + tr(o.stok) + ' adet</span>' : '') +
               (gun ? '<span class="cip ' + es(o.durum) + '" title="' + es(ipucu) + '">' + es(gun) + '</span>' : '') +
               '</span></div>';
          continue;
        }
        h += '<div class="og' + (n === P.s ? " s" : "") + '" role="option" data-n="' + n + '"><span class="mi">' + es(o.ikon) + '</span>' +
             '<span class="ad">' + es(o.ad) + '</span>' + (o.yol ? '<span class="yol">' + es(o.yol) + '</span>' : '') + '</div>';
      }
    }
    const bekliyor = !(P.mod === "urun" && urunVar) && q.length >= 2 && !(D.sonuc_q && sade(D.sonuc_q) === q);
    if (bekliyor) h += '<div class="bilgi">Verilerde aranıyor…</div>';
    else if (!P.gorunen.length) h += '<div class="bilgi">' + (P.mod === "urun"
      ? "Eşleşen ürün yok. SKU'nun bir kısmını ya da modeli yazmayı deneyin."
      : "Sonuç yok. SKU, firma adı, sipariş ya da seri no deneyin.") + '</div>';
    P.lst.innerHTML = h;
  }
  ciz();
}
"""

# Kayıtlı bileşenler TEK önbellekte (sayfa testi her uygulamada _BILESEN'i sıfırlar: tests/duman/conftest.py)
_BILESEN = None


def _bilesen(ad="palet"):
    global _BILESEN
    if _BILESEN is None:
        import streamlit.components.v2 as _v2
        _BILESEN = {"palet": _v2.component("kayran_palet", css=_CSS, js=_JS),
                    "kutu": _v2.component("kayran_stok_kutusu", css=_KUTU_CSS, js=_KUTU_JS)}
    return _BILESEN[ad]


def git(oge_id):
    """Paletten seçilen öğeye git. Sayfa: oturuma yaz + uygulamayı yeniden çiz.
    Ürün: stok kartını aç (bulunduğun sayfada kalır)."""
    if str(oge_id or "") == "kapi":           # Dosya kapısı: bütün Excel yüklemeleri tek pencerede
        from shared.dosya_kapisi import ac
        from kayranpm.stok_karti import kapat as _kart_kapat
        _kart_kapat()                         # aynı anda iki pencere açılamaz: açık stok kartı kapanır
        ac()
        st.rerun(scope="app")
        return
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
        # Kart parçacık içinde açılmaz (açık kartın üstüne açılınca pencere açılıp kapanıyordu): açık kart
        # oturuma yazılır, uygulama yeniden çizilir, pencereyi app.py açar (kayranpm.stok_karti.acik_karti_ciz).
        from kayranpm.stok_karti import ac_ve_ciz
        ac_ve_ciz(h["stok_karti"])
        return
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
        except Exception as _e:  # noqa: BLE001
            sessiz("shared.palet.palet", _e, "debug")
    try:
        from kayranpm.stok_karti_palet import palet_urunleri
        from kayranpm.stok_karti import SON_ANAHTAR
        urunler, son = palet_urunleri(), list(st.session_state.get(SON_ANAHTAR, []))
    except Exception as _e:  # noqa: BLE001 — ürün listesi yoksa palet eski sunucu aramasıyla çalışır
        sessiz("shared.palet.urunler", _e)
        urunler, son = [], []
    veri = {"css": _CSS, "ogeler": palet_ogeleri(yetkiler, ozel, kullanici, kosul),
            "sonuc": sonuc, "sonuc_q": q if len(q.strip()) >= 2 else "", "urunler": urunler, "son": son}
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


# ── Ürün Yönetimi'ndeki geniş "Stok kartı aç" kutusu (Ekim 2026) ───────────────
# Eskiden ayrı bir arama kutusu + sonuç düğmeleriydi (kendi kart açma yolu vardı; kart açıkken başka kod
# arayınca pencere açılıp kapanıyordu). Artık yalnız Ctrl+K penceresini ürün kipinde açar: tek arama, tek yol.
_KUTU_CSS = r"""
:host{display:block}
.kutu{display:flex;align-items:center;gap:10px;width:100%;min-height:40px;padding:0 12px;border-radius:10px;cursor:text;
  border:1px solid var(--k-kenar2);background:var(--k-yuzey1);color:var(--k-silik);font:inherit;font-size:14px;text-align:left}
.kutu:hover{border-color:color-mix(in srgb,var(--k-mor) 45%,transparent);color:var(--k-soluk)}
.kutu:focus-visible{outline:2px solid var(--k-mor);outline-offset:2px}
.mi{font-family:"Material Symbols Rounded";font-weight:normal;font-style:normal;font-size:19px;line-height:1;
  display:inline-block;letter-spacing:normal;text-transform:none;white-space:nowrap;-webkit-font-smoothing:antialiased}
.yazi{flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
kbd{font:inherit;font-size:11px;color:var(--k-silik);border:1px solid var(--k-kenar2);border-radius:5px;padding:1px 6px}
@media (max-width:640px){kbd{display:none}}
"""

_KUTU_JS = r"""
export default function(component){
  const {parentElement} = component;
  if (parentElement.__kutu) return;
  const mac = /Mac|iPhone|iPad/.test(navigator.platform || "");
  const b = document.createElement("button");
  b.type = "button"; b.className = "kutu"; b.setAttribute("aria-label", "Stok kartı aç");
  b.innerHTML = '<span class="mi">search</span><span class="yazi">Stok kartı aç · SKU, model ya da ürün adı</span>' +
                '<kbd>' + (mac ? "\u2318K" : "Ctrl K") + '</kbd>';
  b.addEventListener("click", () => { if (window.__kayranPaletAc) window.__kayranPaletAc("urun"); });
  parentElement.appendChild(b); parentElement.__kutu = b;
}
"""

def stok_karti_kutusu(key="stok_karti_kutusu"):
    """Geniş "Stok kartı aç" kutusu: tıklayınca Ctrl+K penceresi ürün kipinde açılır."""
    _bilesen("kutu")(key=key, data={}, default={}, height="content")
