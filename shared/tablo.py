# -*- coding: utf-8 -*-
"""Ortak tablo bileşeni — TEK görünüm (Ekim 2026).

Kullanım:
    from shared.tablo import tablo
    secilen = tablo(satirlar, key="pnl_kanal", secilebilir=True, pay="Ciro")
    if secilen is not None: ...           # tıklanan satırın ÖZGÜN sırası

• satirlar: list[dict] ya da DataFrame. "_" ile başlayan alanlar kolon olmaz:
  _etiket (ilk hücrede küçük soluk ek, ör. "A.Ş."), _ipucu (ilk hücre title).
• Kolon tipi adından çıkar (shared.tasarim._tablo_kolon_tipi): para / adet / oran.
• İlk hücresi "Σ" ile başlayan satır toplamdır: alt bilgiye sabitlenir, sıralanmaz.
• Başlığa tıkla → sıralama (tarayıcıda, anlık). 9+ satırda arama kutusu.
  ⤓ düğmesi görünen satırları Excel'in açtığı CSV olarak indirir.
• Dar alanda (≤560 px kap genişliği) tablo kart listesine döner.
• secilebilir=True: satır tıklaması Python'a döner (kutucuk sütunu yok).

Streamlit components v2 (≥1.50): iframe yok, yükseklik içeriğe göre.
Yoksa ImportError → çağıran eski çizime düşer (tasarim.tablo_sirali).
"""
import hashlib
import json
import math

from shared.tasarim import _tablo_kolon_tipi, _tr_para, _tr_adet, _tr_oran, tr_sayi

ARAMA_ESIK = 9            # bu kadar ve daha fazla satırda arama kutusu
_ROZET_AD = ("marj", "kârlılık", "karlilik", "kârlılik")


# ── Saf hazırlık ────────────────────────────────────────────────────
def marj_sinifi(v):
    """Marj rozeti rengi: ≥25 iyi · 15–25 orta · 0–15 düşük · <0 eksi."""
    try:
        v = float(v)
    except (TypeError, ValueError):
        return "orta"
    if v < 0:
        return "eksi"
    if v < 15:
        return "dusuk"
    if v < 25:
        return "orta"
    return "iyi"


def _bos_mu(v):
    return v is None or (isinstance(v, float) and math.isnan(v))


def _metin(v, tip, birim):
    if _bos_mu(v):
        return "", None
    try:
        if tip == "para":
            return _tr_para(v, birim), float(v)
        if tip == "adet":
            return _tr_adet(v), float(v)
        if tip == "sayi":
            f = float(v)
            return (_tr_adet(f) if f.is_integer() else tr_sayi(f, 2).rstrip("0").rstrip(",")), f
        if tip == "oran":
            f = float(v)                       # "-%3,0" (eskiden "%-3,0")
            return ("-" + _tr_oran(abs(f), 1)) if f < 0 else _tr_oran(f, 1), f
    except (TypeError, ValueError):
        pass
    if isinstance(v, float) and v.is_integer():
        return str(int(v)), v
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return str(v), v
    return str(v), None


def _kayitlar(satirlar):
    if hasattr(satirlar, "to_dict"):                       # DataFrame
        return satirlar.astype(object).to_dict("records")
    return list(satirlar or [])


