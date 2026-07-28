# -*- coding: utf-8 -*-
"""
otonom/geri_yukle.py — SİLİNEN İTHALAT DOSYASINI GERİ YÜKLE

Gece yedeğinden (kayran-yedek artifact'ı) tek bir ithalat dosyasını ve onun
tüm kalemlerini geri yazar.

GÜVENLİK TASARIMI:
  • VARSAYILAN KURU ÇALIŞMA — hiçbir şey yazmaz, ne yapacağını yazdırır.
    Yazması için ONAY ortam değişkeni tam olarak "EVET" olmalı.
  • Kayıt zaten varsa yazmayı REDDEDER (mükerrer oluşmasın).
  • Sadece ithalat_dosyalari + ithalat_kalemleri tablolarına, sadece
    belirtilen dosya_id için dokunur. Başka hiçbir tabloya değmez.
  • MOD=eksikler tamamen okunur — asla yazmaz.

Ortam değişkenleri:
  SUPABASE_URL, SUPABASE_KEY — GitHub Secrets'tan
  YEDEK_DIZIN — artifact'ın indirildiği klasör (varsayılan "yedek")
  MOD         — "eksikler" ise yedek ile canlıyı karşılaştırır, çıkar
  DOSYA_ID    — geri yüklenecek kayıt kimliği
  ARA         — kimlik yerine METİNLE ara (dosya_no / tedarikci /
                ithalat_takip_no / pi_no / sas_no içinde geçer).
                Doluysa sadece LİSTELER, yazmaz.
  ONAY        — "EVET" ise gerçekten yazar; aksi halde kuru çalışma
"""
import ast
import json
import os
import sys
import glob

import pandas as pd

DOSYA_TABLO = "ithalat_dosyalari"
KALEM_TABLO = "ithalat_kalemleri"
JSON_KOLONLAR = ("masraflar", "grup_masraf_atama")

# Arama bu kolonların hepsine bakar. ithalat_takip_no'nun burada olmaması
# 2025-14 dosyasının "hiç girilmemiş" sanılmasına yol açtı — tekrarlamasın.
ARAMA_KOLONLARI = ("dosya_no", "tedarikci", "ithalat_takip_no", "pi_no", "sas_no")


def _coz(v):
    """Excel'e metin olarak yazılmış dict/JSON değerini geri çevirir."""
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    if isinstance(v, (dict, list)):
        return v
    s = str(v).strip()
    if not s or s.lower() in ("nan", "none", "null"):
        return None
    for _p in (json.loads, ast.literal_eval):
        try:
            return _p(s)
        except Exception:
            continue
    return None


def _temiz(satir):
    """pandas satırını Supabase'e yazılabilir sözlüğe çevirir."""
    out = {}
    for k, v in satir.items():
        if isinstance(v, float) and pd.isna(v):
            out[k] = None
        elif isinstance(v, pd.Timestamp):
            out[k] = v.strftime("%Y-%m-%d")
        elif k in JSON_KOLONLAR:
            out[k] = _coz(v) or {}
        elif hasattr(v, "item"):          # numpy tipleri
            out[k] = v.item()
        else:
            out[k] = v
    return out


def _yedegi_bul(dizin):
    adaylar = sorted(glob.glob(os.path.join(dizin, "**", "*.xlsx"), recursive=True))
    if not adaylar:
        sys.exit(f"HATA: {dizin} altında .xlsx bulunamadı.")
    return adaylar[-1]


def _canli_kimlikler(url, key):
    """ithalat_dosyalari'ndaki tüm id'leri sayfalayarak çeker."""
    from supabase import create_client
    sb = create_client(url, key)
    kimlikler, adim, bas = set(), 1000, 0
    while True:
        par = (sb.table(DOSYA_TABLO).select("id")
               .order("id").range(bas, bas + adim - 1).execute().data) or []
        if not par:
            break
        kimlikler.update(int(r["id"]) for r in par if r.get("id") is not None)
        if len(par) < adim:
            break
        bas += adim
    return kimlikler


