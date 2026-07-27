"""Kâr/marj gizleme katmanı.

NEDEN: Girilmemiş destekler ve masraflar yüzünden brüt/net kâr ve marj
rakamları şu an gerçeği yansıtmıyor. Yanlış rakamla karar alınmasın diye
bu değerler yalnızca yetkili kullanıcıya gösterilir; diğerleri "•••" görür.
Ciro, adet, stok gibi FİZİKSEL/GELİR bilgileri herkese açık kalır — onlar
doğru.

TEK NOKTA: gösterim katmanları (kart üreticileri, tablolar) buradan geçer;
hesaplama mantığına dokunulmaz, yalnız ekrana basılan değer maskelenir.

AYAR: Yetkiyi genişletmek için KAR_GOREBILEN'e kullanıcı adı ekle.
Rakamlar düzeldiğinde bu dosyadaki KAR_GIZLE_AKTIF = False yapmak
maskelemeyi komple kapatır (kod değişikliği gerekmez).
"""

KAR_GIZLE_AKTIF = True
KAR_GOREBILEN = {"ibrahim"}

# Etiket/kolon adı bunlardan birini içeriyorsa maskelenir (küçük harf karşılaştırma)
GIZLI_ANAHTARLAR = (
    "kâr", "kar ", "kar)", "kârlılık", "karlilik",
    "marj", "cogs", "p&l", "pnl",
)

MASKE = "•••"


def _kullanici():
    try:
        import streamlit as st
        return (st.session_state.get("aktif_kullanici") or "").strip().lower()
    except Exception:
        return ""


def kar_gorunur():
    """Aktif kullanıcı kâr/marj rakamlarını görebilir mi?"""
    if not KAR_GIZLE_AKTIF:
        return True
    return _kullanici() in KAR_GOREBILEN


def _gizli_mi(etiket):
    e = str(etiket or "").strip().lower()
    if not e:
        return False
    return any(k in e for k in GIZLI_ANAHTARLAR)


def kart_maskele(satirlar):
    """[(etiket, deger, renk), …] listesindeki kâr/marj değerlerini maskeler.
    Üç elemanlıdan farklı biçimler olduğu gibi bırakılır."""
    if kar_gorunur():
        return satirlar
    out = []
    for s in (satirlar or []):
        try:
            if isinstance(s, (list, tuple)) and len(s) >= 2 and _gizli_mi(s[0]):
                yeni = list(s)
                yeni[1] = MASKE
                if len(yeni) >= 3:
                    yeni[2] = "#64748B"   # nötr gri — yeşil/kırmızı ipucu vermesin
                out.append(tuple(yeni))
                continue
        except Exception:
            pass
        out.append(s)
    return out


def df_maskele(df):
    """DataFrame'deki kâr/marj kolonlarını maskeler (kolon adına göre)."""
    if kar_gorunur() or df is None:
        return df
    try:
        gizli = [c for c in df.columns if _gizli_mi(c)]
        if not gizli:
            return df
        df = df.copy()
        for c in gizli:
            df[c] = MASKE
        return df
    except Exception:
        return df


def kayit_maskele(kayitlar):
    """[{...}, …] sözlük listesindeki kâr/marj alanlarını maskeler."""
    if kar_gorunur():
        return kayitlar
    out = []
    for r in (kayitlar or []):
        if isinstance(r, dict):
            out.append({k: (MASKE if _gizli_mi(k) else v) for k, v in r.items()})
        else:
            out.append(r)
    return out


def deger(etiket, deger_str):
    """Tek bir değeri etiketine göre maskeler."""
    return MASKE if (not kar_gorunur() and _gizli_mi(etiket)) else deger_str


def uyari_ciz():
    """Maskelenen kullanıcıya tek satırlık açıklama şeridi."""
    if kar_gorunur():
        return
    try:
        import streamlit as st
        st.info("🔒 Kâr ve marj rakamları şu an gizli. Girilmemiş destek ve "
                "masraflar nedeniyle bu değerler henüz doğru sonuç vermiyor; "
                "düzeltme tamamlanınca yeniden açılacak. Ciro, adet ve stok "
                "bilgileri güncel ve doğrudur.")
    except Exception:
        pass
