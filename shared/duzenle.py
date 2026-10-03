# -*- coding: utf-8 -*-
"""Düzenlenebilir sade tablo — st.data_editor'un yerine (Ekim 2026, TABLO_SADE).

Kullanıcının seçtiği "I" tasarımı (renklendirmesiz): ürün adının altında SKU, başlık bandı yok,
ferah satır, sayılar Türkçe ve sağa yaslı, birim maliyet soluk. Hücre içinde düzeltilir: sayı,
metin, onay kutusu, açılır seçim, tarih; dinamik tablolarda satır ekle / sil.

Ekranların kodu DEĞİŞMEZ: app.py'de st.data_editor buraya yönlendirilir (shared/izgara.kur).
Dönüş st.data_editor ile aynıdır — düzenlemeler uygulanmış DataFrame — ve oturum durumu da aynı
adları taşır: st.session_state[key] = {"edited_rows": {sıra: {sütun: değer}}, "added_rows": [...],
"deleted_rows": [sıra, ...]}. Desteklenmeyen bir ayar görülürse (bilinmeyen sütun türü, on_change
vb.) Streamlit'in kendi tablosu kullanılır (destekli_mi).

VERİ DEĞİŞİNCE düzenlemeler sıfırlanır (Streamlit de öyle yapıyor): sıra numarasına bağlı
düzenlemeler başka satıra kaymasın. Veri imzası tutulur; eski imzayla yapılmış durum yok sayılır.
Bileşen her kullanıcı işleminde TEK durum değeri gönderir (her gönderim ayrı yeniden çalıştırma
başlatıyor; iki gönderim arada yarım durum okutabilirdi).
"""
import datetime as _dt
import hashlib
import json
import re

AZAMI_SATIR = 3000          # daha uzun tablo Streamlit'in kendi tablosunda kalır
ARAMA_ESIK = 12
_DESTEKLI_TUR = {"text", "number", "checkbox", "selectbox", "date"}
_DESTEKLI_ARG = {"width", "height", "use_container_width", "hide_index", "column_order",
                 "column_config", "num_rows", "disabled", "key", "row_height", "placeholder"}
_URUN_AD = ("ürün", "urun", "ürün adı", "urun adi", "ürün adi", "model")


# ── Saf: hazırlık ───────────────────────────────────────────────────
def _bos(v):
    if v is None:
        return True
    try:
        import pandas as pd
        r = pd.isna(v)
        return bool(r) if isinstance(r, (bool,)) or getattr(r, "shape", None) == () else False
    except Exception:  # noqa: BLE001
        return False


def _ondalik(adim):
    try:
        s = f"{float(adim):.10f}".rstrip("0")
        return len(s.split(".")[1]) if "." in s else 0
    except (TypeError, ValueError):
        return None


def _cfg(v):
    if isinstance(v, str):
        return {"label": v}
    return dict(v) if isinstance(v, dict) else {}


def _tur(cfg, seri):
    import pandas as pd
    tc = cfg.get("type_config") or {}
    t = tc.get("type")
    if t:
        return t
    if pd.api.types.is_bool_dtype(seri):
        return "checkbox"
    if pd.api.types.is_numeric_dtype(seri):
        return "number"
    if pd.api.types.is_datetime64_any_dtype(seri):
        return "date"
    dolu = [x for x in seri.head(50) if not _bos(x)]
    if dolu and all(isinstance(x, _dt.date) for x in dolu):
        return "date"
    return "text"


def _bicim(cfg, ad, tur, seri):
    """JS'nin sayıyı nasıl yazacağı: {on, son, ond(sabit hane), en_cok(azami hane)}."""
    from shared.tasarim import _tablo_kolon_tipi
    tc = cfg.get("type_config") or {}
    fmt = tc.get("format")
    adim = tc.get("step")
    tip = _tablo_kolon_tipi(ad)
    b = {"on": "", "son": "", "ond": None, "en_cok": 4}
    if tur != "number":
        return b
    tam = False
    try:
        import pandas as pd
        tam = pd.api.types.is_integer_dtype(seri)
    except Exception:  # noqa: BLE001
        pass
    if fmt in ("dollar", "euro"):
        b.update(on="$" if fmt == "dollar" else "€", ond=2)
    elif isinstance(fmt, str) and "%" in fmt and fmt not in ("percent",):
        m = re.match(r"^(?P<on>[^%]*)%[,']?(?:\.(?P<d>\d+))?(?P<t>[dfi])(?P<son>.*)$", fmt.replace("%%", "\x00"))
        if m:
            b.update(on=m.group("on").replace("\x00", "%"), son=m.group("son").replace("\x00", "%"),
                     ond=0 if m.group("t") in "di" else int(m.group("d") or 6))
    elif fmt == "percent":
        b.update(son="", on="%", ond=1)
    if b["ond"] is None:
        if tip == "para":
            b["ond"] = 2
        elif adim is not None and _ondalik(adim) is not None:
            b["ond"] = min(_ondalik(adim), 4)
        elif tam:
            b["ond"] = 0
    return b