def _eksikleri_listele(yedek, url, key):
    """Yedekte olup canlıda olmayan dosyaları döker. HİÇBİR ŞEY YAZMAZ."""
    df_d = pd.read_excel(yedek, sheet_name=DOSYA_TABLO)
    yedek_kimlik = {int(x) for x in df_d["id"].dropna().astype(int)}
    canli = _canli_kimlikler(url, key)

    eksik = sorted(yedek_kimlik - canli)
    fazla = sorted(canli - yedek_kimlik)

    print(f"📊 Yedekteki dosya sayısı : {len(yedek_kimlik)}")
    print(f"📊 Canlıdaki dosya sayısı : {len(canli)}")
    print(f"📊 En büyük yedek kimliği : {max(yedek_kimlik) if yedek_kimlik else '—'}")
    print(f"📊 En büyük canlı kimliği : {max(canli) if canli else '—'}\n")

    if not eksik:
        print("✅ Yedekteki her dosya canlıda mevcut. Eksik yok.")
    else:
        print(f"── YEDEKTE VAR, CANLIDA YOK ({len(eksik)} dosya) ──")
        ind = df_d.set_index("id")
        for i in eksik:
            try:
                r = ind.loc[i]
            except Exception:
                print(f"  id={i}  (yedekte satır okunamadı)")
                continue
            print(f"  id={i:<6} takip={str(r.get('ithalat_takip_no','') or '—'):10} "
                  f"dosya_no={str(r.get('dosya_no','') or '—'):14} "
                  f"tedarikci={str(r.get('tedarikci','') or '—')[:28]:28} "
                  f"tarih={str(r.get('tarih',''))[:10]:12} durum={r.get('durum','') or '—'}")
        print("\n🔁 Geri yüklemek için her biri: DOSYA_ID=<id>, ONAY=EVET")

    if fazla:
        print(f"\nℹ️  Canlıda olup yedekte olmayan {len(fazla)} kimlik "
              f"(yedekten SONRA oluşmuş): {fazla[:40]}")

    print("\n🔍 Ölçüm modu — hiçbir şey yazılmadı.")


