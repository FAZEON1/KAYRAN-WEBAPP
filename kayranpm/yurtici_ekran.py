# -*- coding: utf-8 -*-
"""Ürün Yönetimi › Yurt içi alış — yurt içi satın alma girişi (Ekim 2026).

Yalnız yurt içi satın alma girilir (yerli üretim seçeneği kaldırıldı, Ekim 2026); eski kayıtların türü
korunur. İthalat girer gibi: alış tarihi, depoya giriş tarihi, firma, belge no, kalemler (adet, KDV hariç
birim fiyat), masraflar. Kayıt ithalat dosyalarıyla aynı tablolara alim_turu ile yazılır
(veritabani/18); paçal maliyet, Kâr/P&L, stok kartı alımları, Model sorgu ve FIFO stok yaşı
bu alımları kendiliğinden kullanır. Hesap ve doğrulama: kayranpm/yurtici_hesap.py.

Stok: "Stoğa ekle" yeni alımda stok artar (işlenme kaydı düşer; silinirse geri çekilir).
"Mal zaten depoda" geçmiş alımı sonradan girmek içindir: stoğa DOKUNULMAZ.
"""
from datetime import date

import streamlit as st

from shared.tasarim import tr_sayi

from . import yurtici_hesap as H

# Kayıtlı alımlar liste masası (Ekim 2026, ortak masa shared/masa.py; tanım kayranpm/yurtici_masasi.py).
# True: yeni masa. False: eski tablo (yi_liste) aynen (geri almak için YALNIZ bu satır).
YURTICI_MASASI_YENI = True


def _kolon_var():
    """veritabani/18 kurulu mu (alim_turu sütunu)."""
    try:
        from ithalat.database import _get_client
        _get_client().table("ithalat_dosyalari").select("alim_turu").limit(1).execute()
        return True
    except Exception:  # noqa: BLE001
        return False


def _kartlar():
    try:
        from .database import _hepsi
        return {str(u.get("sku") or "").strip(): u.get("urun_adi") or ""
                for u in _hepsi("urunler", "sku, urun_adi") if str(u.get("sku") or "").strip()}
    except Exception:  # noqa: BLE001
        return {}


def _tcmb_getir(gun):
    try:
        import requests
        r = requests.get(H.tcmb_url(gun), timeout=6)
        return r.text if r.status_code == 200 else None
    except Exception:  # noqa: BLE001
        return None


def _tablo_kuru(tarih):
    try:
        from kayranacc.database import get_kur
        return get_kur(tarih)            # yalnız O GÜNÜN kaydı; bugünün kuruna düşmez
    except Exception:  # noqa: BLE001
        return None


@st.cache_data(ttl=86400, show_spinner=False)
def _kur(tarih):
    """(kur, kaynak) — alış tarihinin kuru (yurtici_hesap.tarihli_kur)."""
    return H.tarihli_kur(tarih, _tcmb_getir, _tablo_kuru)


def _alimlar():
    from ithalat.database import get_dosyalar, get_tum_kalemler, alim_turu
    dos = [d for d in (get_dosyalar() or []) if alim_turu(d) in H.TURLER]
    kal = {}
    for k in get_tum_kalemler() or []:
        kal.setdefault(k.get("dosya_id"), []).append(k)
    return dos, kal