def _deger(v, tur):
    """Hücre değeri → JSON (ham)."""
    if _bos(v):
        return None
    if tur == "checkbox":
        return bool(v)
    if tur == "number":
        try:
            f = float(v)
            return int(f) if f.is_integer() and abs(f) < 2 ** 53 else f
        except (TypeError, ValueError):
            return None
    if tur == "date":
        try:
            return v.strftime("%Y-%m-%d")
        except Exception:  # noqa: BLE001
            return str(v)[:10]
    return str(v)


def imza(df, kolonlar):
    try:
        ham = df.astype(object).where(df.notna(), None).values.tolist()
    except Exception:  # noqa: BLE001
        ham = str(df)
    oz = json.dumps([[k["ad"] for k in kolonlar], [str(x) for x in df.index], ham],
                    ensure_ascii=False, default=str)
    return hashlib.md5(oz.encode("utf-8")).hexdigest()[:16]


def duzenle_veri(df, column_config=None, disabled=False, num_rows="fixed", hide_index=None,
                 column_order=None, height=None):
    """Bileşene giden JSON (SAF — test edilir). Desteklenmeyen sütun türünde None döner."""
    import pandas as pd
    cc = dict(column_config or {})
    gizli = {k for k, v in cc.items() if v is None}
    sira = [c for c in (column_order or list(df.columns)) if c in df.columns and c not in gizli]
    kolonlar = []
    for ad in sira:
        cfg = _cfg(cc.get(ad))
        seri = df[ad]
        tur = _tur(cfg, seri)
        if tur not in _DESTEKLI_TUR:
            return None
        tc = cfg.get("type_config") or {}
        kilit = (disabled is True) or (isinstance(disabled, (list, tuple, set)) and ad in disabled) \
            or bool(cfg.get("disabled"))
        kucuk = str(ad).strip().lower()
        kolonlar.append({
            "ad": str(ad), "etiket": str(cfg.get("label") or ad), "tur": tur, "kilit": bool(kilit),
            "ipucu": str(cfg.get("help") or ""), "genislik": cfg.get("width"),
            "hiza": "sag" if tur == "number" else ("orta" if tur == "checkbox" else "sol"),
            "bicim": _bicim(cfg, ad, tur, seri),
            "min": tc.get("min_value"), "max": tc.get("max_value"),
            "adim_ond": _ondalik(tc.get("step")) if tc.get("step") is not None else None,
            "tam": bool(pd.api.types.is_integer_dtype(seri)),
            "secenek": [str(x) for x in (tc.get("options") or [])],
            "zorunlu": bool(cfg.get("required")), "varsayilan": _deger(cfg.get("default"), tur),
            "azami": tc.get("max_chars"), "soluk": "maliyet" in kucuk and "toplam" not in kucuk,
        })
    goster_index = hide_index is False or (hide_index is None and not isinstance(df.index, pd.RangeIndex))
    satirlar = []
    for i in range(len(df)):
        satir = {"i": i, "v": [_deger(df.iloc[i][k["ad"]], k["tur"]) for k in kolonlar]}
        if goster_index:
            satir["x"] = str(df.index[i])
        satirlar.append(satir)
    # SKU ürün adının altında (ikisi de kilitliyse; düzenlenebilir SKU kendi sütununda kalır)
    adlar = [k["ad"].strip().lower() for k in kolonlar]
    birlesik = None
    if "sku" in adlar:
        u = next((j for j, a in enumerate(adlar) if a in _URUN_AD), None)
        s = adlar.index("sku")
        if u is not None and kolonlar[u]["kilit"] and kolonlar[s]["kilit"]:
            birlesik = {"ad": u, "sku": s}
    # Ekranların yüksekliği Streamlit'in 35 px satırına göre hesaplı; sade satır daha yüksek.
    # Tablo içeriği kadar açılır, en çok 640 px (ya da ekranın verdiği daha büyük değer).
    try:
        maks = max(640, int(height)) if height is not None and not isinstance(height, bool) else 640
    except (TypeError, ValueError):
        maks = 640
    return {"kolonlar": kolonlar, "satirlar": satirlar, "dinamik": num_rows in ("dynamic", "add", "delete"),
            "ekle": num_rows in ("dynamic", "add"), "sil": num_rows in ("dynamic", "delete"),
            "index": (str(df.index.name or "") if goster_index else None), "birlesik": birlesik,
            "arama": len(satirlar) >= ARAMA_ESIK, "maks": maks,
            "imza": imza(df, kolonlar)}


