# -*- coding: utf-8 -*-
"""Ref No Takibi — ekran (Ürün Yönetimi › Ref No Takibi).

YAPI
  Başlık        : + Yeni ref no · Firmalar
  Görünüm       : Ref No'lar | Alınan destekler
  Ref No'lar    : solda FİRMA RAYI (tümü + her firma: ref sayısı, bekleyen rozeti)
                  sağda özet (bekleyen / paylaşılan / toplam ≈ USD) · durum ·
                  arama · filtre · Liste | Tablo
  Liste         : DÖNEME göre gruplu (en yeni ay üstte), satırın tamamı tıklanır
  Detay         : tek tıkla "Paylaşıldı" · ref no'yu kopyala · bilgileri düzenle ·
                  kalemler · sil (onaylı)
  Tablo         : seçili firmada toplu düzenleme + Excel içe aktarma (eski,
                  kanıtlanmış editör: ref_no._render_refler)

Veri ve iş kuralları ref_no.py'de (değişmedi); rakamlar ref_hesap.py'de (testli).
"""
import html as _h

import streamlit as st

from shared.tasarim import baslik, css_tek_satir, kpi_serit, mesaj, bos_durum, rv, sayi, tr_sayi
from shared.utils import firma_kisa_ad
from shared import bilesen as B
from . import ref_hesap as R
from . import ref_no as N


# ════════════════════════════════════════════════════════════════════
def _usd(v):
    return "—" if v is None else sayi(v, "$")


def _tutar(r):
    d = R.doviz(r)
    return f"{R.SEMBOL.get(d, d + ' ')}{tr_sayi(R._f(r.get('tutar')), 2)}"


def _kurlar():
    try:
        tl = N._alinan_kur()
    except Exception:  # noqa: BLE001
        tl = None
    return N._eur_usd_kur(), tl


def _veri(firmalar):
    hepsi = []
    for f in firmalar:
        for r in N.get_refler(f["id"]) or []:
            x = dict(r)
            x["_firma"] = f.get("firma_adi", "") or ""
            x["_fid"] = f["id"]
            x["_fkod"] = f.get("firma_kodu", "") or ""
            hepsi.append(x)
    return hepsi


def _ac(rid):
    B.detay_ac("ref", rid)


def _firma_sec(fid):
    st.session_state["ref_firma_id"] = fid
    st.session_state["ref_mod"] = "Liste"


def _yenile(rid=None, metin=None):
    B.yenile(metin, ac=("ref", rid) if rid else None)


# ════════════════════════════════════════════════════════════════════
def _css():
    return "<style>" + css_tek_satir("""
/* Firma rayı */
.st-key-ref_ray{gap:2px !important;}
.st-key-ref_ray > [data-testid="stElementContainer"] [data-testid="stMarkdownContainer"]{margin-bottom:0 !important;}
.rf-f{display:flex;align-items:center;gap:8px;min-width:0;}
.rf-f-ad{flex:1;min-width:0;font-size:13px;font-weight:600;color:var(--k-metin);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
.rf-f-alt{display:flex;gap:6px;align-items:center;margin-top:2px;font-size:11.5px;color:var(--k-silik);}
.rf-kod{font-family:var(--k-mono);font-size:11px;color:var(--k-soluk);}
.rf-rozet{flex-shrink:0;font-size:11px;font-weight:650;line-height:1;padding:3px 7px;border-radius:999px;
  color:var(--k-amber);background:color-mix(in srgb,var(--k-amber) 14%,transparent);}
.rf-ray-bas{font-size:11.5px;font-weight:600;color:var(--k-silik);margin:2px 10px 4px;}
/* Dönem grubu + satır */
.rf-s{display:grid;grid-template-columns:150px minmax(0,1fr) auto;gap:4px 16px;align-items:center;}
.rf-no{font-family:var(--k-mono);font-size:12.5px;font-weight:600;color:var(--k-mor2);letter-spacing:.2px;}
.rf-durum{display:flex;align-items:center;gap:6px;font-size:11.5px;font-weight:600;color:var(--d);margin-top:2px;}
.rf-durum::before{content:"";width:6px;height:6px;border-radius:50%;background:var(--d);}
.rf-ack{min-width:0;font-size:13px;color:var(--k-metin);line-height:1.35;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
.rf-s .k-meta{margin-top:4px;font-size:11.5px;}
.rf-s .k-cip{padding:2px 7px;}
.rf-tut{text-align:right;white-space:nowrap;}
.rf-tut b{display:block;font-family:var(--k-mono);font-variant-numeric:tabular-nums;font-size:14px;font-weight:600;color:var(--k-metin);}
.rf-tut small{font-size:11.5px;color:var(--k-silik);}
/* Detay */
.rf-dt{display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin:-4px 0 4px;}
.rf-dt .rf-no{font-size:20px;font-weight:650;color:var(--k-metin);}
.rf-dt-ust{font-size:13px;color:var(--k-soluk);margin-bottom:12px;}
.rf-dt .k-ikon{font-size:18px;}
@media (max-width:640px){ .rf-s{grid-template-columns:minmax(0,1fr) auto;} .rf-s > div:first-child{grid-column:1 / -1;} }
""") + "</style>"


