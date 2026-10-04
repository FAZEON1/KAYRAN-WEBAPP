# -*- coding: utf-8 -*-
"""Para haritası — sermaye şu an nerede bekliyor? (Ekim 2026, Yönetim › Para haritası)

Soldan sağa paranın mal → alacak → nakit yolu: üretimde · yolda · gümrük / antrepo (ithalat) →
depoda, yaşa göre → müşteri alacağı → banka. Altında borçlar ve net. YALNIZ OKUR; tutarlar
mevcut kaynaklardan (hepsi USD):
  ithalat  → ithalat dosyalarının durumu × kalemlerin net FOB'u (ithalat.database.get_parti_satirlari)
  depo     → bizim stok × paçal, yaş grubu Stok yaşı ile aynı (kayranpm.stok_yasi, FIFO) — kullanıcı
             kararı (Ekim 2026): paçal (KDV'siz); Toplam Aktifler Mikro raporu × 1,20 kullanır
  alacak / cari borç → Toplam Aktifler'e yüklenen cari Excel'i (EUR × 1,10, Toplam Aktifler kuralı)
  banka    → banka bakiyeleri (EUR × 1,08, Banka bakiyeleri kuralı)
  verilen çekler → Firma çekleri, kalan (get_cek_toplamlari)
  bekleyen ödemeler → bilgi olarak (çoğu cari borcun içinde; borçtan ayrıca düşülmez)
Müşteri raflarındaki mal satılmış sayılır (stok_hesap kuralı): alacak kaleminin içindedir.

Saf fonksiyonlar (test edilir): usd, harita, ozet_cumlesi.
"""
EUR_BANKA = 1.08     # kayranacc.banka_ekran.EUR_USD ile aynı
EUR_CARI = 1.10      # Toplam Aktifler'in cari kuralı (kayranacc/main.py)

ITH_ASAMA = [("Üretimde", "Üretimde", ("Üretimde",)), ("Yolda", "Yolda", ("Yolda",)),
             ("Gümrük / antrepo", "Gümrük / antrepo", ("Gümrükte", "Antrepoda"))]
DEPO_ASAMA = [("Depoda · 0–90 gün", ("0–30 gün", "31–60 gün", "61–90 gün")),
              ("Depoda · 91–180 gün", ("91–180 gün",)),
              ("Depoda · 180+ gün", ("180+ gün",))]


def _f(v):
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


def usd(d, kur, eur):
    """{usd, tl, eur} → USD. TL kur yoksa sayılmaz (None döner)."""
    d = d or {}
    tl = _f(d.get("tl"))
    if tl and not kur:
        return None
    return _f(d.get("usd")) + (tl / kur if tl else 0.0) + _f(d.get("eur")) * eur


def _blok(ad, tutar, renk, hedef, alt="", grup=""):
    return {"ad": ad, "tutar": max(_f(tutar), 0.0), "renk": renk, "hedef": hedef, "alt": alt, "grup": grup}


