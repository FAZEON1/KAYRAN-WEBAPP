# -*- coding: utf-8 -*-
"""İzinler (Ekim 2026) — kişi menüsü › İzinler. Herkes kendi izinlerini görür ve talep eder; izin
yöneticisi (özel yetki 'izin_yonetimi' ya da Kullanıcı yönetimi) onaylar, personel kartlarını tutar,
takvimi ve bordro dökümünü alır.

Hesaplar shared.izin_hesap'ta (saf, test edilir), veritabanı shared.izin'de. Gün sayısı talep anında
hesaplanıp kayda yazılır; sonradan ayar değişse de eski kayıt değişmez.
"""
import html as _h
import re
from datetime import date, datetime, timedelta, timezone

import streamlit as st

from shared import bilesen as B
from shared import izin as D
from shared import izin_hesap as H
from shared.izin_belge import belge_no, donus_gunu, izin_formu_pdf, kayit_belgesi_pdf
from shared.tasarim import bos_durum, kisi_adi, kpi_serit, mesaj

BOLUM_HERKES = ["İzinlerim", "Takvim"]
BOLUM_YONETICI = ["İzinlerim", "Onay", "Takvim", "Rapor", "Personel", "Ayarlar"]


def bolumler_icin(onay=False, yonetim=False):
    """Görünen bölümler. onay: izin onaylayan (özel yetki 'izin_onay') · yonetim: personel kartları, rapor ve
    ayarlar (özel yetki 'izin_yonetimi' ya da Kullanıcı yönetimi). Onay yetkisi olmayan onay veremez."""
    return [b for b in BOLUM_YONETICI
            if b in BOLUM_HERKES or (b == "Onay" and onay) or (b == "Rapor" and (onay or yonetim))
            or (b in ("Personel", "Ayarlar") and yonetim)]

# Takvimde tür renkleri (tema değişkenleri); bekleyen talep soluk ve kesik çerçeveli
TUR_RENK = {"yillik": "mor", "evlilik": "cyan", "babalik": "cyan", "olum": "cyan", "evlat_edinme": "cyan",
            "engelli_cocuk": "cyan", "rapor": "kirmizi", "dogum": "pembe", "idari": "yesil", "ucretsiz": "amber"}
DURUM_RENK = {"bekliyor": "amber", "onaylandi": "yesil", "reddedildi": "kirmizi", "iptal": "silik"}
_KOD = re.compile(r"^[a-zçğıöşü0-9_.]{2,30}$")


def _bugun():
    return datetime.now(timezone(timedelta(hours=3))).date()


def _ad(p_or_kod, personel_harita=None):
    if isinstance(p_or_kod, dict):
        return p_or_kod.get("ad") or kisi_adi(p_or_kod.get("kod"))
    p = (personel_harita or {}).get(p_or_kod)
    return (p.get("ad") if p else None) or kisi_adi(p_or_kod)


def _sayi(g):
    return H.tr_gun(g).replace(" gün", "")


# ── Bildirim ────────────────────────────────────────────────────────
def _haber_ver(alicilar, metin, mail=None, gonderen=""):
    """Program içi bildirim + (adresi kayıtlıysa) e-posta. Hata kaydı bozmaz."""
    D.bildir(alicilar, metin, gonderen)
    if not mail:
        return
    try:
        from shared.eposta import adresler, arka_planda
        adr = adresler()
        hedef = sorted({adr[a] for a in alicilar if a in adr and a != gonderen})
        if hedef:
            arka_planda(hedef, mail[0], mail[1])
    except Exception:  # noqa: BLE001
        pass


# ── Sayfa ───────────────────────────────────────────────────────────
def sayfa(kullanici, onay=False, yonetim=False, onaycilar=(), kullanicilar=()):
    """kullanici: oturumdaki kullanıcı · onay: izin onaylayabilir mi · yonetim: personel / rapor / ayar ·
    onaycilar: yeni talep bildirimi alanlar · kullanicilar: programın aktif kullanıcıları (kart önerisi)."""
    kullanici = str(kullanici or "").strip().lower()
    B.baslik_eylem("Hesap", "İzinler",
                   aciklama="Yıllık izin, mazeret izinleri ve rapor. Hafta sonu ve resmi tatiller izinden düşülmez.")
    personeller, talepler = D.personeller(), D.talepler()
    if personeller:
        personeller = sorted(personeller, key=lambda p: H.tr_sira(p.get("ad") or p.get("kod")))
    if personeller is None or talepler is None:
        st.markdown(bos_durum("İzin kayıtları kurulmamış",
                              "veritabani/26_izin.sql Supabase'de bir kez çalıştırılmalı.", "event_busy"),
                    unsafe_allow_html=True)
        return
    bugun = _bugun()
    ayar = D.ayar()
    harita = {p["kod"]: p for p in personeller}
    bolumler = bolumler_icin(onay, yonetim)
    bekleyen = [t for t in talepler if t.get("durum") == "bekliyor"]
    if onay and bekleyen:
        st.markdown(mesaj("uyari", f"{len(bekleyen)} izin talebi onay bekliyor (Onay bölümü)."),
                    unsafe_allow_html=True)
    if st.session_state.get("izin_bolum") not in bolumler:
        st.session_state["izin_bolum"] = bolumler[0]
    bolum = st.segmented_control("Bölüm", bolumler, key="izin_bolum", label_visibility="collapsed") or bolumler[0]
    ctx = dict(kullanici=kullanici, onay=onay, yonetim=yonetim, yonetici=onay or yonetim,
               yoneticiler=list(onaycilar), personeller=personeller, harita=harita, talepler=talepler, bugun=bugun,
               cumartesi=bool(ayar.get("cumartesi")), haric=set(ayar.get("haric") or []))
    if bolum == "İzinlerim":
        _izinlerim(ctx)
    elif bolum == "Takvim":
        _takvim(ctx)
    elif bolum == "Onay":
        _onay(ctx)
    elif bolum == "Rapor":
        _rapor(ctx)
    elif bolum == "Personel":
        _personel(ctx, kullanicilar)
    elif bolum == "Ayarlar":
        _ayarlar(ayar, kullanicilar)


