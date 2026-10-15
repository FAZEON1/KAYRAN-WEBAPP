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
/* Görünüm: stok kartı taslağı "A"nın birebir değerleri (Ekim 2026, kullanıcı: "fontlar, renkler, her şey
   birebir aynı olsun"). Yazı Source Sans 3, SKU ve tuş çipleri JetBrains Mono (yalnız bu pencere ve düğme). */
.tetik{display:inline-flex;align-items:center;gap:8px;border:1px solid var(--k-kenar2);border-radius:999px;
  padding:5px 10px 5px 8px;font-family:var(--sk-govde);font-size:13px;line-height:1.5;color:var(--k-metin);
  background:var(--k-yuzey2);cursor:pointer;white-space:nowrap}
.tetik:hover{border-color:color-mix(in srgb,var(--k-mor) 45%,transparent)}
.tetik:focus-visible{outline:2px solid var(--k-mor);outline-offset:2px}
.tetik svg{flex:none}
.kbd{font-family:var(--sk-mono);font-weight:500;font-size:11px;line-height:1.5;border:1px solid var(--k-kenar2);
  border-bottom-width:2px;border-radius:5px;padding:0 5px;color:var(--k-soluk);background:var(--k-yuzey1);white-space:nowrap}
.mi{font-family:"Material Symbols Rounded";font-weight:normal;font-style:normal;font-size:18px;line-height:1;
  display:inline-block;letter-spacing:normal;text-transform:none;white-space:nowrap;-webkit-font-smoothing:antialiased}
.ort{position:fixed;inset:0;z-index:2147483647;background:var(--sk-ortu);display:none;align-items:flex-start;
  justify-content:center;padding:10vh 14px 0}
.ort.acik{display:flex}
.kutu{width:min(560px,100%);max-height:72vh;display:flex;flex-direction:column;background:var(--k-yuzey3);
  border:1px solid var(--k-kenar2);border-radius:14px;overflow:hidden;box-shadow:0 20px 50px -20px rgba(2,6,23,.7);
  color:var(--k-metin);font-family:var(--sk-govde);font-size:15px;line-height:1.5}
.ust{display:flex;align-items:center;gap:10px;padding:13px 14px;border-bottom:1px solid var(--k-kenar);color:var(--k-silik)}
.ust svg{flex:none}
.ust input{flex:1;min-width:0;border:0;outline:none;background:transparent;color:var(--k-metin);font-family:inherit;
  font-size:15px;font-weight:600;line-height:1.5;padding:0}
.ust input::placeholder{color:var(--k-silik);font-weight:400;opacity:1}
.ust .kbd{cursor:pointer}
.liste{overflow:auto;padding:6px 6px 8px}
.grup{font-size:11px;letter-spacing:.08em;text-transform:uppercase;color:var(--k-silik);padding:6px 8px}
.og{display:grid;grid-template-columns:auto minmax(0,1fr) auto auto;gap:10px;align-items:center;padding:7px 8px;
  border-radius:8px;cursor:pointer}
.og.s{background:color-mix(in srgb,var(--k-mor) 14%,transparent);outline:1px solid color-mix(in srgb,var(--k-mor) 35%,transparent)}
.og .mi{color:var(--k-soluk);font-size:18px;width:18px;text-align:center}
.og.s .mi{color:var(--k-mor)}
.sku{font-family:var(--sk-mono);font-weight:500;font-size:12.5px;color:var(--k-metin);white-space:nowrap}
.ad{font-size:13px;color:var(--k-soluk);overflow:hidden;text-overflow:ellipsis;white-space:nowrap;min-width:0}
.ad.sayfa{font-size:14px;color:var(--k-metin)}
.yol{font-size:12px;color:var(--k-silik);white-space:nowrap}
.cip{font-size:11.5px;font-weight:600;padding:1px 7px;border-radius:999px;white-space:nowrap;font-variant-numeric:tabular-nums}
.c-gri{background:var(--k-yuzey2);color:var(--k-soluk)}
.c-kirmizi{background:color-mix(in srgb,var(--k-kirmizi) 15%,transparent);color:var(--k-kirmizi)}
.c-amber{background:color-mix(in srgb,var(--k-amber) 16%,transparent);color:var(--k-amber)}
.c-yesil{background:color-mix(in srgb,var(--k-yesil) 15%,transparent);color:var(--k-yesil)}
.bilgi{padding:10px 8px;color:var(--k-silik);font-size:13px}
.alt{display:flex;gap:14px;flex-wrap:wrap;padding:8px 14px;border-top:1px solid var(--k-kenar);font-size:12px;color:var(--k-silik)}
@media (max-width:640px){.tetik .kbd{display:none}.ort{padding:8px}.kutu{max-height:85vh}.alt{display:none}}
@media (max-width:520px){.og{grid-template-columns:auto minmax(0,1fr) auto}.og .gizle{display:none}}
"""

# Taslaktaki fontlar belgeye BİR kez eklenir (gölge DOM içindeki yazılar da belgenin fontlarını kullanır).
_FONT_JS = r"""
  if (!document.getElementById("kayran-sk-font")){
    const l = document.createElement("link"); l.id = "kayran-sk-font"; l.rel = "stylesheet";
    l.href = "https://fonts.googleapis.com/css2?family=Source+Sans+3:wght@400;600;700&family=JetBrains+Mono:wght@500&display=swap";
    document.head.appendChild(l);
  }