def harita(v, kur):
    """v: {ithalat: {durum: $}, depo: {yaş grubu: $}, alacak: {usd,tl,eur}|None, banka: [satır],
    borc: {usd,tl,eur}|None, cek: (tl, usd), odeme: (tl, usd), alacak_tarih, ...}.
    Döner: {varlik: [blok], borc: [blok], toplam_varlik, toplam_borc, net, mal_pay, depo, yasli, bilgi, eksik}."""
    eksik = []
    varlik = []
    ith = v.get("ithalat") or {}
    for ad, _k, durumlar in ITH_ASAMA:
        varlik.append(_blok(ad, sum(_f(ith.get(d)) for d in durumlar), "mavi", "ithalat/gecmis",
                            "net FOB", "Mal (ithalat)"))
    depo = v.get("depo") or {}
    renk = {"Depoda · 0–90 gün": "yesil", "Depoda · 91–180 gün": "amber", "Depoda · 180+ gün": "kirmizi"}
    for ad, gruplar in DEPO_ASAMA:
        varlik.append(_blok(ad, sum(_f(depo.get(g)) for g in gruplar), renk[ad], "kayranpm/stok_yasi",
                            "stok × paçal", "Mal (depo)"))
    kayitsiz = sum(_f(t) for g, t in depo.items() if g not in {x for _a, gs in DEPO_ASAMA for x in gs})
    if kayitsiz > 0:
        varlik.append(_blok("Depoda · giriş kaydı yok", kayitsiz, "silik", "kayranpm/stok_yasi",
                            "stok × paçal", "Mal (depo)"))
    if v.get("alacak") is None:
        eksik.append("Müşteri alacağı: cari Excel'i yüklenmemiş (Toplam Aktifler › Veri yükle).")
        alacak = 0.0
    else:
        alacak = usd(v["alacak"], kur, EUR_CARI)
        if alacak is None:
            eksik.append("Müşteri alacağının TL kısmı kur bulunamadığı için sayılmadı.")
            alacak = usd(dict(v["alacak"], tl=0), kur, EUR_CARI)
    varlik.append(_blok("Müşteri alacağı", alacak, "mor", "kayranacc/toplam_aktifler",
                        f"cari Excel · {v.get('alacak_tarih') or 'tarih yok'}", "Alacak"))
    b = {"usd": 0.0, "tl": 0.0, "eur": 0.0}
    for r in v.get("banka") or []:
        pb = str(r.get("para_birimi") or "").upper()
        if pb in ("USD", "TL", "EUR"):
            b[pb.lower()] += _f(r.get("bakiye"))
    banka = usd(b, kur, EUR_BANKA)
    if banka is None:
        eksik.append("Bankadaki TL kur bulunamadığı için sayılmadı.")
        banka = usd(dict(b, tl=0), kur, EUR_BANKA)
    varlik.append(_blok("Banka", banka, "cyan", "kayranacc/banka", "bakiyeler", "Nakit"))

    borc = []
    if v.get("borc") is not None:
        cb = usd(v["borc"], kur, EUR_CARI)
        if cb is None:
            eksik.append("Cari borcun TL kısmı kur bulunamadığı için sayılmadı.")
            cb = usd(dict(v["borc"], tl=0), kur, EUR_CARI)
        borc.append(_blok("Cari borç", cb, "kirmizi", "kayranacc/toplam_aktifler",
                          f"cari Excel · {v.get('alacak_tarih') or 'tarih yok'}"))
    cek_tl, cek_usd = (v.get("cek") or (0.0, 0.0))
    cek = usd({"tl": cek_tl, "usd": cek_usd}, kur, 1.0)
    if cek is None:
        eksik.append("Verilen çeklerin TL kısmı kur bulunamadığı için sayılmadı.")
        cek = _f(cek_usd)
    borc.append(_blok("Verilen çekler", cek, "kirmizi2", "kayranacc/cekler", "kalan tutar"))

    tv = sum(x["tutar"] for x in varlik)
    tb = sum(x["tutar"] for x in borc)
    mal = sum(x["tutar"] for x in varlik if x["grup"].startswith("Mal"))
    depo_top = sum(x["tutar"] for x in varlik if x["grup"] == "Mal (depo)")
    yasli = next((x["tutar"] for x in varlik if x["ad"] == "Depoda · 180+ gün"), 0.0)
    o_tl, o_usd = (v.get("odeme") or (0.0, 0.0))
    odeme = usd({"tl": o_tl, "usd": o_usd}, kur, 1.0)
    return {"varlik": varlik, "borc": borc, "toplam_varlik": tv, "toplam_borc": tb, "net": tv - tb,
            "mal_pay": (mal / tv * 100) if tv > 0 else None, "mal": mal, "depo": depo_top, "yasli": yasli,
            "bekleyen_odeme": odeme, "eksik": eksik}


def ozet_cumlesi(h):
    """'Paranızın %62'si mal olarak bekliyor; depodaki 420 binin 90 bini 180 günü geçmiş.'"""
    from shared.tasarim import tr_sayi, para
    if not h["toplam_varlik"]:
        return "Henüz gösterilecek tutar yok."
    p = [f"Varlıklarınızın %{tr_sayi(h['mal_pay'])}'i mal olarak bekliyor: {para(h['mal'])}"]
    if h["depo"] > 0:
        p.append(f"depodaki malın %{tr_sayi(h['yasli'] / h['depo'] * 100)}'i ({para(h['yasli'])}) 180 günü geçmiş"
                 if h["yasli"] > 0 else "depodaki malın hiçbiri 180 günü geçmemiş")
    return "; ".join(p) + "."


# ── Veri (mevcut okuma fonksiyonları) ───────────────────────────────
def _kur():
    try:
        import streamlit as st
        k = _f(st.session_state.get("kur"))
        if k > 1:
            return k
    except Exception:  # noqa: BLE001
        pass
    try:
        from kayranacc.database import get_kur
        return _f(get_kur()) or None
    except Exception:  # noqa: BLE001
        return None