def _satir_html(r, firma_goster, eur=None, tl=None):
    d = r.get("durum") or "beklemede"
    kat = "".join(B.cip(k.capitalize()) for k in R.kategoriler(r)[:3])
    fr = (f'<span>{_h.escape(firma_kisa_ad(r.get("_firma")))}</span>' if firma_goster else "")
    parca = [x.strip() for x in str(r.get("aciklama") or "").split("·") if x.strip()]
    kalem = f"<span>{len(parca)} kalem</span>" if len(parca) > 1 else ""
    return (f'<div class="rf-s" style="--d:{rv(R.DURUM_RENK.get(d, "silik"))}">'
            f'<div><div class="rf-no">{_h.escape(str(r.get("ref_no") or "—"))}</div>'
            f'<div class="rf-durum">{R.DURUM_AD.get(d, d)}</div></div>'
            f'<div style="min-width:0"><div class="rf-ack" title="{_h.escape(" · ".join(parca), quote=True)}">'
            f'{_h.escape(" · ".join(parca) or "—")}</div>'
            f'<div class="k-meta">{kat}<span>{R.donem_metni(r)}</span>{fr}{kalem}</div></div>'
            f'<div class="rf-tut"><b>{_tutar(r)}</b><small>{_usd_alt(r, eur, tl)}</small></div></div>')


def _usd_alt(r, eur, tl):
    d = R.doviz(r)
    if d == "USD":
        return "USD"
    v = R.usd(r.get("tutar"), d, eur, tl)
    return f"≈ {sayi(v, '$')}" if v is not None else f"{d} · kur yok"


# ════════════════════════════════════════════════════════════════════
def render():
    st.markdown(_css(), unsafe_allow_html=True)
    if not st.session_state.get("_ref_senk3"):
        try:
            N._senkronize_firmalar()
        except Exception as e:  # noqa: BLE001
            from shared.hata_log import kaydet
            kaydet("ref.senkron", e)
        st.session_state["_ref_senk3"] = True
    firmalar = N.get_firmalar() or []

    h1, h2, h3 = st.columns([5.0, 1.15, 1.45], vertical_alignment="center")
    h1.markdown(baslik("🔗 Ürün Yönetimi", "Ref No Takibi",
                       aciklama="Firmalara verdiğimiz destek ref numaraları ve bize gelen destekler."),
                unsafe_allow_html=True)
    if h2.button("Firmalar", icon=":material/domain:", use_container_width=True, key="ref_firmalar_btn",
                 help="Firma ekle, ref kodunu düzenle, sil"):
        _firmalar_dialog(firmalar)
    if h3.button("Yeni ref no", type="primary", icon=":material/add:", use_container_width=True,
                 key="ref_yeni_btn", disabled=not firmalar):
        _yeni_dialog(firmalar)

    gor = st.segmented_control("Görünüm", ["Ref No'lar", "Alınan destekler"], default="Ref No'lar",
                               key="ref_gorunum", label_visibility="collapsed") or "Ref No'lar"
    if gor == "Alınan destekler":
        st.caption("Üretici ve markalardan bize gelen sellout, marketing, rebate gelirleri; "
                   "Satış P&L ve Yönetim'de kâra gelir olarak eklenir.")
        _alinan_gorunum()
        return
    if not firmalar:
        st.markdown(bos_durum("Henüz firma yok", "Sağ üstteki 'Firmalar' ile ilk firmayı ekle "
                              "(örn. VATAN · kod VTN); ref numaraları bu koddan üretilir.", "domain"),
                    unsafe_allow_html=True)
        return

    hepsi = _veri(firmalar)
    fmap = {f["id"]: f for f in firmalar}
    fid = st.session_state.get("ref_firma_id", 0)
    if fid and fid not in fmap:
        fid = st.session_state["ref_firma_id"] = 0
    kapsam = [r for r in hepsi if not fid or r["_fid"] == fid]

    sol, sag = st.columns([1.05, 3.3], gap="medium")
    with sol:
        _firma_rayi(firmalar, hepsi, fid)
    with sag:
        _sag_panel(kapsam, fmap.get(fid), hepsi)

    _sec = B.detay_istendi("ref")
    if _sec:
        r = next((x for x in hepsi if x.get("id") == _sec), None)
        if r:
            _detay_dialog(r, firmalar)


def _firma_rayi(firmalar, hepsi, fid):
    oz = R.firma_ozet(hepsi)
    tum_bek = sum(o["beklemede"] for o in oz.values())
    with st.container(key="ref_ray"):
        st.markdown('<div class="rf-ray-bas">Firmalar</div>', unsafe_allow_html=True)
        sira = [(0, "Tüm firmalar", "", len(hepsi), tum_bek)] + sorted(
            [(f["id"], firma_kisa_ad(f.get("firma_adi")), f.get("firma_kodu", ""),
              oz.get(f["id"], {}).get("adet", 0), oz.get(f["id"], {}).get("beklemede", 0)) for f in firmalar],
            key=lambda x: (-x[4], x[1]))
        for i, ad, kod, adet, bek in sira:
            roz = f'<span class="rf-rozet" title="beklemede">{bek}</span>' if bek else ""
            kod_h = f'<span class="rf-kod">{_h.escape(kod)}</span>·' if kod else ""
            B.tiklanir(f"reff{i}", f'<div class="rf-f"><div style="min-width:0;flex:1"><div class="rf-f-ad">{_h.escape(ad)}</div>'
                                   f'<div class="rf-f-alt">{kod_h}<span>{adet} ref</span></div></div>{roz}</div>',
                       _firma_sec, (i,), tur="ray", secili=(i == fid), etiket=f"{ad} seç")


