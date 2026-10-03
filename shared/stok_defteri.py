# -*- coding: utf-8 -*-
"""KAYRAN — Stok hareket defteri.

Her stok değişimi 'stok_hareketleri' tablosuna bir satır olarak yazılır:
ne zaman, hangi SKU, hangi depo, önce/sonra kaç, hangi işlemden, kim.
BAŞARISIZ denemeler de yazılır (neden başarısız olduğuyla) — "stok neden
düşmedi?" sorusunun cevabı artık kayıtta.

Kapsanan yollar (kayranpm/database.py):
  · stok_hareket_coklu  — satış, iade, teknik servis, ithalat teslimi…
  · depo_sevk           — depolar arası sevk
  · upsert_g5f_stok     — Excel/Mikro stok aktarımı (tam liste)
  · Excel senkron sıfırlama (excel_islemler.py)

KURALLAR
  · Defter yazımı ASLA stok işlemini bozmaz (her şey try/except).
  · toplu() bağlamında satırlar biriktirilir, sonda tek istekle yazılır
    (500 SKU'luk Excel aktarımı 500 ek istek yapmasın).
  · Tampon oturum/iş parçacığı başınadır — iki kullanıcının kayıtları
    birbirine karışmaz.
  · yukleme(kod) bağlamındaki her hareket o yüklemenin koduyla işaretlenir
    (yukleme_kodu sütunu, veritabani/13_yukleme_kodu.sql). Böylece bir Excel
    yüklemesinin stok etkisi sonradan tam olarak bulunup ters çevrilebilir
    (shared/yukleme_gecmisi). Sütun yoksa işaretsiz yazılır, defter durmaz.
"""
import contextlib
import contextvars
import inspect
import threading

TABLO = "stok_hareketleri"
_yerel = threading.local()
_YUKLEME = contextvars.ContextVar("stok_defteri_yukleme_kodu", default="")


@contextlib.contextmanager
def yukleme(kod):
    """Bu blok içindeki bütün stok hareketleri 'kod' ile işaretlenir (yükleme geçmişi)."""
    tok = _YUKLEME.set(str(kod or "")[:40])
    try:
        yield
    finally:
        _YUKLEME.reset(tok)


def aktif_yukleme():
    return _YUKLEME.get()

# Bu dosyalardaki çerçeveler "kaynak" sayılmaz (asıl çağıranı bul).
# Yol SONU ile karşılaştırılır — alt dize eşleşmesi 'test_stok_defteri.py'
# gibi dosyaları da yanlışlıkla atlıyordu.
_ATLA = ("/shared/stok_defteri.py", "/kayranpm/database.py", "/contextlib.py")


def _f(v):
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


def _kullanici():
    try:
        import streamlit as st
        return str(st.session_state.get("aktif_kullanici", "") or "")
    except Exception:
        return ""


def kaynak_bul():
    """Stok işlemini başlatan kod: 'satis/database.py:_stok_uygula_depolu' gibi."""
    try:
        for fr in inspect.stack()[1:25]:
            yol = fr.filename.replace("\\", "/")
            if yol.endswith(_ATLA):
                continue
            parca = yol.split("/")
            kisa = "/".join(parca[-2:]) if len(parca) >= 2 else yol
            return f"{kisa}:{fr.function}"[:120]
    except Exception:
        pass
    return ""


def fark(eski_dk, yeni_dk):
    """İki depo kırılımı arasındaki değişen depolar: [(depo, önce, sonra)]."""
    eski = eski_dk if isinstance(eski_dk, dict) else {}
    yeni = yeni_dk if isinstance(yeni_dk, dict) else {}
    out = []
    for d in sorted(set(eski) | set(yeni)):
        a, b = _f(eski.get(d)), _f(yeni.get(d))
        if abs(a - b) > 1e-9:
            out.append((d, a, b))
    return out


def _tampon():
    return getattr(_yerel, "tampon", None)


def yaz(sku, depo, once, sonra, tur, aciklama="", basarili=True, hata="", kaynak=None):
    """Tek hareket satırı. toplu() içindeyse biriktirir, değilse hemen yazar."""
    try:
        satir = {
            "sku": str(sku or "")[:80], "depo": str(depo or "")[:60],
            "onceki": _f(once), "sonraki": _f(sonra), "degisim": _f(sonra) - _f(once),
            "tur": str(tur or "")[:30], "aciklama": str(aciklama or "")[:300],
            "kaynak": (kaynak if kaynak is not None else kaynak_bul())[:120],
            "kullanici": _kullanici()[:40],
            "basarili": bool(basarili), "hata": str(hata or "")[:500],
        }
        if _YUKLEME.get():
            satir["yukleme_kodu"] = _YUKLEME.get()
        t = _tampon()
        if t is not None:
            t.append(satir)
        else:
            _gonder([satir])
    except Exception:
        pass


def yaz_fark(sku, eski_dk, yeni_dk, tur, aciklama="", kaynak=None):
    """Kırılım farkı kadar satır yaz (değişmeyen depolar yazılmaz)."""
    k = kaynak if kaynak is not None else kaynak_bul()
    for d, a, b in fark(eski_dk, yeni_dk):
        yaz(sku, d, a, b, tur, aciklama, kaynak=k)


def _gonder(satirlar):
    if not satirlar:
        return
    try:
        from shared.auth import _get_supabase
        sb = _get_supabase()
        if not sb:
            return
        for i in range(0, len(satirlar), 500):
            parca = satirlar[i:i + 500]
            try:
                sb.table(TABLO).insert(parca).execute()
            except Exception as e1:
                # yukleme_kodu sütunu henüz yoksa işaretsiz yaz (defter durmasın)
                if "yukleme_kodu" not in str(e1) or not any("yukleme_kodu" in r for r in parca):
                    raise
                sb.table(TABLO).insert([{k: v for k, v in r.items() if k != "yukleme_kodu"}
                                        for r in parca]).execute()
    except Exception as e:
        # Defter yazılamadı — bunu hata kaydına düş (tablo yoksa ilk seferde görünür)
        try:
            from shared.hata_log import kaydet
            kaydet("stok_defteri._gonder", e, f"{len(satirlar)} satır yazılamadı")
        except Exception:
            pass


@contextlib.contextmanager
def toplu():
    """Bu blok içindeki defter satırlarını biriktir, sonda tek seferde yaz.
    İç içe kullanılabilir; yalnız en dıştaki blok yazar."""
    dis = _tampon() is None
    if dis:
        _yerel.tampon = []
    try:
        yield
    finally:
        if dis:
            t, _yerel.tampon = _yerel.tampon, None
            _gonder(t)


def gecmis(sku=None, limit=200, tur=None, yalniz_basarisiz=False):
    """Ekran için hareketler (yeni üstte). Tablo yoksa []."""
    try:
        from shared.auth import _get_supabase
        q = _get_supabase().table(TABLO).select("*").order("zaman", desc=True).limit(limit)
        if sku:
            q = q.eq("sku", sku)
        if tur:
            q = q.eq("tur", tur)
        if yalniz_basarisiz:
            q = q.eq("basarili", False)
        return q.execute().data or []
    except Exception:
        return []