"""
_ARA_SVG = ('<svg width="%d" height="%d" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" '
            'aria-hidden="true"><circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/></svg>')
# Font değişkenleri: gölge kökünde tanımlanır (uygulamanın geri kalanı Inter'de kalır)
_FONT_DEGISKEN = (':host{--sk-govde:"Source Sans 3",system-ui,-apple-system,"Segoe UI",sans-serif;'
                  '--sk-mono:"JetBrains Mono",ui-monospace,Menlo,Consolas,monospace}')
_CSS = _FONT_DEGISKEN + _CSS

_JS = r"""
export default function(component){
  const {data, setTriggerValue, parentElement} = component;
  const P = parentElement.__p || (parentElement.__p = {q:"", s:0, acik:false, t:null});
  P.D = data || {};
  const es = s => String(s ?? "").replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;");
  const harf = {"ç":"c","ğ":"g","ı":"i","ö":"o","ş":"s","ü":"u","â":"a","î":"i","İ":"i","I":"i"};
  const sade = s => String(s||"").replace(/[çğıöşüâîİI]/g, c => harf[c] || c).toLowerCase();
  const ARA = n => '//SVG//'.replace(/%d/g, n);
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
  // Sürüm: tarayıcıda eski sürümün düğmesi/penceresi kaldıysa (uygulama sayfa yenilenmeden güncellenince
  // parentElement aynı kalıyor) baştan kurulur. Eskiden yalnız ilk çizimde kuruluyordu: yeni "Stok kartı"
  // düğmesi kullanıcıda hiç görünmedi (Ekim 2026).
  const SURUM = "sk-a-2";
  if (P.kok && P.surum !== SURUM){ try { P.kok.remove(); } catch (e) {} P.kok = null; }
  //FONT//
  if (!P.kok){
    P.surum = SURUM;
    const k = document.createElement("div");
    const mac = /Mac|iPhone|iPad/.test(navigator.platform || "");
    k.innerHTML = '<button class="tetik" type="button" aria-label="Stok kartı aç">' + ARA(15) +
      '<span class="yazi">Stok kartı</span><span class="kbd">' + (mac ? "⌘ K" : "Ctrl K") + '</span></button>';
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
      '<div class="ort" role="dialog" aria-modal="true" aria-label="Stok kartı ara"><div class="kutu" lang="tr">' +
        '<div class="ust">' + ARA(18) + '<input type="text" autocomplete="off" spellcheck="false" ' +
        'placeholder="SKU, model ya da ürün adı yazın" aria-label="Ara"><span class="kbd kapat">Esc</span></div>' +
        '<div class="liste" role="listbox"></div>' +
        '<div class="alt"><span><span class="kbd">↑</span> <span class="kbd">↓</span> gez</span>' +
        '<span><span class="kbd">Enter</span> kartı aç</span>' +
        '<span><span class="kbd">' + (mac ? "⌘" : "Ctrl") + '</span> <span class="kbd">Enter</span> yeni sekmede</span></div>' +
      '</div></div>';
    parentElement.appendChild(k);
    P.kok = k; P.ort = gk.querySelector(".ort"); P.inp = gk.querySelector("input"); P.lst = gk.querySelector(".liste");
    host.__acik = () => P.acik;
    // Açık pencere (st.dialog) sayfadaki diğer her şeyi "inert" yapıyor (react-aria): palet de tıklanamaz ve
    // yazılamaz oluyordu. Palet açıkken bu işaret kaldırılır, pencere yeniden koyarsa yine kaldırılır.
    const serbest = () => { if (P.acik && (host.inert || host.hasAttribute("aria-hidden"))){ host.inert = false; host.removeAttribute("inert"); host.removeAttribute("aria-hidden"); } };
    new MutationObserver(serbest).observe(host, {attributes: true, attributeFilter: ["inert", "aria-hidden"]});
    P.serbest = serbest;
    // Tek pencere: Ctrl+K, "/", üst şeritteki düğme ve Ürün Yönetimi'ndeki kutu aynı pencereyi açar. Önce ürünler,
    // yazınca altında sayfalar, işlemler ve veri araması (cari, satış, ithalat, servis).
    const ac = () => { P.acik = true; if (P.serbest) P.serbest(); P.ort.classList.add("acik"); P.inp.value = P.q; P.s = 0; ciz();
                       setTimeout(() => { P.inp.focus(); P.inp.select(); }, 0); };
    const kapa = () => { P.acik = false; P.ort.classList.remove("acik"); };
    P.kapa = kapa;
    window.__kayranPaletAc = ac;
    k.querySelector(".tetik").addEventListener("click", () => ac());
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
      else if (e.key === "Enter"){ e.preventDefault(); if (n) git(P.gorunen[P.s], e.ctrlKey || e.metaKey); }
    });
    P.lst.addEventListener("mousemove", e => { const o = e.target.closest(".og"); if (o && +o.dataset.n !== P.s){ P.s = +o.dataset.n; ciz(true); } });
    P.lst.addEventListener("click", e => { const o = e.target.closest(".og"); if (o) git(P.gorunen[+o.dataset.n], e.ctrlKey || e.metaKey); });
  }
  // Örtü rengi temaya göre (taslaktaki gibi: koyu rgba(2,6,23,.62), açık rgba(15,23,42,.45))
  const ortu = P.D.tema === "acik" ? "rgba(15,23,42,.45)" : "rgba(2,6,23,.62)";
  for (const h of [window.__kayranPaletHost, parentElement]) if (h && h.style) h.style.setProperty("--sk-ortu", ortu);
  function git(o, yeniSekme){
    if (!o) return;
    if (yeniSekme && o.urun){                  // Ctrl+Enter: kart yeni sekmede (?kart=SKU, app.py açar)
      const u = new URL(window.location.href); u.searchParams.set("kart", o.sku);
      window.open(u.toString(), "_blank", "noopener"); return;
    }
    clearTimeout(P.t); P.kapa(); P.q = ""; P.sonIstek = null; setTriggerValue("sec", o.id);
  }
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
    const tr = n => Number(n || 0).toLocaleString("tr-TR");
    let gr = [];
    if (!q){
      // Boşken: son açılanlar ve sipariş zamanı gelenler (ürün listesi okunamadıysa sayfalar)
      if (son.length) gr.push(["Son açılanlar", son.slice(0, 5)]);
      const sp = U.filter(o => o.durum === "siparis").slice(0, 6);
      if (sp.length) gr.push(["Sipariş zamanı gelenler", sp]);
      if (!gr.length && urunVar) gr.push(["Ürünler", U.slice(0, 8)]);
      if (!urunVar) gr.push(["Sayfalar", sabit.filter(o => o.tur === "sayfa" && !o.yol).concat(sabit.filter(o => o.tur === "islem")).slice(0, 12)]);
    } else {
      const ul = urunVar ? urunBul() : [];
      if (ul.length) gr.push(["Ürünler · " + tr(ul.length) + " sonuç", ul.slice(0, 30)]);
      if (D.sonuc_q && sade(D.sonuc_q) === q && (D.sonuc || []).some(o => o.tur === "soru")) gr.unshift(["Soru", (D.sonuc || []).filter(o => o.tur === "soru")]);
      const sy = sirala(sabit.filter(o => o.tur === "sayfa" && uy(o))).slice(0, 6);
      const isl = sirala(sabit.filter(o => o.tur === "islem" && uy(o))).slice(0, 4);
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
        const sec = n === P.s ? " s" : "";
        if (o.urun){
          // Çip renkleri taslaktaki gibi: sipariş zamanı kırmızı, yeterli yeşil, satış / stok yok gri
          const gun = o.durum === "satissiz" ? "satış yok" : o.durum === "yok" ? "stok yok"
                    : (o.gun === null || o.gun === undefined) ? "" : tr(o.gun) + " gün";
          const renk = o.durum === "siparis" ? "c-kirmizi" : o.durum === "yeter" ? "c-yesil" : "c-gri";
          const ipucu = o.durum === "siparis" ? "Sipariş zamanı (stok + yolda, tedarik süresince yetmiyor)"
                      : o.durum === "yeter" ? "Son 90 günün satış hızıyla" : "";
          h += '<div class="og' + sec + '" role="option" data-n="' + n + '">' +
               '<span class="sku">' + es(o.sku) + '</span><span class="ad">' + es(o.ad) + '</span>' +
               (o.durum ? '<span class="cip c-gri gizle">' + (o.stok ? tr(o.stok) + ' adet' : '—') + '</span>' : '<span></span>') +
               (gun ? '<span class="cip ' + renk + '" title="' + es(ipucu) + '">' + es(gun) + '</span>' : '<span></span>') +
               '</div>';
          continue;
        }
        h += '<div class="og' + sec + '" role="option" data-n="' + n + '"><span class="mi">' + es(o.ikon) + '</span>' +
             '<span class="ad sayfa">' + es(o.ad) + '</span><span class="yol">' + es(o.yol || "") + '</span><span></span></div>';
      }
    }
    const bekliyor = q.length >= 2 && !(D.sonuc_q && sade(D.sonuc_q) === q);
    if (!P.gorunen.length) h += '<div class="bilgi">' + (bekliyor ? "Verilerde aranıyor…"
      : "Eşleşen yok. SKU'nun bir kısmını, modeli ya da firma adını yazmayı deneyin.") + '</div>';
    P.lst.innerHTML = h;
  }
  ciz();
}
"""
_JS = _JS.replace("  //FONT//\n", _FONT_JS).replace("//SVG//", _ARA_SVG)

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


def _tema():
    try:
        from shared.tasarim import aktif_tema
        return aktif_tema()
    except Exception:  # noqa: BLE001
        return "koyu"


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
            "sonuc": sonuc, "sonuc_q": q if len(q.strip()) >= 2 else "", "urunler": urunler, "son": son,
            "tema": _tema()}
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
# arayınca pencere açılıp kapanıyordu). Artık yalnız Ctrl+K penceresini açar: tek arama, tek yol.
# Görünüm taslaktaki büyük arama kutusunun birebir değerleri (mor çerçeve + 4px halka, 15px yazı).
_KUTU_CSS = _FONT_DEGISKEN + r"""
:host{display:block;padding:4px}
.kutu{display:flex;align-items:center;gap:10px;width:100%;padding:12px 14px;border-radius:10px;cursor:text;
  border:1px solid color-mix(in srgb,var(--k-mor) 45%,transparent);background:var(--k-yuzey1);color:var(--k-silik);
  box-shadow:0 0 0 4px color-mix(in srgb,var(--k-mor) 10%,transparent);
  font-family:var(--sk-govde);font-size:15px;line-height:1.5;text-align:left}
