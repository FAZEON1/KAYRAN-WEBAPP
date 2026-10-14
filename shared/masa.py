# -*- coding: utf-8 -*-
"""ORTAK LİSTE MASASI (Ekim 2026, tüm program yeni tasarım — kullanıcı kararı B).

Kalıp, Muhasebe › Bu hafta ödeme masasından genelleştirildi (prototip
https://claude.ai/artifact/QeMhUiHWNK1sYnAtsRjkzW): özet bandı → çipli süzgeç + arama → tablo (gruplu,
sıralanır) → satıra tıkla: sağda detay paneli (liste görünür kalır) → işaretle: alttaki toplu çubuk →
işlemden sonra bildirim (gerekirse "Geri al"). Klavye: j/k gez · x seç · Enter aç · Esc kapat · / ara.
Telefonda satırlar karta döner, panel tam ekran açılır.

Streamlit components v2 (iframe yok, derleme yok; shared/tablo.py ile aynı altyapı). Bileşen YALNIZ İSTEK
gönderir: {"islem": "ode", "ids": [12], "degerler": {"banka": 3}}. istek_al() her değeri tanıma göre
doğrular (kimlik listede mi, satır işlemin koşuluna uyuyor mu, alan türü/seçenek/zorunluluk); anlamsal
kontrol ve yürütme sayfanın kendi modülünde, bugünkü veritabanı fonksiyonlarıyla.

TANIM (masa(veri) — hepsi Python'da hazırlanır, metinler biçimlenmiş gelir):
  ozet        [{k, et, dg, al, renk, suz?, oran?, ipucu?}]   suz: tıklanınca seçilen görünüm
  gorunumler  [{k, ad, f}]                                     ilki varsayılan; f = koşul (aşağıda)
  secimler    [{alan, ad (hepsi metni), secenekler: [{k, ad}]}] açılır çip (kategori, firma…); satırdaki alan liste ise içeren eşleşir
  anahtarlar  [{k, ad, f}]                                      aç/kapa çip (Yalnız TL…)
  ara         {alanlar: [...], ipucu}
  sutunlar    [{alan, ad, tip, gen, sag?, alt?, alt_renk?, sirala?, dar?}]
                tip: ana (kalın + alt satır) · metin · etiket · durum · sayi
                dar (telefon kartı): ana · sag · alt · durum · gizle
                sıralama anahtarı: satır[alan + "__s"] varsa o, yoksa satır[alan]
  grup        {alan, toplamlar: [{alan, on}]}                  varsayılan sırada grup başlığı
  satirlar    [{id, …, _durum: {ad, renk}, _baslik, _alt, _buyuk, _buyuk_alt, _detay: [[et, deger]], _not}]
  islemler    [{k, ad, dugme, alanlar, f?, birincil?, tehlike?, hizli?, toplu?, okuma?, ipucu?}]
                alanlar: [{ad, et, tip: sayi|metin|tarih|secim|onay|gizli, secenekler?, varsayilan?,
                           varsayilan_alan?, zorunlu?, en_cok_alan?, tam?, gizle_sifir?}]
                hizli: [{ad, degerler}]  — tek tıkla gönderilen hazır değerler (+7 gün)
                toplu: {ad, alanlar: [ad…], degerler?} — çoklu seçimde alttaki çubukta
                okuma: True — salt-okur oturumda da çalışır (ör. ayrıntıyı aç)
                coklu: True — çubukta görünmez ama birden çok kimlik kabul eder (bildirimdeki Geri al)
                yalniz_toplu: True — yan panelde gösterilmez, yalnız alttaki toplu çubukta
  tik         "panel" (varsayılan) ya da işlem anahtarı — satıra tıklayınca o işlem doğrudan gönderilir
  bos         {liste, suzgec}  · bildirim {n, ok, mesaj, geri?: {islem, ids}} · salt · baslik_ipucu
  baslangic   {gor, q, sec, ana, sira} — ilk açılış durumu (verilmezse son kullanılan durum geri gelir)
GÖRÜNÜM DURUMU: görünüm, arama, süzgeç ve sıralama bileşenin "durum" değerinde tutulur; ayrıntı sayfasına
gidip dönünce (bileşen yeniden kurulunca) aynen geri gelir.
KOŞUL f: [[alan, op, değer], …] (VE) — op: eq ne in nin gt lt var yok
"""
import json
from datetime import date

ISLEM_ALAN_TURLERI = ("sayi", "metin", "tarih", "secim", "onay", "gizli")


# ── Koşul (Python ve JS aynı kural) ─────────────────────────────────
def kosul_uyar(satir, f):
    for alan, op, d in f or []:
        v = (satir or {}).get(alan)
        if op == "eq" and not v == d:
            return False
        if op == "ne" and v == d:
            return False
        if op == "in" and v not in (d or []):
            return False
        if op == "nin" and v in (d or []):
            return False
        if op == "gt" and not (_sayi(v) is not None and _sayi(d) is not None and _sayi(v) > _sayi(d)):
            return False
        if op == "lt" and not (_sayi(v) is not None and _sayi(d) is not None and _sayi(v) < _sayi(d)):
            return False
        if op == "var" and not v:
            return False
        if op == "yok" and v:
            return False
    return True


def _sayi(v):
    if isinstance(v, bool):
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if f == f and abs(f) != float("inf") else None