# ── İzinlerim ───────────────────────────────────────────────────────
def _bakiye_serit(b):
    s = b["sonraki"]
    st.markdown(kpi_serit([
        {"etiket": "Kalan yıllık izin", "deger": H.tr_gun(b["kullanilabilir"]),
         "renk": "kirmizi" if b["kullanilabilir"] < 0 else "yesil",
         "alt": (f"{H.tr_gun(b['bekleyen'])} onay bekliyor" if b["bekleyen"] else "onaylı izinler düşüldü")},
        {"etiket": "Yıllık hak", "deger": H.tr_gun(b["bu_yil_hak"]), "renk": "mor",
         "alt": f"kıdem {b['kidem'][0]} yıl {b['kidem'][1]} ay"},
        {"etiket": "Kullanılan", "deger": H.tr_gun(b["kullanilan"]), "renk": "cyan",
         "alt": (f"+ {H.tr_gun(b['planlanan'])} ileri tarihli" if b["planlanan"] else "")},
        {"etiket": "Sonraki hak ediş", "deger": (H.tr_tarih(s["tarih"]) if s else "—"), "renk": "amber",
         "alt": (f"+{s['gun']} gün" if s else "")},
    ]), unsafe_allow_html=True)


def _izinlerim(c):
    p = c["harita"].get(c["kullanici"])
    if not p:
        st.markdown(mesaj("bilgi", "Personel kartın henüz açılmamış. Bakiyeni görmek ve izin istemek için "
                                   "izin yöneticisinin Personel bölümünden kartını açması gerekiyor."),
                    unsafe_allow_html=True)
        return
    kendi = [t for t in c["talepler"] if t.get("personel") == p["kod"]]
    if p.get("ise_giris"):
        _bakiye_serit(H.bakiye(p, kendi, c["bugun"]))
    else:
        st.markdown(mesaj("uyari", "Personel kartında işe giriş tarihi yok; yıllık izin bakiyesi hesaplanamıyor."),
                    unsafe_allow_html=True)
    if not p.get("cikis_tarihi"):
        st.markdown(B.grup_basligi("Yeni izin talebi"), unsafe_allow_html=True)
        _talep_formu(c, p, anahtar="izn_k")
    st.markdown(B.grup_basligi("Geçmiş", f"{len(kendi)} kayıt" if kendi else ""), unsafe_allow_html=True)
    _kayit_belgesi_dugmesi(c, p)
    if not kendi:
        st.caption("Henüz izin kaydın yok.")
    for t in sorted(kendi, key=lambda t: (str(t.get("baslangic")), t.get("id") or 0), reverse=True):
        _kayit_satiri(c, t, sahip=True)


def _talep_formu(c, p, anahtar, yonetici_girisi=False):
    """Talep formu; tarih seçildikçe gün sayısı, döküm, hata ve uyarılar anında görünür."""
    n = st.session_state.get(f"{anahtar}_n", 0)
    k = f"{anahtar}_{n}"
    tur = st.selectbox("İzin türü", H.TUR_SIRA, format_func=H.tur_adi, key=f"{k}_tur")
    st.caption(H.TURLER[tur]["aciklama"])
    c1, c2 = st.columns(2)
    bas = c1.date_input("Başlangıç", None, format="DD.MM.YYYY", key=f"{k}_bas")
    bit = c2.date_input("Bitiş (son izin günü)", None, format="DD.MM.YYYY", key=f"{k}_bit",
                        min_value=bas or None)
    if bas and not bit:
        bit = bas
    yarim = False
    if bas and bit and bas == bit:
        yarim = st.checkbox("Yarım gün", key=f"{k}_yarim", help="Tek günlük yarım gün izin (0,5 gün düşer).")
    yol = 0
    if tur == "yillik":
        yol = int(st.number_input("Ücretsiz yol izni (gün)", min_value=0, max_value=4, value=0, step=1,
                                  key=f"{k}_yol",
                                  help="İznini işyerinin bulunduğu yer dışında geçirecek olana istenirse toplam "
                                       "4 güne kadar ücretsiz yol izni verilir (İş Kanunu md. 56). İzin gününe eklenmez; "
                                       "işe başlama tarihini öteler."))
    aciklama = st.text_input("Açıklama (isteğe bağlı)", key=f"{k}_acik",
                             placeholder="Rapor için tanı yazma; yalnız tarih yeterli." if tur == "rapor" else "")
    adres = st.text_input("İzin süresince adres / telefon (isteğe bağlı)", key=f"{k}_adres",
                          help="İzin formuna yazılır; acil durumda ulaşmak için.")
    onayli = False
    if yonetici_girisi:
        onayli = st.checkbox("Onaylı olarak kaydet", value=True, key=f"{k}_onayli",
                             help="Kâğıt dilekçesi alınmış ya da geçmişte kullanılmış izinler için.")
    if not bas:
        st.caption("Tarihleri seçince izinden düşecek gün sayısı burada görünür.")
        return
    gun = H.izin_gunu(bas, bit, c["cumartesi"], yarim)
    kendi = [t for t in c["talepler"] if t.get("personel") == p["kod"]]
    ayni = H.ayni_bolumdekiler(bas, bit, p["kod"], p.get("departman"), c["personeller"], c["talepler"])
    hatalar, uyarilar = H.denetle(tur, bas, bit, gun, p, kendi, c["bugun"], yarim=yarim, ayni_bolum=ayni)
    st.markdown(kpi_serit([
        {"etiket": "İzinden düşecek", "deger": H.tr_gun(gun), "renk": "mor",
         "alt": "yıllık izin bakiyesinden" if H.TURLER[tur]["duser"] else "yıllık izinden düşmez"},
        {"etiket": "Takvim günü", "deger": H.tr_gun(H.takvim_gunu(bas, bit)), "renk": "cyan",
         "alt": f"{H.tr_tarih(bas)} – {H.tr_tarih(bit)}"},
        {"etiket": "İşe dönüş", "deger": H.tr_tarih(donus_gunu(bit, c["cumartesi"], yol)), "renk": "yesil",
         "alt": "ilk iş günü" + (f", {yol} gün yol izniyle" if yol else "")},
    ]), unsafe_allow_html=True)
    dok = [(g, v, nt) for g, v, nt in H.gun_dokumu(bas, bit, c["cumartesi"]) if v < 1]
    if dok and not yarim:
        with st.expander(f"Sayılmayan günler ({len(dok)})"):
            st.markdown("  \n".join(f"{H.tr_tarih(g)} · {_h.escape(nt)}" + (" · yarım gün sayıldı" if v else "")
                                    for g, v, nt in dok))
    for h in hatalar:
        st.markdown(mesaj("hata", h), unsafe_allow_html=True)
    for u in uyarilar:
        st.markdown(mesaj("uyari", u), unsafe_allow_html=True)
    etiket = "Kaydet" if yonetici_girisi else "Talep gönder"
    if st.button(etiket, key=f"{k}_gonder", type="primary", icon=":material/send:", disabled=bool(hatalar)):
        durum = "onaylandi" if onayli else "bekliyor"
        ok, r = D.talep_ekle(p["kod"], tur, bas, bit, gun, H.takvim_gunu(bas, bit), yarim, aciklama,
                             talep_eden=c["kullanici"], durum=durum,
                             karar_notu="Yönetici girişi" if onayli else "", yol_izni=yol, izin_adresi=adres)
        if not ok:
            st.error(r)
            return
        ad = _ad(p)
        if durum == "bekliyor":
            _haber_ver(c["yoneticiler"], H.bildirim_yeni(ad, r), H.mail_yeni(ad, r), c["kullanici"])
        elif p["kod"] != c["kullanici"]:
            _haber_ver([p["kod"]], H.bildirim_karar(r, True, kisi_adi(c["kullanici"])),
                       H.mail_karar(r, True, kisi_adi(c["kullanici"])), c["kullanici"])
        st.session_state[f"{anahtar}_n"] = n + 1
        st.toast("İzin kaydedildi." if durum == "onaylandi" else "Talep gönderildi; onay bekliyor.")
        st.rerun()