# ── Saf: düzenlemeleri uygula ───────────────────────────────────────
def _cevir(v, kolon, ornek_seri):
    import pandas as pd
    t = kolon["tur"]
    if v is None or (isinstance(v, str) and v == "" and t != "text"):
        if t == "checkbox":
            return False
        if t == "date" and pd.api.types.is_datetime64_any_dtype(ornek_seri):
            return pd.NaT
        return None
    if t == "checkbox":
        return bool(v)
    if t == "number":
        f = float(v)
        if kolon.get("adim_ond") is not None:
            f = round(f, kolon["adim_ond"])
        return int(f) if kolon.get("tam") and f.is_integer() else f
    if t == "date":
        if pd.api.types.is_datetime64_any_dtype(ornek_seri):
            return pd.Timestamp(str(v)[:10])
        dolu = [x for x in ornek_seri.head(50) if not _bos(x)]
        if dolu and isinstance(dolu[0], _dt.date):
            return _dt.date.fromisoformat(str(v)[:10])
        return str(v)[:10]
    return str(v)


def uygula(df, durum, kolonlar):
    """st.data_editor'un döndürdüğü gibi: düzenlenen hücreler, silinen satırlar, eklenen satırlar.
    Dokunulmayan hücreye dokunulmaz (kayıt yolları değişikliği str ile karşılaştırıyor)."""
    import pandas as pd
    durum = durum or {}
    ed = durum.get("edited_rows") or {}
    ek = durum.get("added_rows") or []
    sil = {int(x) for x in (durum.get("deleted_rows") or []) if str(x).lstrip("-").isdigit()}
    if not ed and not ek and not sil:
        return df
    kol = {k["ad"]: k for k in kolonlar}
    out = df.copy()
    for poz, degisen in ed.items():
        try:
            p = int(poz)
        except (TypeError, ValueError):
            continue
        if p < 0 or p >= len(out) or not isinstance(degisen, dict):
            continue
        for ad, v in degisen.items():
            if ad not in kol or kol[ad]["kilit"]:
                continue
            yeni = _cevir(v, kol[ad], out[ad])
            j = out.columns.get_loc(ad)
            try:
                out.iat[p, j] = yeni
            except (TypeError, ValueError):          # int sütuna ondalık → sütunu genişlet
                out[ad] = out[ad].astype(object)
                out.iat[p, j] = yeni
    if sil:
        out = out.iloc[[i for i in range(len(out)) if i not in sil]]
    if ek:
        yeni_satirlar = []
        for r in ek:
            if not isinstance(r, dict):
                continue
            satir = {}
            for c in out.columns:
                k = kol.get(c)
                v = r.get(c, k.get("varsayilan") if k else None)
                satir[c] = _cevir(v, k, df[c]) if k else v
            yeni_satirlar.append(satir)
        if yeni_satirlar:
            if isinstance(df.index, pd.RangeIndex):
                bas = (df.index.max() + 1) if len(df) else 0
                idx = range(bas, bas + len(yeni_satirlar))
            else:
                idx = [None] * len(yeni_satirlar)
            out = pd.concat([out, pd.DataFrame(yeni_satirlar, index=idx)], axis=0)
    return out


def destekli_mi(data, kw):
    """Bu çağrı sade tabloyla karşılanabilir mi? Şüphede Streamlit'in tablosu kalır."""
    try:
        import pandas as pd
        if not isinstance(data, pd.DataFrame) or len(data) > AZAMI_SATIR:
            return False
        if any(k not in _DESTEKLI_ARG for k in kw):
            return False
        if len(set(map(str, data.columns))) != len(data.columns):
            return False
        return duzenle_veri(data, kw.get("column_config"), kw.get("disabled", False), kw.get("num_rows", "fixed"),
                            kw.get("hide_index"), kw.get("column_order")) is not None
    except Exception:  # noqa: BLE001
        return False