.kutu:hover{border-color:color-mix(in srgb,var(--k-mor) 70%,transparent)}
.kutu:focus-visible{outline:2px solid var(--k-mor);outline-offset:2px}
.kutu svg{flex:none}
.yazi{flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
"""

_KUTU_JS = r"""
export default function(component){
  const {parentElement, data} = component;
//FONT//
  const adet = Number((data || {}).adet || 0);
  const yazi = "SKU, model ya da ürün adı yazın" + (adet ? " · " + adet.toLocaleString("tr-TR") + " ürün" : "");
  if (parentElement.__kutu){ parentElement.__kutu.querySelector(".yazi").textContent = yazi; return; }
  const b = document.createElement("button");
  b.type = "button"; b.className = "kutu"; b.setAttribute("aria-label", "Stok kartı aç");
  b.innerHTML = '//SVG//'.replace(/%d/g, 18) + '<span class="yazi"></span>';
  b.querySelector(".yazi").textContent = yazi;
  b.addEventListener("click", () => { if (window.__kayranPaletAc) window.__kayranPaletAc(); });
  parentElement.appendChild(b); parentElement.__kutu = b;
}
""".replace("//FONT//\n", _FONT_JS).replace("//SVG//", _ARA_SVG)


def stok_karti_kutusu(key="stok_karti_kutusu"):
    """Geniş "Stok kartı aç" kutusu: tıklayınca Ctrl+K penceresi açılır."""
    try:
        from kayranpm.stok_karti_palet import palet_urunleri
        adet = len(palet_urunleri())
    except Exception:  # noqa: BLE001
        adet = 0
    _bilesen("kutu")(key=key, data={"adet": adet}, default={}, height="content")