def veri_topla():
    """Kaynakları okur (her biri ayrı denenir; okunamayan kalem 0 ve eksiklere not)."""
    v, notlar = {}, []
    try:
        from ithalat.database import get_dosyalar, get_parti_satirlari, IN_TRANSIT_DURUMLAR
        durum = {d.get("id"): str(d.get("durum") or "") for d in get_dosyalar() or []}
        ith = {}
        for r in get_parti_satirlari() or []:
            d = durum.get(r.get("dosya_id"), "")
            if d in IN_TRANSIT_DURUMLAR:
                ith[d] = ith.get(d, 0.0) + _f(r.get("adet")) * _f(r.get("fob"))
        v["ithalat"] = ith
    except Exception as e:  # noqa: BLE001
        notlar.append(f"İthalat okunamadı ({type(e).__name__}).")
    try:
        from satis.database import get_pacal_map
        from kayranpm.stok_yasi import hesapla
        from kayranpm.stok_yasi_ekran import _grup_degerleri
        v["depo"] = _grup_degerleri(hesapla().get("bizim") or {}, get_pacal_map() or {})
    except Exception as e:  # noqa: BLE001
        notlar.append(f"Depo stoğu okunamadı ({type(e).__name__}).")
    try:
        from kayranacc.database import aktif_excel_oku, aktif_excel_meta_oku
        cari = aktif_excel_oku("_SHARED_", "cari")
        if isinstance(cari, dict) and "borc" in cari:
            v["alacak"], v["borc"] = cari.get("alacak") or {}, cari.get("borc") or {}
        elif isinstance(cari, (list, tuple)) and len(cari) == 3:       # eski biçim: yalnız borç
            v["alacak"], v["borc"] = None, {"usd": cari[0], "tl": cari[1], "eur": cari[2]}
        else:
            v["alacak"], v["borc"] = None, None
        m = aktif_excel_meta_oku("cari") or {}
        v["alacak_tarih"] = str(m.get("yukleme_zamani") or "")[:10]
    except Exception as e:  # noqa: BLE001
        v["alacak"], v["borc"] = None, None
        notlar.append(f"Cari Excel okunamadı ({type(e).__name__}).")
    try:
        from kayranacc.database import get_bankalar
        v["banka"] = get_bankalar() or []
    except Exception as e:  # noqa: BLE001
        notlar.append(f"Banka bakiyeleri okunamadı ({type(e).__name__}).")
    try:
        from kayranacc.database import get_cek_toplamlari
        t = get_cek_toplamlari()
        v["cek"] = (_f(t[0]), _f(t[1]))
    except Exception as e:  # noqa: BLE001
        notlar.append(f"Çekler okunamadı ({type(e).__name__}).")
    try:
        from kayranacc.database import get_tum_odemeler
        bek = [o for o in get_tum_odemeler() or [] if str(o.get("durum") or "") != "odendi"]
        v["odeme"] = (sum(_f(o.get("tutar_tl")) for o in bek), sum(_f(o.get("tutar_usd")) for o in bek))
    except Exception:  # noqa: BLE001
        pass
    return v, notlar


# ── Ekran ───────────────────────────────────────────────────────────
CSS = """<style>
.ph-oz{font-size:15px;color:var(--k-metin);margin:2px 0 14px;line-height:1.5}
.ph-grup{font-size:11.5px;color:var(--k-silik);margin:10px 0 6px;letter-spacing:.2px}
.ph-cubuk{display:flex;height:22px;border-radius:7px;overflow:hidden;background:var(--k-ortu2);margin:0 0 10px;gap:2px}
.ph-cubuk i{display:block;height:100%;min-width:3px}
.ph-b{border-left:3px solid var(--d,var(--k-mor));padding:2px 0 2px 10px;min-height:62px}
.ph-b .a{font-size:12px;color:var(--k-soluk);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.ph-b .t{font-size:17px;font-weight:600;color:var(--k-metin);font-variant-numeric:tabular-nums;margin-top:2px}
.ph-b .s{font-size:11px;color:var(--k-silik);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.ph-net{display:flex;gap:28px;flex-wrap:wrap;margin:14px 0 4px;font-size:13px;color:var(--k-soluk)}
.ph-net b{font-size:18px;color:var(--k-metin);font-variant-numeric:tabular-nums;margin-left:6px}
</style>"""