def _sag_panel(kapsam, firma, hepsi):
    eur, tl = _kurlar()
    bek = [r for r in kapsam if (r.get("durum") or "beklemede") == "beklemede"]
    pay = [r for r in kapsam if r.get("durum") == "paylasildi"]
    t_bek, t_pay = R.toplam(bek, eur, tl), R.toplam(pay, eur, tl)
    t_all = R.toplam([r for r in kapsam if r.get("durum") != "iptal"], eur, tl)
    ham = " · ".join(f"{R.SEMBOL.get(d, d)}{sayi(v)}" for d, v in sorted(t_all["ham"].items(), key=lambda x: -x[1]) if v)
    st.markdown(kpi_serit([
        {"etiket": "Beklemede", "deger": tr_sayi(len(bek)), "renk": "amber" if bek else "silik",
         "alt": f"≈ {_usd(t_bek['usd'])} paylaşılmayı bekliyor" if bek else "paylaşılmamış ref yok"},
        {"etiket": "Paylaşıldı", "deger": tr_sayi(len(pay)), "renk": "yesil", "alt": f"≈ {_usd(t_pay['usd'])}"},
        {"etiket": "Toplam (USD karşılığı)", "deger": _usd(t_all["usd"]), "renk": "mor",
         "alt": ham or "—", "ipucu": "İptaller hariç. TL kayıtlı günlük kurla, EUR güncel kurla çevrildi."},
    ]), unsafe_allow_html=True)
    if t_all["cevrilmeyen"]:
        st.markdown(mesaj("uyari", "Kur bulunamadığı için USD toplamına katılmayan: " + " · ".join(
            f"{R.SEMBOL.get(d, d)}{tr_sayi(v)}" for d, v in t_all["cevrilmeyen"].items())), unsafe_allow_html=True)

    say = {d: sum(1 for r in kapsam if (r.get("durum") or "beklemede") == d) for d in R.DURUMLAR}
    secenek = [f"Tümü ({len(kapsam)})"] + [f"{R.DURUM_AD[d]} ({say[d]})" for d in R.DURUMLAR]
    c1, c4 = st.columns([3.6, 1.2], vertical_alignment="bottom")
    with c1:
        _s = st.segmented_control("Durum", secenek, default=secenek[0], key="ref_durum_sec",
                                  label_visibility="collapsed") or secenek[0]
    durum = (["tumu"] + R.DURUMLAR)[secenek.index(_s)] if _s in secenek else "tumu"
    c2, c3 = st.columns([3.6, 1.2], vertical_alignment="bottom")
    ara = c2.text_input("Ara", key="ref_ara", placeholder="Ref no, açıklama, kategori, tutar…",
                        label_visibility="collapsed")
    katlar = sorted({k for r in kapsam for k in R.kategoriler(r)})
    yillar = sorted({R.donem(r)[:4] for r in kapsam if R.donem(r)}, reverse=True)
    _f = B.filtre(c3, [
        {"etiket": "Kategori", "secenekler": katlar, "key": "ref_f_kat",
         "format_func": lambda x: x if x == "Tümü" else x.capitalize()},
        {"etiket": "Yıl", "secenekler": yillar, "key": "ref_f_yil"}])
    f_kat, f_yil = _f["ref_f_kat"], _f["ref_f_yil"]
    with c4:
        mod = st.segmented_control("Görünüm modu", ["Liste", "Tablo"], default="Liste", key="ref_mod",
                                   label_visibility="collapsed", disabled=firma is None,
                                   help=None if firma else "Tablo düzenleme için soldan bir firma seç") or "Liste"

    if firma is not None:
        siradaki = N.ref_uret(firma.get("firma_kodu", ""), N._yil(), N._sonraki_sira(firma["id"]))
        st.caption(f"{firma.get('firma_adi','')} · ref kodu {firma.get('firma_kodu','')} · sıradaki numara {siradaki}")

    if mod == "Tablo" and firma is not None:
        st.caption("Toplu düzenleme: hücreleri değiştir, 'Değişiklikleri kaydet'e bas. Excel içe aktarma ve "
                   "toplu silme de burada.")
        N._render_refler(firma["id"], firma.get("firma_kodu", ""))
        return

    liste = R.filtrele(kapsam, durum, f_kat, f_yil, ara)
    if not liste:
        st.markdown(bos_durum("Bu görünümde ref yok" if kapsam else "Bu firmada henüz ref yok",
                              "Filtreyi ya da aramayı değiştir." if kapsam else
                              "Sağ üstteki 'Yeni ref no' ile ilk numarayı ata ya da Tablo görünümünden "
                              "Excel içe aktar.", "receipt_long"), unsafe_allow_html=True)
        return
    limit = int(st.session_state.get("ref_limit", 60))
    gosterilen = 0
    for d, grup in R.grupla(liste):
        if gosterilen >= limit:
            break
        tg = R.toplam([r for r in grup if r.get("durum") != "iptal"], eur, tl)
        st.markdown(B.grup_basligi(R.donem_adi(d), f"{len(grup)} ref · ≈ {_usd(tg['usd'])}"),
                    unsafe_allow_html=True)
        for r in grup[:max(0, limit - gosterilen)]:
            B.tiklanir(f"ref{r['id']}", _satir_html(r, firma is None, eur, tl), _ac, (r["id"],), tur="satir",
                       renk=R.DURUM_RENK.get(r.get("durum") or "beklemede", "silik"),
                       etiket=f"{r.get('ref_no','')} detay")
            gosterilen += 1
    if len(liste) > gosterilen:
        if st.button(f"Daha fazla göster ({len(liste) - gosterilen} ref daha)", key="ref_daha",
                     use_container_width=True, type="tertiary"):
            st.session_state["ref_limit"] = limit + 60
            st.rerun(scope="fragment")