# ── Bileşen ─────────────────────────────────────────────────────────
_CSS = r"""
:host{display:block}
.dz{position:relative;container-type:inline-size;font-size:14px;color:var(--k-metin);font-variant-numeric:tabular-nums}
.ust{display:flex;align-items:center;gap:10px;margin:0 0 8px}
.ust .ara{flex:1;max-width:320px;height:34px;box-sizing:border-box;padding:0 12px;border-radius:9px;border:1px solid var(--k-kenar2);
  background:var(--k-yuzey1);color:var(--k-metin);font:inherit;font-size:13px;outline:none}
.ust .ara:focus{border-color:var(--k-mor)}
.ust .bilgi{margin-left:auto;font-size:12px;color:var(--k-silik)}
.ust .bilgi b{color:var(--k-mor2);font-weight:600}
.kap{overflow:auto;border:1px solid var(--k-kenar);border-radius:14px;background:var(--k-yuzey1)}
table{width:100%;border-collapse:separate;border-spacing:0}
th{position:sticky;top:0;z-index:2;background:var(--k-yuzey1);color:var(--k-silik);font-weight:600;font-size:12px;
  text-align:left;padding:11px 14px;border-bottom:1px solid var(--k-kenar);white-space:nowrap;cursor:pointer;user-select:none}
th.sag{text-align:right} th.orta{text-align:center}
th .ok{color:var(--k-mor2);font-size:11px;margin:0 3px}
th .duz{display:inline-block;width:5px;height:5px;border-radius:50%;background:var(--k-mor);opacity:.7;margin:0 0 2px 6px;vertical-align:middle}
td{padding:7px 14px;border-bottom:1px solid var(--k-kenar);vertical-align:middle;white-space:nowrap}
td.sag{text-align:right} td.orta{text-align:center}
td.yazi{max-width:520px;overflow:hidden;text-overflow:ellipsis;padding-top:12px;padding-bottom:12px}
td.soluk{color:var(--k-soluk)}
td .alt{display:block;font-family:"JetBrains Mono",monospace;font-size:11.5px;color:var(--k-silik);margin-top:3px}
td.idx{color:var(--k-silik);font-size:12px}
tbody tr:last-child td{border-bottom:none}
tbody tr:hover td{background:var(--k-yuzey2)}
tr.silindi td{opacity:.35;text-decoration:line-through}
.neg{color:var(--k-kirmizi)}
.g{box-sizing:border-box;width:100%;min-width:72px;height:32px;padding:0 9px;border-radius:8px;border:1px solid transparent;
  background:color-mix(in srgb,var(--k-metin) 4%,transparent);color:var(--k-metin);font:inherit;font-size:14px;outline:none}
.g.sayi{text-align:right;font-variant-numeric:tabular-nums}
tr:hover .g{border-color:var(--k-kenar2)}
.g:focus{border-color:var(--k-mor) !important;box-shadow:0 0 0 3px color-mix(in srgb,var(--k-mor) 22%,transparent);background:var(--k-yuzey0)}
.g.hata{border-color:var(--k-kirmizi) !important}
td.degisti .g,td.degisti input[type=checkbox]{box-shadow:inset 3px 0 0 var(--k-mor)}
select.g{appearance:none;padding-right:26px;cursor:pointer;
  background-image:linear-gradient(45deg,transparent 50%,var(--k-soluk) 50%),linear-gradient(135deg,var(--k-soluk) 50%,transparent 50%);
  background-position:calc(100% - 13px) 14px,calc(100% - 9px) 14px;background-size:4px 4px;background-repeat:no-repeat}
select.g option{background:var(--k-yuzey2);color:var(--k-metin)}
input[type=date].g{color-scheme:dark}
input[type=checkbox]{width:18px;height:18px;accent-color:var(--k-mor);cursor:pointer;vertical-align:middle;border-radius:4px}
.sil-b{opacity:0;border:0;background:transparent;color:var(--k-silik);cursor:pointer;font-size:16px;padding:2px 6px;border-radius:6px}
tr:hover .sil-b{opacity:1}
.sil-b:hover{color:var(--k-kirmizi);background:color-mix(in srgb,var(--k-kirmizi) 12%,transparent)}
.alt-c{display:flex;align-items:center;gap:10px;margin-top:8px}
.ekle{height:32px;padding:0 14px;border-radius:9px;border:1px dashed var(--k-kenar2);background:transparent;color:var(--k-soluk);
  font:inherit;font-size:13px;cursor:pointer}
.ekle:hover{border-color:var(--k-mor);color:var(--k-metin)}
.bos{padding:18px;text-align:center;color:var(--k-silik)}
/* Telefonda (dar kap) her satır bir kart: başlıkta ürün, altında "etiket — kutu" satırları */
@container (max-width:560px){
  .kap{border:none;background:transparent;overflow:visible;max-height:none !important}
  thead{display:none}
  table,tbody,tr,td{display:block;width:auto}
  tbody tr{border:1px solid var(--k-kenar);border-radius:14px;background:var(--k-yuzey1);margin:0 0 10px;padding:6px 0}
  tbody tr:hover td{background:transparent}
  td{display:flex;justify-content:space-between;align-items:center;gap:12px;border:none !important;padding:5px 14px;
     white-space:normal;max-width:none;min-width:0 !important;text-align:right !important}
  td::before{content:attr(data-l);color:var(--k-silik);font-size:12.5px;text-align:left;flex:0 0 auto}
  td.bas{display:block;font-weight:600;font-size:14.5px;text-align:left !important;padding-top:8px}
  td.bas::before,td.silh::before{content:none}
  td.silh{justify-content:flex-end;padding-top:0}
  .g{width:58%;max-width:230px;flex:0 0 auto}
  .sil-b{opacity:1}
  td.yazi{padding-top:5px;padding-bottom:5px}
}
"""