# ── İsteğin genel doğrulanması (saf) ────────────────────────────────
def istek_al(veri, istek):
    """Bileşenden gelen isteği tanıma göre doğrular.
    Döner: ({"islem", "ids", "degerler", "satirlar"}, None) ya da (None, kullanıcıya hata metni).
    Anlamsal kontrol (tutar kalanı aşıyor mu, banka hesapta mı…) sayfanın işi; burada tür ve kapsam."""
    istek = istek if isinstance(istek, dict) else {}
    islemler = {i.get("k"): i for i in veri.get("islemler") or []}
    tanim = islemler.get(istek.get("islem"))
    if not tanim:
        return None, "Bilinmeyen işlem."
    if veri.get("salt") and not tanim.get("okuma"):
        return None, "Salt-okur oturum: işlem yapılamaz."
    ham = istek.get("ids") if isinstance(istek.get("ids"), list) else []
    if not ham:
        return None, "Kayıt seçilmedi."
    sozluk = {s.get("id"): s for s in veri.get("satirlar") or []}
    ids = []
    for i in ham:
        if isinstance(i, bool) or i not in sozluk:
            return None, "Kayıt bulunamadı; sayfayı yenileyip tekrar deneyin."
        if i not in ids:
            ids.append(i)
    if len(ids) > 1 and not (tanim.get("toplu") or tanim.get("coklu")):
        return None, "Bu işlem tek kayıtla yapılır."
    satirlar = [sozluk[i] for i in ids]
    if not all(kosul_uyar(s, tanim.get("f")) for s in satirlar):
        return None, "Seçilenlerden biri bu işleme uygun değil (durumu değişmiş olabilir)."
    gelen = istek.get("degerler") if isinstance(istek.get("degerler"), dict) else {}
    degerler = {}
    for a in tanim.get("alanlar") or []:
        ad, tip = a.get("ad"), a.get("tip")
        if ad not in gelen or gelen.get(ad) in (None, ""):
            if a.get("zorunlu"):
                return None, f"{a.get('et') or ad} gerekli."
            continue
        v = gelen.get(ad)
        if tip in ("sayi", "gizli") and a.get("sayi", tip == "sayi"):
            f = _sayi(v)
            if f is None or f < a.get("en_az", 0):
                return None, f"{a.get('et') or ad}: geçerli bir sayı girin."
            if "en_cok" in a and f > a["en_cok"]:
                return None, f"{a.get('et') or ad}: en çok {a['en_cok']}."
            if a.get("en_cok_alan") and len(satirlar) == 1 and f > (_sayi(satirlar[0].get(a["en_cok_alan"])) or 0) + 1e-9:
                return None, f"{a.get('et') or ad}: kayıttaki tutarı aşamaz."
            degerler[ad] = f
        elif tip == "tarih":
            try:
                degerler[ad] = date.fromisoformat(str(v)[:10]) if len(str(v)) == 10 else None
            except ValueError:
                degerler[ad] = None
            if degerler[ad] is None:
                return None, f"{a.get('et') or ad}: geçerli bir tarih seçin."
        elif tip == "secim":
            gecerli = {str(s.get("k")): s.get("k") for s in a.get("secenekler") or []}
            if str(v) not in gecerli:
                return None, f"{a.get('et') or ad}: listeden seçin."
            degerler[ad] = gecerli[str(v)]
        elif tip == "onay":
            if v is False and not a.get("zorunlu"):
                continue
            if v is not True:
                return None, f"{a.get('et') or ad}: onay kutusunu işaretleyin."
            degerler[ad] = True
        else:
            degerler[ad] = str(v).strip()[: int(a.get("en_uzun", 500))]
    return {"islem": tanim["k"], "ids": ids, "degerler": degerler, "satirlar": satirlar}, None