def _pdf_dugmesi(etiket, anahtar, uret, dosya_adi):
    """Belgeyi istenince üretir (her çizimde değil), sonra indirme düğmesine döner."""
    if st.session_state.get(anahtar):
        st.download_button(etiket, st.session_state[anahtar], file_name=dosya_adi, mime="application/pdf",
                           key=f"{anahtar}_dl", icon=":material/download:", type="primary")
    elif st.button(etiket, key=f"{anahtar}_h", icon=":material/print:"):
        try:
            st.session_state[anahtar] = uret()
        except Exception as e:  # noqa: BLE001
            try:
                from shared.hata_log import kaydet
                kaydet("izin.pdf", e)
            except Exception:  # noqa: BLE001
                pass
            st.error(f"Belge hazırlanamadı: {e}")
            return
        st.rerun()


def _form_dugmesi(c, t):
    p = c["harita"].get(t.get("personel"))
    if not p or t.get("durum") not in ("bekliyor", "onaylandi"):
        return
    kisi = [x for x in c["talepler"] if x.get("personel") == p["kod"]]
    _pdf_dugmesi("İzin formu", f"izn_pdf_{t['id']}_{t.get('durum')}",
                 lambda: izin_formu_pdf(t, p, kisi, c["bugun"], c["cumartesi"]),
                 f"{belge_no(t)}_{p['kod']}.pdf")


def _kayit_belgesi_dugmesi(c, p):
    if not p or not p.get("ise_giris"):
        return
    kisi = [x for x in c["talepler"] if x.get("personel") == p["kod"]]
    _pdf_dugmesi("Yıllık izin kayıt belgesi", f"izn_kb_{p['kod']}_{len(kisi)}",
                 lambda: kayit_belgesi_pdf(p, kisi, c["bugun"]), f"izin_kayit_belgesi_{p['kod']}.pdf")


def _kayit_satiri(c, t, sahip=False, yonetici_eylem=False):
    ad = _ad(t.get("personel"), c["harita"])
    durum = t.get("durum")
    with st.container(border=True):
        k = st.columns([5, 1.6], vertical_alignment="center")
        bas = "" if sahip else f"**{_h.escape(ad)}** · "
        k[0].markdown(bas + _h.escape(H.talep_ozeti(t)), unsafe_allow_html=True)
        k[1].markdown(B.cip(H.DURUMLAR.get(durum, durum), DURUM_RENK.get(durum, "silik")), unsafe_allow_html=True)
        parca = [f"İsteyen {kisi_adi(t.get('talep_eden'))} · {str(t.get('talep_zamani') or '')[:10]}"]
        if t.get("karar_veren"):
            parca.append(f"karar {kisi_adi(t.get('karar_veren'))}")
        if t.get("iptal_eden"):
            parca.append(f"iptal {kisi_adi(t.get('iptal_eden'))}")
        if t.get("aciklama"):
            parca.append(t["aciklama"])
        if t.get("karar_notu"):
            parca.append(f"Not: {t['karar_notu']}")
        st.markdown(B.meta(*parca), unsafe_allow_html=True)
        _form_dugmesi(c, t)
        if sahip and durum == "bekliyor":
            if st.button("Talebi geri çek", key=f"izn_geri_{t['id']}", icon=":material/undo:", type="tertiary"):
                ok, h = D.iptal_et(t["id"], c["kullanici"], "Talep sahibi geri çekti")
                (st.rerun() if ok else st.error(h))
        if yonetici_eylem and durum in ("bekliyor", "onaylandi"):
            with st.popover("İptal et", icon=":material/block:"):
                st.caption("Kayıt silinmez; iptal edildi olarak kalır ve bakiyeye geri yansır.")
                notu = st.text_input("Gerekçe", key=f"izn_ipt_not_{t['id']}")
                if st.button("İptal et", key=f"izn_ipt_{t['id']}", type="primary", disabled=not notu.strip()):
                    ok, h = D.iptal_et(t["id"], c["kullanici"], notu, eski_durum=("bekliyor", "onaylandi"))
                    if ok:
                        _haber_ver([t.get("personel")], H.bildirim_iptal(t, kisi_adi(c["kullanici"]), notu),
                                   gonderen=c["kullanici"])
                        st.rerun()
                    st.error(h)