def tablo_veri(satirlar, birim="$", pay=None, toplam_isaret="Σ", arama=None):
    """Bileşene giden JSON. SAF — test edilir."""
    kayit = _kayitlar(satirlar)
    if not kayit:
        return {"kolonlar": [], "satirlar": [], "toplam": None, "pay": None, "arama": False}
    adlar = [k for k in kayit[0].keys() if not str(k).startswith("_")]
    kolonlar = []
    for ad in adlar:
        tip = _tablo_kolon_tipi(ad)
        if tip is None:
            # Adından tipi çıkmayan ama tüm değerleri sayı olan kolon ("Kapsama
            # (hft)", "Acil"): sağa yaslı, TR biçimli. Tek bir metin varsa metin kalır.
            dolu = [r.get(ad) for r in kayit if not _bos_mu(r.get(ad))]
            if dolu and all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in dolu):
                tip = "sayi"
        kolonlar.append({
            "ad": str(ad), "tip": tip, "hiza": "sag" if tip else "sol",
            "rozet": tip == "oran" and any(r in str(ad).lower() for r in _ROZET_AD),
        })
    pay_i = adlar.index(pay) if pay in adlar else None

    govde, toplam = [], None
    for i, r in enumerate(kayit):
        h, s, neg, rz = [], [], [], []
        rb = r.get("_birim") or birim                     # satır başına para birimi (karışık döviz)
        for ad, k in zip(adlar, kolonlar):
            m, ham = _metin(r.get(ad), k["tip"], rb)
            h.append(m)
            s.append(ham if ham is not None else m)
            neg.append(bool(ham is not None and ham < 0))
            rz.append(marj_sinifi(ham) if k["rozet"] and ham is not None else "")
        satir = {"i": i, "id": str(r.get("_id", i)), "h": h, "s": s, "neg": neg, "rz": rz,
                 "etiket": str(r.get("_etiket") or ""), "ipucu": str(r.get("_ipucu") or "")}
        if h and str(h[0]).strip().startswith(toplam_isaret):
            toplam = satir
        else:
            govde.append(satir)

    if pay_i is not None:
        tp = sum(max(float(x["s"][pay_i]), 0.0) for x in govde
                 if isinstance(x["s"][pay_i], (int, float)))
        for x in govde:
            v = x["s"][pay_i]
            x["pay"] = round(max(float(v), 0.0) / tp * 100, 2) if (tp and isinstance(v, (int, float))) else 0
    return {"kolonlar": kolonlar, "satirlar": govde, "toplam": toplam, "pay": pay_i,
            "arama": (len(govde) >= ARAMA_ESIK) if arama is None else bool(arama)}


def secim_coz(secim, satirlar):
    """Bileşenin tuttuğu kimlik(ler) → GÜNCEL listedeki sıra(lar). Listede artık olmayan
    kimlik düşer (süzgeç değişince seçim başka satıra kaymaz)."""
    if secim is None or secim == "":
        return []
    ids = [str(x) for x in (secim if isinstance(secim, (list, tuple)) else [secim])]
    kayit = _kayitlar(satirlar)
    konum = {str(r.get("_id", i)): i for i, r in enumerate(kayit)}
    return [konum[x] for x in ids if x in konum]


# ── Ünvan kısaltma ──────────────────────────────────────────────────
_TR_BUYUK = str.maketrans("İIŞĞÜÖÇ", "IISGUOC")
_KES = {"SANAYI", "TICARET", "ANONIM", "LIMITED", "SIRKETI", "VE", "HIZMETLER", "HIZMETLERI",
        "DIS", "ITHALAT", "IHRACAT", "PAZARLAMA", "A.S.", "AS", "LTD", "STI", "LTD.", "STI."}
_KES_IKINCI = {"BILISIM", "TEKNOLOJILERI", "ILETISIM", "SISTEMLERI", "REKLAMCILIK",
               "ELEKTRONIK", "BILGISAYAR", "YAZILIM", "TEKNOLOJI"}
_KISALTMA = {"EERA", "PC", "IT", "TV", "HB", "SSD", "USB", "LED"}


def _kucult(k, ascii_):
    if not k:
        return k
    if "-" in k:                                # "D-MARKET" → "D-Market"
        return "-".join(_kucult(p, ascii_) for p in k.split("-"))
    if k.translate(_TR_BUYUK) in _KISALTMA or len(k) <= 2:
        return k
    bas, son = k[0], k[1:]
    if ascii_:                                  # "BILGISAYAR" İ'siz yazılmış
        return bas + son.lower()
    son = son.replace("I", "ı").replace("İ", "i").lower()
    return bas + son


