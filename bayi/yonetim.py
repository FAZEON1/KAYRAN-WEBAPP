# -*- coding: utf-8 -*-
"""Bayi Portalı — Yönetici (admin) ekranı.

Bayi hesaplarını PERSONEL açar/yönetir. Buraya erişim st.secrets['kullanicilar']
ile doğrulanır (personel şifreleri) ve ADMIN kümesiyle sınırlanır — bayiler
buraya giremez. İşlevler: hesap aç, listele, aktif/pasif, şifre sıfırla.

Cari seçimi, "Toplam Aktifler"e yüklenen Cari Alacaklar Excel'inin satır
detayından beslenir (bayi/veri.cari_secenekleri).
"""
import streamlit as st

from shared.auth import kullanici_dogrula_v2, sifre_hash_uret
from bayi.veri import (
    cari_secenekleri, bayi_kullanici_ekle, bayi_kullanici_listele,
    bayi_aktiflik_degistir, bayi_sifre_guncelle,
)

# Bayi hesaplarını yönetebilecek personel kullanıcı adları
ADMIN_KULLANICILAR = {"ibrahim", "derman", "cem"}


def _admin_dogrula(kullanici, sifre):
    k = (kullanici or "").strip().lower()
    if k not in ADMIN_KULLANICILAR:
        return False
    try:
        kullanicilar = dict(st.secrets.get("kullanicilar", {}))
    except Exception:
        kullanicilar = {}
    return kullanici_dogrula_v2(k, sifre, kullanicilar)


def _admin_giris_formu():
    st.markdown('<div style="font-size:20px;font-weight:800;color:#E2E8F0">'
                '🔑 Yönetici Girişi</div>', unsafe_allow_html=True)
    st.caption("Bayi hesaplarını yönetmek için personel kullanıcı adı/şifrenizle girin.")
    with st.form("admin_giris"):
        kul = st.text_input("Kullanıcı adı")
        sif = st.text_input("Şifre", type="password")
        if st.form_submit_button("Giriş", use_container_width=True):
            if _admin_dogrula(kul, sif):
                st.session_state["bayi_admin"] = kul.strip().lower()
                st.rerun()
            else:
                st.error("Yetkisiz kullanıcı veya hatalı şifre.")


def _hesap_ac_formu():
    st.markdown("#### ➕ Yeni Bayi Hesabı")
    secenekler = cari_secenekleri()
    unvan_opts = ["— Cari seç —"] + [s["unvan"] for s in secenekler] + ["✏️ Elle gir"]

    with st.form("bayi_ac", clear_on_submit=False):
        c1, c2 = st.columns(2)
        with c1:
            kul = st.text_input("Kullanıcı adı *", help="Bayinin giriş adı (küçük harf)")
            sec_unvan = st.selectbox("Cari (unvan) *", unvan_opts)
            ad = st.text_input("Yetkili ad soyad")
        with c2:
            sif = st.text_input("Başlangıç şifresi *", type="password")
            manuel_unvan = st.text_input("Cari unvan (elle)", help="Yukarıda '✏️ Elle gir' seçtiyseniz")
            manuel_kod = st.text_input("Cari kod (opsiyonel)",
                                       help="Boş bırakın → bayi tüm döviz alt-hesaplarını görür. "
                                            "Yalnızca tek bir alt-hesaba daraltmak için doldurun.")
        c3, c4 = st.columns(2)
        with c3:
            email = st.text_input("E-posta")
        with c4:
            tel = st.text_input("Telefon")

        if st.form_submit_button("Hesabı Oluştur", use_container_width=True):
            if sec_unvan == "✏️ Elle gir":
                unvan = manuel_unvan.strip()
                kod = manuel_kod.strip()
            elif sec_unvan == "— Cari seç —":
                unvan, kod = "", ""
            else:
                unvan = sec_unvan
                kod = manuel_kod.strip()   # boş → tüm döviz alt-hesapları görünür

            if not kul.strip() or not sif or not unvan:
                st.error("Kullanıcı adı, şifre ve cari zorunlu.")
                return
            if len(sif) < 6:
                st.error("Şifre en az 6 karakter olmalı.")
                return
            ok, msg = bayi_kullanici_ekle(
                kullanici_adi=kul, sifre_hash=sifre_hash_uret(sif),
                cari_unvan=unvan, cari_kod=kod, ad_soyad=ad, email=email, telefon=tel)
            (st.success if ok else st.error)(msg)
            if ok:
                st.rerun()


def _hesap_listesi():
    st.markdown("#### 👥 Bayi Hesapları")
    kayitlar = bayi_kullanici_listele()
    if not kayitlar:
        st.info("Henüz bayi hesabı yok.")
        return
    for b in kayitlar:
        durum = "🟢 Aktif" if b.get("aktif") else "🔴 Pasif"
        with st.expander(f"{durum} · {b.get('kullanici_adi')} · {b.get('cari_unvan')}"):
            st.markdown(f"**Cari kod:** {b.get('cari_kod') or '—'}  \n"
                        f"**Yetkili:** {b.get('ad_soyad') or '—'}  \n"
                        f"**E-posta:** {b.get('email') or '—'} · **Tel:** {b.get('telefon') or '—'}  \n"
                        f"**Son giriş:** {str(b.get('son_giris') or '—')[:19]}")
            c1, c2 = st.columns(2)
            with c1:
                if b.get("aktif"):
                    if st.button("🔴 Pasifleştir", key=f"pasif_{b['id']}", use_container_width=True):
                        ok, m = bayi_aktiflik_degistir(b["id"], False)
                        (st.success if ok else st.error)(m); st.rerun()
                else:
                    if st.button("🟢 Aktifleştir", key=f"aktif_{b['id']}", use_container_width=True):
                        ok, m = bayi_aktiflik_degistir(b["id"], True)
                        (st.success if ok else st.error)(m); st.rerun()
            with c2:
                with st.popover("🔑 Şifre sıfırla", use_container_width=True):
                    yeni = st.text_input("Yeni şifre", type="password", key=f"ys_{b['id']}")
                    if st.button("Kaydet", key=f"sk_{b['id']}"):
                        if len(yeni or "") < 6:
                            st.error("En az 6 karakter.")
                        else:
                            ok, m = bayi_sifre_guncelle(b["id"], sifre_hash_uret(yeni))
                            (st.success if ok else st.error)(m)


def render():
    if not st.session_state.get("bayi_admin"):
        _admin_giris_formu()
        return
    c1, c2 = st.columns([3, 1])
    with c1:
        st.markdown('<div style="font-size:22px;font-weight:800;color:#E2E8F0">'
                    '🛠️ Bayi Yönetimi</div>', unsafe_allow_html=True)
        st.caption(f"Yönetici: {st.session_state['bayi_admin']}")
    with c2:
        if st.button("Çıkış", use_container_width=True):
            st.session_state.pop("bayi_admin", None)
            st.rerun()
    st.markdown("---")
    _hesap_ac_formu()
    st.markdown("---")
    _hesap_listesi()