# ── Bileşen ─────────────────────────────────────────────────────────
_CSS = r"""
.ms{color:var(--k-metin);font-size:13.5px;line-height:1.45;font-variant-numeric:tabular-nums}
.ms *{box-sizing:border-box}
.ms button,.ms input,.ms select{font:inherit;color:inherit}
.ms button{cursor:pointer}
.ms :focus-visible{outline:2px solid var(--k-mor);outline-offset:2px}
.ms .govde{display:grid;grid-template-columns:minmax(0,1fr);gap:16px;align-items:start}
.ms.detayli .govde{grid-template-columns:minmax(0,1fr) 380px}
.ms .ozet{display:grid;grid-template-columns:repeat(var(--n,4),minmax(0,1fr));background:var(--k-yuzey1);border:1px solid var(--k-kenar);
  border-radius:12px;margin-bottom:14px;overflow:hidden}
.ms .ozet>*{all:unset;box-sizing:border-box;padding:13px 16px;border-right:1px solid var(--k-kenar);display:flex;flex-direction:column;gap:2px;min-width:0}
.ms .ozet>*:last-child{border-right:0}
.ms .ozet button{cursor:pointer}.ms .ozet button:hover{background:var(--k-ortu2)}
.ms .ozet button[aria-pressed="true"]{box-shadow:inset 0 -2px 0 var(--k-mor)}
.ms .ozet .et{font-size:12px;color:var(--k-soluk);display:flex;align-items:center;gap:6px}
.ms .ozet .dg{font-size:21px;font-weight:650;letter-spacing:-.4px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.ms .ozet .al{font-size:12px;color:var(--k-silik);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.ms .nk{width:7px;height:7px;border-radius:50%;background:currentColor;display:inline-block;flex-shrink:0}
.ms .r-kirmizi{color:var(--k-kirmizi)}.ms .r-amber{color:var(--k-amber)}.ms .r-yesil{color:var(--k-yesil)}
.ms .r-silik{color:var(--k-silik)}.ms .r-mor{color:var(--k-mor2)}.ms .r-cyan{color:var(--k-cyan)}.ms .r-soluk{color:var(--k-soluk)}
.ms .ilr{height:4px;border-radius:2px;background:var(--k-kenar2);overflow:hidden;margin-top:6px}
.ms .ilr i{display:block;height:100%;background:var(--k-yesil)}
.ms .suz{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-bottom:10px}
.ms .cip{border:1px solid var(--k-kenar2);background:transparent;border-radius:999px;padding:4px 12px;font-size:12.5px;color:var(--k-soluk);
  display:inline-flex;gap:6px;align-items:center;white-space:nowrap;max-width:240px}
.ms .cip:hover{color:var(--k-metin)}
.ms .cip[aria-pressed="true"],.ms select.cip.dolu{background:var(--k-vurgu);border-color:color-mix(in srgb,var(--k-mor) 55%,transparent);color:var(--k-mor2);font-weight:600}
.ms .cip .s{font-size:11px;opacity:.8}
.ms .ayr{width:1px;height:20px;background:var(--k-kenar2);margin:0 2px}
.ms select.cip{appearance:none;-webkit-appearance:none;background:transparent;text-overflow:ellipsis}
.ms select option{color:var(--k-metin);background:var(--k-yuzey1)}
.ms .kutu{display:flex;align-items:center;gap:8px;border:1px solid var(--k-kenar2);background:var(--k-yuzey1);border-radius:8px;
  padding:5px 10px;margin-left:auto;min-width:220px;flex:0 1 320px}
.ms .kutu input{border:0;background:transparent;outline:0;width:100%;font-size:13px}
.ms .tablo{border:1px solid var(--k-kenar);border-radius:12px;background:var(--k-yuzey1);overflow:hidden}
.ms .sat{display:grid;grid-template-columns:var(--kol);align-items:center;border-bottom:1px solid var(--k-kenar);min-height:46px}
.ms.detayli .sat{grid-template-columns:var(--kol-dar)}
.ms.detayli .k-dar-gizle{display:none}
.ms .sat>*{padding:0 10px;min-width:0}
.ms .sag{text-align:right}
.ms .bsat{background:var(--k-yuzey2);min-height:36px;font-size:12px;color:var(--k-soluk);font-weight:500}
.ms .bsat button{all:unset;cursor:pointer;display:inline-flex;gap:4px;align-items:center}
.ms .bsat button:hover{color:var(--k-metin)}
.ms .bsat .sag button{justify-content:flex-end;width:100%}
.ms .gun{display:flex;align-items:center;gap:10px;padding:12px 14px 6px;font-size:12.5px;color:var(--k-soluk);border-bottom:1px solid var(--k-kenar);flex-wrap:wrap;row-gap:2px}
.ms .gun b{color:var(--k-metin);font-weight:600;font-size:13px}
.ms .gun .t{margin-left:auto}
.ms .satir{cursor:pointer}
.ms .satir:hover{background:var(--k-ortu2)}
.ms .satir.secili{background:var(--k-vurgu)}
.ms .satir.odak{box-shadow:inset 3px 0 0 var(--k-mor)}
.ms .satir.acik{background:var(--k-yuzey2)}
.ms .satir.soluk{opacity:.55}
.ms .ana b{display:block;font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.ms .ana small,.ms .hc small{display:block;font-size:12px;color:var(--k-silik);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.ms .hc{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.ms .etk{display:inline-block;font-size:11.5px;padding:2px 8px;border-radius:6px;background:var(--k-yuzey2);color:var(--k-soluk);
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:100%;vertical-align:middle}
.ms .drm{display:inline-flex;align-items:center;gap:6px;font-size:12px;font-weight:500;white-space:nowrap}
.ms .onay{width:16px;height:16px;border-radius:4px;border:1.5px solid var(--k-kenar2);display:grid;place-items:center;background:transparent;padding:0}
.ms .onay[aria-checked="true"],.ms .onay[aria-checked="mixed"]{background:var(--k-dolgu);border-color:var(--k-dolgu)}
.ms .onay[aria-checked="true"]::after{content:"";width:8px;height:4px;border-left:2px solid #fff;border-bottom:2px solid #fff;transform:rotate(-45deg) translate(1px,-1px)}
.ms .onay[aria-checked="mixed"]::after{content:"";width:8px;height:2px;background:#fff}
.ms .onay:disabled{opacity:.3;cursor:default}
.ms .bos{padding:40px 20px;text-align:center;color:var(--k-soluk)}
.ms .daha{display:block;width:100%;border:0;border-top:1px solid var(--k-kenar);background:transparent;padding:10px;color:var(--k-mor2);font-weight:600}
.ms .kisa{display:flex;gap:14px;flex-wrap:wrap;color:var(--k-silik);font-size:12px;margin-top:10px}
.ms kbd{font-family:var(--k-mono,monospace);font-size:11px;border:1px solid var(--k-kenar2);border-radius:4px;padding:0 5px;color:var(--k-soluk)}
.ms .panel{position:sticky;top:8px;border:1px solid var(--k-kenar);border-radius:12px;background:var(--k-yuzey1);
  max-height:calc(100vh - 24px);overflow:auto;display:flex;flex-direction:column}
.ms .pbas{display:flex;align-items:flex-start;gap:10px;padding:16px 18px 12px;border-bottom:1px solid var(--k-kenar)}
.ms .pbas h3{font-size:16px;margin:0;font-weight:650;line-height:1.3;word-break:break-word}
.ms .pbas p{margin:2px 0 0;color:var(--k-soluk);font-size:12.5px}
.ms .kapat{margin-left:auto;border:0;background:transparent;color:var(--k-silik);border-radius:6px;padding:2px 6px;font-size:18px;line-height:1}
.ms .kapat:hover{color:var(--k-metin);background:var(--k-ortu2)}
.ms .pgov{padding:14px 18px 18px;display:flex;flex-direction:column;gap:16px}
.ms .buyuk{font-size:24px;font-weight:650;letter-spacing:-.5px;word-break:break-word}
.ms .buyuk small{font-size:13px;color:var(--k-soluk);font-weight:500;margin-left:6px}
.ms dl{display:grid;grid-template-columns:minmax(80px,max-content) 1fr;gap:6px 12px;font-size:13px;margin:0}
.ms dt{color:var(--k-silik)}.ms dd{margin:0;min-width:0;word-break:break-word}
.ms .sekmeler{display:flex;gap:2px;background:var(--k-yuzey2);border-radius:8px;padding:2px;flex-wrap:wrap}
.ms .sekmeler button{flex:1;border:0;background:transparent;border-radius:6px;padding:6px 8px;font-size:12.5px;color:var(--k-soluk);font-weight:500}
.ms .sekmeler button[aria-pressed="true"]{background:var(--k-yuzey1);color:var(--k-metin);box-shadow:var(--k-golge)}
.ms .form{display:grid;grid-template-columns:1fr 1fr;gap:10px}
.ms .form label{display:flex;flex-direction:column;gap:4px;font-size:12px;color:var(--k-soluk)}
.ms .form .tam{grid-column:1/-1}
.ms .form input,.ms .form select{border:1px solid var(--k-kenar2);background:var(--k-yuzey0);border-radius:8px;padding:7px 10px;font-size:13px;width:100%}
.ms .form label.kutucuk{flex-direction:row;align-items:center;gap:8px;color:var(--k-metin)}
.ms .form label.kutucuk input{width:auto}
.ms .ipucu{font-size:12px;color:var(--k-silik)}
.ms .hata{font-size:12.5px;color:var(--k-kirmizi)}
.ms .eylem{display:flex;gap:8px;flex-wrap:wrap}
.ms .dug{display:inline-flex;align-items:center;justify-content:center;gap:6px;border:1px solid var(--k-kenar2);background:var(--k-yuzey1);
  border-radius:8px;padding:7px 12px;font-weight:500;font-size:13px;white-space:nowrap}
.ms .dug:hover{background:var(--k-ortu2)}
.ms .dug.bir{background:var(--k-dolgu);border-color:var(--k-dolgu);color:var(--k-dolgu-metin)}
.ms .dug.bir:hover{filter:brightness(1.08)}
.ms .dug.teh{color:var(--k-kirmizi)}
.ms .dug:disabled{opacity:.5;cursor:default;filter:none}
.ms .not{font-size:13px;color:var(--k-soluk);background:var(--k-ortu);border-radius:8px;padding:10px 12px}
.ms .toplu{position:fixed;left:50%;bottom:calc(20px + env(safe-area-inset-bottom,0px));transform:translateX(-50%);display:flex;align-items:center;gap:8px;
  background:var(--k-yuzey3);border:1px solid var(--k-kenar2);border-radius:12px;padding:8px 8px 8px 14px;box-shadow:0 12px 40px rgba(0,0,0,.35);
  z-index:999990;max-width:calc(100% - 32px);flex-wrap:nowrap;white-space:nowrap}
.ms .toplu select,.ms .toplu input{border:1px solid var(--k-kenar2);background:var(--k-yuzey1);border-radius:8px;padding:6px 8px;font-size:13px;width:180px;min-width:0}
.ms .bildirim{position:fixed;right:max(20px,env(safe-area-inset-right,0px));bottom:calc(84px + env(safe-area-inset-bottom,0px));background:var(--k-yuzey3);
  border:1px solid var(--k-kenar2);border-radius:10px;padding:10px 12px 10px 14px;display:flex;gap:12px;align-items:center;
  box-shadow:0 12px 40px rgba(0,0,0,.35);z-index:999991;font-size:13px;max-width:min(460px,calc(100% - 32px))}
.ms .bildirim.kotu{border-color:color-mix(in srgb,var(--k-kirmizi) 50%,transparent)}
.ms .bildirim button{border:0;background:transparent;color:var(--k-mor2);font-weight:600}
.ms [hidden]{display:none !important}
@media (prefers-reduced-motion: reduce){.ms *{transition:none !important}}
@media (max-width:900px){
  .ms.detayli .govde{grid-template-columns:minmax(0,1fr)}
  .ms .panel{position:fixed;inset:0;z-index:999980;border-radius:0;max-height:none;border:0}
  .ms .ozet{grid-template-columns:repeat(2,minmax(0,1fr))}
  .ms .ozet>*:nth-child(2n){border-right:0}
  .ms .ozet>*{border-bottom:1px solid var(--k-kenar)}
  .ms .kutu{margin-left:0;flex:1 1 100%;min-width:0}
  .ms .bsat,.ms .kisa{display:none}
  .ms .sat,.ms.detayli .sat{grid-template-columns:36px minmax(0,1fr) auto;grid-template-areas:"o a s" "o l d";row-gap:2px;padding:9px 0}
  .ms .sat.secimsiz,.ms.detayli .sat.secimsiz{grid-template-columns:minmax(0,1fr) auto;grid-template-areas:"a s" "l d";padding-left:4px}
  .ms .sat>*{display:none}
  .ms .sat>.d-o{display:block;grid-area:o}.ms .sat>.d-ana{display:block;grid-area:a}.ms .sat>.d-sag{display:block;grid-area:s;text-align:right}
  .ms .sat>.d-alt{display:block;grid-area:l}.ms .sat>.d-durum{display:block;grid-area:d;text-align:right}
  .ms .toplu{bottom:calc(92px + env(safe-area-inset-bottom,0px));flex-wrap:wrap;white-space:normal;left:12px;right:12px;transform:none;max-width:none}
  .ms .toplu select,.ms .toplu input{flex:1 1 100%;width:auto}
  .ms .bildirim{bottom:calc(92px + env(safe-area-inset-bottom,0px));left:12px;right:12px;max-width:none}
  .ms.detayli .toplu{display:none}
}
"""