def kisa_unvan(tam):
    """'VATAN BILGISAYAR SANAYI VE TICARET ANONIM SIRKETI' → ('Vatan Bilgisayar', 'A.Ş.').
    Şirket türü ve sektör ekleri atılır; zaten kısa / küçük harfli ad dokunulmaz."""
    s = " ".join(str(tam or "").split())
    if not s:
        return "", ""
    if s != s.upper():                         # elle yazılmış görünen ad
        return s, ""
    n = s.translate(_TR_BUYUK)
    # Döviz eki: aynı firmanın TL / USD carisi ayrışsın (shared.utils.firma_kisa_ad
    # ile aynı kural ve aynı döviz listesi — iki ayrı tanım olmasın).
    doviz = ""
    try:
        from shared.utils import firma_kisa_ad
        _k = firma_kisa_ad(s)
        if " · " in _k:
            doviz = _k.rsplit(" · ", 1)[1]
            s = " ".join(s.split()[:-1])
    except Exception:
        pass
    tur = "A.Ş." if ("ANONIM" in n or " A.S" in n) else ("Ltd. Şti." if ("LIMITED" in n or " LTD" in n) else "")
    ascii_ = not any(c in s for c in "İŞĞÜÖÇ")
    tut = []
    for k in s.split():
        kn = k.translate(_TR_BUYUK)
        if kn in _KES:
            break
        if len(tut) >= 2 and kn in _KES_IKINCI:
            break
        tut.append(k)
        if len(tut) >= 3:
            break
    if not tut:
        tut = s.split()[:2]
    kisa = " ".join(_kucult(k, ascii_) for k in tut)
    return (f"{kisa} · {doviz}" if doviz else kisa), tur


