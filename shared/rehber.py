# -*- coding: utf-8 -*-
"""KAYRAN — Tasarım Rehberi (yalnız yönetici).

NEDEN: Tasarım kararları kodda değil EKRANDA verilsin. Buradaki her parça
programın geri kalanında kullanılan GERÇEK bileşendir (kopya değil): burada
bir şeyi değiştirmek, onu kullanan her ekranı değiştirir. Yeni bir ekran
yaparken önce buraya bak; burada olmayan bir görünüm icat etme.

Koyu / Açık anahtarı yalnız bu sayfadaki bileşenleri önizler. Programın
tamamı için tema seçimi: sol menü › HESAP › Görünüm (kullanıcı bazlı,
kullanici_tercih tablosu). Modüllerdeki renkler tema değişkenlerine taşındı
(var(--k-…) / trenk("…") / RENK["…"]); yeni kod sabit renk kodu YAZMAZ.
"""
import streamlit as st

from shared import tasarim as T


def _bolum(baslik, aciklama=""):
    ac = (f'<div style="color:var(--k-soluk);font-size:12.5px;margin-top:2px">{aciklama}</div>'
          if aciklama else "")
    st.markdown(f'<div style="margin:22px 0 10px"><div style="color:var(--k-metin);font-size:15px;'
                f'font-weight:700">{baslik}</div>{ac}</div>', unsafe_allow_html=True)


def _renkler(tema):
    palet = T.TEMALAR[tema]
    kart = palet["yuzey1"]
    satirlar = []
    for grup, anahtarlar in (
        ("Yüzeyler", ["yuzey0", "yuzey1", "yuzey2", "yuzey3"]),
        ("Metin", ["metin", "soluk", "silik"]),
        ("Anlam", ["mor", "yesil", "kirmizi", "amber", "cyan"]),
        ("Açık tonlar", ["mor2", "yesil2", "kirmizi2", "amber2", "cyan2", "mavi", "pembe"]),
    ):
        kutular = ""
        for k in anahtarlar:
            v = palet[k]
            olcum = ""
            if grup != "Yüzeyler" and v.startswith("#"):
                oran = T.kontrast(v, kart)
                esik = 4.5 if grup == "Metin" else 3.0
                renk = "var(--k-yesil)" if oran >= esik else "var(--k-kirmizi)"
                olcum = (f'<div style="font-size:11px;color:{renk};font-family:var(--k-mono)">'
                         f'{oran:.1f}:1 {"✓" if oran >= esik else "✗"}</div>')
            kutular += (
                f'<div style="min-width:108px;flex:1">'
                f'<div style="height:40px;border-radius:8px;background:var(--k-{k});'
                f'border:1px solid var(--k-kenar2)"></div>'
                f'<div style="font-size:12px;color:var(--k-metin);font-weight:600;margin-top:5px">{k}</div>'
                f'<div style="font-size:11px;color:var(--k-silik);font-family:var(--k-mono)">{v}</div>'
                f'{olcum}</div>')
        satirlar.append(
            f'<div style="font-size:11px;color:var(--k-soluk);font-weight:600;letter-spacing:.6px;'
            f'text-transform:uppercase;margin:10px 0 6px">{grup}</div>'
            f'<div style="display:flex;gap:10px;flex-wrap:wrap">{kutular}</div>')
    st.markdown("".join(satirlar), unsafe_allow_html=True)
    st.caption("Oranlar kart zemini üzerinde ölçülür. Metin için eşik 4.5:1, anlam renkleri için 3:1 (WCAG AA).")


def _tipografi():
    ornek = [("hero", "$849.220", True), ("deger", "$678.033", True),
             ("baslik", "Sayfa başlığı", False), ("orta", "Alt başlık · vurgulu satır", False),
             ("govde", "Gövde metni, tablo ve liste satırı", False),
             ("kucuk", "Rozet · açıklama · zaman damgası", False), ("etiket", "KPI ETİKETİ", False)]
    h = ""
    for anahtar, metin, mono in ornek:
        aile = "font-family:var(--k-mono);font-variant-numeric:tabular-nums;" if mono else ""
        h += (f'<div style="display:flex;align-items:baseline;gap:14px;padding:6px 0;'
              f'border-bottom:1px solid var(--k-kenar)">'
              f'<span style="width:104px;flex-shrink:0;white-space:nowrap;font-size:11px;color:var(--k-silik);'
              f'font-family:var(--k-mono)">{anahtar} · {T.FONT[anahtar]}</span>'
              f'<span style="font-size:{T.FONT[anahtar]};color:var(--k-metin);{aile}">{metin}</span></div>')
    st.markdown(h, unsafe_allow_html=True)


def _dugmeler():
    c = st.columns(5)
    c[0].button("Kaydet", type="primary", key="rh_d1", use_container_width=True)
    c[1].button("Filtrele", key="rh_d2", use_container_width=True)
    c[2].button("Vazgeç", type="tertiary", key="rh_d3", use_container_width=True)
    c[3].button("Kaydı Sil", key="rh_ornek_sil", icon=":material/delete:", use_container_width=True)
    c[4].button("Pasif", key="rh_d5", disabled=True, use_container_width=True)
    st.markdown(
        '<div style="color:var(--k-soluk);font-size:12.5px;line-height:1.6;margin-top:4px">'
        '<b style="color:var(--k-metin)">Ana</b> <code>type="primary"</code> — sayfanın asıl eylemi, '
        'sayfa başına en fazla bir tane · <b style="color:var(--k-metin)">İkincil</b> varsayılan — '
        'yardımcı eylemler · <b style="color:var(--k-metin)">Sade</b> <code>type="tertiary"</code> — '
        'vazgeç, temizle · <b style="color:var(--k-kirmizi)">Tehlikeli</b> — anahtarında '
        '<code>_sil</code> geçen düğme otomatik kırmızı olur.</div>', unsafe_allow_html=True)


