# -*- coding: utf-8 -*-
"""KAYRAN — Patron panosu (ana sayfa, yalnız yetkili) · Ekim 2026 yeniden tasarım.

Eskisinde: kartlar canlı satış görünümünden (v_satis_pnl), grafik gece tazelenen ayrı
bir özet tablodan (mv_gunluk_pnl) besleniyordu → rakamlar tutmuyordu; grafik yalnız
satış olan günleri EŞİT aralıkla çiziyordu (zaman ekseni yanlış, tarih yoktu); "bu ay"
ayın ilk günlerinde 1–2 günü kıyassız gösteriyordu; tarih sunucu (UTC) günüydü.

Şimdi:
  · TEK KAYNAK: kartlar, grafik, kanal payı aynı v_satis_pnl satırlarından
  · dönem seçici (bu ay · son 30 gün · bu çeyrek) + önceki dönemin AYNI gün sayısıyla kıyas
  · takvim günlü grafik (satışsız gün = 0): ciro sütunu, 7 günlük ortalama, net kâr
  · kanal payı · tıklanır veri kalitesi çipleri · son 24 saatin kritik işlemleri
Saf hesaplar test edilir (tests/test_patron.py).
"""
import calendar
import html as _h
from datetime import date, timedelta

import streamlit as st

from shared.tasarim import tr_sayi

DONEMLER = ["Bu ay", "Son 30 gün", "Bu çeyrek"]
GUN_KISA = ["Pzt", "Sal", "Çar", "Per", "Cum", "Cmt", "Paz"]


# ── Saf hesaplar ────────────────────────────────────────────────────
def _f(v):
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


def _gun(v):
    if isinstance(v, date):
        return v
    try:
        return date.fromisoformat(str(v or "")[:10])
    except ValueError:
        return None


def _ay_kaydir(d, n):
    y, m = divmod(d.month - 1 + n, 12)
    y, m = d.year + y, m + 1
    return date(y, m, min(d.day, calendar.monthrange(y, m)[1]))