# ── Onay ────────────────────────────────────────────────────────────
def _onay(c):
    bekleyen = sorted((t for t in c["talepler"] if t.get("durum") == "bekliyor"),
                      key=lambda t: (str(t.get("baslangic")), t.get("id") or 0))
    st.markdown(B.grup_basligi("Onay bekleyen talepler", f"{len(bekleyen)} talep" if bekleyen else ""),
                unsafe_allow_html=True)
    if not bekleyen:
        st.markdown(bos_durum("Onay bekleyen talep yok", "Yeni talep gelince burada ve zil simgesinde görünür.",
                              "task_alt"), unsafe_allow_html=True)
    for t in bekleyen:
        _onay_karti(c, t)
    st.markdown(B.grup_basligi("Başkası adına izin gir"), unsafe_allow_html=True)
    aktif = [p for p in c["personeller"] if not p.get("cikis_tarihi")]
    if not aktif:
        st.caption("Önce Personel bölümünden kart aç.")
        return
    kod = st.selectbox("Personel", [p["kod"] for p in aktif], format_func=lambda k: _ad(k, c["harita"]),
                       key="izn_y_kisi")
    _talep_formu(c, c["harita"][kod], anahtar=f"izn_y_{kod}", yonetici_girisi=True)


def _onay_karti(c, t):
    p = c["harita"].get(t.get("personel")) or {"kod": t.get("personel")}
    kisi = [x for x in c["talepler"] if x.get("personel") == p["kod"] and x.get("id") != t.get("id")]
    bas, bit = H.tarih(t.get("baslangic")), H.tarih(t.get("bitis"))
    ayni = H.ayni_bolumdekiler(bas, bit, p["kod"], p.get("departman"), c["personeller"],
                               [x for x in c["talepler"] if x.get("id") != t.get("id")])
    hatalar, uyarilar = H.denetle(t.get("tur"), bas, bit, float(t.get("gun") or 0), p, kisi, c["bugun"],
                                  yarim=bool(t.get("yarim_gun")), ayni_bolum=ayni)
    uyarilar = [u for u in uyarilar if not u.startswith("Geçmiş tarihli")] + hatalar
    with st.container(border=True):
        st.markdown(f"**{_h.escape(_ad(p))}** · {_h.escape(H.talep_ozeti(t))}")
        parca = [f"Talep {str(t.get('talep_zamani') or '')[:16].replace('T', ' ')}"]
        if t.get("aciklama"):
            parca.append(t["aciklama"])
        if t.get("tur") == "yillik" and p.get("ise_giris"):
            b = H.bakiye(p, kisi, c["bugun"])
            parca.append(f"Kalan {H.tr_gun(b['kullanilabilir'])} → onaylanırsa "
                         f"{H.tr_gun(b['kullanilabilir'] - float(t.get('gun') or 0))}")
        st.markdown(B.meta(*parca), unsafe_allow_html=True)
        for u in uyarilar:
            st.markdown(mesaj("uyari", u), unsafe_allow_html=True)
        k = st.columns([3, 1, 1], vertical_alignment="bottom")
        notu = k[0].text_input("Not (reddederken zorunlu)", key=f"izn_not_{t['id']}")
        if k[1].button("Onayla", key=f"izn_on_{t['id']}", type="primary", icon=":material/check:",
                       use_container_width=True):
            _karar(c, t, True, notu)
        if k[2].button("Reddet", key=f"izn_red_{t['id']}", icon=":material/close:", use_container_width=True):
            if not notu.strip():
                st.error("Reddetmek için gerekçe yaz.")
            else:
                _karar(c, t, False, notu)


def _karar(c, t, onay, notu):
    ok, h = D.karar_ver(t["id"], onay, c["kullanici"], notu)
    if not ok:
        st.error(h)
        return
    ben = kisi_adi(c["kullanici"])
    _haber_ver([t.get("personel")], H.bildirim_karar(t, onay, ben, notu.strip()),
               H.mail_karar(t, onay, ben, notu.strip()), c["kullanici"])
    st.toast("Onaylandı." if onay else "Reddedildi.")
    st.rerun()


# ── Takvim ──────────────────────────────────────────────────────────
TAKVIM_CSS = """<style>
.izn-kap{overflow-x:auto;border:1px solid var(--k-kenar);border-radius:10px;background:var(--k-yuzey1)}
.izn-tbl{border-collapse:separate;border-spacing:0;font-size:12px;min-width:100%}
.izn-tbl th,.izn-tbl td{padding:0;text-align:center;border-bottom:1px solid var(--k-kenar)}
.izn-tbl thead th{color:var(--k-soluk);font-weight:600;padding:6px 0;min-width:26px;line-height:1.2}
.izn-tbl thead th small{display:block;color:var(--k-silik);font-weight:500;font-size:10px}
.izn-tbl .izn-ad{position:sticky;left:0;z-index:1;background:var(--k-yuzey1);text-align:left;
  padding:0 12px;white-space:nowrap;color:var(--k-metin);font-weight:600;min-width:120px;
  border-right:1px solid var(--k-kenar)}
.izn-tbl td{height:30px}
.izn-tbl .izn-hs{background:color-mix(in srgb,var(--k-metin) 4%,transparent)}
.izn-tbl .izn-tt{background:color-mix(in srgb,var(--k-amber) 9%,transparent)}
.izn-tbl .izn-bg{box-shadow:inset 0 0 0 2px color-mix(in srgb,var(--k-mor) 55%,transparent)}
.izn-c{display:block;margin:4px 2px;height:20px;border-radius:5px;background:var(--r)}
.izn-c.bk{background:color-mix(in srgb,var(--r) 30%,transparent);outline:1px dashed var(--r);outline-offset:-1px}
.izn-lj{display:flex;flex-wrap:wrap;gap:14px;margin:10px 2px 0;color:var(--k-soluk);font-size:12px}
.izn-lj span{display:inline-flex;align-items:center;gap:6px}
.izn-lj i{display:inline-block;width:14px;height:10px;border-radius:3px;background:var(--r)}
.izn-lj i.bk{background:color-mix(in srgb,var(--r) 30%,transparent);outline:1px dashed var(--r)}
</style>"""
_GUN_KISA = ["Pt", "Sa", "Ça", "Pe", "Cu", "Ct", "Pz"]