_JS = r"""
export default function(component){
  const {data, setTriggerValue, setStateValue, parentElement} = component;
  const D = data || {};
  const R = D.satirlar || [], ISL = D.islemler || [], SUT = D.sutunlar || [], GOR = D.gorunumler || [];
  const B0 = D.baslangic || {};
  const S = parentElement.__ms || (parentElement.__ms = {gor:B0.gor || (GOR[0]||{}).k || "", sec:Object.assign({}, B0.sec || {}),
                                                         ana:Object.assign({}, B0.ana || {}), q:B0.q || "", sira:B0.sira || null, secim:new Set(),
                                                         acik:null, sekme:null, odak:0, sonBildirim:null, form:{}, sinir:200});
  const durumYaz = () => { try { setStateValue("durum", {gor:S.gor, q:S.q, sec:S.sec, ana:S.ana, sira:S.sira}); } catch (_) {} };
  if (S.gor && !GOR.some(g => g.k === S.gor)) S.gor = (GOR[0]||{}).k || "";
  let kok = parentElement.querySelector(".ms");
  if (!kok){ kok = document.createElement("div"); kok.className = "ms"; parentElement.appendChild(kok); }
  const idler = new Set(R.map(r => r.id));
  const e = s => String(s ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
  const kucuk = s => String(s ?? "").toLocaleLowerCase("tr-TR");
  const trs = (n, d=2) => Number(n||0).toLocaleString("tr-TR", {minimumFractionDigits:d, maximumFractionDigits:d});
  const sayiOku = s => { const t = String(s ?? "").trim().replace(/\s/g, "").replace(/\./g, "").replace(",", "."); return t === "" ? null : Number(t); };
  const sayiYaz = (n, d) => n === null || n === undefined || n === "" ? "" : trs(Number(n), d ?? 2).replace(/\./g, "");
  const uyar = (r, f) => (f || []).every(([a, op, d]) => { const v = r[a];
    return op === "eq" ? v === d : op === "ne" ? v !== d : op === "in" ? (d||[]).includes(v) : op === "nin" ? !(d||[]).includes(v)
         : op === "gt" ? Number(v) > Number(d) : op === "lt" ? Number(v) < Number(d) : op === "var" ? !!v : op === "yok" ? !v : true; });
  const secilebilir = r => !D.salt && ISL.some(i => i.toplu && uyar(r, i.f));
  const secimVar = !D.salt && ISL.some(i => i.toplu);
  for (const i of [...S.secim]) if (!idler.has(i) || !secilebilir(R.find(r => r.id === i))) S.secim.delete(i);
  if (S.acik !== null && !idler.has(S.acik)) S.acik = null;
  const gonder = (islem, ids, degerler) => setTriggerValue("istek", {islem, ids, degerler: degerler || {}, n: Date.now() + Math.random()});

  function suzulmus(){
    const g = GOR.find(x => x.k === S.gor), q = kucuk(S.q.trim()), ar = (D.ara || {}).alanlar || [];
    let r = R.filter(x => !g || uyar(x, g.f));
    for (const s of D.secimler || []) if (S.sec[s.alan]) r = r.filter(x => Array.isArray(x[s.alan]) ? x[s.alan].map(String).includes(S.sec[s.alan]) : String(x[s.alan]) === S.sec[s.alan]);
    for (const a of D.anahtarlar || []) if (S.ana[a.k]) r = r.filter(x => uyar(x, a.f));
    if (q) r = r.filter(x => kucuk(ar.map(a => x[a]).join(" ")).includes(q));
    if (S.sira){
      const [a, y] = S.sira, v = x => { const s = x[a + "__s"]; return s !== undefined ? s : (typeof x[a] === "string" ? kucuk(x[a]) : x[a]); };
      r = r.slice().sort((p, q2) => { const A = v(p), B = v(q2), bA = A === null || A === undefined || A === "", bB = B === null || B === undefined || B === "";
        return bA || bB ? (bA === bB ? 0 : bA ? 1 : -1) : (A === B ? 0 : A > B ? 1 : -1) * y; });   // boş değer her yönde sonda
    }
    return r;
  }

  const kolon = c => c.gen || (c.tip === "ana" ? "minmax(150px,1fr)" : c.tip === "durum" ? "112px" : c.sag ? "120px" : "110px");
  const kol = (secimVar ? "40px " : "") + SUT.map(kolon).join(" ");
  const kolDar = (secimVar ? "40px " : "") + SUT.filter(c => !c.genis).map(kolon).join(" ");
  kok.style.setProperty("--kol", kol); kok.style.setProperty("--kol-dar", kolDar);

  function ozetHtml(){
    const O = D.ozet || [];
    if (!O.length) return "";
    return `<div class="ozet" style="--n:${Math.min(O.length, 5)}">` + O.map(k => {
      const ic = `<span class="et">${k.renk && k.renk !== "silik" && k.nokta !== false ? `<span class="nk r-${e(k.renk)}"></span>` : ""}${e(k.et)}</span>
        <span class="dg ${k.renk ? "r-" + e(k.renk) : ""}">${e(k.dg)}</span>${k.al ? `<span class="al" title="${e(k.al)}">${e(k.al)}</span>` : ""}
        ${k.oran !== undefined && k.oran !== null ? `<span class="ilr"><i style="width:${Math.max(0, Math.min(100, Math.round(k.oran*100)))}%"></i></span>` : ""}`;
      return k.suz ? `<button data-suz="${e(k.suz)}" aria-pressed="${S.gor === k.suz}" title="${e(k.ipucu||"")}">${ic}</button>` : `<div title="${e(k.ipucu||"")}">${ic}</div>`;
    }).join("") + `</div>`;
  }

  function suzHtml(){
    let h = `<div class="suz">`;
    if (GOR.length > 1) h += GOR.map(g => `<button class="cip" data-gor="${e(g.k)}" aria-pressed="${S.gor === g.k}">${e(g.ad)} <span class="s">${R.filter(x => uyar(x, g.f)).length}</span></button>`).join("");
    const sc = (D.secimler || []).filter(s => (s.secenekler || []).length > 1);
    if (sc.length || (D.anahtarlar || []).length) h += GOR.length > 1 ? `<span class="ayr"></span>` : "";
    h += sc.map(s => `<select class="cip ${S.sec[s.alan] ? "dolu" : ""}" data-secim="${e(s.alan)}" aria-label="${e(s.ad)}"><option value="">${e(s.ad)}</option>`
      + s.secenekler.map(o => `<option value="${e(o.k)}" ${S.sec[s.alan] === String(o.k) ? "selected" : ""}>${e(o.ad)}</option>`).join("") + `</select>`).join("");
    h += (D.anahtarlar || []).map(a => `<button class="cip" data-ana="${e(a.k)}" aria-pressed="${!!S.ana[a.k]}">${e(a.ad)}</button>`).join("");
    if (D.ara) h += `<label class="kutu"><input data-ara placeholder="${e((D.ara.ipucu || "Ara") + "  ( / )")}" value="${e(S.q)}" autocomplete="off" aria-label="Ara"></label>`;
    return h + `</div>`;
  }

  function hucre(c, r){
    const v = r[c.alan], alt = c.alt ? r[c.alt] : null, ar = c.alt_renk ? r[c.alt_renk] : null;
    if (c.tip === "ana") return `<b title="${e(v)}">${e(v ?? "—")}</b>${alt ? `<small title="${e(alt)}">${e(alt)}</small>` : ""}`;
    if (c.tip === "etiket") return v ? `<span class="etk">${e(v)}</span>` : "";
    if (c.tip === "durum"){ const d = r._durum || {}; return d.ad ? `<span class="drm r-${e(d.renk||"soluk")}"><span class="nk"></span>${e(d.ad)}</span>` : ""; }
    const ana = v === null || v === undefined || v === "" ? `<span class="r-silik">—</span>` : e(v);
    return ana + (alt ? `<small class="${ar ? "r-" + e(ar) : ""}">${e(alt)}</small>` : "");
  }
  const darSinif = c => c.dar === "ana" ? "d-ana" : c.dar === "sag" ? "d-sag" : c.dar === "alt" ? "d-alt" : c.dar === "durum" || c.tip === "durum" ? "d-durum" : c.tip === "ana" ? "d-ana" : "";

  function tabloHtml(r){
    const sec = r.filter(secilebilir);
    const hepsi = sec.length && sec.every(x => S.secim.has(x.id)), biraz = !hepsi && sec.some(x => S.secim.has(x.id));
    const ok = a => S.sira && S.sira[0] === a ? (S.sira[1] > 0 ? " ↑" : " ↓") : "";
    let h = `<div class="tablo" role="grid" aria-label="${e(D.baslik_ipucu || "Liste")}"><div class="sat bsat ${secimVar ? "" : "secimsiz"}" role="row">`
      + (secimVar ? `<div><button class="onay" data-hepsi role="checkbox" aria-checked="${hepsi ? "true" : biraz ? "mixed" : "false"}" aria-label="Görünenlerin hepsini seç" ${sec.length ? "" : "disabled"}></button></div>` : "")
      + SUT.map(c => `<div class="${c.sag ? "sag" : ""} ${c.genis ? "k-dar-gizle" : ""}">${c.sirala === false ? e(c.ad) : `<button data-sira="${e(c.alan)}">${e(c.ad)}${ok(c.alan)}</button>`}</div>`).join("") + `</div>`;
    if (!r.length) h += `<div class="bos">${e(R.length ? ((D.bos||{}).suzgec || "Bu süzgece uyan kayıt yok.") : ((D.bos||{}).liste || "Kayıt yok."))}</div>`;
    const gr = D.grup && !S.sira ? D.grup : null;
    let son = Symbol(), n = 0;
    for (let i = 0; i < r.length && n < S.sinir; i++, n++){
      const x = r[i];
      if (gr && x[gr.alan] !== son){
        son = x[gr.alan];
        const g = r.filter(y => y[gr.alan] === son);
        const t = (gr.toplamlar || []).map(t => { const s = g.reduce((a, y) => a + Number(y[t.alan] || 0), 0); return s ? (t.on || "") + trs(s, t.ondalik ?? 2) + (t.son || "") : ""; }).filter(Boolean).join(" + ");
        h += `<div class="gun"><b>${e(son || "—")}</b><span>${g.length} ${e(gr.birim || "kayıt")}</span>${t ? `<span class="t">${e(t)}</span>` : ""}</div>`;
      }
      const s = secilebilir(x);
      h += `<div class="sat satir ${secimVar ? "" : "secimsiz"} ${S.secim.has(x.id) ? "secili" : ""} ${S.acik === x.id ? "acik" : ""} ${i === S.odak ? "odak" : ""} ${x._soluk ? "soluk" : ""}"
             role="row" data-id="${e(JSON.stringify(x.id))}" data-i="${i}">`
        + (secimVar ? `<div class="d-o"><button class="onay" role="checkbox" aria-checked="${S.secim.has(x.id)}" data-sec="${e(JSON.stringify(x.id))}" aria-label="Seç" ${s ? "" : "disabled"}></button></div>` : "")
        + SUT.map(c => `<div class="${c.tip === "ana" ? "ana" : "hc"} ${c.sag ? "sag" : ""} ${c.genis ? "k-dar-gizle" : ""} ${darSinif(c)}">${hucre(c, x)}</div>`).join("") + `</div>`;
    }
    if (r.length > S.sinir) h += `<button class="daha" data-daha>${r.length - S.sinir} kayıt daha göster</button>`;
    h += `</div>`;
    return h + `<div class="kisa"><span><kbd>j</kbd> <kbd>k</kbd> satır gez</span>${secimVar ? `<span><kbd>x</kbd> seç</span>` : ""}<span><kbd>Enter</kbd> aç</span><span><kbd>Esc</kbd> kapat</span>${D.ara ? `<span><kbd>/</kbd> ara</span>` : ""}</div>`;
  }

  function alanHtml(a, F, r){
    const v = F[a.ad] ?? "";
    const et = e(a.et || a.ad);
    if (a.tip === "gizli") return "";
    if (a.gizle_sifir && !Number(r[a.varsayilan_alan])) return "";
    if (a.tip === "secim") return `<label class="${a.tam ? "tam" : ""}">${et}<select data-f="${e(a.ad)}"><option value="" ${v === "" ? "selected" : ""} disabled>${e(a.bos || "Seç…")}</option>`
      + (a.secenekler || []).map(o => `<option value="${e(o.k)}" ${String(v) === String(o.k) ? "selected" : ""}>${e(o.ad)}</option>`).join("") + `</select></label>`;
    if (a.tip === "onay") return `<label class="tam kutucuk"><input type="checkbox" data-f="${e(a.ad)}" ${v ? "checked" : ""}>${e(String(a.et || "").replace("{baslik}", r._baslik || ""))}</label>`;
    if (a.tip === "tarih") return `<label class="${a.tam ? "tam" : ""}">${et}<input type="date" data-f="${e(a.ad)}" value="${e(v)}"></label>`;
    if (a.tip === "sayi") return `<label class="${a.tam ? "tam" : ""}">${et}<input data-f="${e(a.ad)}" inputmode="decimal" value="${e(v)}"></label>`;
    return `<label class="${a.tam !== false ? "tam" : ""}">${et}<input data-f="${e(a.ad)}" value="${e(v)}" maxlength="${a.en_uzun || 500}"></label>`;
  }

  function formDurumu(isl, r){
    const F = S.form[r.id + "|" + isl.k] || (S.form[r.id + "|" + isl.k] = Object.fromEntries((isl.alanlar || []).map(a => {
      let v = a.varsayilan_alan !== undefined ? r[a.varsayilan_alan] : a.varsayilan;
      if (a.tip === "sayi" && v !== undefined && v !== null && v !== "") v = sayiYaz(v, a.ondalik);
      if (a.tip === "onay") v = false;
      return [a.ad, v ?? ""]; })));
    return F;
  }
  const eksik = (isl, F) => (isl.alanlar || []).some(a => a.zorunlu && a.tip !== "gizli" && (a.tip === "onay" ? !F[a.ad] : F[a.ad] === "" || F[a.ad] === null || F[a.ad] === undefined));

  function panelHtml(){
    const r = R.find(x => x.id === S.acik);
    if (!r) return "";
    const uyan = ISL.filter(i => uyar(r, i.f) && (!D.salt || i.okuma) && !i.yalniz_toplu);
    const formlu = uyan.filter(i => (i.alanlar || []).some(a => a.tip !== "gizli") || i.hizli);
    const dugmeli = uyan.filter(i => !formlu.includes(i));
    if (!S.sekme || !formlu.some(i => i.k === S.sekme)) S.sekme = formlu.length ? formlu[0].k : null;
    let ic = r._not ? `<div class="not">${e(r._not)}</div>` : "";
    if (D.salt && !uyan.length) ic += `<div class="not">Salt-okur oturum: işlem yapılamaz.</div>`;
    if (formlu.length > 1) ic += `<div class="sekmeler" role="group" aria-label="İşlem">${formlu.map(i => `<button data-sekme="${e(i.k)}" aria-pressed="${S.sekme === i.k}">${e(i.ad)}</button>`).join("")}</div>`;
    const isl = formlu.find(i => i.k === S.sekme);
    if (isl){
      const F = formDurumu(isl, r);
      ic += (isl.hizli || []).length ? `<div class="eylem">${isl.hizli.map((h, j) => `<button class="dug" data-hizli="${j}">${e(h.ad)}</button>`).join("")}</div>` : "";
      const al = (isl.alanlar || []).filter(a => a.tip !== "gizli");
      if (al.length) ic += `<div class="form">${al.map(a => alanHtml(a, F, r)).join("")}</div>`;
      if (isl.ipucu) ic += `<span class="ipucu">${e(isl.ipucu)}</span>`;
      if (F.__hata) ic += `<span class="hata" role="alert">${e(F.__hata)}</span>`;
      if (al.length) ic += `<div class="eylem"><button class="dug ${isl.tehlike ? "teh" : "bir"}" data-gonder="${e(isl.k)}" ${eksik(isl, F) ? "disabled" : ""}>${e(isl.dugme || isl.ad)}</button></div>`;
    }
    if (dugmeli.length) ic += `<div class="eylem">${dugmeli.map(i => `<button class="dug ${i.birincil ? "bir" : ""} ${i.tehlike ? "teh" : ""}" data-gonder="${e(i.k)}">${e(i.dugme || i.ad)}</button>`).join("")}</div>`;
    return `<aside class="panel" aria-label="Ayrıntı">
      <div class="pbas"><div><h3>${e(r._baslik ?? "")}</h3>${r._alt ? `<p>${e(r._alt)}</p>` : ""}</div><button class="kapat" data-kapat aria-label="Ayrıntıyı kapat">×</button></div>
      <div class="pgov">
        ${r._buyuk || r._durum ? `<div>${r._buyuk ? `<div class="buyuk">${e(r._buyuk)}${r._buyuk_alt ? `<small>${e(r._buyuk_alt)}</small>` : ""}</div>` : ""}
          ${r._durum && r._durum.ad ? `<span class="drm r-${e(r._durum.renk||"soluk")}"><span class="nk"></span>${e(r._durum.ad)}${r._durum.ek ? " · " + e(r._durum.ek) : ""}</span>` : ""}</div>` : ""}
        ${(r._detay || []).length ? `<dl>${r._detay.map(([a, b]) => `<dt>${e(a)}</dt><dd>${e(b)}</dd>`).join("")}</dl>` : ""}
        ${ic}</div></aside>`;
  }

  function topluHtml(){
    const s = R.filter(x => S.secim.has(x.id));
    if (!s.length || D.salt) return "";
    const tk = ISL.filter(i => i.toplu && s.every(x => uyar(x, i.f)));
    const T = S.form.__toplu || (S.form.__toplu = {});
    const toplam = (D.toplu_toplam || []).map(t => { const v = s.reduce((a, x) => a + Number(x[t.alan] || 0), 0); return v ? (t.on || "") + trs(v, t.ondalik ?? 2) : ""; }).filter(Boolean).join(" + ");
    let h = `<div class="toplu" role="region" aria-label="Seçili kayıtlar"><span><b>${s.length} seçili</b>${toplam ? " · " + e(toplam) : ""}</span>`;
    for (const i of tk){
      const al = (i.alanlar || []).filter(a => (i.toplu.alanlar || []).includes(a.ad));
      h += al.map(a => a.tip === "secim" ? `<select data-tf="${e(i.k)}|${e(a.ad)}" aria-label="${e(a.et || a.ad)}"><option value="" ${!T[i.k + "|" + a.ad] ? "selected" : ""} disabled>${e(a.bos || a.et || "Seç…")}</option>`
        + (a.secenekler || []).map(o => `<option value="${e(o.k)}" ${String(T[i.k + "|" + a.ad]) === String(o.k) ? "selected" : ""}>${e(o.ad)}</option>`).join("") + `</select>`
        : `<input data-tf="${e(i.k)}|${e(a.ad)}" ${a.tip === "tarih" ? 'type="date"' : 'inputmode="decimal"'} placeholder="${e(a.et || a.ad)}" value="${e(T[i.k + "|" + a.ad] || "")}">`).join("");
      const hazir = al.every(a => !a.zorunlu || T[i.k + "|" + a.ad]);
      h += `<button class="dug ${i.birincil ? "bir" : ""}" data-toplu="${e(i.k)}" ${hazir ? "" : "disabled"}>${e(i.toplu.ad || i.ad)}</button>`;
    }
    return h + `<button class="kapat" data-tkapat aria-label="Seçimi kaldır">×</button></div>`;
  }

  function bildirimHtml(){
    const b = D.bildirim;
    if (!b || S.sonBildirim === b.n) return "";
    return `<div class="bildirim ${b.ok === false ? "kotu" : ""}" role="status"><span>${e(b.mesaj)}</span>${b.geri && (b.geri.ids || []).length ? `<button data-gerial>Geri al</button>` : ""}</div>`;
  }

  function degerTopla(isl, F){
    const d = {};
    for (const a of isl.alanlar || []){
      let v = F[a.ad];
      if (a.tip === "sayi"){ if (v === "" || v === undefined || v === null) continue; v = sayiOku(v); if (v === null || isNaN(v)){ F.__hata = `${a.et || a.ad}: geçerli bir sayı girin.`; return null; } }
      if (a.tip === "onay") v = !!v;
      if (v === "" || v === undefined) continue;
      d[a.ad] = v;
    }
    return d;
  }

  function ciz(){
    const imza = JSON.stringify([S.gor, S.q, S.sec, S.ana, S.sira]);
    if (S.sonDurum !== imza){ S.sonDurum = imza; if (S.durumKur) durumYaz(); }
    S.durumKur = true;
    const r = suzulmus();
    S.gorunen = r;
    if (S.odak >= r.length) S.odak = Math.max(0, r.length - 1);
    kok.classList.toggle("detayli", S.acik !== null && (D.tik || "panel") === "panel");
    const a = document.activeElement, odak = a && kok.contains(a) ? (a.getAttribute("data-f") ? "f:" + a.getAttribute("data-f") : a.hasAttribute("data-ara") ? "ara" : null) : null;
    kok.innerHTML = ozetHtml() + suzHtml() + `<div class="govde"><div style="min-width:0">${tabloHtml(r)}</div>${(D.tik || "panel") === "panel" ? panelHtml() : ""}</div>` + topluHtml() + bildirimHtml();
    if (odak){
      const el = odak === "ara" ? kok.querySelector("[data-ara]") : kok.querySelector(`[data-f="${odak.slice(2)}"]`);
      if (el){ el.focus(); if (el.setSelectionRange && !["date","checkbox"].includes(el.type)) try { el.setSelectionRange(el.value.length, el.value.length); } catch (_) {} }
    }
    if (D.bildirim && S.sonBildirim !== D.bildirim.n){
      const n = D.bildirim.n; clearTimeout(S.bz);
      S.bz = setTimeout(() => { S.sonBildirim = n; const b = kok.querySelector(".bildirim"); if (b) b.remove(); }, 7000);
    }
  }

  function satirAc(id, i){
    S.odak = i;
    if ((D.tik || "panel") !== "panel") return gonder(D.tik, [id], {});
    if (S.acik !== id){ S.acik = id; S.sekme = null; } else S.acik = null;
    ciz();
  }

  kok.onclick = (ev) => {
    const t = ev.target.closest("button, [data-id]");
    if (!t || !kok.contains(t)) return;
    const d = t.dataset, idOku = s => JSON.parse(s);
    if (d.suz !== undefined){ S.gor = d.suz; S.odak = 0; return ciz(); }
    if (d.gor !== undefined){ S.gor = d.gor; S.odak = 0; return ciz(); }
    if (d.ana !== undefined){ S.ana[d.ana] = !S.ana[d.ana]; return ciz(); }
    if (d.sira !== undefined){ S.sira = S.sira && S.sira[0] === d.sira ? (S.sira[1] > 0 ? [d.sira, -1] : null) : [d.sira, 1]; return ciz(); }
    if (d.daha !== undefined){ S.sinir += 200; return ciz(); }
    if (d.hepsi !== undefined){ const g = (S.gorunen || []).filter(secilebilir); const h = g.every(x => S.secim.has(x.id));
      g.forEach(x => h ? S.secim.delete(x.id) : S.secim.add(x.id)); return ciz(); }
    if (d.sec !== undefined){ ev.stopPropagation(); const i = idOku(d.sec); S.secim.has(i) ? S.secim.delete(i) : S.secim.add(i); return ciz(); }
    if (d.kapat !== undefined){ S.acik = null; return ciz(); }
    if (d.sekme !== undefined){ S.sekme = d.sekme; return ciz(); }
    if (d.tkapat !== undefined){ S.secim.clear(); return ciz(); }
    if (d.gerial !== undefined){ S.sonBildirim = D.bildirim.n; return gonder(D.bildirim.geri.islem, D.bildirim.geri.ids, {}); }
    if (d.hizli !== undefined){ const isl = ISL.find(i => i.k === S.sekme); if (isl) return gonder(isl.k, [S.acik], isl.hizli[Number(d.hizli)].degerler || {}); return; }
    if (d.gonder !== undefined){
      const isl = ISL.find(i => i.k === d.gonder), r = R.find(x => x.id === S.acik);
      if (!isl || !r) return;
      const F = formDurumu(isl, r); F.__hata = "";
      const deg = degerTopla(isl, F);
      if (deg === null) return ciz();
      return gonder(isl.k, [r.id], deg);
    }
    if (d.toplu !== undefined){
      const isl = ISL.find(i => i.k === d.toplu), T = S.form.__toplu || {};
      const deg = Object.assign({}, isl.toplu.degerler || {});
      for (const a of isl.alanlar || []) if ((isl.toplu.alanlar || []).includes(a.ad) && T[isl.k + "|" + a.ad]) deg[a.ad] = a.tip === "sayi" ? sayiOku(T[isl.k + "|" + a.ad]) : T[isl.k + "|" + a.ad];
      return gonder(isl.k, [...S.secim], deg);
    }
    if (d.id !== undefined) return satirAc(idOku(d.id), Number(d.i));
  };
  kok.oninput = (ev) => {
    const t = ev.target, d = t.dataset;
    if (d.ara !== undefined){ S.q = t.value; S.odak = 0; return ciz(); }
    if (d.f !== undefined && S.acik !== null && S.sekme){
      const F = S.form[S.acik + "|" + S.sekme]; if (!F) return;
      F[d.f] = t.type === "checkbox" ? t.checked : t.value; F.__hata = "";
      if (t.tagName === "SELECT" || t.type === "checkbox" || t.type === "date") ciz();
      else { const isl = ISL.find(i => i.k === S.sekme), b = kok.querySelector(`[data-gonder="${S.sekme}"]`); if (b && isl) b.disabled = eksik(isl, F); }
    }
    if (d.tf !== undefined){ (S.form.__toplu || (S.form.__toplu = {}))[d.tf] = t.value; if (t.tagName === "SELECT") ciz();
      else { const k = d.tf.split("|")[0], isl = ISL.find(i => i.k === k), b = kok.querySelector(`[data-toplu="${k}"]`);
        if (b && isl) b.disabled = !(isl.alanlar || []).filter(a => (isl.toplu.alanlar || []).includes(a.ad)).every(a => !a.zorunlu || S.form.__toplu[k + "|" + a.ad]); } }
  };
  kok.onchange = (ev) => {
    const t = ev.target, d = t.dataset;
    if (d.secim !== undefined){ S.sec[d.secim] = t.value; S.odak = 0; return ciz(); }
  };
  S.ciz = ciz; S.satirAc = satirAc;
  if (!parentElement.__msKlavye){
    parentElement.__msKlavye = true;
    document.addEventListener("keydown", (ev) => {
      const s = parentElement.__ms;
      if (!parentElement.isConnected || !s || !s.ciz) return;
      const k = parentElement.querySelector(".ms");
      if (!k || k.getBoundingClientRect().height === 0) return;          // sayfada görünmüyor
      const a = document.activeElement, yaz = a && (["INPUT","SELECT","TEXTAREA"].includes(a.tagName) || a.isContentEditable);
      if (ev.key === "Escape"){ if (yaz && k.contains(a)) { a.blur(); return; } if (s.acik !== null){ s.acik = null; s.ciz(); } else if (s.secim.size){ s.secim.clear(); s.ciz(); } return; }
      if (yaz || ev.ctrlKey || ev.metaKey || ev.altKey) return;
      if (document.querySelector('[role="dialog"]')) return;
      if (document.querySelectorAll(".ms").length > 1 && !k.contains(document.activeElement) && document.activeElement !== document.body) return;
      const r = s.gorunen || [];
      if (ev.key === "/"){ const x = k.querySelector("[data-ara]"); if (x){ ev.preventDefault(); x.focus(); } }
      else if (ev.key === "j" || ev.key === "ArrowDown"){ if (!r.length) return; ev.preventDefault(); s.odak = Math.min(r.length - 1, s.odak + 1); s.ciz(); k.querySelector(".satir.odak")?.scrollIntoView({block:"nearest"}); }
      else if (ev.key === "k" || ev.key === "ArrowUp"){ if (!r.length) return; ev.preventDefault(); s.odak = Math.max(0, s.odak - 1); s.ciz(); k.querySelector(".satir.odak")?.scrollIntoView({block:"nearest"}); }
      else if (ev.key === "x" && r[s.odak]){ const i = r[s.odak].id; const sat = k.querySelector(`.satir.odak [data-sec]`); if (sat && !sat.disabled){ s.secim.has(i) ? s.secim.delete(i) : s.secim.add(i); s.ciz(); } }
      else if (ev.key === "Enter" && r[s.odak]){ s.satirAc(r[s.odak].id, s.odak); }
    });
  }
  ciz();
}
"""