def donem_araligi(secim, bugun):
    """Seçili dönem ve kıyas dönemi: önceki dönemin AYNI gün sayısı.
    2 Ekim'de 'Bu ay' = 1–2 Ekim, kıyas 1–2 Eylül (ayın tamamı değil)."""
    if secim == "Son 30 gün":
        bas = bugun - timedelta(days=29)
        return dict(bas=bas, bit=bugun, onceki_bas=bas - timedelta(days=30), onceki_bit=bas - timedelta(days=1),
                    kiyas="önceki 30 güne göre")
    if secim == "Bu çeyrek":
        bas = date(bugun.year, 3 * ((bugun.month - 1) // 3) + 1, 1)
        ob = _ay_kaydir(bas, -3)
        oson = bas - timedelta(days=1)
        return dict(bas=bas, bit=bugun, onceki_bas=ob,
                    onceki_bit=min(ob + timedelta(days=(bugun - bas).days), oson),
                    kiyas="geçen çeyreğin aynı günlerine göre")
    bas = bugun.replace(day=1)
    ob = _ay_kaydir(bas, -1)
    return dict(bas=bas, bit=bugun, onceki_bas=ob, onceki_bit=_ay_kaydir(bugun, -1),   # ay sonu kırpılır
                kiyas="geçen ayın aynı günlerine göre")


def _aralikta(rows, bas, bit):
    return [r for r in rows if (g := _gun(r.get("tarih"))) and bas <= g <= bit]


def ozet(rows):
    """v_satis_pnl satırları → ciro, net kâr, destek, adet, marj (satis.ozet_from_view ile aynı formül)."""
    o = {"ciro": 0.0, "net_kar": 0.0, "destek": 0.0, "adet": 0}
    for r in rows:
        o["ciro"] += _f(r.get("ciro"))
        o["net_kar"] += _f(r.get("net_kar"))
        o["destek"] += _f(r.get("destek"))
        o["adet"] += int(_f(r.get("adet")))
    ns = o["ciro"] - o["destek"]
    o["marj"] = (o["net_kar"] / ns * 100) if ns > 0 else 0.0
    return o


def degisim(simdi, once):
    return round((simdi - once) / abs(once) * 100, 1) if once else None


def gunluk_seri(rows, bas, bit):
    """[(gün, ciro, net kâr)] — HER takvim günü (satışsız gün 0)."""
    gun = {}
    for r in rows:
        g = _gun(r.get("tarih"))
        if g and bas <= g <= bit:
            c, n = gun.get(g, (0.0, 0.0))
            gun[g] = (c + _f(r.get("ciro")), n + _f(r.get("net_kar")))
    out, g = [], bas
    while g <= bit:
        c, n = gun.get(g, (0.0, 0.0))
        out.append((g, c, n))
        g += timedelta(days=1)
    return out


def hareketli_ort(degerler, n=7):
    out = []
    for i in range(len(degerler)):
        p = degerler[max(0, i - n + 1):i + 1]
        out.append(round(sum(p) / len(p), 2))
    return out


def kanal_payi(rows, n=5, ad_fn=None):
    """[(kanal, ciro, pay %)] — ilk n kanal + 'Diğer'. ad_fn: kanal kodu → görünen ad;
    paylar GÖRÜNEN ADA göre birleşir (iki kod aynı ada eşlenince ayrı satır oluyordu)."""
    k = {}
    for r in rows:
        ad = str(r.get("kanal") or "—").strip() or "—"
        if ad_fn:
            ad = ad_fn(ad) or ad
        k[ad] = k.get(ad, 0.0) + _f(r.get("ciro"))
    top = sum(k.values()) or 1
    s = sorted(k.items(), key=lambda x: -x[1])
    out = [(a, c, round(c / top * 100, 1)) for a, c in s[:n]]
    if len(s) > n:
        d = sum(c for _, c in s[n:])
        out.append(("Diğer", d, round(d / top * 100, 1)))
    return out


# ── Kartlar ─────────────────────────────────────────────────────────
def _usd(v):
    return f"&#36;{tr_sayi(v)}"                        # düz "$" birden çok geçerse LaTeX sanılır


def _spark(seri, renk):
    if len(seri) < 3 or not any(seri):
        return ""
    mx, mn = max(seri), min(seri)
    rng = (mx - mn) or 1
    W, H = 120, 30
    pts = " ".join(f"{i / (len(seri) - 1) * W:.1f},{H - (v - mn) / rng * (H - 4) - 2:.1f}" for i, v in enumerate(seri))
    return (f'<svg viewBox="0 0 {W} {H}" preserveAspectRatio="none" style="width:100%;height:30px;display:block;'
            f'margin-top:8px"><polyline points="{pts}" fill="none" stroke-width="1.6" stroke-linejoin="round" '
            f'vector-effect="non-scaling-stroke" style="stroke:var(--k-{renk});opacity:.85"/></svg>')


def kart_html(baslik, deger, onceki, tur, seri, renk, kiyas="önceki döneme göre"):
    if tur == "yuzde":
        val = f"%{tr_sayi(deger, 1)}"
        fark = round(deger - onceki, 1) if onceki is not None else None
        if fark is None:
            alt, r = "", "silik"
        else:
            alt = (f"{'▲' if fark > 0 else ('▼' if fark < 0 else '■')} {tr_sayi(abs(fark), 1)} puan · {kiyas}")
            r = "yesil" if fark > 0 else ("kirmizi" if fark < 0 else "silik")
    else:
        val = _usd(deger)
        d = degisim(deger, onceki or 0)
        if d is None:
            alt, r = "önceki dönemde satış yok", "silik"
        else:
            alt = f"{'▲' if d > 0 else ('▼' if d < 0 else '■')} %{tr_sayi(abs(d), 1)} · {kiyas}"
            r = "yesil" if d > 0 else ("kirmizi" if d < 0 else "silik")
    from shared.tasarim import KART_YENI, kart_hucresi
    if KART_YENI:
        # Ortak kart: büyük değer, ▲/▼ rozeti (hesap yukarıda, marjda "puan"), eğilim çizgisi.
        # Renk anlam taşır: net kâr eksiye düşerse değer kırmızı.
        rz = None
        if alt and alt[0] in "▲▼■":
            parca = alt.split(" · ", 1)
            rz = (parca[0], {"yesil": "iyi", "kirmizi": "kotu"}.get(r))
            alt = parca[1] if len(parca) > 1 else ""
        return kart_hucresi({"etiket": baslik, "deger": val, "vurgu": True, "rozet": rz,
                             "alt": _h.escape(alt) + (" · son 30 gün" if len(seri or []) >= 2 else ""),
                             "seri": seri, "anlam": "kotu" if renk == "kirmizi" else None})
    return (f'<div class="pp-kart" style="--pp-r:var(--k-{renk})">'
            f'<div class="pp-ad">{_h.escape(baslik)}</div>'
            f'<div class="pp-deger">{val}</div>'
            f'<div class="pp-alt" style="color:var(--k-{r})">{alt}</div>{_spark(seri, renk)}'
            + ('<div style="font-size:10.5px;color:var(--k-silik);margin-top:2px">son 30 gün</div>'
               if _spark(seri, renk) else "") + '</div>')


# "Toplam aktif" bileşenleri → rakamı veren sayfa (modül, sayfa kodu). Toplam aktifler
# sayfasına (Muhasebe) değil, rakamın kaynağına gider.
AKTIF_HEDEFLERI = [
    ("Stok", "stok", "kayranpm", "tum_urunler"),
    ("İthalat", "ithalat", "ithalat", "gecmis"),
    ("Banka", "banka", "kayranacc", "banka"),
    ("Alacak", "alacak", "kayranacc", "cari_ekstre"),
]


def aktif_dugmeleri(snap):
    """[(anahtar, etiket, modül, sayfa kodu)]: pozitif bileşenler, '$' tutarıyla."""
    if not snap:
        return []
    return [(k, f"{ad} · {_usd(_f(snap.get(k)))}", mod, sayfa)
            for ad, k, mod, sayfa in AKTIF_HEDEFLERI if _f(snap.get(k)) > 0]


def _aktif_kart(snap):
    if not snap:
        return ('<div class="pp-kart" style="--pp-r:var(--k-cyan)"><div class="pp-ad">Toplam aktif</div>'
                '<div class="pp-deger" style="color:var(--k-silik)">—</div>'
                '<div class="pp-alt">Muhasebe › Toplam Aktifler işlenince görünür</div></div>')
    from kayranpm.urun_hesap import tarih_tr
    top = _f(snap.get("toplam"))
    kal = [("Stok", _f(snap.get("stok")), "mor"), ("İthalat", _f(snap.get("ithalat")), "mavi"),
           ("Banka", _f(snap.get("banka")), "cyan"), ("Alacak", _f(snap.get("alacak")), "yesil")]
    poz = sum(v for _, v, _ in kal) or 1
    bar = "".join(f'<div title="{a}: &#36;{tr_sayi(v)}" style="flex:{v};background:var(--k-{c})"></div>'
                  for a, v, c in kal if v > 0)
    lej = " · ".join(f'<span style="color:var(--k-{c})">●</span> {a} %{tr_sayi(v / poz * 100, 0)}'
                     for a, v, c in kal if v > 0)
    return (f'<div class="pp-kart" style="--pp-r:var(--k-cyan)"><div class="pp-ad">Toplam aktif</div>'
            f'<div class="pp-deger">{_usd(top)}</div>'
            f'<div class="pp-alt">{tarih_tr(snap.get("tarih"), saat=True)} itibarıyla · borç ve çek düşülmüş</div>'
            f'<div style="display:flex;height:6px;border-radius:3px;overflow:hidden;gap:2px;margin-top:10px">{bar}</div>'
            f'<div style="font-size:11px;color:var(--k-silik);margin-top:5px">{lej}</div></div>')


CSS = """<style>
.pp-bas{display:flex;align-items:baseline;gap:10px;margin:0}
.pp-bas b{font-size:17px;font-weight:700;color:var(--k-metin)}
.pp-bas span{font-size:12.5px;color:var(--k-silik)}
.pp-kartlar{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:10px;margin:6px 0 12px}
.pp-kart{position:relative;background:linear-gradient(180deg,var(--k-yuzey2),var(--k-yuzey1));
  border:1px solid var(--k-kenar2);border-radius:14px;padding:14px 16px 12px;overflow:hidden}
.pp-kart::before{content:"";position:absolute;inset:0 0 auto 0;height:2px;background:var(--pp-r);opacity:.9}
.pp-ad{font-size:12.5px;color:var(--k-soluk);font-weight:550}
.pp-deger{font-family:var(--k-mono);font-size:26px;font-weight:700;color:var(--k-metin);letter-spacing:-.5px;
  margin-top:4px;line-height:1.15}
.pp-alt{font-size:12px;margin-top:3px;color:var(--k-silik)}
.pp-kutu{background:var(--k-yuzey1);border:1px solid var(--k-kenar2);border-radius:14px;padding:12px 14px}
.pp-kb{font-size:13px;font-weight:650;color:var(--k-metin);margin-bottom:6px}
.pp-kb span{font-weight:400;color:var(--k-silik);font-size:12px;margin-left:6px}
</style>"""


# ── Veri (önbellekli) ───────────────────────────────────────────────
@st.cache_data(ttl=300, show_spinner=False)
def _satirlar(bas_iso, bit_iso):
    """v_satis_pnl satırları; görünüm yoksa satışlardan gün × kanal bazında üretilir."""
    from satis.database import get_satis_pnl_view
    v = get_satis_pnl_view(bas_iso, bit_iso)
    if v is not None:
        return [{k: r.get(k) for k in ("tarih", "kanal", "ciro", "net_kar", "destek", "adet")} for r in v]
    from satis.database import get_satislar_yalin, ozet_hesapla
    gr = {}
    for s in get_satislar_yalin(bas_iso, bit_iso) or []:
        gr.setdefault((str(s.get("tarih"))[:10], s.get("kanal") or "—"), []).append(s)
    out = []
    for (t, k), ss in gr.items():
        o = ozet_hesapla(ss)[0]
        out.append({"tarih": t, "kanal": k, "ciro": o.get("ciro"), "net_kar": o.get("net_kar"),
                    "destek": o.get("destek"), "adet": o.get("adet")})
    return out


@st.cache_data(ttl=600, show_spinner=False)
def _veri_kalitesi(yil_bas_iso, bugun_iso):
    """Maliyetsiz satış (onarılır / ithalatsız) ve eksi stok sayıları."""
    import re
    v = {}
    try:
        from satis.database import get_satislar_yalin, get_pacal_map

        def _n(x):
            return re.sub(r"[^A-Z0-9]", "", str(x or "").upper())
        pacal = {_n(k): p for k, p in (get_pacal_map() or {}).items()}
        on = ith = 0
        for s in get_satislar_yalin(yil_bas_iso, bugun_iso) or []:
            if _f(s.get("birim_maliyet")) <= 0 and int(_f(s.get("adet"))) > 0:
                if _f(pacal.get(_n(s.get("sku")))) > 0:
                    on += 1
                else:
                    ith += 1
        v["onarilir"], v["ithalatsiz"] = on, ith
    except Exception:  # noqa: BLE001
        pass
    try:
        from kayranpm.analitik import dashboard_hesapla
        v["eksi_stok"] = sum(1 for u in dashboard_hesapla() or [] if _f(u.get("toplam_stok")) < 0)
    except Exception:  # noqa: BLE001
        pass
    return v


@st.cache_data(ttl=300, show_spinner=False)
def _kritik(dun_iso):
    from shared.audit import get_loglar
    from shared.yukleme_takvimi import sorumlu_adi as kisi_adi   # gokhan → Gökhan (Türkçe harfli ad)
    out = []
    for log in get_loglar(limit=200, baslangic=dun_iso) or []:
        isl, tab = str(log.get("islem", "")).lower(), str(log.get("tablo", "")).lower()
        if ("sil" in isl or "yükle" in isl or "import" in isl or "toplu" in isl
                or (tab in ("odemeler", "satislar", "cekler", "bankalar") and "güncelle" in isl)):
            out.append({"zaman": str(log.get("zaman", "")), "kim": kisi_adi(log.get("kullanici") or "?"),
                        "islem": log.get("islem", ""), "modul": log.get("modul", "") or log.get("tablo", "")})
    return out


# ── Grafik ──────────────────────────────────────────────────────────
def _grafik(seri):
    """Günlük ciro (ana renk) · 7 günlük ortalama (silik, kesikli) · net kâr (nötr; eksi gün
    kırmızı nokta). Düzen: shared/grafik.py."""
    import plotly.graph_objects as go
    from shared.grafik import duzen, rol
    x = [g.strftime("%d.%m") for g, _, _ in seri]
    ciro = [c for _, c, _ in seri]
    nk = [n for _, _, n in seri]
    ort = hareketli_ort(ciro, 7)
    hov = [f"{g:%d.%m} {GUN_KISA[g.weekday()]} · ciro ${tr_sayi(c)} · net kâr ${tr_sayi(n)}"
           + (f" · marj %{tr_sayi(n / c * 100, 1)}" if c else "") for g, c, n in seri]
    fg = go.Figure()
    fg.add_bar(x=x, y=ciro, name="Ciro", marker=dict(color=rol("ana"), opacity=.75, line=dict(width=0)),
               customdata=hov, hovertemplate="%{customdata}<extra></extra>")
    fg.add_scatter(x=x, y=ort, name="7 günlük ortalama", mode="lines",
                   line=dict(color=rol("silik"), width=1.6, dash="dash"), hoverinfo="skip")
    fg.add_scatter(x=x, y=nk, name="Net kâr", mode="lines+markers", line=dict(color=rol("ikincil"), width=1.6),
                   marker=dict(size=[7 if (n or 0) < 0 else 0 for n in nk], color=rol("kotu")), hoverinfo="skip")
    adim = max(1, len(x) // 8)
    return duzen(fg, yukseklik=260, bargap=.25, hovermode="x",
                 xaxis=dict(type="category", tickmode="array", tickvals=x[::adim]),
                 yaxis=dict(tickprefix="$", tickformat=",.0f"))

def _kanal_html(kp):
    if not kp:
        return '<div style="color:var(--k-silik);font-size:12.5px">Bu dönemde satış yok.</div>'
    renk = ["mor", "cyan", "yesil", "amber", "pembe", "silik"]
    return "".join(
        f'<div style="padding:5px 0"><div style="display:flex;justify-content:space-between;font-size:13px">'
        f'<span>{_h.escape(a)}</span>'
        f'<span style="font-family:var(--k-mono);color:var(--k-soluk)">%{tr_sayi(p, 0)} · {_usd(c)}</span></div>'
        f'<div style="height:6px;border-radius:3px;background:var(--k-kenar2);margin-top:4px;overflow:hidden">'
        f'<div style="height:100%;width:{p:.1f}%;background:var(--k-{renk[i % len(renk)]})"></div></div></div>'
        for i, (a, c, p) in enumerate(kp))


def _firma_ad(kod):
    try:
        from shared.utils import firma_gorunen_ad
        return firma_gorunen_ad(kod)
    except Exception:  # noqa: BLE001
        return kod


# ── Ekran ───────────────────────────────────────────────────────────
def render(sayfaya_git):
    """Ana sayfada çağrılır. sayfaya_git(modul): veri kalitesi çiplerinden geçiş."""
    st.markdown(CSS, unsafe_allow_html=True)
    from shared.tasarim import KART_YENI
    if KART_YENI:
        # "Toplam aktif" kartı (pp-kart) ortak kartla aynı yüzeyde: degrade ve üst şerit yok
        st.markdown('<style>.pp-kart{background:var(--k-yuzey1) !important;border:1px solid var(--k-kenar) !important;}'
                    '.pp-kart::before{display:none !important;}'
                    '.pp-deger{font-family:inherit !important;font-size:28px !important;font-weight:600 !important;}'
                    '.pp-kartlar .k-kart{min-width:0;}</style>', unsafe_allow_html=True)

    @st.fragment
    def _govde():
        from shared.utils import tr_today
        bugun = tr_today()                          # İstanbul günü (sunucu UTC)
        c1, c2 = st.columns([2.2, 1.6], vertical_alignment="center")
        c1.markdown('<div class="pp-bas"><b>Patron panosu</b><span>yalnız sana görünür</span></div>',
                    unsafe_allow_html=True)
        secim = c2.segmented_control("Dönem", DONEMLER, default="Bu ay", key="pp_donem",
                                     label_visibility="collapsed") or "Bu ay"
        d = donem_araligi(secim, bugun)
        grafik_bas = min(d["bas"], bugun - timedelta(days=29))
        try:
            rows = _satirlar(min(d["onceki_bas"], grafik_bas).isoformat(), bugun.isoformat())
        except Exception as e:  # noqa: BLE001
            st.warning(f"Satış verisi okunamadı: {type(e).__name__}")
            return
        simdi = ozet(_aralikta(rows, d["bas"], d["bit"]))
        once = ozet(_aralikta(rows, d["onceki_bas"], d["onceki_bit"]))
        # Kart eğilim çizgisi grafikle aynı aralık (en az 30 gün): ayın ilk günlerinde
        # dönem 1–2 gün olduğundan çizgi çıkmıyor, kartın yarısı boş kalıyordu.
        seri = gunluk_seri(rows, grafik_bas, bugun)
        donem_seri = seri
        try:
            from kayranacc.database import get_ayar
            snap = get_ayar("toplam_aktif_snapshot")
        except Exception:  # noqa: BLE001
            snap = None
        st.markdown(
            '<div class="pp-kartlar">'
            + kart_html("Ciro", simdi["ciro"], once["ciro"], "para", [c for _, c, _ in donem_seri], "mor", d["kiyas"])
            + kart_html("Net kâr", simdi["net_kar"], once["net_kar"], "para", [n for _, _, n in donem_seri],
                        "yesil" if simdi["net_kar"] >= 0 else "kirmizi", d["kiyas"])
            + kart_html("Marj", simdi["marj"], once["marj"] if once["ciro"] else None, "yuzde", [], "amber",
                        d["kiyas"])
            + _aktif_kart(snap) + "</div>", unsafe_allow_html=True)
        adlar = aktif_dugmeleri(snap)
        if adlar:
            st.markdown('<div class="pp-kb" style="margin-top:2px">Toplam aktif ayrıntısı<span>'
                        'tıkla, rakamı veren sayfaya git</span></div>', unsafe_allow_html=True)
            for c, (k, m, mod, sayfa) in zip(st.columns(max(4, len(adlar))), adlar):
                if c.button(m, key=f"pp_aktif_{k}", use_container_width=True,
                            on_click=sayfaya_git, args=(mod, sayfa)):
                    st.rerun()

        from kayranpm.urun_hesap import tarih_tr
        g1, g2 = st.columns([2.4, 1], gap="medium")
        with g1:
            st.markdown(f'<div class="pp-kb">Günlük ciro ve net kâr<span>{tarih_tr(grafik_bas.isoformat())} – '
                        f'{tarih_tr(bugun.isoformat())} · {len(seri)} gün</span></div>', unsafe_allow_html=True)
            from shared.grafik import goster as _goster
            _goster(_grafik(seri), key="pp_grafik")
        with g2:
            st.markdown(f'<div class="pp-kb">Kanal payı<span>{secim.lower()}</span></div>'
                        + _kanal_html(kanal_payi(_aralikta(rows, d["bas"], d["bit"]), ad_fn=_firma_ad)),
                        unsafe_allow_html=True)

        vk = _veri_kalitesi(bugun.replace(month=1, day=1).isoformat(), bugun.isoformat())
        cipler = [(k, m, s, mod) for k, m, s, mod in (
            ("onarilir", "🔧 {} satışın maliyeti 0 — tek tıkla onarılır", vk.get("onarilir"), "satis"),
            ("ithalatsiz", "🚫 {} satış ithalatsız / eşleşmiyor (%100 marj)", vk.get("ithalatsiz"), "satis"),
            ("eksi_stok", "📉 {} ürün eksi stokta", vk.get("eksi_stok"), "kayranpm")) if s]
        if cipler:
            st.markdown('<div class="pp-kb" style="margin-top:6px">Veri kalitesi<span>kâr ve marjı etkiler · '
                        'tıkla, ilgili sayfaya git</span></div>', unsafe_allow_html=True)
            kol = st.columns(max(3, len(cipler)))          # tek çip tüm satırı kaplamasın
            for c, (k, m, s, mod) in zip(kol, cipler):
                if c.button(m.format(tr_sayi(s)), key=f"pp_vk_{k}", use_container_width=True,
                            on_click=sayfaya_git, args=(mod,)):
                    st.rerun()                     # tam yenileme: modül sayfası açılsın
        try:
            kr = _kritik((bugun - timedelta(days=1)).isoformat())
        except Exception:  # noqa: BLE001
            kr = []
        if kr:
            with st.expander(f"Son 24 saat · {len(kr)} kritik işlem (silme, toplu yükleme, ödeme/satış güncelleme)"):
                st.markdown("".join(
                    f'<div style="display:flex;justify-content:space-between;gap:10px;font-size:12.5px;padding:3px 0">'
                    f'<span><b>{_h.escape(k["kim"])}</b> · {_h.escape(str(k["islem"]))} '
                    f'<span style="color:var(--k-silik)">· {_h.escape(str(k["modul"]))}</span></span>'
                    f'<span style="color:var(--k-silik);white-space:nowrap">{tarih_tr(k["zaman"], saat=True)}</span></div>'
                    for k in kr[:12]), unsafe_allow_html=True)

    _govde()
