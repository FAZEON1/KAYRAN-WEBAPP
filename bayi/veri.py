# -*- coding: utf-8 -*-
"""Bayi Portalı — veri katmanı.

Üç veri alanını okur/yazar:
  1) Cari bakiye  → "Toplam Aktifler"e yüklenen Cari Alacaklar Excel'inin satır
                    detayı (aktif_excel_verileri · dosya_tipi='cari_detay').
  2) Bayi hesapları → bayi_kullanicilar tablosu (CRUD).
  3) Servis takibi → ts_kayitlar / ts_gecmis (teknik servis modülü), bayinin
                     cari unvanına göre FİLTRELİ, SALT-OKUNUR.

Tasarım notu: Bakiye için ayrı bir tablo tutulmaz; kaynak tek noktadır (yüklenen
Excel). Bu, verinin muhasebedeki gerçekle her yükleme sonrası senkron kalmasını
sağlar. Dated ekstre (hareket dökümü) Faz 1 kapsamı dışındadır — mevcut Excel
yalnızca güncel bakiye snapshot'ı içerir.
"""
from datetime import datetime, timezone, timedelta

import streamlit as st
from supabase import create_client, Client

TR_TZ = timezone(timedelta(hours=3))


# ── Supabase istemcisi ──────────────────────────────────────────────
@st.cache_resource(show_spinner=False)
def get_client() -> Client:
    """Süreç başına tek Supabase bağlantısı (sunucu tarafı; anahtar tarayıcıya gitmez)."""
    url = st.secrets["supabase"]["url"]
    key = st.secrets["supabase"].get("service_role_key") or st.secrets["supabase"]["key"]
    return create_client(url, key)


def _rows(resp):
    return resp.data if resp.data else []


def _row(resp):
    d = resp.data if resp.data else None
    return d[0] if isinstance(d, list) and d else (d or None)


def _f(v, d=0.0):
    try:
        if v is None or v == "":
            return float(d)
        return float(v)
    except (TypeError, ValueError):
        return float(d)


def _simdi_iso():
    return datetime.now(TR_TZ).isoformat(timespec="seconds")


def _norm(s):
    """Unvan/kod karşılaştırması için normalize: kırp + tek boşluk + büyük harf."""
    return " ".join(str(s or "").split()).upper()


# ════════════════════════════════════════════════════════════════════
# 1) CARİ BAKİYE — yüklenen Cari Alacaklar Excel'inden
# ════════════════════════════════════════════════════════════════════
@st.cache_data(ttl=120, show_spinner=False)
def cari_detay_tumu():
    """Cari Alacaklar Excel'inin satır detayını döndürür.

    Kaynak: aktif_excel_verileri (dosya_tipi='cari_detay'), kayranacc yükleme
    akışında yazılır. Her satır:
      {kod, unvan, doviz, borc, alacak, bakiye}
    (bakiye < 0 → siz borçlusunuz; bakiye > 0 → cari size borçlu = ALACAK)

    Detay henüz yazılmamışsa (eski yükleme) boş liste döner.
    """
    try:
        from kayranacc.database import aktif_excel_oku
        v = aktif_excel_oku("ortak", "cari_detay")
        return v if isinstance(v, list) else []
    except Exception:
        return []