def _form(on, v, kartlar):
    """Alım formu. on: widget anahtar öneki; v: varsayılanlar (düzenlemede kayıttan)."""
    import pandas as pd
    from shared import form as F
    # Yeni düzen (Ekim 2026): belge bilgileri iki sıkı satır; alım türü sabit (yalnız yurt içi satın alma)
    tur = v.get("tur") if v.get("tur") in H.TURLER else "yurtici"     # yeni alım: yalnız yurt içi satın alma
    c1, c2, d1, d2 = st.columns([1.1, 1.5, 1, 1])
    belge = c1.text_input("Fatura / belge no", value=v.get("belge", ""), key=f"{on}_belge",
                          placeholder="boşsa YI-tarih")
    firma = c2.text_input("Satın alınan firma", value=v.get("firma", ""), key=f"{on}_firma",
                          placeholder="faturayı kesen firma")
    _bug = date.today()
    alis = d1.date_input("Alış tarihi", value=date.fromisoformat(v["alis_tarihi"]) if v.get("alis_tarihi") else _bug,
                         format="DD.MM.YYYY", key=f"{on}_alis")
    giris = d2.date_input("Depoya giriş", format="DD.MM.YYYY", key=f"{on}_giris",
                          value=date.fromisoformat(v["giris_tarihi"]) if v.get("giris_tarihi") else alis,
                          help="Stok yaşı bu tarihten başlar.")
    d3, p1, p2, _p3 = st.columns([1.3, 1, 1, 1.2], vertical_alignment="bottom")
    depolar = H.SATILABILIR_DEPOLAR
    depo = d3.selectbox("Teslim deposu", depolar, key=f"{on}_depo",
                        index=depolar.index(v["depo"]) if v.get("depo") in depolar else 0)
    para = p1.radio("Para birimi", ["TL", "USD"], horizontal=True, key=f"{on}_para",
                    index=0 if str(v.get("para") or "TL").upper() == "TL" else 1)
    kur = 1.0
    if para == "TL":
        kayitli = float(v.get("kur") or 0) if str(v.get("para") or "").upper() == "TL" else 0.0
        oneri, kaynak = (kayitli, "kayıtlı kur") if kayitli > 1 else _kur(alis.isoformat())
        kur = F.sayi_kutusu("Kur (TL / USD)", f"{on}_kur_{alis.isoformat()}",   # tarih değişince o günün kuru
                            float(oneri or 0.0), basamak=4, kap=p2, placeholder="0,0000",
                            yardim="Alış tarihinin TCMB döviz satış kuru otomatik gelir; faturadaki kurla "
                                  "değiştirebilirsin.")
        if oneri and kaynak:
            _p3.caption(f"Önerilen: {kaynak}. Faturadaki kur farklıysa değiştir.")
        else:
            _p3.warning("Bu tarihin kuru bulunamadı; faturadaki kuru gir.")

    st.markdown(f"**Kalemler** · birim fiyat KDV hariç, {para}")
    skular = sorted(kartlar)
    satir = v.get("kalemler") or [{"sku": None, "adet": None, "fiyat": None}]
    duz = st.data_editor(
        pd.DataFrame(satir, columns=["sku", "adet", "fiyat"]), num_rows="dynamic", hide_index=True,
        use_container_width=True, key=f"{on}_kalem",
        column_config={
            "sku": st.column_config.SelectboxColumn("SKU", options=skular, required=True, width="medium"),
            "adet": st.column_config.NumberColumn("Adet", min_value=0.0, step=1.0, format="localized"),
            "fiyat": st.column_config.NumberColumn(f"Birim fiyat ({para})", min_value=0.0, step=0.0001,
                                                   format="localized"),
        })
    kalemler = [{"sku": (r.get("sku") or ""), "adet": r.get("adet"), "fiyat": r.get("fiyat")}
                for r in duz.to_dict("records")]
    st.markdown(f"**Masraflar** · {para}, KDV hariç; birim maliyete fiyat payına göre eklenir")
    mc = st.columns(len(H.MASRAFLAR) + 1)
    masraflar = {}
    for (slug, ad), c in zip(H.MASRAFLAR, mc):
        masraflar[slug] = F.sayi_kutusu(ad, f"{on}_m_{slug}", float((v.get("masraflar") or {}).get(slug) or 0.0),
                                        kap=c)
    notu = st.text_input("Not", value=v.get("not", ""), key=f"{on}_not")
    return {"tur": tur, "belge": belge, "firma": firma, "alis_tarihi": alis.isoformat(),
            "giris_tarihi": giris.isoformat(), "depo": depo, "para": para, "kur": kur,
            "kalemler": kalemler, "masraflar": masraflar, "not": notu}


def _onizleme(f, kartlar):
    h = H.maliyet_hesapla(f["kalemler"], f["masraflar"], f["para"], f["kur"])
    if not h["satirlar"]:
        return
    from shared.tablo import tablo
    tablo([{"SKU": r["sku"], "Ürün": kartlar.get(r["sku"], ""), "Adet": r["adet"],
            f"Birim fiyat ({f['para']})": r["fiyat"], "Birim fiyat ($)": round(r["birim_usd"], 4),
            "Birim maliyet ($)": round(r["maliyet_usd"], 4)} for r in h["satirlar"]],
          key=f"yi_onizleme_{f['para']}", dosya_adi="yurtici_onizleme", kompakt=True)
    st.caption(f"Mal bedeli {tr_sayi(h['mal_bedeli'], 2)} {f['para']} · masraf {tr_sayi(h['masraf'], 2)} "
               f"{f['para']} · masraf oranı %{tr_sayi(h['oran'], 1)} · birim maliyet paçala bu rakamla girer.")