_JS = r"""
export default function(component){
  const {data, setStateValue, parentElement} = component;
  const D = data || {}, K = D.kolonlar || [];
  let d = parentElement.__dz;
  if (!d || d.imza !== D.imza){
    const b = D.baslangic || {};
    d = parentElement.__dz = {imza: D.imza, ed: b.edited_rows || {}, ek: b.added_rows || [],
                              sil: new Set((b.deleted_rows || []).map(Number)), q: "", sk: null, sy: 1, kur: false};
  }
  if (d.kur && parentElement.querySelector(".dz")) return;      // aynı veri: DOM'a dokunma (odak kaybolmasın)
  d.kur = true;
  const es = s => String(s ?? "").replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;");
  const nf = {};
  const tr = (v, ond, en) => {
    const a = ond ?? 0, b = (ond ?? en ?? 4);
    const k = a + ":" + b;
    nf[k] = nf[k] || new Intl.NumberFormat("tr-TR", {minimumFractionDigits: a, maximumFractionDigits: b});
    return nf[k].format(v);
  };
  const yaz = (v, k) => {                          // ekranda görünen
    if (v === null || v === undefined || v === "") return "";
    if (k.tur === "number"){
      const b = k.bicim || {}, n = Number(v);
      if (!isFinite(n)) return String(v);
      const s = tr(Math.abs(n), b.ond, b.en_cok);
      return (n < 0 ? "-" : "") + (b.on || "") + s + (b.son || "");
    }
    if (k.tur === "date"){ const p = String(v).slice(0,10).split("-"); return p.length===3 ? p[2]+"."+p[1]+"."+p[0] : String(v); }
    return String(v);
  };
  const ham = v => (v === null || v === undefined) ? "" : String(v).replace(".", ",");
  const coz = (s, k) => {                          // girilen metin → sayı (TR: 1.234,56; 93,98; 93.98)
    let t = String(s).trim().replace(/[\s$€%₺]/g, "");
    if (t === "") return {v: null};
    if (t.includes(",") && t.includes(".")) t = t.replace(/\./g, "").replace(",", ".");
    else if (t.includes(",")) t = t.replace(",", ".");
    else if ((t.match(/\./g) || []).length > 1) t = t.replace(/\./g, "");
    let n = Number(t);
    if (!isFinite(n)) return {hata: true};
    if (k.adim_ond !== null && k.adim_ond !== undefined) n = Number(n.toFixed(k.adim_ond));
    if (k.min !== null && k.min !== undefined && n < k.min) return {hata: true};
    if (k.max !== null && k.max !== undefined && n > k.max) return {hata: true};
    return {v: n};
  };
  const BIR = D.birlesik;
  const gorunur = K.map((k,j) => !(BIR && j === BIR.sku));
  const ILK = (D.index !== null && D.index !== undefined) ? -1 : gorunur.indexOf(true);   // kartta başlık olan sütun
  const genis = k => k.genislik === "small" ? 80 : k.genislik === "medium" ? 130 : k.genislik === "large" ? 260 :
                     (typeof k.genislik === "number" ? k.genislik : null);
  // değer: düzenlenmişse düzenleme, yoksa özgün
  const deger = (r, j) => {
    if (r.ek !== undefined) return d.ek[r.ek]?.[K[j].ad] ?? null;
    const e = d.ed[String(r.i)];
    return (e && Object.prototype.hasOwnProperty.call(e, K[j].ad)) ? e[K[j].ad] : r.v[j];
  };
  const degisti = (r, j) => r.ek === undefined && !!(d.ed[String(r.i)] && Object.prototype.hasOwnProperty.call(d.ed[String(r.i)], K[j].ad));
  const hucre = (r, j) => {
    const k = K[j], v = deger(r, j);
    const cls = [k.hiza, degisti(r,j) ? "degisti" : "", j === ILK ? "bas" : ""];
    const dl = ' data-l="'+es(k.etiket)+'"';
    const w = genis(k) || (k.kilit ? null : (k.tur === "text" ? 150 : k.tur === "selectbox" ? 130 : k.tur === "date" ? 140 : k.tur === "number" ? 96 : null));
    const st = w ? ' style="min-width:'+w+'px"' : "";
    if (k.kilit){
      cls.push(k.tur === "text" ? "yazi" : "", k.soluk ? "soluk" : "", (k.tur==="number" && Number(v) < 0) ? "neg" : "");
      let ic = k.tur === "checkbox" ? '<input type="checkbox" disabled'+(v?" checked":"")+'>' : es(yaz(v, k));
      if (BIR && j === BIR.ad){ const s = deger(r, BIR.sku); if (s) ic += '<span class="alt">'+es(s)+'</span>'; }
      const ip = (k.tur === "text" && String(v ?? "").length > 40) ? ' title="'+es(v)+'"' : "";
      return '<td class="'+cls.join(" ").trim()+'"'+st+ip+dl+'>'+ic+'</td>';
    }
    const at = 'data-j="'+j+'"';
    let ic;
    if (k.tur === "checkbox") ic = '<input type="checkbox" '+at+(v?" checked":"")+'>';
    else if (k.tur === "selectbox"){
      const se = [...k.secenek]; if (v !== null && v !== undefined && v !== "" && !se.includes(String(v))) se.unshift(String(v));
      const bos_ = v === null || v === undefined || v === "";
      ic = '<select class="g" '+at+'>'+((k.zorunlu && !bos_) ? "" : '<option value=""'+(bos_?" selected":"")+(k.zorunlu?" disabled":"")+'>'+(k.zorunlu?"Seç…":"")+'</option>')+
           se.map(o => '<option'+(String(v)===o?" selected":"")+'>'+es(o)+'</option>').join("")+'</select>';
    }
    else if (k.tur === "date") ic = '<input class="g" type="date" '+at+' value="'+es(v ? String(v).slice(0,10) : "")+'">';
    else if (k.tur === "number") ic = '<input class="g sayi" inputmode="decimal" autocomplete="off" '+at+' value="'+es(yaz(v,k))+'">';
    else ic = '<input class="g" type="text" autocomplete="off" '+at+(k.azami ? ' maxlength="'+k.azami+'"' : "")+' value="'+es(v ?? "")+'">';
    return '<td class="'+cls.join(" ").trim()+'"'+st+dl+'>'+ic+'</td>';
  };
  let kok = parentElement.querySelector(".dz");
  if (!kok){ kok = document.createElement("div"); kok.className = "dz"; parentElement.appendChild(kok); }
  const bas = (D.index !== null && D.index !== undefined ? '<th>'+es(D.index)+'</th>' : "") +
    K.map((k,j) => gorunur[j] ? '<th data-j="'+j+'" class="'+k.hiza+'"'+(k.ipucu?' title="'+es(k.ipucu)+'"':"")+'>'+
      (k.hiza==="sag" ? '<span class="ok"></span>' : "")+es(k.etiket)+(k.kilit ? "" : '<span class="duz" title="Düzenlenebilir"></span>')+
      (k.hiza!=="sag" ? '<span class="ok"></span>' : "")+'</th>' : "").join("") + (D.sil ? '<th style="width:34px"></th>' : "");
  kok.innerHTML =
    (D.arama ? '<div class="ust"><input class="ara" type="search" placeholder="Ara…" aria-label="Tabloda ara"><span class="bilgi"></span></div>' : "") +
    '<div class="kap" style="max-height:'+(D.maks||560)+'px"><table><thead><tr>'+bas+'</tr></thead><tbody></tbody></table></div>' +
    (D.ekle ? '<div class="alt-c"><button class="ekle" type="button">+ Satır ekle</button></div>' : "");
  const govde = kok.querySelector("tbody");
  const bilgi = kok.querySelector(".bilgi");
  const satirlar = () => {
    let R = (D.satirlar || []).filter(r => !d.sil.has(r.i));
    const q = d.q.toLocaleLowerCase("tr");
    if (q) R = R.filter(r => K.some((k,j) => String(yaz(deger(r,j), k)).toLocaleLowerCase("tr").includes(q)));
    if (d.sk !== null){
      const j = d.sk;
      R = [...R].sort((a,b) => { const x = deger(a,j), z = deger(b,j);
        const s = (typeof x === "number" && typeof z === "number") ? x - z : String(x ?? "").localeCompare(String(z ?? ""), "tr");
        return s * d.sy; });
    }
    return R.concat(d.ek.map((_, n) => ({ek: n})));
  };
  const ciz = () => {
    const R = satirlar();
    govde.innerHTML = R.length ? R.map(r =>
      '<tr data-i="'+(r.ek === undefined ? r.i : "")+'" data-ek="'+(r.ek ?? "")+'">' +
      (D.index !== null && D.index !== undefined ? '<td class="idx bas">'+es(r.x ?? "")+'</td>' : "") +
      K.map((_,j) => gorunur[j] ? hucre(r,j) : "").join("") +
      (D.sil ? '<td class="silh"><button class="sil-b" type="button" title="Satırı sil" aria-label="Satırı sil">&#215;</button></td>' : "") +
      '</tr>').join("") : '<tr><td class="bos" colspan="99">Satır yok</td></tr>';
    if (bilgi){
      const n = Object.values(d.ed).reduce((t,e) => t + Object.keys(e||{}).length, 0);
      bilgi.innerHTML = (n ? '<b>'+n+' hücre değişti</b> · ' : "") + R.length + " satır";
    }
    kok.querySelectorAll("th[data-j]").forEach(th => { const j = +th.dataset.j;
      th.querySelector(".ok").textContent = d.sk === j ? (d.sy > 0 ? "↑" : "↓") : ""; });
  };
  const kaydet = (tr_, j, v) => {
    const k = K[j];
    if (tr_.dataset.ek !== ""){ const n = +tr_.dataset.ek; d.ek[n] = {...d.ek[n], [k.ad]: v}; setStateValue("added_rows", d.ek); return; }
    const i = tr_.dataset.i, r = (D.satirlar || [])[+i], e = {...(d.ed[i] || {})};
    const ozgun = r ? r.v[j] : undefined;
    if ((v ?? null) === (ozgun ?? null)) delete e[k.ad]; else e[k.ad] = v;
    if (Object.keys(e).length) d.ed[i] = e; else delete d.ed[i];
    setStateValue("edited_rows", d.ed);
  };
  govde.addEventListener("focusin", e => {
    const t = e.target; if (!t.matches || !t.matches("input.sayi")) return;
    const tr_ = t.closest("tr"), j = +t.dataset.j;
    const v = tr_.dataset.ek !== "" ? d.ek[+tr_.dataset.ek]?.[K[j].ad] : deger((D.satirlar||[])[+tr_.dataset.i], j);
    t.value = ham(v); t.select();
  });
  govde.addEventListener("focusout", e => {
    const t = e.target; if (!t.matches || !t.matches("input.sayi")) return;
    const tr_ = t.closest("tr"), j = +t.dataset.j;
    const v = tr_.dataset.ek !== "" ? d.ek[+tr_.dataset.ek]?.[K[j].ad] : deger((D.satirlar||[])[+tr_.dataset.i], j);
    if (!t.classList.contains("hata")) t.value = yaz(v, K[j]);
  });
  govde.addEventListener("change", e => {
    const t = e.target, j = +t.dataset.j; if (isNaN(j)) return;
    const k = K[j], tr_ = t.closest("tr");
    let v;
    if (t.type === "checkbox") v = t.checked;
    else if (k.tur === "number"){
      const c = coz(t.value, k);
      if (c.hata || (c.v === null && k.zorunlu)){ t.classList.add("hata"); t.title = "Geçersiz sayı"; return; }
      t.classList.remove("hata"); t.title = ""; v = c.v;
    }
    else if (k.tur === "date") v = t.value || null;
    else { v = t.value; if (k.tur === "selectbox" && v === "") v = null; }
    kaydet(tr_, j, v);
    const td = t.closest("td"); if (td && tr_.dataset.ek === "") td.classList.toggle("degisti", degisti((D.satirlar||[])[+tr_.dataset.i], j));
    if (bilgi){ const n = Object.values(d.ed).reduce((s,x) => s + Object.keys(x||{}).length, 0);
      bilgi.innerHTML = (n ? '<b>'+n+' hücre değişti</b> · ' : "") + govde.querySelectorAll("tr[data-i]").length + " satır"; }
  });
  govde.addEventListener("keydown", e => {        // Enter: alttaki satırın aynı hücresi
    if (e.key !== "Enter" || !e.target.matches("input.g")) return;
    e.preventDefault(); e.target.blur();
    const tr_ = e.target.closest("tr"), j = e.target.dataset.j;
    const alt = tr_.nextElementSibling && tr_.nextElementSibling.querySelector('[data-j="'+j+'"]');
    if (alt) alt.focus();
  });
  govde.addEventListener("click", e => {
    const b = e.target.closest(".sil-b"); if (!b) return;
    const tr_ = b.closest("tr");
    if (tr_.dataset.ek !== ""){ d.ek.splice(+tr_.dataset.ek, 1); setStateValue("added_rows", d.ek); }
    else { d.sil.add(+tr_.dataset.i); setStateValue("deleted_rows", [...d.sil]); }
    ciz();
  });
  const ekle = kok.querySelector(".ekle");
  if (ekle) ekle.addEventListener("click", () => {
    const yeni = {}; K.forEach(k => { yeni[k.ad] = k.varsayilan ?? (k.tur === "checkbox" ? false : null); });
    d.ek.push(yeni); setStateValue("added_rows", d.ek); ciz();
    const son = govde.querySelector("tr:last-child .g"); if (son) son.focus();
  });
  kok.querySelectorAll("th[data-j]").forEach(th => th.addEventListener("click", () => {
    const j = +th.dataset.j;
    if (d.sk === j) d.sy = -d.sy; else { d.sk = j; d.sy = K[j].tur === "number" ? -1 : 1; }
    ciz();
  }));
  const ara = kok.querySelector(".ara");
  if (ara){ ara.value = d.q; ara.addEventListener("input", e => { d.q = e.target.value; ciz(); }); }
  ciz();
}
"""