# ════════════════════════════════════════════════════════════════════
# Detay
# ════════════════════════════════════════════════════════════════════
@st.dialog("Ref no detayı", width="large")
def _detay_dialog(r, firmalar):
    rid, d = r["id"], (r.get("durum") or "beklemede")
    st.markdown(_css() + f'<div class="rf-dt" style="--d:{rv(R.DURUM_RENK.get(d, "silik"))}">'
                f'<span class="rf-no">{_h.escape(str(r.get("ref_no") or ""))}</span>'
                f'<span class="rf-durum" style="font-size:13px">{R.DURUM_AD.get(d, d)}</span></div>'
                f'<div class="rf-dt-ust">{_h.escape(r.get("_firma", ""))} · {R.donem_metni(r)} · '
                f'<b style="color:var(--k-metin)">{_tutar(r)}</b></div>', unsafe_allow_html=True)

    # Tek tık durum + kopyalanabilir numara
    a1, a2, a3 = st.columns([1.6, 1.2, 2.2], vertical_alignment="center")
    if d == "beklemede":
        if a1.button("Paylaşıldı olarak işaretle", type="primary", icon=":material/check_circle:",
                     use_container_width=True, key=f"ref_pay_{rid}"):
            _durum_yaz(r, "paylasildi")
            _yenile(rid, f"{r.get('ref_no')} paylaşıldı olarak işaretlendi")
    else:
        if a1.button("Beklemeye al", icon=":material/undo:", use_container_width=True, key=f"ref_bek_{rid}"):
            _durum_yaz(r, "beklemede")
            _yenile(rid, f"{r.get('ref_no')} beklemeye alındı")
    if d != "iptal":
        if a2.button("İptal et", icon=":material/block:", use_container_width=True, key=f"ref_ipt_{rid}"):
            _durum_yaz(r, "iptal")
            _yenile(rid, f"{r.get('ref_no')} iptal edildi")
    with a3:
        st.code(str(r.get("ref_no") or ""), language=None)

    t1, t2 = st.tabs(["Bilgiler", "Kalemler"])
    with t1:
        _bilgi_formu(r)
    with t2:
        st.caption("Kalem girersen tutar, aylık kırılım ve kategori dağılımı kalemlerden hesaplanır.")
        N.kalem_yonet_paneli(r, r.get("_firma", ""))


def _durum_yaz(r, yeni):
    from datetime import date
    pay = str(date.today()) if yeni == "paylasildi" else (r.get("paylasim_tarihi") if yeni == "iptal" else None)
    N.ref_guncelle(r["id"], r.get("ref_no"), r.get("aciklama"), yeni, (str(r.get("tarih") or "")[:10] or None), pay)


