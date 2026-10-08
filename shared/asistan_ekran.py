# -*- coding: utf-8 -*-
"""Sistem › Ofis'te Elif ve Kerem'in bölümleri (Ekim 2026). Sayfayı shared/ofis_ekran.py çizer.

  telegram_bolumu() : Elif (Telegram asistanı) — kurulum durumu ve Telegram hesabı ↔ program kullanıcısı
  pazar_bolumu()    : Kerem (pazar araştırmacısı) — haftalık raporlar
"""
from datetime import datetime, timedelta, timezone

import streamlit as st

from shared import asistan as A
from shared import bilesen as B
from shared.tasarim import bos_durum, mesaj, tr_sayi


def _tr_zaman(iso):
    try:
        z = datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
        if z.tzinfo is None:
            z = z.replace(tzinfo=timezone.utc)
        return z.astimezone(timezone(timedelta(hours=3))).strftime("%d.%m.%Y")
    except (TypeError, ValueError):
        return str(iso or "")[:10]


def _kullanicilar():
    try:
        from shared.yetki import yetki_tablosu
        return sorted(k for k, v in (yetki_tablosu() or {}).items() if v.get("aktif"))
    except Exception:  # noqa: BLE001
        return []


def telegram_bolumu():
    harita = A.telegram_haritasi()
    kurulu = A.sql_kurulu()
    if not kurulu:
        st.markdown(mesaj("uyari", "Veritabanı kurulumu eksik: veritabani/25_asistanlar.sql Supabase'de bir kez "
                                   "çalıştırılmalı."), unsafe_allow_html=True)
    st.markdown("Elif'e Telegram'dan Türkçe soru yaz; cevap programdaki Soru sor ile aynı hesaptan, yaklaşık bir "
                "dakikada gelir. Yalnız aşağıda bir kullanıcıya bağlanmış hesaplar cevap alır ve o "
                "kullanıcının yetkileri geçerlidir (muhasebe yetkisi olmayan ödeme soramaz).")
    with st.expander("Kurulum adımları (bir kez)", icon=":material/checklist:", expanded=not harita):
        st.markdown(
            "1. **Veritabanı:** " + ("kurulu." if kurulu else "kurulmadı (yukarıdaki uyarı).") + "\n"
            "2. **GitHub anahtarı:** GitHub → Settings → Developer settings → Fine-grained tokens → "
            "Generate new token. Repository access: yalnız *KAYRAN-WEBAPP*; Permissions → *Contents: "
            "Read and write*. Üretilen anahtarı Supabase → Edge Functions → Secrets'a **GH_DISPATCH_TOKEN** "
            "adıyla ekle. Anahtarı kimseye (Claude dahil) yazma.\n"
            "3. **Telegram'a bağla:** GitHub → Actions → *Telegram asistanı* → Run workflow. Çıktıda "
            "\"Webhook adresi … telegram-webhook\" görünmeli.\n"
            "4. **Hesabını ekle:** Telegram'da bota /start yaz; bot sana Telegram kimliğini söyler. "
            "Kimliği aşağıya ekle.")

    st.markdown(B.grup_basligi("Bağlı hesaplar", f"{len(harita)} hesap"), unsafe_allow_html=True)
    if harita:
        for kimlik, kul in sorted(harita.items(), key=lambda kv: kv[1]):
            k1, k2, k3 = st.columns([2, 2, 1], vertical_alignment="center")
            k1.markdown(f"`{kimlik}`")
            k2.markdown(kul)
            if k3.button("Kaldır", key=f"tg_sil_{kimlik}", icon=":material/link_off:"):
                yeni = {k: v for k, v in harita.items() if k != kimlik}
                ok, h = A.telegram_haritasi_yaz(yeni)
                (st.rerun() if ok else st.error(f"Kaydedilemedi: {h}"))
    else:
        st.caption("Henüz bağlı hesap yok.")

    k1, k2, k3 = st.columns([2, 2, 1], vertical_alignment="bottom")
    kimlik = k1.text_input("Telegram kimliği", key="tg_yeni_kimlik", placeholder="ör. 123456789").strip()
    kullar = _kullanicilar()
    kul = (k2.selectbox("Program kullanıcısı", kullar, key="tg_yeni_kul") if kullar
           else k2.text_input("Program kullanıcısı", key="tg_yeni_kul_metin").strip().lower())
    if k3.button("Ekle", key="tg_ekle", type="primary", icon=":material/add_link:",
                 disabled=not (kimlik and kul)):
        if not kimlik.lstrip("-").isdigit():
            st.error("Telegram kimliği yalnız rakamdan oluşur (bot /start'ta söyler).")
        else:
            ok, h = A.telegram_haritasi_yaz(dict(harita, **{kimlik: kul}))
            (st.rerun() if ok else st.error(f"Kaydedilemedi: {h}"))


def pazar_bolumu():
    r = A.raporlar()
    if r is None:
        st.markdown(bos_durum("Pazar raporu tablosu kurulmamış",
                              "veritabani/25_asistanlar.sql Supabase'de bir kez çalıştırılmalı.", "travel_explore"),
                    unsafe_allow_html=True)
        return
    st.caption("Kerem her pazartesi sabahı çok satan ürünlerin rakip fiyatlarını, yeni ürünleri, "
               "navlun, kur ve mevzuat haberlerini tarar. Özeti sabah brifingiyle Telegram'a gelir.")
    if not r:
        st.markdown(bos_durum("Henüz rapor yok", "İlk rapor pazartesi sabahı burada görünür.", "travel_explore"),
                    unsafe_allow_html=True)
        return
    st.markdown(B.grup_basligi("Raporlar", f"{tr_sayi(len(r))} rapor"), unsafe_allow_html=True)
    for i, x in enumerate(r):
        with st.expander(f"{_tr_zaman(x.get('zaman'))} · {x.get('baslik') or 'Pazar raporu'}", expanded=i == 0):
            if x.get("ozet"):
                st.markdown(f"**Özet:** {x['ozet']}")
            st.markdown(x.get("icerik") or "")