_BILESEN = None


def _bilesen():
    global _BILESEN
    if _BILESEN is None:
        import streamlit.components.v2 as _v2
        _BILESEN = _v2.component("kayran_duzenle", css=_CSS, js=_JS)
    return _BILESEN


_DURUM = ("edited_rows", "added_rows", "deleted_rows")


def _js(v):
    return json.dumps(v, sort_keys=True, default=str)


def gecerli_durum(onceki, bayat):
    """Veri değiştikten sonra bileşende kalan ESKİ durumu ayıklar (SAF — test edilir).
    onceki: oturumdaki durum; bayat: veri değiştiği anda kaydedilen {ad: json}. Bir tür değişiklik
    (ör. düzeltilen hücreler) yeni bir kullanıcı işlemiyle değişene dek eski kabul edilir."""
    out = {}
    for ad in _DURUM:
        v = (onceki or {}).get(ad)
        if v is None or (bayat and bayat.get(ad) == _js(v)):
            continue
        out[ad] = v
    return out


def _oturum_durumu(anahtar):
    import streamlit as st
    ham = st.session_state.get(anahtar) if anahtar in st.session_state else None
    out = {}
    for ad in _DURUM:
        try:
            out[ad] = ham.get(ad) if ham is not None else None
        except Exception:  # noqa: BLE001
            out[ad] = None
    return out