def _bilgi_formu(r):
    import json
    rid = r["id"]
    kat_opts = N._kategori_listesi([r])
    kat_cur = (R.kategoriler(r) or [""])[0]
    a = sorted(R.aylik(r))
    tek_ay = len(a) <= 1
    with st.form(f"ref_bilgi_{rid}", border=False):
        ack = st.text_input("Açıklama", value=r.get("aciklama") or "")
        b1, b2, b3 = st.columns([1.4, 1, 1.4])
        tutar = b1.number_input("Tutar", min_value=0.0, step=100.0, format="%.2f", value=float(R._f(r.get("tutar"))))
        dvz = b2.selectbox("Döviz", N.DOVIZLER, index=N.DOVIZLER.index(R.doviz(r)) if R.doviz(r) in N.DOVIZLER else 0)
        kat = b3.selectbox("Kategori", ["—"] + kat_opts,
                           index=(kat_opts.index(kat_cur) + 1) if kat_cur in kat_opts else 0,
                           disabled=len(R.kategoriler(r)) > 1,
                           help="Çok kategorili kayıtta kategori Kalemler sekmesinden yönetilir"
                           if len(R.kategoriler(r)) > 1 else None)
        c1, c2, c3 = st.columns([1.2, 1, 1.8])
        _ay0 = int(a[0][5:7]) if a else 0
        ay = c1.selectbox("Dönem ayı", list(range(0, 13)), index=_ay0,
                          format_func=lambda m: "—" if m == 0 else R.AY_AD[m], disabled=not tek_ay,
                          help=None if tek_ay else "Çok aylı kayıt; dönemler Kalemler sekmesinden yönetilir")
        yil = c2.number_input("Yıl", min_value=2020, max_value=2100, step=1,
                              value=int(a[0][:4]) if a else int(r.get("yil") or N._yil()), disabled=not tek_ay)
        ref_no = c3.text_input("Ref no", value=r.get("ref_no") or "",
                               help="Yalnız bozuk numarayı düzeltmek için. Aynı firmada tekrar edemez.")
        if st.form_submit_button("Kaydet", type="primary", icon=":material/save:"):
            ref_no = ref_no.strip()
            diger = {str(x.get("ref_no") or "").strip().upper() for x in N.get_refler(r["_fid"]) if x["id"] != rid}
            if not ref_no:
                st.error("Ref no boş olamaz.")
            elif ref_no.upper() in diger:
                st.error(f"{ref_no} bu firmada zaten kullanılıyor.")
            elif not ack.strip():
                st.error("Açıklama boş olamaz.")
            else:
                aylik = None
                if tek_ay:
                    aylik = json.dumps({f"{int(yil)}-{ay:02d}": tutar}) if ay else ""
                N.ref_guncelle(rid, ref_no, ack.strip(), r.get("durum") or "beklemede",
                               (str(r.get("tarih") or "")[:10] or None), r.get("paylasim_tarihi"),
                               tutar=tutar, doviz=dvz,
                               kategori=(None if len(R.kategoriler(r)) > 1 else ("" if kat == "—" else kat)),
                               aylik=aylik)
                _yenile(rid, "Ref kaydedildi")
    with st.expander("Sil", icon=":material/delete:"):
        if B.onayli_sil(f"Evet, {r.get('ref_no')} kaydını sil", key=f"ref_{rid}", dugme="Ref'i sil",
                        aciklama="Ref kaydı kalıcı olarak silinir; numara tekrar kullanılmaz."):
            N.ref_sil(rid)
            st.session_state.pop("_ref_sec", None)
            _yenile(None, f"{r.get('ref_no')} silindi")


# ════════════════════════════════════════════════════════════════════
# Yeni ref no
# ════════════════════════════════════════════════════════════════════
@st.dialog("Yeni ref no", width="large")
def _yeni_dialog(firmalar):
    from datetime import date
    fmap = {f["id"]: f for f in firmalar}
    vars_ = st.session_state.get("ref_firma_id") or None
    ids = [f["id"] for f in sorted(firmalar, key=lambda f: firma_kisa_ad(f.get("firma_adi")))]
    fid = st.selectbox("Firma", ids, index=ids.index(vars_) if vars_ in ids else None,
                       placeholder="Firma seç…", format_func=lambda i: firma_kisa_ad(fmap[i].get("firma_adi")),
                       key="ref_yeni_firma")
    if not fid:
        st.caption("Numara firmanın ref kodundan üretilir: FZ + kod + RF + yıl + sıra.")
        return
    f = fmap[fid]
    siradaki = N.ref_uret(f.get("firma_kodu", ""), N._yil(), N._sonraki_sira(fid))
    st.markdown(f'<div style="display:flex;align-items:baseline;gap:10px;margin:2px 0 10px">'
                f'<span style="font-size:12.5px;color:var(--k-soluk)">Atanacak numara</span>'
                f'<span style="font-family:var(--k-mono);font-size:22px;font-weight:650;color:var(--k-mor2)">'
                f'{_h.escape(siradaki)}</span></div>', unsafe_allow_html=True)
    with st.form("ref_yeni_form", border=False):
        ack = st.text_input("Açıklama", placeholder="örn. EYLÜL MONİTÖR SELLOUT")
        b1, b2, b3 = st.columns([1.4, 1, 1.4])
        tutar = b1.number_input("Tutar", min_value=0.0, step=100.0, format="%.2f")
        dvz = b2.selectbox("Döviz", N.DOVIZLER)
        kat = b3.selectbox("Kategori", N._kategori_listesi(N.get_refler(fid)), index=None, placeholder="Seç…")
        c1, c2, c3 = st.columns(3)
        ay = c1.selectbox("Dönem ayı", list(range(1, 13)), index=date.today().month - 1,
                          format_func=lambda m: R.AY_AD[m])
        yil = c2.number_input("Yıl", min_value=2020, max_value=2100, step=1, value=date.today().year)
        durum = c3.selectbox("Durum", R.DURUMLAR[:2], format_func=lambda x: R.DURUM_AD[x])
        if st.form_submit_button(f"{siradaki} numarasını ata", type="primary", icon=":material/add:"):
            if not ack.strip():
                st.error("Açıklama gerekli; boş ref no atanmaz.")
            else:
                ok, msg = N.ref_ekle(fid, f.get("firma_kodu", ""), ack.strip(), durum, date.today(),
                                     tutar=tutar, doviz=dvz, kategori=kat or "", donem_ay=ay, donem_yil=int(yil))
                if ok:
                    st.cache_data.clear()
                    yeni = next((x for x in N.get_refler(fid) if x.get("ref_no") == siradaki), None)
                    st.session_state["ref_firma_id"] = fid
                    _yenile(yeni["id"] if yeni else None, f"{siradaki} atandı")
                else:
                    st.error(msg)