# ── Bileşen ─────────────────────────────────────────────────────────
_CSS = r"""
:host{display:block}
.kt{container-type:inline-size;font-size:13px;color:var(--k-metin);font-variant-numeric:tabular-nums}
.ust{display:flex;align-items:center;gap:8px;margin:0 0 8px}
.ara{flex:1;min-width:0;position:relative}
.ara input{width:100%;box-sizing:border-box;height:32px;padding:0 10px 0 30px;border-radius:8px;
  border:1px solid var(--k-kenar2);background:var(--k-yuzey1);color:var(--k-metin);font:inherit;outline:none}
.ara input:focus{border-color:var(--k-mor)}
.ara svg{position:absolute;left:9px;top:9px;opacity:.55}
.say{font-size:11px;color:var(--k-silik);white-space:nowrap;margin-left:auto}
.cs{font-size:12px;color:var(--k-soluk);white-space:nowrap}
.cs b{color:var(--k-mor2);font-weight:600}
.cs a{color:var(--k-soluk)}
.sirala{display:none;height:32px;border-radius:8px;border:1px solid var(--k-kenar2);background:var(--k-yuzey1);
  color:var(--k-metin);font:inherit;font-size:12px;padding:0 6px;max-width:44%}
.btn{height:30px;min-width:30px;border-radius:8px;border:1px solid var(--k-kenar2);background:transparent;
  color:var(--k-soluk);cursor:pointer;display:inline-flex;align-items:center;justify-content:center;padding:0 8px}
.btn:hover{color:var(--k-metin);border-color:var(--k-mor)}
.kap{overflow:auto;border:1px solid var(--k-kenar);border-radius:12px;background:var(--k-yuzey1)}
table{width:100%;border-collapse:separate;border-spacing:0}
th{position:sticky;top:0;z-index:2;background:var(--k-yuzey2);color:var(--k-soluk);font-weight:500;font-size:12px;
  text-align:left;padding:9px 12px;border-bottom:1px solid var(--k-kenar2);white-space:nowrap;cursor:pointer;user-select:none}
th.sag,td.sag{text-align:right}
th:hover{color:var(--k-metin)}
th .ok{display:inline-block;color:var(--k-mor2);font-size:11px}
th .ok:not(:empty){margin:0 3px}
td{padding:9px 12px;border-bottom:1px solid var(--k-kenar);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:320px}
tbody tr:last-child td{border-bottom:none}
tbody tr:hover td{background:var(--k-ortu2)}
.sec tbody tr{cursor:pointer}
tbody tr.secili td{background:var(--k-vurgu)}
tbody tr.secili td:first-child{box-shadow:inset 2px 0 0 var(--k-mor)}
th:first-child,td:first-child{position:sticky;left:0;z-index:1;background:var(--k-yuzey1)}
th:first-child{z-index:3;background:var(--k-yuzey2)}
tbody tr:hover td:first-child{background:var(--k-yuzey2)}
.et{color:var(--k-silik);font-size:11px;margin-left:6px}
.neg{color:var(--k-kirmizi)}
.cubuk{height:3px;border-radius:2px;background:var(--k-kenar2);margin-top:5px;margin-left:auto;max-width:140px}
.cubuk i{display:block;height:3px;border-radius:2px;background:var(--k-mor);margin-left:auto}
.rz{display:inline-block;padding:1px 8px;border-radius:999px;font-size:12px;font-weight:500}
.rz.iyi{background:color-mix(in srgb,var(--k-yesil) 16%,transparent);color:var(--k-yesil)}
.rz.orta{background:var(--k-ortu2);color:var(--k-soluk)}
.rz.dusuk{background:color-mix(in srgb,var(--k-amber) 16%,transparent);color:var(--k-amber)}
.rz.eksi{background:color-mix(in srgb,var(--k-kirmizi) 16%,transparent);color:var(--k-kirmizi)}
tfoot td,tfoot td:first-child{position:sticky;bottom:0;background:var(--k-yuzey2);font-weight:600;border-top:1px solid var(--k-kenar2);border-bottom:none}
tfoot td:first-child{left:0;z-index:3}
.kt{position:relative}
.ust.yuzer{position:absolute;right:8px;top:5px;z-index:5;margin:0;opacity:0;transition:opacity .15s}
.kt:hover .ust.yuzer,.ust.yuzer:focus-within{opacity:1}
.ust.yuzer .say{display:none}
.ust.yuzer .btn{height:26px;min-width:26px;background:var(--k-yuzey2)}
.bos{padding:18px;text-align:center;color:var(--k-silik)}
@container (max-width:560px){
  .sirala{display:block}
  .ust{flex-wrap:wrap}
  .ust .ara{flex-basis:100%}
  .kap{border:none;background:transparent;overflow:visible;max-height:none !important}
  table,tbody,tfoot,tr,td{display:block;width:auto}
  thead{display:none}
  tbody tr,tfoot tr{border:1px solid var(--k-kenar);border-radius:12px;background:var(--k-yuzey1);margin:0 0 8px;padding:6px 0}
  tfoot tr{background:var(--k-yuzey2)}
  td{position:static !important;display:flex;justify-content:space-between;align-items:center;gap:12px;
     border:none;padding:4px 12px;max-width:none;white-space:normal;text-align:right !important;background:transparent !important}
  td:first-child{font-weight:600;font-size:14px;text-align:left !important;justify-content:flex-start;padding-top:6px;box-shadow:none !important}
  td:not(:first-child)::before{content:attr(data-l);color:var(--k-silik);font-size:12px;font-weight:400;text-align:left}
  .cubuk{display:none}
  tfoot td{position:static}
}
"""

