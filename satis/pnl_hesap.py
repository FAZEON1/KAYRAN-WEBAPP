# -*- coding: utf-8 -*-
"""Satış › Kâr / P&L hesabı — TEK fonksiyon (Ekim 2026).

Eskiden satis/main.py içinde satır satır yazılıydı. Ayrılınca:
  • önceki dönem aynı fonksiyonla hesaplanır (ana kartta ▲/▼),
  • okunamayan kalem SESSİZCE 0 sayılmaz: eksikler listesine yazılır, ekranda görünür,
  • Ref No'nun TL tutarları kaydın tarihindeki kurla çevrilir — Yönetim P&L ile aynı
    kural (yonetim_hesap.tl_usd); eskiden tek kurla (oturum / günün kuru) çevriliyordu.

Bu "katkı kârı"dır (işletme giderleri yok, firma/kategori süzgeci var); Yönetim'in
pnl_topla'sı ayrı bir tanımdır, birleştirilmez.
"""
from datetime import date, timedelta


def _tarih(x):
    return x if isinstance(x, date) else date.fromisoformat(str(x)[:10])


def onceki_donem(bas, bit):
    """Aynı uzunlukta, hemen önceki dönem."""
    b, e = _tarih(bas), _tarih(bit)
    gun = (e - b).days + 1
    return b - timedelta(days=gun), b - timedelta(days=1)


def _tr_upper(s):
    try:
        from kayranpm.ref_no import _tr_upper as tu
        return tu(s)
    except Exception:
        return str(s).replace("i", "İ").replace("ı", "I").upper()


def satis_pnl(bas, bit, kanal_f, kat_f, kaynak, satislar=None):
    """Dönemin katkı kârı. kanal_f / kat_f: "Tümü" ya da değer.
    satislar verilirse yeniden okunmaz (sayfa zaten okumuştur); süzgeç yine uygulanır."""
    from satis.database import ozet_hesapla
    eksik = []
    filtreli = (kanal_f != "Tümü" or kat_f != "Tümü")
    katmap = kaynak.katmap() or {}

    from shared.utils import sku_anahtar

    def _kat(sku):
        return (katmap.get(sku_anahtar(sku), "") or "").strip()   # anahtar normalize (Faz 3)

    # Kategori süzgeci YAZIMDAN BAĞIMSIZ (shared.ana_veri): sayfa seçenekleri tek yazımla
    # ('Kasa') gelir, kartta 'KASA' / 'kasa', destek kırılımında 'MONITÖR' olabilir.
    from shared.ana_veri import kategori_anahtar
    _kat_anh = kategori_anahtar(kat_f) if kat_f != "Tümü" else ""

    def _kat_tutar(sku):
        return kategori_anahtar(_kat(sku)) == _kat_anh

    def _kat_topla(sozluk):
        return sum(float(v or 0) for k, v in (sozluk or {}).items() if kategori_anahtar(k) == _kat_anh)

    sat = list(satislar if satislar is not None else (kaynak.satislar(bas, bit) or []))
    if kanal_f != "Tümü":
        sat = [s for s in sat if (s.get("kanal") or "").strip() == kanal_f]
    if kat_f != "Tümü":
        sat = [s for s in sat if _kat_tutar(s.get("sku"))]
    if not sat:
        return {"bos": True, "eksikler": eksik}

    top, kanal, urun = ozet_hesapla(sat)

    # ── İadeler ──
    try:
        isat, itop = kaynak.iade_ozet(bas, bit)
        itop = dict(itop or {})
    except Exception as e:  # noqa: BLE001
        isat, itop = [], {}
        eksik.append(f"İadeler okunamadı ({type(e).__name__}) — net kâr iadeleri düşmüyor")
    itop.setdefault("i_tutar", 0.0)
    itop.setdefault("i_kar", 0.0)
    try:
        ikan = kaynak.iade_kanal(bas, bit) or {}
    except Exception:  # noqa: BLE001
        ikan = {}
    if filtreli:
        # İade toplamları da aynı süzgeçle (kanal + kategori)
        try:
            pacal = kaynak.pacal() or {}
            ft = fk = 0.0
            fa = 0
            for ir in kaynak.iadeler(bas, bit) or []:
                kn = (ir.get("kanal") or "").strip()
                sku = str(ir.get("sku") or "").strip()
                if kanal_f != "Tümü" and kn != kanal_f:
                    continue
                if kat_f != "Tümü" and not _kat_tutar(sku):
                    continue
                net = float(ir.get("iade_net") or 0)
                adet = int(ir.get("iade_adet") or 0)
                ft += net
                fa += adet
                fk += net - adet * pacal.get(sku.upper(), pacal.get(sku, 0.0))
            itop["i_tutar"], itop["i_kar"] = ft, fk
            # Net adet de süzgece göre (eskiden süzgeçsiz toplam kalıyordu: firma seçilse de 7.061)
            itop["i_adet"], itop["net_adet"] = fa, int(top.get("adet") or 0) - fa
        except Exception as e:  # noqa: BLE001
            itop["i_tutar"] = itop["i_kar"] = 0.0
            itop["i_adet"], itop["net_adet"] = 0, int(top.get("adet") or 0)
            eksik.append(f"Süzgeçli iadeler okunamadı ({type(e).__name__}) — iadeler düşmüyor")

    # ── Kategori desteği (kategori süzgeci + firma "Tümü") ──
    kat_destek = 0.0
    if kat_f != "Tümü" and kanal_f == "Tümü":
        try:
            _, adk, _ = kaynak.alinan_kirilim(bas, bit)
            kat_destek = _kat_topla(adk)
        except Exception as e:  # noqa: BLE001
            eksik.append(f"Kategori desteği okunamadı ({type(e).__name__}) — kâra eklenmedi")

    net_ciro = top["ciro"] - itop["i_tutar"]
    net_kar = top["net_kar"] - itop["i_kar"]
    net_satis = top["ciro"] - top["destek"] - itop["i_tutar"]

    # ── Ref No destekleri: kaydın tarihindeki kurla (Yönetim ile aynı) ──
    from yonetim_hesap import tl_usd
    ref_usd = 0.0
    try:
        try:
            kmap = kaynak.kur_haritasi(bas, bit) or {}
        except Exception:  # noqa: BLE001
            kmap = {}
        try:
            yedek = float(kaynak.yedek_kur() or 0)
        except Exception:  # noqa: BLE001
            yedek = 0.0
        kur_yok = 0
        for x in kaynak.ref_tutarlari(bas, bit) or []:
            u = tl_usd(x.get("tutar"), x.get("doviz"), x.get("donem") or x.get("tarih"), kmap, yedek)
            if u is None:
                kur_yok += 1
                continue
            ref_usd += u
        if kur_yok:
            eksik.append(f"Kur bulunamadı: TL cinsi {kur_yok} Ref No kaydı hesaba katılmadı")
    except Exception as e:  # noqa: BLE001
        ref_usd = 0.0
        eksik.append(f"Ref No destekleri okunamadı ({type(e).__name__}) — net kârdan düşülmedi")

    # ── Alınan destek (gelir; yalnız süzgeçsiz) ──
    alinan_usd = 0.0
    if not filtreli:
        try:
            alinan_usd = float(kaynak.alinan(bas, bit) or 0)
        except Exception as e:  # noqa: BLE001
            eksik.append(f"Alınan destek okunamadı ({type(e).__name__}) — net kâra eklenmedi")

    # ── Kategori süzgecinde Ref No'nun o kategoriye düşen payı ──
    ref_kat, ref_dagitilmayan = 0.0, []
    if kat_f != "Tümü":
        try:
            rk = kaynak.ref_kirilim(bas, bit) or {}
            ref_kat = _kat_topla(rk.get("kategori"))
            ref_dagitilmayan = rk.get("dagitilmayan") or []
        except Exception as e:  # noqa: BLE001
            eksik.append(f"Ref No kategori kırılımı okunamadı ({type(e).__name__}) — kategoriye düşülmedi")
    ref_g = ref_kat if kat_f != "Tümü" else (ref_usd if (ref_usd > 0.005 and not filtreli) else 0.0)

    nihai = net_kar - ref_g + alinan_usd + kat_destek
    return {
        "bos": False, "top": top, "kanal": kanal, "urun": urun,
        "isat": isat, "itop": itop, "ikan": ikan, "sku_iade": {r["sku"]: r for r in isat},
        "net_ciro": net_ciro, "net_kar": net_kar, "net_satis": net_satis,
        "net_marj": (net_kar / net_satis * 100) if net_satis > 0 else 0.0,
        "kat_destek": kat_destek, "ref_usd": ref_usd, "alinan_usd": alinan_usd,
        "ref_kat": ref_kat, "ref_dagitilmayan": ref_dagitilmayan, "ref_g": ref_g,
        "nihai": nihai, "nihai_marj": (nihai / net_satis * 100) if net_satis > 0 else 0.0,
        "filtreli": filtreli, "eksikler": eksik,
    }