def takvim_html(yil, ay, satirlar, bugun, cumartesi=False, ayrinti=True):
    """Ay takvimi tablosu (saf; test edilir). ayrinti=False: tür gizli, herkes için tek renk 'İzinli'."""
    gunler = H.ay_gunleri(yil, ay)
    sinif = {}
    for g in gunler:
        s = []
        if g.weekday() == 6 or (g.weekday() == 5 and not cumartesi):
            s.append("izn-hs")
        elif H.T.tatil(g):
            s.append("izn-tt")
        if g == bugun:
            s.append("izn-bg")
        sinif[g] = " ".join(s)
    bas = "".join(f'<th class="{sinif[g]}" title="{_h.escape((H.T.tatil(g) or ("",))[0])}">'
                  f'{g.day}<small>{_GUN_KISA[g.weekday()]}</small></th>' for g in gunler)
    govde = []
    for r in satirlar:
        hucre = []
        for g in gunler:
            v = r["gunler"].get(g)
            ic = ""
            if v:
                tur, durum = v
                renk = TUR_RENK.get(tur, "mor") if ayrinti else "mor"
                bas_ = H.tur_adi(tur) if ayrinti else "İzinli"
                ipucu = f"{bas_} · {H.DURUMLAR.get(durum, durum)}"
                ic = (f'<span class="izn-c{" bk" if durum == "bekliyor" else ""}" style="--r:var(--k-{renk})" '
                      f'title="{_h.escape(ipucu)}"></span>')
            hucre.append(f'<td class="{sinif[g]}">{ic}</td>')
        govde.append(f'<tr><td class="izn-ad">{_h.escape(r["ad"])}</td>{"".join(hucre)}</tr>')
    if ayrinti:
        kullanilan = []
        for kod, renk in TUR_RENK.items():
            ad = "Mazeret izni" if renk == "cyan" else H.tur_adi(kod)
            if (ad, renk) not in kullanilan:
                kullanilan.append((ad, renk))
    else:
        kullanilan = [("İzinli", "mor")]
    lejant = "".join(f'<span><i style="--r:var(--k-{r})"></i>{_h.escape(a)}</span>' for a, r in kullanilan)
    lejant += '<span><i class="bk" style="--r:var(--k-silik)"></i>Onay bekliyor</span>'
    return (f'<div class="izn-kap"><table class="izn-tbl"><thead><tr><th class="izn-ad">Personel</th>{bas}</tr>'
            f'</thead><tbody>{"".join(govde)}</tbody></table></div><div class="izn-lj">{lejant}</div>')


def _takvim(c):
    b = c["bugun"]
    st.session_state.setdefault("izn_tak_ay", (b.year, b.month))
    yil, ay = st.session_state["izn_tak_ay"]

    def _kaydir(d):
        y, a = st.session_state["izn_tak_ay"]
        a += d
        y, a = (y - 1, 12) if a < 1 else (y + 1, 1) if a > 12 else (y, a)
        st.session_state["izn_tak_ay"] = (y, a)
    # Tek satır (telefonda da alt alta dizilmez): ‹ Ay Yıl ›
    with st.container(horizontal=True, vertical_alignment="center", key="izn_tak_nav"):
        st.button("Önceki", key="izn_tak_geri", icon=":material/chevron_left:", on_click=_kaydir, args=(-1,))
        st.markdown(f"<div style='font-weight:650;font-size:16px;min-width:120px;text-align:center'>"
                    f"{H.ay_adi(ay)} {yil}</div>", unsafe_allow_html=True)
        st.button("Sonraki", key="izn_tak_ileri", icon=":material/chevron_right:", on_click=_kaydir, args=(1,))
        if (yil, ay) != (b.year, b.month):
            st.button("Bu ay", key="izn_tak_bugun", type="tertiary",
                      on_click=lambda: st.session_state.update(izn_tak_ay=(b.year, b.month)))
    ilk, son = date(yil, ay, 1), H.ay_gunleri(yil, ay)[-1]
    kisiler = [p for p in c["personeller"]
               if (not p.get("cikis_tarihi") or H.tarih(p["cikis_tarihi"]) >= ilk)
               and (not p.get("ise_giris") or H.tarih(p["ise_giris"]) <= son)]
    if not kisiler:
        st.markdown(bos_durum("Personel kartı yok", "İzin yöneticisi Personel bölümünden kart açınca takvim dolar.",
                              "calendar_month"), unsafe_allow_html=True)
        return
    bolumler = sorted({p.get("departman") for p in kisiler if p.get("departman")})
    if bolumler:
        sec = st.selectbox("Bölüm", ["Tümü"] + bolumler, key="izn_tak_bolum")
        if sec != "Tümü":
            kisiler = [p for p in kisiler if p.get("departman") == sec]
    satirlar = H.takvim(yil, ay, kisiler, c["talepler"])
    st.markdown(TAKVIM_CSS + takvim_html(yil, ay, satirlar, b, c["cumartesi"], ayrinti=c["yonetici"]),
                unsafe_allow_html=True)
    tatiller = [(g, a) for g, (a, _o) in sorted(H.T.yil_tatilleri(yil).items()) if g.month == ay]
    if tatiller:
        st.caption("Resmi tatiller: " + " · ".join(f"{g.day} {H.ay_adi(ay)} {a}" for g, a in tatiller))
    if not H.T.bilinen_yil(yil):
        st.caption(f"{yil} yılının dini bayram tarihleri programda henüz yok.")