_JS = r"""
export default function(component){
  const {data, setTriggerValue, setStateValue, parentElement} = component;
  const D = data || {}, K = D.kolonlar || [];
  const durum = parentElement.__kt || (parentElement.__kt = {q:"", sk:null, sy:-1, sec:(D.secili ?? null),
                                                              secs:new Set((D.secililer || []).map(String))});
  const coklu = !!D.coklu, kalici = !!D.kalici;
  let kok = parentElement.querySelector(".kt");
  if (!kok){ kok = document.createElement("div"); kok.className = "kt"; parentElement.appendChild(kok); }
  const es = s => String(s ?? "").replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;");
  const ARA = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/></svg>';
  const INDIR = '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 4v11m0 0-4-4m4 4 4-4M5 20h14"/></svg>';
  kok.innerHTML =
    '<div class="ust' + (D.arama ? '' : ' yuzer') + '">' +
      (D.arama ? '<label class="ara">'+ARA+'<input type="search" placeholder="Ara…" aria-label="Tabloda ara"></label>' : '') +
      (D.arama ? '<select class="sirala" aria-label="Sırala"><option value="">Sırala</option>' +
        K.map((k,i)=>'<option value="'+i+':-1">'+es(k.ad)+(k.tip?' · büyükten':' · Z→A')+'</option><option value="'+i+':1">'+es(k.ad)+(k.tip?' · küçükten':' · A→Z')+'</option>').join("") +
        '</select>' : '') +
      (coklu ? '<span class="cs"></span>' : '') +
      '<span class="say"></span>' +
      '<button class="btn" type="button" title="Excel için indir (CSV)" aria-label="İndir">'+INDIR+'</button>' +
    '</div>' +
    '<div class="kap' + (D.secilebilir ? ' sec' : '') + '" style="max-height:' + (D.maks || 520) + 'px">' +
      '<table><thead><tr>' + K.map((k,i)=>'<th data-i="'+i+'" class="'+(k.hiza==="sag"?"sag":"")+'">'+(k.hiza==="sag" ? '<span class="ok"></span>'+es(k.ad) : es(k.ad)+'<span class="ok"></span>')+'</th>').join("") +
      '</tr></thead><tbody></tbody><tfoot></tfoot></table>' +
    '</div>';
  const govde = kok.querySelector("tbody"), alt = kok.querySelector("tfoot"), say = kok.querySelector(".say");
  const hucre = (r,j,kok_) => {
    const k = K[j], m = r.h[j];
    let ic = es(m);
    if (k.rozet && r.rz[j]) ic = '<span class="rz '+r.rz[j]+'">'+es(m)+'</span>';
    if (j===0 && r.etiket) ic += '<span class="et">'+es(r.etiket)+'</span>';
    if (D.pay===j && r.pay !== undefined && !kok_) ic += '<div class="cubuk"><i style="width:'+Math.max(r.pay,1.5)+'%"></i></div>';
    const cls = [k.hiza==="sag"?"sag":"", (r.neg[j] && !k.rozet)?"neg":""].join(" ").trim();
    const ip = (j===0 && r.ipucu) ? r.ipucu : (!k.tip && String(m).length>28 ? m : "");
    return '<td data-l="'+es(k.ad)+'"'+(cls?' class="'+cls+'"':'')+(ip?' title="'+es(ip)+'"':'')+'>'+ic+'</td>';
  };
  const sirala = R => {
    if (durum.sk===null) return R;
    const j = durum.sk, y = durum.sy;
    return [...R].sort((a,b)=>{
      const x=a.s[j], z=b.s[j];
      const s = (typeof x==="number" && typeof z==="number") ? x-z : String(x).localeCompare(String(z),"tr");
      return s*y;
    });
  };
  let gorunen = [];
  const ciz = () => {
    const q = durum.q.toLocaleLowerCase("tr");
    let R = (D.satirlar||[]).filter(r => !q || r.h.some(h => String(h).toLocaleLowerCase("tr").includes(q)) ||
                                          (r.etiket||"").toLocaleLowerCase("tr").includes(q));
    gorunen = sirala(R);
    govde.innerHTML = gorunen.length ? gorunen.map(r =>
      '<tr data-i="'+r.i+'" data-id="'+es(r.id)+'"'+((coklu ? durum.secs.has(r.id) : durum.sec===r.id)?' class="secili"':'')+'>'
      +K.map((_,j)=>hucre(r,j,false)).join("")+'</tr>').join("")
      : '<tr><td class="bos" colspan="'+K.length+'">Eşleşen satır yok</td></tr>';
    alt.innerHTML = D.toplam ? '<tr>'+K.map((_,j)=>hucre(D.toplam,j,true)).join("")+'</tr>' : "";
    const n = (D.satirlar||[]).length;
    say.textContent = q ? (gorunen.length+" / "+n+" satır") : (n+" satır");
    const cs = kok.querySelector(".cs");
    if (cs){
      cs.innerHTML = durum.secs.size ? '<b>'+durum.secs.size+' seçili</b> · <a href="#" class="temizle">temizle</a>' : 'satıra tıkla: seç / bırak';
      const t = cs.querySelector(".temizle");
      if (t) t.addEventListener("click", e => { e.preventDefault(); durum.secs.clear(); setStateValue("secililer", []); ciz(); });
    }
    kok.querySelectorAll("th").forEach(th => {
      const i = +th.dataset.i; th.querySelector(".ok").textContent = durum.sk===i ? (durum.sy>0?"↑":"↓") : "";
    });
  };
  kok.querySelectorAll("th").forEach(th => th.addEventListener("click", () => {
    const i = +th.dataset.i;
    if (durum.sk===i) durum.sy = -durum.sy; else { durum.sk = i; durum.sy = K[i].tip ? -1 : 1; }
    ciz();
  }));
  const sec = kok.querySelector(".sirala");
  if (sec){
    sec.value = durum.sk===null ? "" : (durum.sk+":"+durum.sy);
    sec.addEventListener("change", e => {
      const v = e.target.value; if (!v){ durum.sk = null; } else { const [i,y] = v.split(":"); durum.sk = +i; durum.sy = +y; }
      ciz();
    });
  }
  const giris = kok.querySelector(".ara input");
  if (giris){ giris.value = durum.q; giris.addEventListener("input", e => { durum.q = e.target.value; ciz(); }); }
  if (D.secilebilir) govde.addEventListener("click", e => {
    const tr = e.target.closest("tr[data-i]"); if (!tr) return;
    const id = tr.dataset.id;
    if (coklu){                                       // çoklu: tıkla seç / bırak
      durum.secs.has(id) ? durum.secs.delete(id) : durum.secs.add(id); ciz();
      setStateValue("secililer", [...durum.secs]); return;
    }
    if (kalici){                                      // kalıcı tekli: aynı satıra tekrar tık = bırak
      durum.sec = (durum.sec === id) ? null : id; ciz();
      setStateValue("secili", durum.sec); return;
    }
    durum.sec = id; ciz();
    setStateValue("secili", durum.sec);
    setTriggerValue("tik", +tr.dataset.i);
  });
  kok.querySelector(".btn").addEventListener("click", () => {
    const hucreCsv = (r,j) => { const v=r.s[j]; const t = typeof v==="number" ? String(v).replace(".",",") : String(r.h[j]??"");
                                return /[;"\n]/.test(t) ? '"'+t.replace(/"/g,'""')+'"' : t; };
    const satir = r => K.map((_,j)=>hucreCsv(r,j)).join(";");
    const L = [K.map(k=>k.ad).join(";")].concat(gorunen.map(satir), D.toplam ? [satir(D.toplam)] : []);
    const b = new Blob(["\ufeff"+L.join("\r\n")], {type:"text/csv;charset=utf-8"});
    const a = document.createElement("a"); a.href = URL.createObjectURL(b); a.download = (D.dosya||"tablo")+".csv";
    document.body.appendChild(a); a.click(); a.remove(); setTimeout(()=>URL.revokeObjectURL(a.href), 2000);
  });
  ciz();
}
"""