# ════════════════════════════════════════════════════════════════════
# Firmalar (ekle · düzenle · sil) — eski iki pencere tek pencerede
# ════════════════════════════════════════════════════════════════════
@st.dialog("Firmalar", width="large")
def _firmalar_dialog(firmalar):
    t1, t2 = st.tabs(["Yeni firma", "Düzenle / sil"])
    with t1:
        cariler = sorted(set(N._cari_isimleri()), key=lambda s: s.lower())
        mevcut = {N._norm(f.get("firma_adi")) for f in firmalar}
        secilebilir = [c for c in cariler if N._norm(c) not in mevcut]
        elle = st.toggle("Firma adını elle yaz", value=not secilebilir, key="ref_firma_elle")
        with st.form("ref_firma_ekle_f", border=False):
            if secilebilir and not elle:
                ad = st.selectbox("Firma (cari listesinden)", secilebilir, index=None, placeholder="Seç…") or ""
            else:
                ad = st.text_input("Firma adı", placeholder="örn. VATAN BİLGİSAYAR")
            kod = st.text_input("Ref kodu", placeholder="örn. VTN", max_chars=6,
                                help="2-6 harf/rakam. FZ<KOD>RF<yıl><sıra> — 'FZ' ve 'RF' otomatik eklenir.")
            if st.form_submit_button("Firmayı ekle", type="primary", icon=":material/add:"):
                if not ad.strip() or not kod.strip():
                    st.error("Firma ve ref kodu gerekli.")
                else:
                    ok, msg = N.firma_ekle(ad, kod)
                    if ok:
                        _yenile(None, msg)
                    else:
                        st.error(msg)
    with t2:
        if not firmalar:
            st.caption("Kayıtlı firma yok.")
            return
        f = st.selectbox("Firma", firmalar, key="ref_fy_sec",
                         format_func=lambda x: f"{firma_kisa_ad(x.get('firma_adi'))} · {x.get('firma_kodu','')}")
        gecerli, msg = N.kod_dogrula(f.get("firma_kodu", ""))
        if not gecerli:
            st.markdown(mesaj("hata", f"Bu firmanın ref kodu bozuk: {msg}"), unsafe_allow_html=True)
        with st.form(f"ref_fy_form_{f['id']}", border=False):
            y1, y2 = st.columns([2.2, 1])
            yad = y1.text_input("Firma adı", value=f.get("firma_adi") or "")
            ykod = y2.text_input("Ref kodu", value=f.get("firma_kodu") or "")
            st.caption(f"Örnek numara: {N.ref_uret(ykod.strip() or f.get('firma_kodu',''), N._yil(), 1)}")
            if st.form_submit_button("Kaydet", type="primary", icon=":material/save:"):
                ok, m = N.firma_guncelle(f["id"], yad, ykod)
                if ok:
                    _yenile(None, m)
                else:
                    st.error(m)
        adet = N.firma_ref_sayisi(f["id"])
        st.divider()
        st.markdown(f"**Firmayı sil** · bağlı {adet} ref")
        refsil = st.checkbox(f"Bağlı {adet} ref'i de sil", key="ref_fy_refsil", disabled=not adet)
        onay = st.checkbox(f"Evet, {firma_kisa_ad(f.get('firma_adi'))} firmasını sil", key="ref_fy_onay")
        if st.button("Firmayı sil", icon=":material/delete:", disabled=not onay or (adet and not refsil),
                     key="ref_fy_sil"):
            ok, m = N.firma_sil(f["id"], refleri_de_sil=refsil)
            if ok:
                st.session_state["ref_firma_id"] = 0
                _yenile(None, m)
            else:
                st.error(m)


# ════════════════════════════════════════════════════════════════════
# Alınan destekler (üretici / markadan bize gelen) — Ref No'larla aynı dil
# ════════════════════════════════════════════════════════════════════
def _ad_ac(rid):
    B.detay_ac("ad", rid)