# ── Rapor ───────────────────────────────────────────────────────────
def _rapor(c):
    from kayranpm.stok_yasi import excel_bytes
    from shared.tablo import tablo
    b = c["bugun"]
    st.markdown(B.grup_basligi("İzin bakiyeleri", H.tr_tarih(b) + " itibarıyla"), unsafe_allow_html=True)
    bak = H.bakiye_tablosu(c["personeller"], c["talepler"], b)
    if bak:
        tablo(bak, key="izn_bakiye", dosya_adi="izin_bakiyeleri", birim="")
        st.caption("Kalan = devir + hak edilen − kullanılan − planlanan (onaylı, ileri tarihli). Bekleyen talepler "
                   "kalandan düşülmez; onaylanınca düşer.")
    else:
        st.caption("Henüz personel kartı yok.")

    st.markdown(B.grup_basligi("Aylık döküm", "bordro için onaylı izinler"), unsafe_allow_html=True)
    k = st.columns([1, 1, 2], vertical_alignment="bottom")
    yil = k[0].selectbox("Yıl", list(range(b.year + 1, b.year - 4, -1)), index=1, key="izn_dok_yil")
    ay = k[1].selectbox("Ay", list(range(1, 13)), index=b.month - 1, format_func=H.ay_adi, key="izn_dok_ay")
    gunler = H.ay_gunleri(yil, ay)
    adlar = {p["kod"]: _ad(p) for p in c["personeller"]}
    dok = H.donem_dokumu(c["talepler"], gunler[0], gunler[-1], adlar, c["cumartesi"])
    if dok:
        tablo([dict(r, **{"Başlangıç": H.tr_tarih(r["Başlangıç"]), "Bitiş": H.tr_tarih(r["Bitiş"])}) for r in dok],
              key="izn_dokum", dosya_adi=f"izin_dokumu_{yil}_{ay:02d}", birim="")
        ucretsiz = sum(r["Takvim günü"] for r in dok if r["Ücretli"] == "Hayır")
        if ucretsiz:
            st.caption(f"Ücretsiz izin ve rapor toplam {ucretsiz} takvim günü: bordroda eksik gün olarak bildirilir.")
    else:
        st.caption(f"{H.ay_adi(ay)} {yil} döneminde onaylı izin yok.")
    k[2].download_button("Excel: bakiyeler ve aylık döküm",
                         excel_bytes({"Bakiyeler": bak,
                                      f"{H.ay_adi(ay)} {yil}": [dict(r, **{"Başlangıç": H.tr_tarih(r["Başlangıç"]),
                                                                           "Bitiş": H.tr_tarih(r["Bitiş"])})
                                                                  for r in dok]}),
                         file_name=f"izinler_{yil}_{ay:02d}.xlsx", icon=":material/download:", key="izn_excel",
                         use_container_width=True)

    st.markdown(B.grup_basligi("Bütün kayıtlar"), unsafe_allow_html=True)
    k = st.columns(2)
    kisi = k[0].selectbox("Personel", ["Tümü"] + sorted(adlar, key=lambda x: adlar[x]),
                          format_func=lambda x: "Tümü" if x == "Tümü" else adlar.get(x, x), key="izn_kay_kisi")
    durum = k[1].selectbox("Durum", ["Tümü"] + list(H.DURUMLAR),
                           format_func=lambda x: "Tümü" if x == "Tümü" else H.DURUMLAR[x], key="izn_kay_durum")
    liste = [t for t in c["talepler"] if (kisi == "Tümü" or t.get("personel") == kisi)
             and (durum == "Tümü" or t.get("durum") == durum)]
    liste.sort(key=lambda t: (str(t.get("baslangic")), t.get("id") or 0), reverse=True)
    goster = st.session_state.get("izn_kay_n", 20)
    for t in liste[:goster]:
        _kayit_satiri(c, t, yonetici_eylem=c["onay"])
    if len(liste) > goster:
        st.button(f"Daha fazla göster ({len(liste) - goster} kayıt daha)", key="izn_kay_daha", type="tertiary",
                  on_click=lambda: st.session_state.update(izn_kay_n=goster + 20))
    if not liste:
        st.caption("Kayıt yok.")


# ── Personel ────────────────────────────────────────────────────────
def personel_denetle(kod, yeni, ise_giris, dogum, devir_t, devir_g, cikis, mevcut_kodlar):
    """Personel kartı hataları (saf; test edilir)."""
    h = []
    if yeni:
        if not _KOD.match(kod or ""):
            h.append("Kod 2–30 karakter; küçük harf, rakam, nokta ya da alt çizgi olmalı (ör. ahmet).")
        elif kod in mevcut_kodlar:
            h.append("Bu kod zaten var (kartlı personel ya da programın kullanıcısı); listeden seç.")
    if not ise_giris:
        h.append("İşe giriş tarihi gerekli (yıllık izin hakkı buna göre hesaplanır).")
    else:
        if dogum and dogum >= ise_giris:
            h.append("Doğum tarihi işe giriş tarihinden önce olmalı.")
        if dogum and H.yas(dogum, ise_giris) < 14:
            h.append("İşe girişte yaş 14'ten küçük görünüyor; doğum tarihini kontrol et.")
        if devir_t and devir_t < ise_giris:
            h.append("Devir tarihi işe giriş tarihinden önce olamaz.")
        if cikis and cikis < ise_giris:
            h.append("İşten çıkış tarihi işe girişten önce olamaz.")
    if devir_t and (devir_g is None or devir_g < -60 or devir_g > 400):
        h.append("Devreden gün -60 ile 400 arasında olmalı.")
    return h


def _adresler():
    try:
        from shared.eposta import adresler
        return adresler()
    except Exception:  # noqa: BLE001
        return {}


def _bilgilendir(c, p):
    """Çalışana kart bilgilendirme e-postasını gönderir (bekleyerek; sonucu ekranda söylenir).
    Döner: (ok, mesaj)."""
    adres = H.bilgi_adresi(p, _adresler())
    if not adres:
        return False, "e-posta adresi yok"
    from shared.eposta import gonder
    from shared.izin_belge import LOGO
    kisi = [t for t in c["talepler"] if t.get("personel") == p["kod"]]
    konu, html = H.mail_bilgilendirme(p, kisi, c["bugun"], kisi_adi(c["kullanici"]))
    try:
        with open(LOGO, "rb") as f:
            logo = [(H.LOGO_CID, f.read(), "png")]
    except OSError:
        logo, html = None, html.replace(f"<img src='cid:{H.LOGO_CID}'", "<img hidden src=''")
    ok, kod = gonder([adres], konu, html, gomulu=logo)
    if not ok:
        return False, {"smtp_yok": "programın e-posta hesabı ayarlı değil"}.get(kod, kod)
    D.bilgi_isaretle(p["kod"])
    return True, adres