_BILESEN = None
_CALISMA = {"isaret": None, "sayac": {}}


def _bilesen():
    global _BILESEN
    if _BILESEN is None:
        import streamlit.components.v2 as _v2          # yoksa ImportError → eski çizim
        _BILESEN = _v2.component("kayran_tablo", css=_CSS, js=_JS)
    return _BILESEN


def _oto_anahtar(veri):
    """Anahtarsız tablolar için kararlı anahtar: aynı tablo her çalıştırmada aynı
    anahtarı alır (arama/sıralama korunur); aynı çalıştırmada aynı içerik ikinci
    kez çizilirse sıra eki alır (DuplicateElementId olmaz)."""
    oz = json.dumps([[k["ad"] for k in veri["kolonlar"]], len(veri["satirlar"]),
                     veri["satirlar"][0]["h"] if veri["satirlar"] else None],
                    ensure_ascii=False, default=str)
    taban = "kt_" + hashlib.md5(oz.encode("utf-8")).hexdigest()[:12]
    try:
        from streamlit.runtime.scriptrunner_utils.script_run_context import get_script_run_ctx
        ctx = get_script_run_ctx()
        isaret = ctx.cursors if ctx is not None else None      # her çalıştırmada yeni sözlük
    except Exception:
        isaret = None
    if isaret is not _CALISMA["isaret"]:
        _CALISMA["isaret"], _CALISMA["sayac"] = isaret, {}
    n = _CALISMA["sayac"].get(taban, 0)
    _CALISMA["sayac"][taban] = n + 1
    return taban if n == 0 else f"{taban}_{n}"