_BILESEN = None


def _bilesen():
    global _BILESEN
    if _BILESEN is None:
        import streamlit.components.v2 as _v2
        _BILESEN = _v2.component("kayran_masa", css=_CSS, js=_JS)
    return _BILESEN


def _jsonlanir(veri):
    """Bileşene giden veri JSON'a çevrilebilmeli (tarih, Decimal… metne)."""
    return json.loads(json.dumps(veri, ensure_ascii=False, default=str))


def onceki_durum(key):
    """Bileşenin son bildirdiği görünüm durumu (görünüm, arama, süzgeç, sıralama) ya da None."""
    try:
        import streamlit as st
        d = (st.session_state.get(key) or {}).get("durum")
    except Exception:  # noqa: BLE001
        return None
    return d if isinstance(d, dict) else None


def masa(veri, key):
    """Masayı çizer; kullanıcı bir işlem yaptıysa YALNIZ o çalıştırmada isteği (dict) döner.
    Görünüm durumu oturumda kalır: bileşen yeniden kurulduğunda (ayrıntıdan dönüş) son durumla açılır."""
    if "baslangic" not in veri:
        veri = dict(veri, baslangic=onceki_durum(key))
    sonuc = _bilesen()(key=key, data=_jsonlanir(veri), default={"durum": None}, height="content",
                       on_istek_change=lambda: None, on_durum_change=lambda: None)
    try:
        return getattr(sonuc, "istek")
    except Exception:  # noqa: BLE001
        return getattr(sonuc, "get", lambda *_: None)("istek")