def _yeni(kartlar, kolon):
    """Yeni alım (Ekim 2026 düzeni): solda belge + kalemler + masraflar, sağda (telefonda altta sabit) özet,
    stok seçimi ve Kaydet. Hesap ve kayıt aynı (yurtici_hesap)."""
    from shared import form as F
    st.markdown(F.css(), unsafe_allow_html=True)
    sol, sag = st.columns([2.75, 1], gap="medium")
    with sol:
        mesaj_yeri = st.container()
        f = _form("yi_yeni", {}, kartlar)
        from shared.dosya_kapisi import mikro_kapsar
        if mikro_kapsar("g5f_sayim"):                 # kayranpm.main.stok_mikrodan ile aynı karar
            # Stok Mikro'dan: alım stoğa elle eklenmez (zaten yazılmıyordu; seçenek yanıltıyordu, 22.10.2026).
            stok = H.STOK_VAR
            st.caption("Stok Mikro'dan gelir: alımın stoğa girişi Mikro'daki irsaliyeyle olur.")
        else:
            stok = st.radio("Stok", [H.STOK_EKLE, H.STOK_VAR], key="yi_yeni_stok", horizontal=True,
                            help="Geçmiş bir alımı sonradan giriyorsan ve mal depoda zaten sayılıysa ikinciyi seç; "
                                 "yoksa stok iki kez girer.")
        _onizleme(f, kartlar)
    hatalar = H.dogrula(f, kartlar)
    with sag, st.container(key="kf_ozet_yurtici"):
        h = H.maliyet_hesapla(f["kalemler"], f["masraflar"], f["para"], f["kur"])
        p = f["para"]
        _adet = sum(r["adet"] for r in h["satirlar"])
        st.markdown(F.ozet_paneli("Alım özeti", [
            ("Kalem / adet", f"{len(h['satirlar'])} · {tr_sayi(_adet)}"),
            ("Mal bedeli", f"{tr_sayi(h['mal_bedeli'], 2)} {p}"),
            ("Masraf", f"{tr_sayi(h['masraf'], 2)} {p} · %{tr_sayi(h['oran'], 1)}"),
        ] + ([("Kur", tr_sayi(f["kur"], 4))] if p == "TL" else []),
            vurgu=("Toplam", f"{tr_sayi(h['mal_bedeli'] + h['masraf'], 2)} {p}", "metin"),
            uyarilar=[f"{len(hatalar)} eksik: " + hatalar[0]] if hatalar and h["satirlar"] else ()),
            unsafe_allow_html=True)
        _kaydet = st.button("Alımı kaydet", type="primary", icon=":material/save:", key="yi_kaydet",
                            disabled=not kolon, use_container_width=True)
    if _kaydet:
        with mesaj_yeri:
            if hatalar:
                st.error("Kaydedilmedi, eksikler var:\n\n" + "\n".join("- " + x for x in hatalar))
                return
            from ithalat.database import ekle_dosya
            a = H.kayit_argumanlari(f, ad_bul=kartlar.get)
            ok, msg = ekle_dosya(a["dosya_no"], a["tarih"], a["tedarikci"], "", a["doviz"], a["kur"],
                                 a["masraflar"], a["notlar"], a["kalemler"], durum="Teslim Alındı",
                                 teslim_tarihi=a["teslim_tarihi"], teslim_deposu=a["teslim_deposu"],
                                 alim_turu=a["alim_turu"], stok_ekle=(stok == H.STOK_EKLE))
            if ok:
                st.cache_data.clear()
                for k in [k for k in st.session_state if str(k).startswith("yi_yeni_")]:
                    del st.session_state[k]
                st.toast(f"Alım kaydedildi: {a['dosya_no']}", icon=":material/check_circle:")
                st.rerun()
            st.error(msg)


def _kayitli_masa(kartlar, kolon):
    """Yeni liste (YURTICI_MASASI_YENI): ortak masa; Düzenle bugünkü formu masanın altında açar."""
    from shared.masa import calistir
    from shared.utils import gun_ay_yil
    from ithalat.database import _masraf_dict
    from . import yurtici_masasi as YM
    from .masa_ortak import csv_bayt
    dos, kal = _alimlar()
    if not dos:
        st.info("Henüz yurt içi alış kaydı yok.")
        return
    tablo = YM.tablo_satirlari(dos, kal, _masraf_dict, gun_ay_yil)
    calistir(YM.masa_verisi(tablo), "yi_masasi", YM.yurutucu())
    c1, c2 = st.columns([4, 1.2], vertical_alignment="center")
    c1.caption("Satıra tıkla: ayrıntı, düzenleme ve silme yan panelde. Düzenleme formu masanın altında açılır.")
    c2.download_button("CSV indir", data=csv_bayt(tablo), file_name="yurtici_alimlar.csv", mime="text/csv",
                       key="yi_csv", icon=":material/download:", use_container_width=True,
                       help="Kayıtlı alımlar tablosu (Excel açar)")
    sec = st.session_state.get(YM.SECIM_KEY)
    d = next((x for x in dos if x.get("id") == sec), None) if sec is not None else None
    if d is None:
        st.session_state.pop(YM.SECIM_KEY, None)
        return
    if st.button("Düzenlemeyi kapat", key="yi_duz_kapat", icon=":material/close:", type="tertiary"):
        st.session_state.pop(YM.SECIM_KEY, None)
        st.rerun()
    _duzenle_formu(d, kal.get(d.get("id"), []), kartlar, kolon)


