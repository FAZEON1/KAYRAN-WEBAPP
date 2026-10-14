# -*- coding: utf-8 -*-
"""KAYRAN API (yeni uygulama, Faz 0 — Ekim 2026).

Yeni ön yüz (web/, Next.js) yalnız bu API ile konuşur; API mevcut Python iş kurallarını (shared/,
modül klasörleri) olduğu gibi kullanır ve aynı Supabase veritabanına bağlanır. Eski Streamlit
uygulaması geçiş boyunca yanında çalışmaya devam eder.

Faz 0 uçları:
  GET  /saglik   — ayakta mı (Render sağlık kontrolü)
  POST /giris    — kullanıcı adı + şifre → HttpOnly oturum çerezi (eski girişle aynı doğrulama ve kilit)
  POST /cikis    — çerezi siler
  GET  /ben      — oturumdaki kullanıcı, yetkileri ve sol menü

Çalıştırma (yerelde):  uvicorn api.main:app --reload   (depo kökünden)
"""
from api import uyum

uyum.kur()                                   # shared/ içe aktarılmadan ÖNCE (streamlit yerine)

import os  # noqa: E402

from fastapi import Depends, FastAPI, HTTPException, Request, Response  # noqa: E402
from pydantic import BaseModel  # noqa: E402

from api import oturum  # noqa: E402
from api.menu import menu_agaci  # noqa: E402

GELISTIRME = os.environ.get("ORTAM", "").lower() == "gelistirme"

app = FastAPI(title="KAYRAN API", docs_url="/belgeler" if GELISTIRME else None, redoc_url=None,
              openapi_url="/openapi.json" if GELISTIRME else None)


def _anahtar():
    return os.environ.get("OTURUM_ANAHTARI", "")


def _kullanicilar():
    import streamlit as st
    return dict(st.secrets.get("kullanicilar", {}) or {})


class GirisIstegi(BaseModel):
    kullanici: str
    sifre: str


@app.get("/saglik")
def saglik():
    return {"durum": "ayakta"}


@app.post("/giris")
def giris(istek: GirisIstegi, cevap: Response):
    from shared.auth import giris_basarili, giris_basarisiz, giris_kontrol, kullanici_dogrula_v2
    if len(_anahtar()) < 32:
        raise HTTPException(503, "Sunucu ayarı eksik: oturum anahtarı tanımlı değil.")
    k = (istek.kullanici or "").strip()
    if not k or not istek.sifre:
        raise HTTPException(400, "Kullanıcı adı ve şifre gerekli.")
    izin, kalan = giris_kontrol(k)
    if not izin:
        raise HTTPException(429, f"Çok fazla hatalı deneme. {kalan // 60} dk {kalan % 60} sn sonra tekrar deneyin.")
    if not kullanici_dogrula_v2(k, istek.sifre, _kullanicilar()):
        sayi, kilit = giris_basarisiz(k)
        if kilit:
            raise HTTPException(429, f"Çok fazla hatalı deneme. Hesap {kilit // 60} dakika kilitlendi.")
        ek = f" {max(0, 5 - sayi)} deneme hakkınız kaldı." if sayi >= 3 else ""
        raise HTTPException(401, "Kullanıcı adı veya şifre hatalı." + ek)
    giris_basarili(k)
    cevap.set_cookie(oturum.CEREZ, oturum.uret(k, _anahtar()), max_age=oturum.SURE_SN, httponly=True,
                     secure=not GELISTIRME, samesite="lax", path="/")
    return {"kullanici": k}


@app.post("/cikis")
def cikis(cevap: Response):
    cevap.delete_cookie(oturum.CEREZ, path="/")
    return {"durum": "çıkış yapıldı"}


def oturumdaki_kullanici(istek: Request):
    """Geçerli çerez + kullanıcı hâlâ aktif → kullanıcı adı; değilse 401."""
    k = oturum.coz(istek.cookies.get(oturum.CEREZ, ""), _anahtar())
    if not k:
        raise HTTPException(401, "Oturum yok ya da süresi doldu.")
    from shared.yetki import kullanici_kaydi
    db_var, kayit = kullanici_kaydi(k)
    if db_var and kayit is not None and not kayit.get("aktif", True):
        raise HTTPException(401, "Hesap pasif.")
    if (db_var and kayit is None and k not in _kullanicilar()) or (not db_var and k not in _kullanicilar()):
        raise HTTPException(401, "Kullanıcı bulunamadı.")
    return k


@app.get("/ben")
def ben(kullanici: str = Depends(oturumdaki_kullanici)):
    """Yetki kaynağı eski uygulamayla aynı (kullanici_yetkileri tablosu). Tablo okunamazsa eski uygulama
    koddaki sabit listelere düşer; API düşmez — kimseye yetki vermez (güvenli taraf)."""
    from shared.yetki import OZEL, moduller, ozel_yetki, salt_okur
    yetkiler = moduller(kullanici, {})
    ozel = {ad for ad in OZEL if ozel_yetki(kullanici, ad, ())}
    return {
        "kullanici": kullanici,
        "salt_okur": bool(salt_okur(kullanici, ())),
        "moduller": yetkiler,
        "ozel": sorted(ozel),
        "menu": menu_agaci(yetkiler, ozel, kullanici, os.environ.get("ESKI_UYGULAMA_URL", "")),
    }