# ── Sayfa tarafı yardımcı: istek → yürüt → bildirim → yenile ─────────
def calistir(veri, key, yurut):
    """Ortak akış. veri'ye bir önceki işlemin bildirimi eklenir, masa çizilir; istek geldiyse istek_al ile
    doğrulanır ve yurut(temiz) çağrılır. yurut → {"ok", "mesaj", "geri"?: {"islem", "ids"}} döner.
    Ek anahtarlar: "yenileme": False → sayfa yeniden çalışmaz, aynı çalıştırmada devam eder (ör. yurut
    B.detay_ac(...) çağırdı; sayfa masadan sonra B.detay_istendi(...) ile bugünkü pencereyi açar);
    "sessiz": True → bildirim gösterilmez; "onbellek": False → yeniden çalıştırmada önbellek boşaltılmaz
    (yalnız görünüm değişti, ör. B.sec ile sayfa içi ayrıntıya geçiş).
    Sonuç bir sonraki çizimde bildirim olarak görünür. Dönüş: masanın döndürdüğü ham istek (genelde None)."""
    import streamlit as st
    bkey = f"_masa_bildirim_{key}"
    veri = dict(veri, bildirim=st.session_state.pop(bkey, None))
    istek = masa(veri, key)
    if not istek:
        return None
    temiz, hata = istek_al(veri, istek)
    if hata:
        sonuc = {"ok": False, "mesaj": hata}
    else:
        try:
            sonuc = yurut(temiz) or {"ok": True, "mesaj": "Tamam"}
        except Exception as ex:  # noqa: BLE001 — kullanıcıya söyle, kayda geç
            from shared.hata_log import kaydet
            kaydet(f"masa.{key}.{temiz['islem']}", ex)
            sonuc = {"ok": False, "mesaj": "İşlem yapılamadı; ayrıntı Sistem kayıtları'nda."}
    if sonuc.get("yenileme") is False:          # ör. ayrıntı penceresi açıldı — sayfa aynı çalıştırmada devam
        if not sonuc.get("sessiz"):
            st.session_state[bkey] = dict(sonuc, n=istek.get("n"))
        return istek
    if not sonuc.get("sessiz"):                  # sessiz: bildirim yok (ör. sayfa içi ayrıntıya geçildi)
        st.session_state[bkey] = dict(sonuc, n=istek.get("n"))
    if sonuc.get("onbellek", True):
        st.cache_data.clear()
    st.rerun()