def _kayitli(kartlar, kolon):
    if YURTICI_MASASI_YENI:
        return _kayitli_masa(kartlar, kolon)
    from shared.tablo import tablo
    from shared.utils import gun_ay_yil
    from ithalat.database import _masraf_dict
    dos, kal = _alimlar()
    if not dos:
        st.info("Henüz yurt içi alış kaydı yok.")
        return
    dos = sorted(dos, key=lambda d: str(d.get("teslim_tarihi") or d.get("tarih") or ""), reverse=True)
    satirlar = []
    for d in dos:
        ks = kal.get(d.get("id"), [])
        mal = sum(H._f(k.get("adet")) * H._f(k.get("birim_fob")) for k in ks)
        masraf = sum(H._f(v) for v in _masraf_dict(d).values())
        satirlar.append({"Depoya giriş": gun_ay_yil(d.get("teslim_tarihi")), "Alış": gun_ay_yil(d.get("tarih")),
                         "Tür": H.TURLER.get(d.get("alim_turu"), ""), "Belge": d.get("dosya_no") or "",
                         "Firma": d.get("tedarikci") or "", "Kalem": len(ks),
                         "Adet": sum(H._f(k.get("adet")) for k in ks), "Tutar ($)": round(mal + masraf, 2),
                         "Stok": "eklendi" if d.get("stok_islendi") is True else "zaten depodaydı"})
    sec = tablo(satirlar, key="yi_liste", kalici=True, dosya_adi="yurtici_alimlar")
    if sec is None:
        st.caption("Ayrıntı, düzenleme ve silme için bir satıra tıkla.")
        return
    d = dos[sec]
    _duzenle_formu(d, kal.get(d.get("id"), []), kartlar, kolon)


def _duzenle_formu(d, ks, kartlar, kolon):
    """Kayıtlı alımın düzenleme formu ve silme (eski tablo da yeni masa da bunu açar)."""
    with st.container(border=True):
        st.markdown(f"**{d.get('dosya_no')}** · {H.TURLER.get(d.get('alim_turu'), '')}")
        v = H.formdan(d, ks)
        on = f"yi_duz_{d.get('id')}"
        f = _form(on, v, kartlar)
        _onizleme(f, kartlar)
        st.caption("Stoğa eklenmiş alımda adet değişikliği stoğa da yansır; 'zaten depodaydı' kaydında "
                   "stoğa dokunulmaz.")
        b1, b2 = st.columns(2)
        if b1.button("Değişiklikleri kaydet", type="primary", icon=":material/save:", key=f"{on}_kaydet",
                     disabled=not kolon, use_container_width=True):
            hatalar = H.dogrula(f, kartlar)
            if hatalar:
                st.error("Kaydedilmedi, eksikler var:\n\n" + "\n".join("- " + x for x in hatalar))
            else:
                from ithalat.database import guncelle_dosya
                a = H.kayit_argumanlari(f, ad_bul=kartlar.get)
                ok, msg = guncelle_dosya(d["id"], a["dosya_no"], d.get("pi_no") or "", a["tarih"], a["tedarikci"],
                                         "", a["doviz"], a["kur"], a["masraflar"], a["notlar"], a["kalemler"],
                                         durum="Teslim Alındı", teslim_tarihi=a["teslim_tarihi"],
                                         teslim_deposu=a["teslim_deposu"])
                if ok and a["alim_turu"] != d.get("alim_turu"):
                    from ithalat.database import _get_client
                    _get_client().table("ithalat_dosyalari").update({"alim_turu": a["alim_turu"]}) \
                        .eq("id", d["id"]).execute()
                if ok:
                    st.cache_data.clear()
                    st.toast("Alım güncellendi.", icon=":material/check_circle:")
                    st.rerun()
                st.error(msg)
        onay = b2.checkbox("Silmeyi onaylıyorum", key=f"{on}_sil_onay")
        if b2.button("Alımı sil", icon=":material/delete:", key=f"{on}_sil", disabled=not onay,
                     use_container_width=True):
            from ithalat.database import yurtici_sil
            ok, msg = yurtici_sil(d["id"])
            if ok:
                st.cache_data.clear()
                st.toast(msg, icon=":material/check_circle:")
                st.rerun()
            st.error(msg)


def goster():
    """Yeni alım + kayıtlı alımlar."""
    kolon = _kolon_var()
    if not kolon:
        st.warning("Kayıt için veritabanında 'alım türü' sütunu gerekiyor (veritabani/18_alim_turu.sql). "
                   "Kurulana kadar alım kaydedilemez.")
    kartlar = _kartlar()
    t1, t2 = st.tabs(["Yeni alım", "Kayıtlı alımlar"])
    with t1:
        _yeni(kartlar, kolon)
    with t2:
        _kayitli(kartlar, kolon)
