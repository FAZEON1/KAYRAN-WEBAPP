# -*- coding: utf-8 -*-
"""Telefona uygulama gibi kurulum (Ekim 2026).

Streamlit sayfanın <head> kısmını yazmaya izin vermez; bu yüzden küçük bir betik (st.components.v1.html,
yükseklik 0) uygulama belgesine ve — Streamlit Cloud uygulamayı kendi çerçevesinin içinde açtığı için —
erişilebiliyorsa en dıştaki belgeye şunları ekler:
  · <link rel="manifest">  static/manifest.json (ad, simge, tam ekran açılış)
  · <link rel="apple-touch-icon">  iPhone ana ekran simgesi
  · iOS / Android "uygulama gibi aç" ve tema rengi meta etiketleri
Dosyalar static/ klasöründe; .streamlit/config.toml'da enableStaticServing açık (adres: <uygulama>/app/static/).
Adresler uygulamanın kendi yolundan hesaplanır (Cloud'da /~/+/ altında da doğru çıkar).

kurulum_betigi() saf (test edilir). Telefonda nasıl kurulacağını kisi menüsündeki "Telefona kur" anlatır.
"""
import json

TEMA = "#0B1120"
AD = "KAYRAN"


# Streamlit Cloud'un kendi simge / uygulama tanımı etiketleri: telefon önce bunları görüp Streamlit
# simgesiyle kuruyordu (Ekim 2026, kullanıcı bildirimi). Bizimkiler data-kayran taşır, onlar silinir.
YABANCI = ('link[rel="manifest"],link[rel~="icon"],link[rel="apple-touch-icon"],'
           'link[rel="apple-touch-icon-precomposed"],link[rel="mask-icon"],'
           'meta[name="apple-mobile-web-app-title"],meta[name="application-name"],meta[name="theme-color"]')


def kurulum_betigi():
    """Sayfaya eklenecek <script>: yabancı simge / manifest etiketlerini kaldırır (her çalışmada; geri
    eklenen olursa bir sonraki çizimde yine kalkar), bizimkileri bir kez ekler. Hata verirse sessiz geçer."""
    ayar = json.dumps({"tema": TEMA, "ad": AD, "yabanci": YABANCI})
    return ("<script>(function(){try{var A=" + ayar + ";"
            "var app=window.parent;var taban=new URL('app/static/',app.location.href.split('?')[0].replace(/[^/]*$/,''));"
            "function temizle(d){d.querySelectorAll(A.yabanci).forEach(function(e){"
            "if(!e.hasAttribute('data-kayran'))e.remove();});}"
            "function ekle(d){if(!d||!d.head)return;temizle(d);"
            "if(d.getElementById('kayran-manifest'))return;var h=d.head;"
            "function el(t,o){var e=d.createElement(t);e.setAttribute('data-kayran','1');"
            "for(var k in o)e.setAttribute(k,o[k]);h.appendChild(e);return e;}"
            "el('link',{id:'kayran-manifest',rel:'manifest',href:new URL('manifest.json',taban).href});"
            "el('link',{rel:'icon',type:'image/png',sizes:'192x192',href:new URL('ikon-192.png',taban).href});"
            "el('link',{rel:'apple-touch-icon',sizes:'180x180',href:new URL('apple-touch-icon.png',taban).href});"
            "el('meta',{name:'apple-mobile-web-app-capable',content:'yes'});"
            "el('meta',{name:'mobile-web-app-capable',content:'yes'});"
            "el('meta',{name:'apple-mobile-web-app-status-bar-style',content:'black-translucent'});"
            "el('meta',{name:'apple-mobile-web-app-title',content:A.ad});"
            "el('meta',{name:'application-name',content:A.ad});"
            "el('meta',{name:'theme-color',content:A.tema});}"
            "ekle(app.document);try{if(window.top!==app)ekle(window.top.document);}catch(e){}"
            "}catch(e){}})();</script>")


KURULUM_ADIMLARI = {
    "iPhone (Safari)": [
        "Programı Safari'de aç ve giriş yap.",
        "Alttaki Paylaş düğmesine (yukarı oklu kare) dokun.",
        "\"Ana Ekrana Ekle\"yi seç, adı KAYRAN olarak bırak, \"Ekle\"ye dokun.",
        "Ana ekrandaki KAYRAN simgesinden aç.",
    ],
    "Android (Chrome)": [
        "Programı Chrome'da aç ve giriş yap.",
        "Sağ üstteki üç noktaya dokun.",
        "\"Uygulamayı yükle\" ya da \"Ana ekrana ekle\"yi seç ve onayla.",
        "Ana ekrandaki KAYRAN simgesinden aç.",
    ],
}
