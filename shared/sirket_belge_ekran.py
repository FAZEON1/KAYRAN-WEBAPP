# -*- coding: utf-8 -*-
"""Şirket belgeleri (Ekim 2026; kişi menüsü, eskiden Yönetim altında) — yalnız Yönetim yetkilileri (app.py kapısı).

Şirketin resmi belgeleri (vergi levhası, sicil gazetesi, faaliyet belgesi …): türe göre güncel
sürüm + eski sürümler, geçerlilik uyarısı, seçilenleri tek ZIP indirme ve şirket künyesi.
Hesaplar shared.sirket_belge_hesap'ta, veritabanı / dosya alanı shared.sirket_belge'de.
"""
import html as _h
from datetime import date, datetime, timedelta, timezone

import streamlit as st

from shared import bilesen as B
from shared import sirket_belge as D
from shared.sirket_belge_hesap import (EN_FAZLA_MB, KUNYE_ALANLARI, TURLER, UYARI_GUN, belge_kabul,
                                       edefter_kunye, gruplandir, indirme_adi, kunye_birlestir, kunye_metni,
                                       sure_durumu, uyarilar, zip_icerik)
from shared.tasarim import bos_durum, kpi_serit, mesaj, tr_sayi

DURUM = {"dolmus": ("Süresi doldu", "kirmizi"), "yaklasiyor": ("Süresi yaklaşıyor", "amber"),
         "gecerli": ("Geçerli", "yesil"), "suresiz": ("Süresiz", "silik")}


def _bugun():
    return datetime.now(timezone(timedelta(hours=3))).date()


def _tr(v):
    try:
        return date.fromisoformat(str(v)[:10]).strftime("%d.%m.%Y")
    except (TypeError, ValueError):
        return "—"


def _tarih(v):
    try:
        return date.fromisoformat(str(v)[:10])
    except (TypeError, ValueError):
        return None


def _mb(n):
    return f"{tr_sayi((n or 0) / 1024 / 1024, 1)} MB"


def sayfa():
    kayitlar = D.listele()
    B.baslik_eylem("Yönetici", "Şirket belgeleri",
                   aciklama="Vergi levhası, sicil gazetesi, faaliyet belgesi gibi resmi belgeler ve şirket künyesi. "
                            "Yalnız yöneticiler görür.")
    if kayitlar is None:
        st.markdown(bos_durum("Belge arşivi kurulmamış",
                              "veritabani/24_sirket_belgeleri.sql Supabase'de bir kez çalıştırılmalı.", "folder_off"),
                    unsafe_allow_html=True)
        return
    bugun = _bugun()
    gruplar = gruplandir(kayitlar)
    uyar = uyarilar(kayitlar, bugun)
    dolan = [u for u in uyar if u["durum"] == "dolmus"]
    st.markdown(kpi_serit([
        {"etiket": "Belge türü", "deger": tr_sayi(len(gruplar)), "renk": "mor",
         "alt": f"{tr_sayi(len(kayitlar))} dosya, eski sürümlerle"},
        {"etiket": "Süresi dolan", "deger": tr_sayi(len(dolan)), "renk": "kirmizi" if dolan else "yesil"},
        {"etiket": f"{UYARI_GUN} gün içinde dolacak", "deger": tr_sayi(len(uyar) - len(dolan)),
         "renk": "amber" if len(uyar) > len(dolan) else "yesil"},
        {"etiket": "Kapladığı yer", "deger": _mb(sum(int(r.get("boyut") or 0) for r in kayitlar)), "renk": "cyan"},
    ]), unsafe_allow_html=True)
    for u in uyar:
        if u["durum"] == "dolmus":
            st.markdown(mesaj("hata", f"{u['tur']}: süresi {_tr(u['kayit'].get('bitis_tarihi'))} tarihinde doldu "
                                      f"({-u['kalan']} gün önce). Yenisini yükle."), unsafe_allow_html=True)
        else:
            st.markdown(mesaj("uyari", f"{u['tur']}: süresi {_tr(u['kayit'].get('bitis_tarihi'))} tarihinde doluyor "
                                       f"({u['kalan']} gün kaldı)."), unsafe_allow_html=True)

    t_belge, t_yukle, t_kunye = st.tabs(["Belgeler", "Belge yükle", "Şirket künyesi"])
    with t_belge:
        _belgeler(gruplar, bugun)
    with t_yukle:
        _yukle_formu()
    with t_kunye:
        _kunye()