def _alinan_gorunum():
    from datetime import date
    eur, tl = _kurlar()
    bugun = date.today()
    c0, c1, c2, c3, c4 = st.columns([1.0, 2.6, 1.0, 1.05, 1.35], vertical_alignment="bottom")
    yil = c0.selectbox("Yıl", [bugun.year, bugun.year - 1, bugun.year + 1], key="ad2_yil",
                       label_visibility="collapsed")
    kayitlar = [dict(r, donem_=str(r.get("donem") or "")[:7]) for r in (N.get_alinan_destekler(yil) or [])]
    ara = c1.text_input("Ara", key="ad2_ara", placeholder="Firma, açıklama, fatura no, tutar…",
                        label_visibility="collapsed")
    firmalar = sorted({(r.get("firma") or "").strip() for r in kayitlar if (r.get("firma") or "").strip()})
    turler = sorted({(r.get("tur") or "").strip() for r in kayitlar if (r.get("tur") or "").strip()})
    _f = B.filtre(c2, [{"etiket": "Firma", "secenekler": firmalar, "key": "ad2_f_firma"},
                       {"etiket": "Tür", "secenekler": turler, "key": "ad2_f_tur"}])
    f_firma, f_tur = _f["ad2_f_firma"], _f["ad2_f_tur"]
    if c3.button("Excel", icon=":material/upload_file:", use_container_width=True, key="ad2_excel"):
        _ad_excel_dialog()
    if c4.button("Yeni kayıt", icon=":material/add:", type="primary", use_container_width=True, key="ad2_yeni"):
        _ad_yeni_dialog(firmalar)

    from shared.utils import tr_kucuk
    a = tr_kucuk(ara)
    liste = [r for r in kayitlar
             if (f_firma == "Tümü" or (r.get("firma") or "").strip() == f_firma)
             and (f_tur == "Tümü" or (r.get("tur") or "").strip() == f_tur)
             and (not a or a in tr_kucuk(f"{r.get('firma','')} {r.get('aciklama','')} {r.get('fatura_no','')} "
                                         f"{r.get('tutar','')} {r.get('tur','')} {r.get('kategori','')}"))]
    bu_ay = f"{bugun.year:04d}-{bugun.month:02d}"
    t = R.toplam(liste, eur, tl)
    t_ay = R.toplam([r for r in liste if r["donem_"] == bu_ay], eur, tl)
    ham = " · ".join(f"{R.SEMBOL.get(d, d)}{sayi(v)}" for d, v in sorted(t["ham"].items(), key=lambda x: -x[1]) if v)
    st.markdown(kpi_serit([
        {"etiket": f"{yil} toplam (USD karşılığı)", "deger": _usd(t["usd"]), "renk": "yesil", "alt": ham or "—"},
        {"etiket": f"Bu ay · {R.donem_adi(bu_ay)}", "deger": _usd(t_ay["usd"]), "renk": "mor",
         "alt": f"{sum(1 for r in liste if r['donem_'] == bu_ay)} kayıt"},
        {"etiket": "Kayıt", "deger": tr_sayi(len(liste)), "renk": "cyan",
         "alt": f"{len({(r.get('firma') or '').strip() for r in liste})} firma"},
    ]), unsafe_allow_html=True)
    if t["cevrilmeyen"]:
        st.markdown(mesaj("uyari", "Kur bulunamadığı için USD toplamına katılmayan: " + " · ".join(
            f"{R.SEMBOL.get(d, d)}{tr_sayi(v)}" for d, v in t["cevrilmeyen"].items())), unsafe_allow_html=True)
    if not liste:
        st.markdown(bos_durum("Bu dönemde alınan destek yok" if not kayitlar else "Filtreye uyan kayıt yok",
                              "'Yeni kayıt' ile ekle ya da Excel şablonuyla toplu yükle." if not kayitlar
                              else "Filtreyi ya da aramayı değiştir.", "savings"), unsafe_allow_html=True)
        return
    gruplar = {}
    for r in liste:
        gruplar.setdefault(r["donem_"], []).append(r)
    for d in sorted(gruplar, reverse=True):
        g = gruplar[d]
        tg = R.toplam(g, eur, tl)
        st.markdown(B.grup_basligi(R.donem_adi(d), f"{len(g)} kayıt · ≈ {_usd(tg['usd'])}"),
                    unsafe_allow_html=True)
        for r in sorted(g, key=lambda x: -R._f(x.get("tutar"))):
            cip = "".join(B.cip(x) for x in ((r.get("tur") or "").strip().capitalize(),
                                             (r.get("kategori") or "").strip().capitalize()) if x)
            fat = f'<span>Fatura {_h.escape(str(r.get("fatura_no")))}</span>' if r.get("fatura_no") else ""
            B.tiklanir(f"ad{r['id']}",
                       f'<div class="rf-s" style="grid-template-columns:150px minmax(0,1fr) auto">'
                       f'<div><div class="rf-no" style="font-family:inherit;color:var(--k-metin);font-size:13.5px">'
                       f'{_h.escape((r.get("firma") or "—").strip())}</div></div>'
                       f'<div style="min-width:0"><div class="rf-ack">{_h.escape(r.get("aciklama") or "—")}</div>'
                       f'<div class="k-meta">{cip}{fat}</div></div>'
                       f'<div class="rf-tut"><b>{_tutar(r)}</b><small>{_usd_alt(r, eur, tl)}</small></div></div>',
                       _ad_ac, (r["id"],), tur="satir", renk="yesil", etiket="Detay")
    _sec = B.detay_istendi("ad")
    if _sec:
        r = next((x for x in kayitlar if x.get("id") == _sec), None)
        if r:
            _ad_detay_dialog(r, eur, tl)