def _bilesenler():
    st.markdown(T.kpi_serit([
        {"etiket": "Bu ay ciro", "deger": "$678.033", "renk": "mor", "alt": "Geçen ay $612.410"},
        {"etiket": "Net kâr", "deger": "$209.639", "renk": "yesil", "alt": "%30,9 marj"},
        {"etiket": "Bekleyen ödeme", "deger": "₺1.240.500", "renk": "amber", "alt": "12 kalem"},
        {"etiket": "Gecikmiş", "deger": "2", "renk": "kirmizi", "alt": "₺226.500"},
    ]), unsafe_allow_html=True)
    st.markdown(
        '<div style="display:flex;gap:8px;flex-wrap:wrap;margin:6px 0 14px">'
        + "".join(T.rozet(m, r) for m, r in (("Ödendi", "yesil"), ("Bekliyor", "amber"),
                                             ("Gecikmiş", "kirmizi"), ("Yolda", "cyan"), ("Taslak", "mor")))
        + '</div>', unsafe_allow_html=True)
    st.markdown(
        '<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:8px">'
        + T.mesaj("bilgi", "Kur her sabah 09:00'da güncellenir.")
        + T.mesaj("basari", "Sevk kaydedildi, stok düşüldü.")
        + T.mesaj("uyari", "3 üründe maliyet girilmemiş; marj %100 görünüyor.")
        + T.mesaj("hata", "Stok güncellenemedi. İşlem Sistem Kayıtları'na yazıldı.")
        + '</div>', unsafe_allow_html=True)
    st.markdown('<div style="height:12px"></div>', unsafe_allow_html=True)
    st.markdown(
        '<div style="display:flex;flex-direction:column;gap:6px;max-width:720px">'
        + "".join(
            '<div style="display:flex;align-items:center;justify-content:space-between;gap:8px;'
            'padding:6px 10px;border-radius:8px;background:var(--k-yuzey1);border:1px solid var(--k-kenar)">'
            + T.urun_etiketi(ad, sku, kalin=True)
            + f'<span style="color:var(--k-kirmizi);font-size:12px;font-weight:700;flex-shrink:0">{g}g</span></div>'
            for ad, sku, g in (
                ("FAZEON F14 PLUS 14\" DİZÜSTÜ BİLGİSAYAR INTEL N100 8GB 256GB SSD GRİ", "F14P-8256G", 4),
                ("FAZEON F14 PLUS 14\" DİZÜSTÜ BİLGİSAYAR INTEL N100 16GB 512GB SSD SİYAH", "F14P-16512S", 6)))
        + '</div>', unsafe_allow_html=True)
    st.markdown('<div style="height:12px"></div>', unsafe_allow_html=True)
    st.markdown(T.bos_durum("Bekleyen sevk yok",
                            "Yeni sevk Depo → Depolar Arası Sevk sayfasından açılır.",
                            "local_shipping"), unsafe_allow_html=True)


def goster():
    st.markdown(T.baslik("🎨 Yönetim", "Tasarım Rehberi",
                         aciklama="Programdaki ortak parçaların tamamı. Yeni ekran yaparken buradan seç."),
                unsafe_allow_html=True)
    tema = st.segmented_control("Tema önizlemesi", ["Koyu", "Açık"], default="Koyu",
                                key="rehber_tema", label_visibility="collapsed") or "Koyu"
    acik = tema == "Açık"
    if acik:
        st.markdown(T.mesaj("bilgi", "Bileşenlerin açık temadaki hâli. Programın tamamını açık temada görmek "
                                     "için sol menüde HESAP › Görünüm'den Açık'ı seç."),
                    unsafe_allow_html=True)
    anahtar = "rehber_acik" if acik else "rehber_koyu"
    st.markdown(f'<style>.st-key-rehber_acik{{{T.tema_degiskenleri("acik")}'
                'background:var(--k-yuzey0);color:var(--k-metin);border-radius:14px;padding:6px 18px 18px;}'
                '.st-key-rehber_acik code{background:var(--k-ortu2);color:var(--k-mor2);}</style>',
                unsafe_allow_html=True)
    with st.container(key=anahtar):
        _bolum("Renkler", "Her rengin bir anlamı var: yeşil iyi, kırmızı acil, amber dikkat, "
                          "camgöbeği bilgi, mor marka/nötr. Süs için renk kullanılmaz.")
        _renkler("acik" if acik else "koyu")
        _bolum("Yazı ölçeği", "Yedi boyut. Rakamlar eşit genişlikte (mono) yazılır ki sütunlarda hizalansın.")
        _tipografi()
        _bolum("Düğmeler", "Sayfada göz önce ana düğmeyi bulmalı.")
        _dugmeler()
        _bolum("Kartlar, rozetler, mesajlar, liste satırı, boş durum")
        _bilesenler()