def tablo(satirlar, *, key=None, secilebilir=False, kalici=False, coklu=False, pay=None, arama=None,
          birim="$", maks_yukseklik=520, kap=None, dosya_adi="tablo", toplam_isaret="Σ"):
    """Tabloyu çizer. Dönüş:
      secilebilir=True → tıklanan satırın sırası, yalnız tıklandığı çalıştırmada (pencere açmak için)
      kalici=True      → seçili satırın sırası ya da None; seçim sonraki çalıştırmalarda da durur
                          (altta açılan ayrıntı için). Aynı satıra tekrar tık = bırak.
      coklu=True       → seçili satırların sıraları (liste); satıra tıkla seç / bırak.
    kalici/coklu seçim satır KİMLİĞİNE (_id, yoksa sıra) bağlıdır; liste değişince seçim
    başka satıra kaymaz (secim_coz)."""
    if kalici or coklu:
        secilebilir = True
    import streamlit as st
    veri = tablo_veri(satirlar, birim=birim, pay=pay, toplam_isaret=toplam_isaret, arama=arama)
    hedef = kap if kap is not None else st
    if not veri["kolonlar"]:
        hedef.caption("Gösterilecek veri yok.")
        return None
    bil = _bilesen()
    anahtar = key or _oto_anahtar(veri)
    _onceki = st.session_state.get(anahtar, {}) or {}
    veri.update({"secilebilir": bool(secilebilir), "kalici": bool(kalici), "coklu": bool(coklu),
                 "maks": int(maks_yukseklik), "dosya": dosya_adi,
                 "secili": _onceki.get("secili") if secilebilir else None,
                 "secililer": list(_onceki.get("secililer") or []) if coklu else []})
    yuk = dict(key=anahtar, data=veri, default={"secili": None, "secililer": []}, height="content",
               on_tik_change=lambda: None, on_secili_change=lambda: None, on_secililer_change=lambda: None)
    if kap is not None:
        with kap:
            sonuc = bil(**yuk)
    else:
        sonuc = bil(**yuk)
    if not secilebilir:
        return None

    def _al(ad):
        try:
            return getattr(sonuc, ad)
        except Exception:
            return getattr(sonuc, "get", lambda *_: None)(ad)
    if coklu:
        return secim_coz(_al("secililer"), satirlar)
    if kalici:
        s = secim_coz(_al("secili"), satirlar)
        return s[0] if s else None
    return _al("tik")