@st.dialog("Alınan destek", width="medium")
def _ad_detay_dialog(r, eur, tl):
    st.markdown(_css() + f'<div class="rf-dt"><span class="rf-no" style="font-family:inherit">'
                f'{_h.escape((r.get("firma") or "").strip())}</span></div>'
                f'<div class="rf-dt-ust">{R.donem_adi(str(r.get("donem") or "")[:7])} · '
                f'<b style="color:var(--k-metin)">{_tutar(r)}</b> · {_usd_alt(r, eur, tl)}</div>', unsafe_allow_html=True)
    for etk, v in (("Tür", r.get("tur")), ("Kategori", r.get("kategori")), ("Fatura no", r.get("fatura_no")),
                   ("Açıklama", r.get("aciklama"))):
        if v:
            st.markdown(f'<div style="display:flex;gap:12px;padding:6px 0;border-bottom:1px solid var(--k-kenar)">'
                        f'<span style="width:90px;color:var(--k-silik);font-size:12.5px">{etk}</span>'
                        f'<span style="font-size:13px">{_h.escape(str(v))}</span></div>', unsafe_allow_html=True)
    if B.onayli_sil("Evet, bu kaydı sil", key=f"ad2_{r['id']}", dugme="Kaydı sil",
                    aciklama="Kayıt düzeltmek için silip yeniden girin (değişiklik geçmişi bozulmasın)."):
        if N.alinan_destek_sil(r["id"]):
            st.session_state.pop("_ad_sec", None)
            _yenile(None, "Kayıt silindi")
        else:
            st.error("Silinemedi — kayıt başkası tarafından silinmiş olabilir.")


@st.dialog("Yeni alınan destek", width="large")
def _ad_yeni_dialog(firmalar):
    from datetime import date
    try:
        from satis.database import get_sku_kategori
        katlar = sorted({(v or "").strip().upper() for v in get_sku_kategori().values() if (v or "").strip()})
    except Exception:  # noqa: BLE001
        katlar = []
    with st.form("ad2_yeni_form", border=False):
        a1, a2, a3 = st.columns(3)
        firma = a1.text_input("Firma / marka", placeholder="örn. FAZEON, MSI")
        tur = a2.selectbox("Tür", N.ALINAN_TURLER)
        kat = a3.selectbox("Kategori", ["GENEL"] + katlar, help="Hangi ürün kategorisi için? Dağıtılamıyorsa GENEL.")
        b1, b2, b3, b4 = st.columns([1, 1.3, 0.9, 1.3])
        ay = b1.selectbox("Ay", list(range(1, 13)), index=date.today().month - 1, format_func=lambda m: R.AY_AD[m])
        yil = b2.number_input("Yıl", min_value=2020, max_value=2100, step=1, value=date.today().year)
        dvz = b3.selectbox("Döviz", ["USD", "TL", "EUR"])
        tutar = b4.number_input("Tutar", min_value=0.0, step=100.0, format="%.2f")
        c1, c2 = st.columns([1, 2])
        fat = c1.text_input("Fatura no", placeholder="isteğe bağlı")
        ack = c2.text_input("Açıklama", placeholder="örn. Eylül sellout hakedişi")
        if firmalar:
            st.caption("Daha önce girilen firmalar: " + ", ".join(firmalar[:8]))
        if st.form_submit_button("Kaydet", type="primary", icon=":material/save:"):
            ok, msg = N.alinan_destek_ekle(firma, tur, f"{int(yil)}-{ay:02d}", tutar, dvz, fat, ack, kat)
            if ok:
                _yenile(None, msg)
            else:
                st.error(msg)


@st.dialog("Excel ile toplu yükleme", width="large")
def _ad_excel_dialog():
    import io
    import pandas as pd
    from datetime import date
    st.caption("Başlıklar: FİRMA · TÜR · DÖNEM · TUTAR · DÖVİZ · FATURA NO · AÇIKLAMA · KATEGORİ — "
               "sıra önemli değil, ada göre eşleşir. DÖNEM: 2026-07, 07.2026 ya da tarih.")
    sab = pd.DataFrame([{"FİRMA": "FAZEON", "TÜR": "SELLOUT", "DÖNEM": f"{date.today():%Y-%m}", "TUTAR": 1500.00,
                         "DÖVİZ": "USD", "KATEGORİ": "MONİTÖR", "FATURA NO": "", "AÇIKLAMA": "Örnek satır"}])
    buf = io.BytesIO()
    sab.to_excel(buf, index=False)
    st.download_button("Şablonu indir", buf.getvalue(), file_name="alinan_destek_sablon.xlsx",
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                       icon=":material/download:")
    up = st.file_uploader("Excel dosyası", type=["xlsx", "xls"], key="ad2_up")
    if up is not None:
        try:
            df = pd.read_excel(up)
        except Exception as e:  # noqa: BLE001
            st.error(f"Dosya okunamadı: {e}")
            return
        st.dataframe(df.head(10), use_container_width=True, hide_index=True)
        st.caption(f"{len(df)} satır bulundu; ilk 10 gösteriliyor.")
        if st.button("İçe aktar", type="primary", icon=":material/move_to_inbox:", key="ad2_imp"):
            eklenen, atlanan, hatalar = N.alinan_destek_excel_ice_aktar(df)
            for h in hatalar[:5]:
                st.error(h)
            if eklenen:
                _yenile(None, f"{eklenen} kayıt eklendi" + (f", {atlanan} satır atlandı" if atlanan else ""))