def _satir(r, bugun, eski=False):
    durum, kalan = sure_durumu(r.get("bitis_tarihi"), bugun)
    ad, renk = DURUM[durum]
    gecerlilik = f"{_tr(r.get('bitis_tarihi'))} · {ad}" if r.get("bitis_tarihi") else ad
    k = st.columns([3.2, 1.3, 2.2, 0.8, 0.8, 0.8], vertical_alignment="center")
    notu = f" · {_h.escape(r.get('notu'))}" if r.get("notu") else ""
    k[0].markdown(f"**{_h.escape(r.get('ad') or '')}**  \n"
                  f"<span style='color:var(--k-silik)'>{_mb(r.get('boyut'))} · {_h.escape(r.get('yukleyen') or '—')}"
                  f"{notu}</span>", unsafe_allow_html=True)
    k[1].markdown(_tr(r.get("belge_tarihi")))
    k[2].markdown(B.cip(gecerlilik, "silik" if eski else renk), unsafe_allow_html=True)
    lk = f"sb_link_{r['id']}"
    if st.session_state.get(lk):
        k[3].link_button("Aç", st.session_state[lk], icon=":material/open_in_new:",
                         help="Link 10 dakika geçerli")
    elif k[3].button("Aç", key=f"sb_ac_{r['id']}", icon=":material/visibility:"):
        st.session_state[lk] = D.link(r["yol"]) or ""
        if not st.session_state[lk]:
            st.error("Belge açılamadı; dosya alanına ulaşılamadı.")
        st.rerun()
    with k[4].popover("", icon=":material/edit:", help="Tarihleri ve notu düzenle"):
        bt = st.date_input("Belge tarihi", _tarih(r.get("belge_tarihi")), format="DD.MM.YYYY",
                           key=f"sb_dbt_{r['id']}")
        bs = st.date_input("Son geçerlilik (yoksa boş)", _tarih(r.get("bitis_tarihi")), format="DD.MM.YYYY",
                           key=f"sb_dbs_{r['id']}")
        nt = st.text_input("Not", r.get("notu") or "", key=f"sb_dnt_{r['id']}")
        if st.button("Kaydet", key=f"sb_dkay_{r['id']}", type="primary"):
            ok, h = D.guncelle(r["id"], bt, bs, nt)
            (st.rerun() if ok else st.error(f"Kaydedilemedi: {h}"))
    with k[5].popover("", icon=":material/delete:", help="Sil"):
        st.markdown(f"**{_h.escape(r.get('ad') or '')}** kalıcı olarak silinsin mi? Geri alınamaz.")
        if st.button("Evet, sil", key=f"sb_sil_{r['id']}", type="primary"):
            ok, h = D.sil(r)
            (st.rerun() if ok else st.error(f"Silinemedi: {h}"))


def _belgeler(gruplar, bugun):
    if not gruplar:
        st.markdown(bos_durum("Henüz belge yok", "Belge yükle sekmesinden ilk belgeyi ekle.", "folder_open"),
                    unsafe_allow_html=True)
        return
    for g in gruplar:
        st.markdown(B.grup_basligi(g["tur"], f"{len(g['eskiler']) + 1} sürüm" if g["eskiler"] else ""),
                    unsafe_allow_html=True)
        _satir(g["guncel"], bugun)
        if g["eskiler"]:
            with st.expander(f"Eski sürümler ({len(g['eskiler'])})"):
                for r in g["eskiler"]:
                    _satir(r, bugun, eski=True)
    eksik = [t for t in TURLER[:7] if t not in {g["tur"] for g in gruplar}]
    if eksik:
        st.caption("Henüz yüklenmemiş temel belgeler: " + ", ".join(eksik) + ".")

    st.markdown(B.grup_basligi("Toplu indir", "seçilenler tek ZIP"), unsafe_allow_html=True)
    secenek = {g["guncel"]["id"]: g for g in gruplar}
    secilen = st.multiselect("İndirilecek belgeler (her türün güncel sürümü)", list(secenek),
                             format_func=lambda i: secenek[i]["tur"], key="sb_zip_sec",
                             placeholder="Belge seç")
    if st.button("ZIP hazırla", key="sb_zip", icon=":material/folder_zip:", disabled=not secilen):
        dosyalar, olmayan = [], []
        with st.spinner("Belgeler toplanıyor…"):
            for i in secilen:
                r = secenek[i]["guncel"]
                v = D.indir(r["yol"])
                (dosyalar.append((indirme_adi(r), v)) if v else olmayan.append(r.get("tur")))
        if olmayan:
            st.error("Alınamayan belgeler: " + ", ".join(olmayan))
        st.session_state["sb_zip_veri"] = zip_icerik(dosyalar) if dosyalar else None
    if st.session_state.get("sb_zip_veri"):
        st.download_button("ZIP'i indir", st.session_state["sb_zip_veri"],
                           file_name=f"sirket_belgeleri_{_bugun().isoformat()}.zip", mime="application/zip",
                           icon=":material/download:", key="sb_zip_dl", type="primary")