def cari_bakiye(cari_kod=None, cari_unvan=None):
    """Bir bayinin güncel cari durumu — BAYİ PERSPEKTİFİNDE. Önce kod, yoksa unvan.

    Kaynak Excel şirket defteri perspektifindedir: orada `bakiye > 0` "cari şirkete
    borçlu" demektir; bu, BAYİ açısından BORÇ'tur. Burada işaret bayiye çevrilir:
      bayi_borc   = şirket-defteri pozitif bakiyelerin toplamı (bayinin ödeyeceği)
      bayi_alacak = şirket-defteri negatif bakiyelerin mutlak toplamı (bayi lehine)
      net         = bayi_borc − bayi_alacak   (net > 0 → bayi borçlu)

    Döner: {
        'bulundu': bool,
        'satirlar': [ {kod, unvan, doviz, borc, alacak, bakiye}, ... ],  # ham satırlar
        'doviz_bazli': { 'USD': {'bayi_borc','bayi_alacak','net'}, 'TL': {...}, ... },
    }
    """
    kod_n = _norm(cari_kod)
    unvan_n = _norm(cari_unvan)
    satirlar = []
    for r in cari_detay_tumu():
        if unvan_n:
            # Unvan birincil anahtar (bayi = firma). Bir firmanın birden çok döviz
            # alt-hesabı olabilir → hepsi gösterilir. kod verilmişse tek alt-hesaba daralt.
            if _norm(r.get("unvan")) == unvan_n and (not kod_n or _norm(r.get("kod")) == kod_n):
                satirlar.append(r)
        elif kod_n and _norm(r.get("kod")) == kod_n:
            satirlar.append(r)

    doviz_bazli = {}
    for r in satirlar:
        d = _norm(r.get("doviz")) or "TL"
        doviz_bazli.setdefault(d, {"bayi_borc": 0.0, "bayi_alacak": 0.0, "net": 0.0})
        bakiye = _f(r.get("bakiye"))          # şirket-defteri işareti
        if bakiye > 0:                        # cari şirkete borçlu → bayinin borcu
            doviz_bazli[d]["bayi_borc"] += bakiye
        elif bakiye < 0:                      # şirket cariye borçlu → bayi lehine
            doviz_bazli[d]["bayi_alacak"] += abs(bakiye)
        doviz_bazli[d]["net"] = doviz_bazli[d]["bayi_borc"] - doviz_bazli[d]["bayi_alacak"]

    return {
        "bulundu": bool(satirlar),
        "satirlar": satirlar,
        "doviz_bazli": doviz_bazli,
    }


@st.cache_data(ttl=120, show_spinner=False)
def cari_secenekleri():
    """Admin ekranı için benzersiz UNVAN listesi — yüklenen cari detayından.

    Aynı firmanın birden çok döviz alt-hesabı (kod) tek unvana toplanır; admin
    unvanla bağlar, bayi tüm dövizlerini görür. Döner: [{unvan, kodlar:[...]}].
    """
    grup = {}
    for r in cari_detay_tumu():
        unvan = str(r.get("unvan") or "").strip()
        if not unvan:
            continue
        kod = str(r.get("kod") or "").strip()
        grup.setdefault(_norm(unvan), {"unvan": unvan, "kodlar": []})
        if kod and kod not in grup[_norm(unvan)]["kodlar"]:
            grup[_norm(unvan)]["kodlar"].append(kod)
    secenek = list(grup.values())
    secenek.sort(key=lambda x: x["unvan"].lower())
    return secenek


# ════════════════════════════════════════════════════════════════════
# 2) BAYİ KULLANICILARI — bayi_kullanicilar tablosu (CRUD)
# ════════════════════════════════════════════════════════════════════
def bayi_kullanici_getir(kullanici_adi):
    """Kullanıcı adına göre bayi kaydını döndürür (aktif/pasif fark etmeksizin)."""
    k = (kullanici_adi or "").strip().lower()
    if not k:
        return None
    try:
        return _row(get_client().table("bayi_kullanicilar")
                    .select("*").eq("kullanici_adi", k).limit(1).execute())
    except Exception:
        return None


@st.cache_data(ttl=30, show_spinner=False)
def bayi_kullanici_listele():
    """Tüm bayi hesapları (admin ekranı)."""
    try:
        return _rows(get_client().table("bayi_kullanicilar")
                     .select("*").order("olusturma_tarihi", desc=True).execute())
    except Exception:
        return []