def main():
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_KEY")
    if not url or not key:
        sys.exit("HATA: SUPABASE_URL / SUPABASE_KEY yok.")

    mod = (os.environ.get("MOD") or "").strip().lower()
    ara = (os.environ.get("ARA") or "").strip()
    onay = os.environ.get("ONAY", "").strip().upper() == "EVET"
    dizin = os.environ.get("YEDEK_DIZIN", "yedek")

    yedek = _yedegi_bul(dizin)
    print(f"📦 Yedek dosyası : {os.path.basename(yedek)}")

    # ── EKSİKLER MODU: yedek ile canlıyı karşılaştır, çık ──
    if mod == "eksikler":
        print("🎯 Aranan kayıt  : —  (EKSİKLERİ LİSTELE modu)")
        print("🔐 Mod           : SALT OKUNUR — hiçbir şey yazılmaz\n")
        _eksikleri_listele(yedek, url, key)
        return

    dosya_id = None
    if not ara:
        try:
            dosya_id = int(os.environ.get("DOSYA_ID", "").strip())
        except Exception:
            sys.exit("HATA: DOSYA_ID sayı olmalı (ya da ARA doldur, ya da MOD=eksikler).")

    print(f"🎯 Aranan kayıt  : "
          + (f"metin '{ara}'" if ara else f"{DOSYA_TABLO}.id = {dosya_id}"))
    print(f"🔐 Mod           : {'YAZMA (ONAY=EVET)' if onay else 'KURU ÇALIŞMA — hiçbir şey yazılmaz'}\n")

    xl = pd.ExcelFile(yedek)
    if DOSYA_TABLO not in xl.sheet_names:
        sys.exit(f"HATA: Yedekte '{DOSYA_TABLO}' sayfası yok.")

    df_d = pd.read_excel(yedek, sheet_name=DOSYA_TABLO)

    # ── ARAMA MODU: kimliği bilmiyorsan metinle bul ──
    if ara:
        _a = ara.lower()

        def _esles(r):
            for k in ARAMA_KOLONLARI:
                if _a in str(r.get(k, "") or "").lower():
                    return True
            return False

        _m = df_d[df_d.apply(_esles, axis=1)]
        if _m.empty:
            print(f"\n❌ '{ara}' ile eşleşen kayıt yok.")
            print(f"   Taranan kolonlar: {', '.join(ARAMA_KOLONLARI)}")
            return                      # 'sonuç yok' bir hata değil → exit 0
        print(f"\n── EŞLEŞEN {len(_m)} KAYIT ──")
        for _, r in _m.iterrows():
            print(f"  id={int(r['id']):<6} takip={str(r.get('ithalat_takip_no','') or '—'):10} "
                  f"dosya_no={str(r.get('dosya_no','') or '—'):14} "
                  f"tedarikci={str(r.get('tedarikci','') or '—')[:28]:28} "
                  f"tarih={str(r.get('tarih',''))[:10]:12} durum={r.get('durum','') or '—'}")
        print("\n🔍 Geri yüklemek istediğin kimliği DOSYA_ID alanına yazıp tekrar çalıştır.")
        return

    hedef = df_d[df_d["id"] == dosya_id]
    if hedef.empty:
        print(f"❌ Bu yedekte id={dosya_id} YOK.")
        print("   Kayıt bu yedek alındıktan SONRA oluşturulmuş olabilir.")
        print("   Mevcut kimlikler (son 15):", sorted(df_d["id"].dropna().astype(int))[-15:])
        sys.exit(1)

    dosya = _temiz(hedef.iloc[0].to_dict())
    print("── GERİ YÜKLENECEK DOSYA ──")
    for k in ("id", "dosya_no", "pi_no", "sas_no", "tarih", "tedarikci",
              "doviz", "kur", "durum", "teslim_tarihi", "teslim_deposu",
              "ithalat_takip_no"):
        if k in dosya and dosya[k] not in (None, ""):
            print(f"  {k:20} {dosya[k]}")
    if dosya.get("masraflar"):
        print(f"  {'masraflar':20} {dosya['masraflar']}")
    if dosya.get("grup_masraf_atama"):
        print(f"  {'grup_masraf_atama':20} {dosya['grup_masraf_atama']}")

    kalemler = []
    if KALEM_TABLO in xl.sheet_names:
        df_k = pd.read_excel(yedek, sheet_name=KALEM_TABLO)
        if "dosya_id" in df_k.columns:
            kalemler = [_temiz(r) for _, r in df_k[df_k["dosya_id"] == dosya_id].iterrows()]

    print(f"\n── KALEMLER ({len(kalemler)} satır) ──")
    for k in kalemler:
        print(f"  {str(k.get('sku','')):22} {str(k.get('urun_grubu','') or '—'):16} "
              f"adet {k.get('adet')} × FOB {k.get('birim_fob')}")
    _tfob = sum(float(k.get("adet") or 0) * float(k.get("birim_fob") or 0) for k in kalemler)
    print(f"  {'':22} {'TOPLAM FOB':16} {_tfob:,.2f}")

    if not onay:
        print("\n🔍 Kuru çalışma bitti. Yazmak için iş akışını ONAY='EVET' ile tekrar çalıştır.")
        return

    # ── Yazma ── (supabase yalnız burada gerekir; kuru çalışma kütüphanesiz döner)
    from supabase import create_client
    sb = create_client(url, key)
    mevcut = sb.table(DOSYA_TABLO).select("id").eq("id", dosya_id).execute().data or []
    if mevcut:
        sys.exit(f"❌ id={dosya_id} ZATEN VAR — mükerrer oluşmasın diye durduruldu.")

    try:
        sb.table(DOSYA_TABLO).insert(dosya).execute()
        yeni_id = dosya_id
        print(f"\n✅ Dosya geri yazıldı (id={yeni_id}).")
    except Exception as e:
        # id kolonu 'generated always' ise açık id reddedilir → id'siz dene
        print(f"  ! Açık id ile yazılamadı ({str(e)[:90]}) — id'siz deneniyor…")
        dosya.pop("id", None)
        res = sb.table(DOSYA_TABLO).insert(dosya).execute()
        yeni_id = (res.data or [{}])[0].get("id")
        if not yeni_id:
            sys.exit("❌ Dosya yazılamadı.")
        print(f"\n✅ Dosya geri yazıldı — YENİ id={yeni_id} (eski {dosya_id}).")

    if kalemler:
        for k in kalemler:
            k.pop("id", None)
            k["dosya_id"] = yeni_id
        sb.table(KALEM_TABLO).insert(kalemler).execute()
        print(f"✅ {len(kalemler)} kalem geri yazıldı.")

    print("\n🎉 Bitti. Programda İthalat → Geçmiş İthalatlar'dan kontrol et.")


if __name__ == "__main__":
    main()
