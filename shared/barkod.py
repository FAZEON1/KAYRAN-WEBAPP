# -*- coding: utf-8 -*-
"""KAYRAN — Kamerayla barkod / QR okuma.

NEDEN: Depo ve teknik servis seri numarasını telefondan ELLE yazıyordu:
yavaş, ve "SN24F14P0O12345" gibi O/0, I/1 karışıklıkları mükerrer kayıt
uyarılarını da şaşırtıyor. Artık alanın üstündeki "Kamerayla okut" ile
barkodun fotoğrafı çekilir, numara alana kendisi yazılır.

Kullanım — okuyucu, hedef giriş kutusundan ÖNCE çağrılır (form içinde
değil, formun ÜSTÜNDE; form içindeki alan ancak kaydedince güncellenir):

    from shared.barkod import barkod_okuyucu
    barkod_okuyucu("mk_seri")                       # ← önce
    with st.form("mk_form"):
        seri = st.text_input("Seri No *", key="mk_seri")   # ← okunan değer burada

Çözücü: zxing-cpp (pip; sistem kurulumu gerektirmez). Code128, Code39,
EAN/UPC, QR, DataMatrix okur. Kütüphane yoksa okuyucu nazikçe devre dışı
kalır, elle giriş her zaman çalışır.
"""
import hashlib
import io

import streamlit as st

# Seri numarası için tercih sırası: EAN/UPC ürün kodudur (her kutuda aynı),
# seri no genelde Code128 / QR / DataMatrix'tir. Etikette ikisi birden varsa
# EAN'ı sona atarız.
_URUN_KODU_BICIMLERI = ("EAN", "UPC", "ISBN")


def coz(veri):
    """Görüntü baytları → [(metin, biçim), …]. Okunamazsa []. Kütüphane yoksa None."""
    try:
        import zxingcpp
        from PIL import Image, ImageOps
    except ImportError as e:
        from shared.hata_log import kaydet
        kaydet("barkod.kutuphane", e)
        return None
    try:
        im = Image.open(io.BytesIO(veri))
        im = ImageOps.exif_transpose(im)          # telefon fotoğrafının yönü
        im.thumbnail((2200, 2200))                # büyük fotoğrafta hız
        denemeler = [im.convert("RGB"), ImageOps.autocontrast(im.convert("L"))]
    except Exception as e:  # noqa: BLE001 — bozuk / desteklenmeyen dosya
        from shared.hata_log import kaydet
        kaydet("barkod.gorsel", e)
        return []
    goruldu, sonuc = set(), []
    for g in denemeler:
        for r in zxingcpp.read_barcodes(g):
            metin = (r.text or "").strip()
            if metin and metin not in goruldu:
                goruldu.add(metin)
                sonuc.append((metin, str(r.format)))
        if sonuc:
            break
    return sonuc


def sirala(adaylar):
    """Seri no için en olası aday önce: ürün kodu (EAN/UPC) biçimleri sona."""
    def _urun_kodu(b):
        return any(k in b.upper().replace("-", "") for k in _URUN_KODU_BICIMLERI)
    return sorted(adaylar, key=lambda a: _urun_kodu(a[1]))


def barkod_okuyucu(hedef_key, anahtar=None, etiket="Kamerayla okut"):
    """hedef_key'li giriş kutusunu kamerayla doldurur. Okunan değeri döndürür.

    Aynı fotoğraf tekrar tekrar yazılmaz: kullanıcı okunan numarayı elle
    düzeltirse sonraki yenilemede üstüne yazılmaz."""
    k = anahtar or f"bk_{hedef_key}"
    if not st.toggle(etiket, key=f"{k}_ac", help="Barkodu kameraya tut ve fotoğraf çek; "
                     "numara aşağıdaki alana kendisi yazılır. Telefonda arka kameraya "
                     "geçmek için kameradaki çevirme düğmesini kullan."):
        return None

    foto = st.camera_input("Barkodu çerçeveye ortala, yakından ve düz çek",
                           key=f"{k}_kam", resolution="1080p")
    kaynak = foto
    if foto is None:
        kaynak = st.file_uploader("…veya fotoğraf seç (telefonda doğrudan kamerayı açar)",
                                  type=["jpg", "jpeg", "png", "webp"], key=f"{k}_dosya")
    if kaynak is None:
        return None

    veri = kaynak.getvalue()
    iz = hashlib.sha1(veri).hexdigest()
    if st.session_state.get(f"{k}_iz") != iz:
        st.session_state[f"{k}_iz"] = iz
        adaylar = coz(veri)
        st.session_state[f"{k}_adaylar"] = None if adaylar is None else sirala(adaylar)
        st.session_state.pop(f"{k}_yazilan", None)
    adaylar = st.session_state.get(f"{k}_adaylar")

    if adaylar is None:
        st.warning("Barkod okuyucu şu an kullanılamıyor; numarayı elle yaz.")
        return None
    if not adaylar:
        st.warning("Barkod okunamadı. Barkodu yakından, düz tutup iyi ışıkta tekrar çek — "
                   "ya da numarayı elle yaz.")
        return None

    secim = adaylar[0][0]
    if len(adaylar) > 1:
        secim = st.radio("Fotoğrafta birden fazla barkod var — hangisi seri no?",
                         [a[0] for a in adaylar], key=f"{k}_sec",
                         format_func=lambda t: f"{t}  ·  {dict(adaylar)[t]}")
    # Yalnız YENİ bir okuma/seçim alana yazılır (elle düzeltme ezilmesin)
    if st.session_state.get(f"{k}_yazilan") != secim:
        st.session_state[hedef_key] = secim
        st.session_state[f"{k}_yazilan"] = secim
    st.success(f"Okundu: {secim}")
    return secim


def barkod_temizle(hedef_key, anahtar=None):
    """Yeni kayda geçerken okuyucunun eski fotoğrafını/seçimini sil
    (önceki ürünün barkodu yeni kayda taşınmasın)."""
    k = anahtar or f"bk_{hedef_key}"
    for ek in ("_ac", "_kam", "_dosya", "_iz", "_adaylar", "_yazilan", "_sec"):
        st.session_state.pop(k + ek, None)