def _yukle_formu():
    n = st.session_state.get("sb_yukle_n", 0)
    tur = st.selectbox("Belge türü", TURLER, key=f"sb_tur_{n}")
    if tur == "Diğer":
        tur = st.text_input("Türün adı", key=f"sb_tur_ad_{n}", placeholder="ör. Kalite belgesi").strip() or "Diğer"
    dosya = st.file_uploader(f"Dosya (PDF, JPG, PNG, Excel, Word · en fazla {EN_FAZLA_MB} MB)",
                             type=["pdf", "jpg", "jpeg", "png", "xlsx", "xls", "docx", "doc"], key=f"sb_dosya_{n}")
    c1, c2 = st.columns(2)
    belge_t = c1.date_input("Belge tarihi", _bugun(), format="DD.MM.YYYY", key=f"sb_bt_{n}")
    bitis = c2.date_input("Son geçerlilik tarihi (yoksa boş bırak)", None, format="DD.MM.YYYY", key=f"sb_bs_{n}",
                          help="Faaliyet belgesi, borcu yoktur yazısı gibi süreli belgelerde doldur; "
                               f"{UYARI_GUN} gün kala sayfanın üstünde uyarı çıkar.")
    notu = st.text_input("Not (isteğe bağlı)", key=f"sb_not_{n}")
    st.caption("Aynı türde yeni belge yüklenince eskisi silinmez; eski sürüm olarak altında kalır.")
    if st.button("Yükle", key="sb_yukle", type="primary", icon=":material/upload:", disabled=dosya is None):
        veri = dosya.getvalue()
        ok, sebep = belge_kabul(dosya.name, len(veri))
        if not ok:
            st.error(sebep)
            return
        ok, r = D.yukle(veri, dosya.name, tur, belge_t, bitis, notu, st.session_state.get("aktif_kullanici", ""))
        if not ok:
            st.error(r)
            return
        st.session_state["sb_yukle_n"] = n + 1          # alanlar boşalsın
        st.toast(f"{tur} yüklendi.")
        st.rerun()


def _kunye():
    from shared.sirket import sirket_bilgi
    kayitli = D.kunye_oku()
    if kayitli:
        deger = sirket_bilgi()
    else:
        deger = kunye_birlestir(sirket_bilgi(), edefter_kunye(D.edefter_ayari()))
        st.markdown(mesaj("bilgi", "Künye henüz kaydedilmedi. Alanlar e-Defter ayarlarından dolduruldu; "
                                   "kontrol edip kaydet."), unsafe_allow_html=True)
    with st.form("sb_kunye"):
        yeni = {}
        for k, ad in KUNYE_ALANLARI:
            if k == "adres":
                yeni[k] = st.text_area(ad, deger.get(k, ""), height=80)
            else:
                yeni[k] = st.text_input(ad, deger.get(k, ""))
        if st.form_submit_button("Künyeyi kaydet", type="primary"):
            ok, h = D.kunye_yaz(yeni)
            if ok:
                st.toast("Künye kaydedildi.")
                st.rerun()
            st.error(f"Kaydedilemedi: {h}")
    st.caption("Programın yazdırdığı irsaliye ve sevk belgelerinin başlığı bu künyeden gelir.")
    metin = kunye_metni(deger)
    if metin:
        st.markdown("**Kopyalamak için** (sağ üstteki simgeyle)")
        st.code(metin, language=None)
