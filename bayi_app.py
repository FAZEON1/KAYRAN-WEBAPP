# -*- coding: utf-8 -*-
"""
KAYRAN — BAYİ PORTALI (Faz 1)

Ayrı Streamlit uygulaması. Bayiler kendi cari durumlarını (Özet) ve teknik
servis/iade kayıtlarını (Servis Takibi) görür. Ana KAYRAN uygulamasından
bağımsız çalışır; aynı Supabase'i ve shared/ kodunu kullanır.

Çalıştırma:
    streamlit run bayi_app.py

Kurulum (bir kez):
    sql/bayi_kullanicilar.sql dosyasını Supabase SQL Editor'de çalıştırın.
    Ardından "🔑 Yönetici girişi" ile personel olarak girip bayi hesabı açın.
"""
import streamlit as st

st.set_page_config(page_title="KAYRAN Bayi Portalı", page_icon="🤝",
                   layout="wide", initial_sidebar_state="expanded")

from bayi.kimlik import giris_yap, oturum_kapat, giris_var_mi, aktif_bayi, sifre_degistir
from bayi import ozet, servis, yonetim


# ── Giriş ekranı ─────────────────────────────────────────────────────
def _giris_ekrani():
    _, orta, _ = st.columns([1, 1.2, 1])
    with orta:
        st.markdown(
            '<div style="text-align:center;padding:8px 0 4px">'
            '<div style="font-size:34px">🤝</div>'
            '<div style="font-size:24px;font-weight:800;color:#E2E8F0">KAYRAN Bayi Portalı</div>'
            '<div style="font-size:14px;color:#94A3B8;margin-top:2px">Cari durumu ve servis takibi</div>'
            '</div>',
            unsafe_allow_html=True,
        )
        with st.form("bayi_login"):
            kul = st.text_input("Kullanıcı adı")
            sif = st.text_input("Şifre", type="password")
            if st.form_submit_button("Giriş yap", use_container_width=True):
                ok, mesaj, _ = giris_yap(kul, sif)
                if ok:
                    st.rerun()
                else:
                    st.error(mesaj)

        with st.expander("🔑 Yönetici girişi"):
            st.caption("Bayi hesabı açmak/yönetmek için personel paneli.")
            if st.button("Yönetici paneline geç", use_container_width=True):
                st.session_state["_admin_mode"] = True
                st.rerun()


# ── Admin modu ───────────────────────────────────────────────────────
def _admin_ekrani():
    if st.button("← Bayi girişine dön"):
        st.session_state.pop("_admin_mode", None)
        st.session_state.pop("bayi_admin", None)
        st.rerun()
    yonetim.render()


# ── Giriş yapmış bayi ────────────────────────────────────────────────
def _portal():
    bayi = aktif_bayi()
    with st.sidebar:
        st.markdown(
            f'<div style="padding:6px 2px 12px">'
            f'<div style="font-size:18px;font-weight:800;color:#E2E8F0">🤝 Bayi Portalı</div>'
            f'<div style="font-size:13px;color:#94A3B8;margin-top:4px">'
            f'{bayi.get("ad_soyad") or bayi.get("kullanici_adi")}</div>'
            f'<div style="font-size:12px;color:#64748B">{bayi.get("cari_unvan","")}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )
        sayfa = st.radio("Menü", ["📊 Özet", "🔧 Servis Takibi", "🔒 Şifre Değiştir"],
                         label_visibility="collapsed")
        st.markdown("---")
        if st.button("🚪 Çıkış yap", use_container_width=True):
            oturum_kapat()
            st.rerun()

    if sayfa == "📊 Özet":
        ozet.render(bayi)
    elif sayfa == "🔧 Servis Takibi":
        servis.render(bayi)
    elif sayfa == "🔒 Şifre Değiştir":
        _sifre_degistir(bayi)


def _sifre_degistir(bayi):
    st.markdown('<div style="font-size:22px;font-weight:800;color:#E2E8F0">'
                '🔒 Şifre Değiştir</div>', unsafe_allow_html=True)
    st.markdown("---")
    with st.form("sifre_form"):
        eski = st.text_input("Mevcut şifre", type="password")
        yeni = st.text_input("Yeni şifre (en az 6 karakter)", type="password")
        yeni2 = st.text_input("Yeni şifre (tekrar)", type="password")
        if st.form_submit_button("Güncelle", use_container_width=True):
            if yeni != yeni2:
                st.error("Yeni şifreler eşleşmiyor.")
            else:
                ok, msg = sifre_degistir(bayi.get("id"), eski, yeni)
                (st.success if ok else st.error)(msg)


# ── Yönlendirme ──────────────────────────────────────────────────────
def main():
    if st.session_state.get("_admin_mode"):
        _admin_ekrani()
    elif giris_var_mi():
        _portal()
    else:
        _giris_ekrani()


if __name__ == "__main__":
    main()