def _git(hedef):
    from shared.palet import git
    git(hedef)


def cubuk_html(bloklar, olcek):
    """Orantılı tek çubuk: her parça tutarı / ölçek kadar geniş (fare üstünde ad ve tutar)."""
    import html as _h
    from shared.tasarim import para, tr_sayi
    if not olcek:
        return ""
    parca = ""
    for b in bloklar:
        if b["tutar"] <= 0.5:
            continue
        w = b["tutar"] / olcek * 100
        parca += (f'<i style="width:{w:.3f}%;background:var(--k-{b["renk"]})" '
                  f'title="{_h.escape(b["ad"])} · {para(b["tutar"])} · %{tr_sayi(w, 1)}"></i>')
    return f'<div class="ph-cubuk">{parca}</div>'


def _kartlar(bloklar, anahtar, olcek, sutun=5):
    """Eşit genişlikte tıklanır kartlar (okunur); tıklanınca ilgili sayfa."""
    import streamlit as st
    from shared import bilesen as B
    from shared.tasarim import para, tr_sayi
    goster = [b for b in bloklar if b["tutar"] > 0.5]
    if not goster:
        st.caption("Tutar yok.")
        return
    for i in range(0, len(goster), sutun):
        for c, b in zip(st.columns(sutun, gap="small"), goster[i:i + sutun]):
            pay = f" · %{tr_sayi(b['tutar'] / olcek * 100)}" if olcek else ""
            with c:
                B.tiklanir(f"ph_{anahtar}_{b['ad']}",
                           f'<div class="ph-b" style="--d:var(--k-{b["renk"]})"><div class="a">{b["ad"]}</div>'
                           f'<div class="t">{para(b["tutar"])}</div><div class="s">{b["alt"]}{pay}</div></div>',
                           _git, (b["hedef"],), tur="kart", renk=b["renk"], etiket=f"{b['ad']} sayfasını aç")


def sayfa():
    import streamlit as st
    from shared.tasarim import baslik, para
    st.markdown(baslik(":material/account_tree: Yönetim", "Para haritası",
                       aciklama="Sermayeniz şu an nerede bekliyor · tüm tutarlar USD · tıklayınca ilgili sayfa"),
                unsafe_allow_html=True)
    st.markdown(CSS, unsafe_allow_html=True)
    from shared.islem import bekle
    with bekle("Para haritası hazırlanıyor"):
        v, notlar = veri_topla()
        kur = _kur()
        h = harita(v, kur)
    st.markdown(f'<div class="ph-oz">{ozet_cumlesi(h)}</div>', unsafe_allow_html=True)
    tv = h["toplam_varlik"]
    st.markdown('<div class="ph-grup">VARLIKLAR · mal → alacak → nakit</div>' + cubuk_html(h["varlik"], tv),
                unsafe_allow_html=True)
    _kartlar(h["varlik"], "v", tv)
    st.markdown('<div class="ph-grup">BORÇLAR · varlıklara oranla</div>' + cubuk_html(h["borc"], tv),
                unsafe_allow_html=True)
    _kartlar(h["borc"], "b", tv)
    st.markdown(f'<div class="ph-net"><span>Varlıklar<b>{para(h["toplam_varlik"])}</b></span>'
                f'<span>Borçlar<b>{para(h["toplam_borc"])}</b></span>'
                f'<span>Net<b>{para(h["net"])}</b></span></div>', unsafe_allow_html=True)
    alt = ["Depo: bizim stok × paçal (KDV'siz); Toplam Aktifler Mikro raporu × 1,20 kullandığı için "
           "rakamlar farklıdır. İthalat: yoldaki malın net FOB değeri (tedarikçiye ödenip ödenmediği "
           "sistemde tutulmuyor). Müşteri raflarındaki mal satılmıştır, alacağın içindedir."]
    if h.get("bekleyen_odeme"):
        alt.append(f"Bekleyen ödemeler {para(h['bekleyen_odeme'])} — çoğu cari borcun içinde olduğu için "
                   f"borçtan ayrıca düşülmedi.")
    if kur:
        from shared.tasarim import tr_sayi
        alt.append(f"Kur ₺{tr_sayi(kur, 2)}.")
    for n in notlar + h["eksik"]:
        st.caption(n)
    st.caption(" ".join(alt))