def bayi_kullanici_ekle(kullanici_adi, sifre_hash, cari_unvan, cari_kod="",
                        ad_soyad="", email="", telefon="", notlar=""):
    """Yeni bayi hesabı ekler. Döner: (ok, mesaj)."""
    k = (kullanici_adi or "").strip().lower()
    if not k:
        return False, "Kullanıcı adı boş olamaz."
    if not (cari_unvan or "").strip():
        return False, "Cari unvan zorunlu (servis eşleşmesi için)."
    if bayi_kullanici_getir(k):
        return False, f"'{k}' kullanıcı adı zaten var."
    try:
        get_client().table("bayi_kullanicilar").insert({
            "kullanici_adi": k, "sifre_hash": sifre_hash,
            "cari_kod": (cari_kod or "").strip(), "cari_unvan": cari_unvan.strip(),
            "ad_soyad": (ad_soyad or "").strip(), "email": (email or "").strip(),
            "telefon": (telefon or "").strip(), "aktif": True,
            "olusturma_tarihi": _simdi_iso(), "notlar": (notlar or "").strip(),
        }).execute()
        _liste_temizle()
        return True, f"✅ '{k}' bayi hesabı oluşturuldu."
    except Exception as e:
        return False, f"❌ Hata: {type(e).__name__}: {str(e)[:160]}"


def bayi_kullanici_guncelle(kullanici_id, alanlar):
    """Verilen alanları günceller (sözlük). Döner: (ok, mesaj)."""
    try:
        get_client().table("bayi_kullanicilar").update(alanlar).eq("id", kullanici_id).execute()
        _liste_temizle()
        return True, "✅ Güncellendi."
    except Exception as e:
        return False, f"❌ Hata: {type(e).__name__}: {str(e)[:160]}"


def bayi_aktiflik_degistir(kullanici_id, aktif):
    """Bayiyi aktifleştir/pasifleştir."""
    return bayi_kullanici_guncelle(kullanici_id, {"aktif": bool(aktif)})


def bayi_sifre_guncelle(kullanici_id, yeni_hash):
    """Şifre hash'ini günceller."""
    return bayi_kullanici_guncelle(kullanici_id, {"sifre_hash": yeni_hash})


def son_giris_yaz(kullanici_adi):
    """Başarılı girişte son_giris zaman damgasını günceller (best-effort)."""
    k = (kullanici_adi or "").strip().lower()
    if not k:
        return
    try:
        get_client().table("bayi_kullanicilar").update(
            {"son_giris": _simdi_iso()}).eq("kullanici_adi", k).execute()
        _liste_temizle()
    except Exception:
        pass


def _liste_temizle():
    try:
        bayi_kullanici_listele.clear()
    except Exception:
        pass


# ════════════════════════════════════════════════════════════════════
# 3) SERVİS TAKİBİ — ts_kayitlar / ts_gecmis (salt-okunur, cari FİLTRELİ)
# ════════════════════════════════════════════════════════════════════
@st.cache_data(ttl=60, show_spinner=False)
def bayi_servis_kayitlari(cari_unvan):
    """Bayinin cari unvanına ait tüm servis/iade kayıtları (yeni→eski).

    ts_kayitlar.firma_bilgisi alanı ile eşleşir (teknik servis mal kabulünde
    'Firma (Cari Unvan)' buraya yazılır). Eşleşme büyük/küçük harf duyarsız.
    """
    unvan = (cari_unvan or "").strip()
    if not unvan:
        return []
    try:
        # ilike ile tam eşleşme (case-insensitive); wildcard YOK → başka cariye sızmaz
        rows = _rows(get_client().table("ts_kayitlar")
                     .select("*").ilike("firma_bilgisi", unvan)
                     .order("id", desc=True).execute())
        return rows
    except Exception:
        return []


def bayi_servis_gecmisi(kayit_id):
    """Bir servis kaydının durum geçmişi (eski→yeni). ts_gecmis tablosundan."""
    try:
        return _rows(get_client().table("ts_gecmis")
                     .select("*").eq("kayit_id", kayit_id)
                     .order("tarih", desc=False).execute())
    except Exception:
        return []