def _personel(c, kullanicilar):
    from shared.tablo import tablo
    b = c["bugun"]
    adr = _adresler()
    flas = st.session_state.pop("izn_bilgi_flas", None)
    if flas:
        st.markdown(mesaj(*flas), unsafe_allow_html=True)
    kartli = {p["kod"] for p in c["personeller"]}
    # İzin takibine girmeyen kullanıcılar (ortaklar vb.; Ayarlar'dan seçilir) listelenmez
    kartsiz = sorted({str(k).strip().lower() for k in kullanicilar or [] if k} - kartli - c["haric"])
    if kartsiz:
        st.markdown(mesaj("bilgi", "Kartı olmayan kullanıcılar: " + ", ".join(kisi_adi(k) for k in kartsiz)
                          + ". Kart açılmadan izin isteyemezler."), unsafe_allow_html=True)
    if c["personeller"]:
        satir = []
        for p in c["personeller"]:
            kt = [t for t in c["talepler"] if t.get("personel") == p["kod"]]
            bk = H.bakiye(p, kt, b) if p.get("ise_giris") else None
            satir.append({"_id": p["kod"], "Personel": _ad(p), "Kod": p["kod"], "Bölüm": p.get("departman") or "",
                          "İşe giriş": H.tr_tarih(p.get("ise_giris")),
                          "Kıdem": f"{bk['kidem'][0]} yıl {bk['kidem'][1]} ay" if bk else "—",
                          "Yıllık hak": bk["bu_yil_hak"] if bk else 0, "Kalan": bk["kalan"] if bk else 0,
                          "Bilgilendirme": H.bilgi_durumu(p, adr)})
        tablo(satir, key="izn_per_liste", dosya_adi="personel", birim="")

    st.markdown(B.grup_basligi("Kart aç / düzenle"), unsafe_allow_html=True)
    secenek = ["__yeni__"] + kartsiz + sorted(kartli, key=lambda k: _ad(k, c["harita"]))
    sec = st.selectbox("Kişi", secenek, key="izn_per_sec",
                       format_func=lambda k: "Yeni personel (programa girmeyen)" if k == "__yeni__"
                       else (f"{_ad(k, c['harita'])} · kart var" if k in kartli else f"{kisi_adi(k)} · kart yok"))
    p = c["harita"].get(sec, {})
    yeni = sec == "__yeni__"
    k = f"izn_per_{sec}"
    c1, c2 = st.columns(2)
    kod = c1.text_input("Kod", key=f"{k}_kod", placeholder="ör. ahmet").strip().lower() if yeni else sec
    if not yeni:
        c1.text_input("Kod", sec, disabled=True, key=f"{k}_kod_g")
    ad = c2.text_input("Ad soyad", p.get("ad") or ("" if yeni else kisi_adi(sec)), key=f"{k}_ad")
    c1, c2, c3 = st.columns([1, 1, 1])
    sicil = c3.text_input("Sicil no (isteğe bağlı)", p.get("sicil_no") or "", key=f"{k}_sicil",
                          help="İzin formunda ve izin kayıt belgesinde yazılır.")
    bolum = c1.text_input("Bölüm", p.get("departman") or "", key=f"{k}_bolum",
                          help="Aynı bölümden iki kişi aynı gün izinliyse uyarı çıkar (ör. Depo, Muhasebe).")
    giris = c2.date_input("İşe giriş tarihi", H.tarih(p.get("ise_giris")), format="DD.MM.YYYY", key=f"{k}_giris",
                          min_value=date(1970, 1, 1), max_value=b + timedelta(days=365))
    c1, c2 = st.columns(2)
    dogum = c1.date_input("Doğum tarihi (isteğe bağlı)", H.tarih(p.get("dogum_tarihi")), format="DD.MM.YYYY",
                          key=f"{k}_dogum", min_value=date(1940, 1, 1), max_value=b,
                          help="18 yaş ve altı ile 50 yaş ve üstü en az 20 gün yıllık izin alır.")
    cikis = c2.date_input("İşten çıkış tarihi (çalışıyorsa boş)", H.tarih(p.get("cikis_tarihi")),
                          format="DD.MM.YYYY", key=f"{k}_cikis", min_value=date(1970, 1, 1))
    devir_var = st.checkbox("Programa geçerken kalan izni var (bordrodan)", bool(p.get("devir_tarihi")),
                            key=f"{k}_devir_var",
                            help="Bu tarihe kadarki hak ve kullanımlar programa tek tek girilmez; o günkü kalan "
                                 "izin yazılır. Sonrası program tarafından hesaplanır.")
    devir_t, devir_g = None, None
    if devir_var:
        c1, c2 = st.columns(2)
        devir_t = c1.date_input("Kalan iznin tarihi", H.tarih(p.get("devir_tarihi")) or b, format="DD.MM.YYYY",
                                key=f"{k}_devir_t", min_value=date(1970, 1, 1), max_value=b)
        devir_g = c2.number_input("O tarihteki kalan izin (gün)", value=float(p.get("devir_gun") or 0), step=0.5,
                                  min_value=-60.0, max_value=400.0, key=f"{k}_devir_g")
    notu = st.text_input("Not (isteğe bağlı)", p.get("notu") or "", key=f"{k}_not")
    # E-posta sorulmaz (kullanıcı kararı: Serdar'a iş çıkmasın). Bilgilendirme yalnız Kullanıcı yönetiminde
    # kayıtlı adrese gider; adresi kayıtlı olmayana gitmez. Adres karta kopyalanmaz.
    eposta = p.get("eposta") or ""
    kayitli = adr.get(kod, "") if kod else ""
    st.caption(f"Bilgilendirme e-postası kayıtlı adrese gider: {kayitli}" if kayitli else
               "Kayıtlı e-posta adresi yok; bilgilendirme e-postası gönderilmez.")
    hatalar = personel_denetle(kod, yeni, giris, dogum, devir_t, devir_g, cikis, kartli | set(kartsiz))
    if giris and not hatalar:
        on = dict(p, ise_giris=giris, dogum_tarihi=dogum, devir_tarihi=devir_t, devir_gun=devir_g,
                  cikis_tarihi=cikis)
        bk = H.bakiye(on, [t for t in c["talepler"] if t.get("personel") == kod], b)
        st.caption(f"Kıdem {bk['kidem'][0]} yıl {bk['kidem'][1]} ay · yıllık hak {bk['bu_yil_hak']} gün · "
                   f"kalan {H.tr_gun(bk['kalan'])}"
                   + (f" · sonraki hak {H.tr_tarih(bk['sonraki']['tarih'])} ({bk['sonraki']['gun']} gün)"
                      if bk["sonraki"] else ""))
    for h in hatalar:
        st.markdown(mesaj("hata", h), unsafe_allow_html=True)
    if p:
        durum = H.bilgi_durumu(p, adr)
        st.caption(f"Bilgilendirme e-postası: {durum.lower() if not durum.startswith('Gönderildi') else durum}")
        k1, k2 = st.columns(2)
        with k1:
            _kayit_belgesi_dugmesi(c, p)
        if p.get("bilgi_zamani") and H.bilgi_adresi(p, adr) and \
                k2.button("Bilgilendirmeyi tekrar gönder", key=f"{k}_tekrar", icon=":material/forward_to_inbox:"):
            ok, m = _bilgilendir(c, p)
            st.session_state["izn_bilgi_flas"] = (("basari", f"Bilgilendirme e-postası tekrar gönderildi: {m}")
                                                 if ok else ("uyari", f"E-posta gönderilemedi: {m}"))
            st.rerun()
    if st.button("Kartı kaydet", key=f"{k}_kaydet", type="primary", icon=":material/save:", disabled=bool(hatalar)):
        ok, h = D.personel_kaydet(kod, ad, bolum, giris, dogum, devir_t, devir_g, cikis, notu, sicil, eposta)
        if not ok:
            st.error(h)
            return
        # Kart ilk kez (ya da adres ilk kez) kaydedildi: çalışana bilgilendirme e-postası kendiliğinden gider
        kayit = dict(p, kod=kod, ad=ad or kod, departman=bolum, sicil_no=sicil, eposta=eposta,
                     ise_giris=giris.isoformat() if giris else None,
                     dogum_tarihi=dogum.isoformat() if dogum else None,
                     devir_tarihi=devir_t.isoformat() if devir_t else None, devir_gun=devir_g,
                     cikis_tarihi=cikis.isoformat() if cikis else None)
        flas = ("basari", f"{ad or kod} kaydedildi.")
        if H.bilgi_gerekli(kayit, adr):
            gitti, m = _bilgilendir(c, kayit)
            flas = (("basari", f"{ad or kod} kaydedildi; bilgilendirme e-postası gönderildi: {m}") if gitti else
                    ("uyari", f"{ad or kod} kaydedildi ama bilgilendirme e-postası gönderilemedi ({m}). "
                              "Kart bir sonraki kaydedilişinde yeniden denenir."))
        elif not kayit.get("bilgi_zamani") and not kayit.get("cikis_tarihi"):
            flas = ("bilgi", f"{ad or kod} kaydedildi. Kayıtlı e-posta adresi olmadığı için bilgilendirme "
                             "gönderilmedi.")
        st.session_state["izn_bilgi_flas"] = flas
        st.rerun()