def duzenle(data, *, key=None, column_config=None, disabled=False, num_rows="fixed", hide_index=None,
            column_order=None, height=None, kap=None, **_):
    """st.data_editor gibi çizer; düzenlemeler uygulanmış DataFrame döner."""
    import streamlit as st
    veri = duzenle_veri(data, column_config, disabled, num_rows, hide_index, column_order, height)
    anahtar = key or ("dz_" + veri["imza"])
    imza_k, bayat_k = f"_dz_imza_{anahtar}", f"_dz_bayat_{anahtar}"
    onceki = _oturum_durumu(anahtar)
    if st.session_state.get(imza_k) not in (None, veri["imza"]):
        # Veri değişti: o ana kadarki durum eski sıra numaralarına göre — geçersiz
        st.session_state[bayat_k] = {ad: _js(onceki.get(ad)) for ad in _DURUM if onceki.get(ad) is not None}
    st.session_state[imza_k] = veri["imza"]
    veri["baslangic"] = gecerli_durum(onceki, st.session_state.get(bayat_k))
    yuk = dict(key=anahtar, data=veri, height="content",
               default={"edited_rows": {}, "added_rows": [], "deleted_rows": []},
               on_edited_rows_change=lambda: None, on_added_rows_change=lambda: None,
               on_deleted_rows_change=lambda: None)
    bil = _bilesen()
    if kap is not None:
        with kap:
            bil(**yuk)
    else:
        bil(**yuk)
    durum = gecerli_durum(_oturum_durumu(anahtar), st.session_state.get(bayat_k))
    return uygula(data, durum, veri["kolonlar"])