class Kaynak:
    """Gerçek veri kaynağı. Kur yöntemleri Yönetim'inkiyle aynı (yonetim_hesap.Kaynak)."""

    def __init__(self, oturum_kuru=0.0):
        from yonetim_hesap import Kaynak as _YK
        self._yk = _YK(oturum_kuru)

    def satislar(self, bas, bit):
        from satis.database import get_satislar_yalin
        return get_satislar_yalin(bas, bit)

    def katmap(self):
        from satis.database import get_sku_kategori
        return get_sku_kategori()

    def iade_ozet(self, bas, bit):
        from satis.database import iade_satis_net_ozet
        return iade_satis_net_ozet(bas, bit)

    def iade_kanal(self, bas, bit):
        from satis.database import iade_kanal_ozet
        return iade_kanal_ozet(bas, bit)

    def iadeler(self, bas, bit):
        from satis.database import get_iadeler
        return get_iadeler(bas, bit)

    def pacal(self):
        from satis.database import get_pacal_map
        return get_pacal_map()

    def ref_tutarlari(self, bas, bit):
        from kayranpm.ref_no import get_tum_ref_tutarlari
        return get_tum_ref_tutarlari(bas, bit)

    def alinan(self, bas, bit):
        from kayranpm.ref_no import alinan_destek_aralik_usd
        return alinan_destek_aralik_usd(bas, bit)

    def alinan_kirilim(self, bas, bit):
        from kayranpm.ref_no import alinan_destek_kirilim_usd
        return alinan_destek_kirilim_usd(bas, bit)

    def ref_kirilim(self, bas, bit):
        from kayranpm.ref_no import ref_destek_kirilim_usd
        return ref_destek_kirilim_usd(bas, bit)

    def kur_haritasi(self, bas, bit):
        return self._yk.kur_haritasi(bas, bit)

    def yedek_kur(self):
        return self._yk.yedek_kur()