# ── Ayarlar ─────────────────────────────────────────────────────────
def _ayarlar(ayar, kullanicilar=()):
    st.markdown(B.grup_basligi("İzin takibine girmeyen kullanıcılar"), unsafe_allow_html=True)
    secenek = sorted({str(k).strip().lower() for k in kullanicilar or [] if k} | set(ayar.get("haric") or []),
                     key=H.tr_sira)
    haric = st.multiselect("Kullanıcılar", secenek, default=[k for k in (ayar.get("haric") or []) if k in secenek],
                           format_func=kisi_adi, key="izn_ayar_haric", label_visibility="collapsed",
                           placeholder="Kimse seçilmedi",
                           help="Programı kullanan ama çalışan olmayanlar (ortaklar, dış danışmanlar). Personel "
                                "bölümündeki \"kart yok\" listesinde görünmezler.")
    if sorted(haric) != sorted(ayar.get("haric") or []):
        if st.button("Kaydet", key="izn_ayar_haric_kaydet", type="primary"):
            ok, h = D.ayar_yaz({**ayar, "haric": sorted(haric)})
            (st.rerun() if ok else st.error(h))
    st.markdown(B.grup_basligi("Çalışma günleri"), unsafe_allow_html=True)
    cmt = st.toggle("Cumartesi çalışılıyor", bool(ayar.get("cumartesi")), key="izn_ayar_cmt",
                    help="Açıksa Cumartesi iş günü sayılır ve izne denk gelirse izinden düşer.")
    st.caption("Pazar ve resmi tatiller her zaman izinden düşülmez; arife ve 28 Ekim yarım gün sayılır. "
               "Ayar yalnız bundan sonraki taleplere uygulanır; kaydedilmiş izinlerin gün sayısı değişmez.")
    if cmt != bool(ayar.get("cumartesi")):
        if st.button("Kaydet", key="izn_ayar_kaydet", type="primary"):
            ok, h = D.ayar_yaz({**ayar, "cumartesi": cmt})
            (st.rerun() if ok else st.error(h))
    st.markdown(B.grup_basligi("Resmi tatil takvimi"), unsafe_allow_html=True)
    st.caption(f"Bayram tarihleri {H.T.ILK_YIL}–{H.T.SON_YIL} yılları için tanımlı (Diyanet takvimi). Sonraki yıl "
               "programa eklenene kadar o yıla düşen izinlerde uyarı çıkar.")
