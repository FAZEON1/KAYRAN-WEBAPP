"""
HESAP MAKINESi - Urun Karlilik & Break-Even Modulu
Sadece ibrahim kullanicisina gorunur.
"""
import streamlit as st
import json
import io
from datetime import datetime

def _get_supabase():
    try:
        from supabase import create_client
        url = st.secrets["supabase"]["url"]
        key = st.secrets["supabase"]["key"]
        return create_client(url, key)
    except Exception:
        return None

def _hesap_kaydet(kullanici, urun_adi, alis_fiyati, masraflar_yuzdesi, senaryolar, notlar=""):
    sb = _get_supabase()
    if not sb:
        return False, "Supabase baglanti yok"
    try:
        masraflar_tutar = float(alis_fiyati) * float(masraflar_yuzdesi) / 100
        data = {
            "kullanici": kullanici,
            "urun_adi": urun_adi or "",
            "alis_fiyati": float(alis_fiyati),
            "masraflar": float(masraflar_yuzdesi),
            "toplam_maliyet": float(alis_fiyati) + masraflar_tutar,
            "senaryolar": json.dumps(senaryolar, ensure_ascii=False),
            "notlar": notlar or "",
            "olusturma_tarihi": datetime.now().isoformat()
        }
        sb.table("hm_urun_karliligi").insert(data).execute()
        return True, "ok"
    except Exception as e:
        return False, str(e)

def _hesaplari_getir(kullanici):
    sb = _get_supabase()
    if not sb:
        return []
    try:
        r = sb.table("hm_urun_karliligi").select("*").eq("kullanici", kullanici).order("olusturma_tarihi", desc=True).execute()
        return r.data or []
    except Exception:
        return []

def _hesap_sil(kayit_id):
    sb = _get_supabase()
    if not sb:
        return False
    try:
        sb.table("hm_urun_karliligi").delete().eq("id", kayit_id).execute()
        return True
    except Exception:
        return False

def _hesap_guncelle(kayit_id, notlar):
    sb = _get_supabase()
    if not sb:
        return False
    try:
        sb.table("hm_urun_karliligi").update({"notlar": notlar}).eq("id", kayit_id).execute()
        return True
    except Exception:
        return False

def hesapla_satis_fiyati(maliyet, marj_yuzdesi):
    if marj_yuzdesi >= 100:
        return None
    return maliyet / (1 - marj_yuzdesi / 100)

def hesapla_marj(maliyet, satis_fiyati):
    if satis_fiyati <= 0:
        return None
    return ((satis_fiyati - maliyet) / satis_fiyati) * 100

def hesapla_kar(maliyet, satis_fiyati):
    return satis_fiyati - maliyet

def uygula_indirim(satis_fiyati, indirim_yuzdesi=0, indirim_tutar=0):
    fiyat = satis_fiyati
    if indirim_yuzdesi > 0:
        fiyat = fiyat * (1 - indirim_yuzdesi / 100)
    elif indirim_tutar > 0:
        fiyat = fiyat - indirim_tutar
    return fiyat


def _hm_css():
    return """
<style>
.hm-card{background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.08);border-radius:16px;padding:20px 22px;margin-bottom:16px;}
.hm-senaryo-kart{background:rgba(99,102,241,0.06);border:1px solid rgba(99,102,241,0.15);border-radius:12px;padding:14px 16px;margin-bottom:10px;}
.hm-label{font-size:10px;color:#64748B;letter-spacing:1.5px;text-transform:uppercase;font-weight:700;margin-bottom:4px;}
.hm-deger{font-size:22px;font-weight:800;color:#FFFFFF;font-family:JetBrains Mono,monospace;}
.hm-separator{height:1px;background:rgba(255,255,255,0.06);margin:20px 0;}
[data-testid="stNumberInput"] label,[data-testid="stTextInput"] label,[data-testid="stTextArea"] label{color:#CBD5E1!important;font-size:12px!important;font-weight:600!important;}
[data-testid="stNumberInput"] input,[data-testid="stTextInput"] input{background:rgba(255,255,255,0.04)!important;border:1px solid rgba(255,255,255,0.12)!important;color:#FFFFFF!important;border-radius:10px!important;}
[data-testid="stTextArea"] textarea{background:rgba(255,255,255,0.04)!important;border:1px solid rgba(255,255,255,0.12)!important;color:#FFFFFF!important;border-radius:10px!important;}
</style>
"""

def _urun_karlilik_bolumu():
    aktif_kullanici = st.session_state.get("aktif_kullanici", "")
    st.markdown('<div style="display:inline-block;padding:6px 14px;background:rgba(99,102,241,0.12);border:1px solid rgba(99,102,241,0.25);border-radius:20px;margin-bottom:18px"><span style="color:#A5B4FC;font-size:11px;font-weight:600;letter-spacing:1px;text-transform:uppercase">Urun Karlilik Hesaplayici</span></div>', unsafe_allow_html=True)
    st.markdown('<p style="color:#94A3B8;font-size:13px;margin-bottom:24px">Urun maliyeti ve satis fiyatini girerek net marji hesaplayin.</p>', unsafe_allow_html=True)

    if "hm_senaryolar" not in st.session_state:
        st.session_state.hm_senaryolar = [
            {"id": 1, "ad": "Senaryo 1", "fiyat": 0.0, "marj": 0.0,
             "indirim_tipi": "Yok", "indirim_yuzdesi": 0.0, "indirim_tutar": 0.0}
        ]
    if "hm_senaryo_sayac" not in st.session_state:
        st.session_state.hm_senaryo_sayac = 1

    st.markdown('<div class="hm-card">', unsafe_allow_html=True)
    st.markdown('<div style="color:#FFFFFF;font-size:15px;font-weight:700;margin-bottom:16px">Maliyet Bilgileri (KDV Haric)</div>', unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1.5, 1.5, 1])
    with col1:
        urun_adi = st.text_input("Urun Adi / Kodu (opsiyonel)", placeholder="Orn: Monitor XG27AQM", key="hm_urun_adi")
    with col2:
        alis_fiyati = st.number_input("Alis Fiyati ($)", min_value=0.0, value=0.0, step=0.01, format="%.2f", key="hm_alis")
    with col3:
        masraflar_yuzdesi = st.number_input("Ek Masraflar (%)", min_value=0.0, max_value=99.9, value=0.0, step=0.1, format="%.1f", help="Kargo, komisyon, ambalaj vb. (alis fiyatinin yuzdesi)", key="hm_masraf")
    masraflar_tutar = alis_fiyati * masraflar_yuzdesi / 100
    toplam_maliyet = alis_fiyati + masraflar_tutar
    colm1, colm2, colm3, colm4 = st.columns(4)
    with colm1:
        st.markdown('<div class="hm-label">Alis Fiyati</div><div class="hm-deger">$' + "{:.2f}".format(alis_fiyati) + '</div>', unsafe_allow_html=True)
    with colm2:
        st.markdown('<div class="hm-label">Ek Masraflar</div><div class="hm-deger">%' + "{:.1f}".format(masraflar_yuzdesi) + '</div>', unsafe_allow_html=True)
    with colm3:
        st.markdown('<div class="hm-label">Masraf Tutari</div><div class="hm-deger">$' + "{:.2f}".format(masraflar_tutar) + '</div>', unsafe_allow_html=True)
    with colm4:
        st.markdown('<div class="hm-label">Toplam Maliyet</div><div class="hm-deger" style="color:#60A5FA">$' + "{:.2f}".format(toplam_maliyet) + '</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)


    st.markdown('<div class="hm-card">', unsafe_allow_html=True)
    st.markdown('<div style="color:#FFFFFF;font-size:15px;font-weight:700;margin-bottom:4px">Fiyat Senaryolari</div>', unsafe_allow_html=True)
    st.markdown('<p style="color:#94A3B8;font-size:12px;margin-bottom:16px">Her senaryo icin satis fiyati veya marj giriniz — biri girilince digeri otomatik hesaplanir.</p>', unsafe_allow_html=True)

    senaryolar_sonuc = []
    for idx, sen in enumerate(st.session_state.hm_senaryolar):
        sen_id = sen["id"]
        sen_ad_val = sen.get("ad", "Senaryo")
        st.markdown('<div class="hm-senaryo-kart"><div style="color:#A5B4FC;font-size:11px;font-weight:700;letter-spacing:1px;margin-bottom:10px"> ' + sen_ad_val + '</div>', unsafe_allow_html=True)
        cs1, cs2, cs3, cs4, cs5 = st.columns([1.5, 1, 1, 1, 0.5])
        with cs1:
            sen_ad = st.text_input("Senaryo Adi", value=sen["ad"], key="sen_ad_" + str(sen_id))
        with cs2:
            sen_fiyat = st.number_input("Satis Fiyati ($)", min_value=0.0, value=float(sen["fiyat"]), step=0.01, format="%.2f", key="sen_fiyat_" + str(sen_id))
        with cs3:
            sen_marj = st.number_input("Marj (%)", min_value=0.0, max_value=99.9, value=float(sen["marj"]), step=0.1, format="%.1f", key="sen_marj_" + str(sen_id))
        with cs4:
            ind_secenekler = ["Yok", "Yuzde (%)", "Tutar ($)"]
            ind_mevcut = sen.get("indirim_tipi", "Yok")
            if ind_mevcut not in ind_secenekler:
                ind_mevcut = "Yok"
            indirim_tipi = st.selectbox("Indirim Tipi", ind_secenekler, index=ind_secenekler.index(ind_mevcut), key="sen_ind_tip_" + str(sen_id))
        with cs5:
            sil_btn = st.button("", key="sen_sil_" + str(sen_id), help="Senaryoyu sil")

        prev_fiyat = sen.get("_prev_fiyat", sen["fiyat"])
        prev_marj = sen.get("_prev_marj", sen["marj"])
        if toplam_maliyet > 0:
            fiyat_degisti = abs(sen_fiyat - prev_fiyat) > 0.001
            marj_degisti = abs(sen_marj - prev_marj) > 0.001
            if fiyat_degisti and sen_fiyat > 0:
                hm = hesapla_marj(toplam_maliyet, sen_fiyat)
                if hm is not None:
                    sen_marj = hm
            elif marj_degisti and sen_marj > 0:
                hf = hesapla_satis_fiyati(toplam_maliyet, sen_marj)
                if hf is not None:
                    sen_fiyat = hf

        ind_yuzdesi = 0.0
        ind_tutar = 0.0
        if indirim_tipi == "Yuzde (%)":
            ind_yuzdesi = st.number_input("Indirim Yuzdesi (%)", min_value=0.0, max_value=99.9, value=float(sen.get("indirim_yuzdesi", 0)), step=0.1, format="%.1f", key="ind_yuz_" + str(sen_id))
        elif indirim_tipi == "Tutar ($)":
            ind_tutar = st.number_input("Indirim Tutari ($)", min_value=0.0, value=float(sen.get("indirim_tutar", 0)), step=0.01, format="%.2f", key="ind_tut_" + str(sen_id))

        ind_fiyat = uygula_indirim(sen_fiyat, ind_yuzdesi, ind_tutar)
        ind_marj = hesapla_marj(toplam_maliyet, ind_fiyat) if ind_fiyat > 0 and toplam_maliyet > 0 else 0
        kar = hesapla_kar(toplam_maliyet, ind_fiyat)

        if toplam_maliyet > 0 and sen_fiyat > 0:
            kar_renk = "#10B981" if kar > 0 else "#EF4444" if kar < 0 else "#F59E0B"
            cr1, cr2, cr3, cr4 = st.columns(4)
            with cr1:
                st.markdown('<div class="hm-label">Satis Fiyati</div><div class="hm-deger">$' + "{:.2f}".format(sen_fiyat) + '</div>', unsafe_allow_html=True)
            with cr2:
                if indirim_tipi != "Yok":
                    st.markdown('<div class="hm-label">Ind. Fiyat</div><div class="hm-deger" style="color:#F59E0B">$' + "{:.2f}".format(ind_fiyat) + '</div>', unsafe_allow_html=True)
                else:
                    st.markdown('<div class="hm-label">Indirim</div><div style="color:#64748B;font-size:14px">Yok</div>', unsafe_allow_html=True)
            with cr3:
                st.markdown('<div class="hm-label">Net Kar</div><div class="hm-deger" style="color:' + kar_renk + '">$' + "{:.2f}".format(kar) + '</div>', unsafe_allow_html=True)
            with cr4:
                marj_val = ind_marj if ind_marj else 0
                st.markdown('<div class="hm-label">Marj</div><div class="hm-deger" style="color:' + kar_renk + '">%' + "{:.1f}".format(marj_val) + '</div>', unsafe_allow_html=True)

        if not sil_btn:
            senaryolar_sonuc.append({"id": sen_id, "ad": sen_ad, "fiyat": sen_fiyat, "marj": sen_marj,
                                     "indirim_tipi": indirim_tipi, "indirim_yuzdesi": ind_yuzdesi, "indirim_tutar": ind_tutar,
                                     "_prev_fiyat": sen_fiyat, "_prev_marj": sen_marj})
        st.markdown('</div>', unsafe_allow_html=True)

    st.session_state.hm_senaryolar = senaryolar_sonuc

    if st.button("+ Yeni Senaryo Ekle", key="hm_senaryo_ekle"):
        st.session_state.hm_senaryo_sayac += 1
        yeni_id = st.session_state.hm_senaryo_sayac
        st.session_state.hm_senaryolar.append({"id": yeni_id, "ad": "Senaryo " + str(yeni_id),
                                               "fiyat": 0.0, "marj": 0.0, "indirim_tipi": "Yok", "indirim_yuzdesi": 0.0, "indirim_tutar": 0.0})
        st.rerun()

    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="hm-separator"></div>', unsafe_allow_html=True)
    cks1, cks2, cks3 = st.columns([2, 1, 1])
    with cks1:
        notlar_kayit = st.text_area("Not / Yorum (opsiyonel)", placeholder="Bu hesaplamaya dair notunuzu girin...", key="hm_notlar", height=80)
    with cks2:
        st.markdown('<div style="height:28px"></div>', unsafe_allow_html=True)
        kaydet_btn = st.button("Hesaplamay Kaydet", key="hm_kaydet", use_container_width=True, type="primary")
    with cks3:
        st.markdown('<div style="height:28px"></div>', unsafe_allow_html=True)
        sifirla_btn = st.button("Formu Sifirla", key="hm_sifirla", use_container_width=True)

    if kaydet_btn:
        if toplam_maliyet <= 0:
            st.warning("Lutfen once maliyet bilgilerini girin.")
        elif not senaryolar_sonuc:
            st.warning("En az bir senaryo eklemelisiniz.")
        else:
            ok, msg = _hesap_kaydet(aktif_kullanici, urun_adi, alis_fiyati, masraflar_yuzdesi, senaryolar_sonuc, notlar_kayit)
            if ok:
                st.success("Hesaplama basariyla kaydedildi!")
                if "hm_gecmis_cache" in st.session_state:
                    del st.session_state["hm_gecmis_cache"]
            else:
                st.error("Kaydetme hatasi: " + str(msg))
    if sifirla_btn:
        for k in ["hm_urun_adi", "hm_alis", "hm_masraf", "hm_senaryolar", "hm_senaryo_sayac", "hm_notlar"]:
            if k in st.session_state:
                del st.session_state[k]
        st.rerun()


def _gecmis_hesaplamalar():
    aktif_kullanici = st.session_state.get("aktif_kullanici", "")
    st.markdown('<div class="hm-separator"></div>', unsafe_allow_html=True)
    st.markdown('<div style="color:#FFFFFF;font-size:15px;font-weight:700;margin-bottom:16px">Kaydedilmis Hesaplamalar</div>', unsafe_allow_html=True)
    if "hm_gecmis_cache" not in st.session_state:
        with st.spinner("Yukleniyor..."):
            st.session_state.hm_gecmis_cache = _hesaplari_getir(aktif_kullanici)
    kayitlar = st.session_state.hm_gecmis_cache
    cg1, cg2, cg3 = st.columns([1, 1, 4])
    with cg1:
        if st.button("Yenile", key="hm_gecmis_yenile"):
            if "hm_gecmis_cache" in st.session_state:
                del st.session_state["hm_gecmis_cache"]
            st.rerun()
    with cg2:
        if kayitlar:
            excel_data = _kayitlari_excel_olustur(kayitlar)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            st.download_button(label="Excel Indir", data=excel_data,
                               file_name="hesap_makinesi_" + ts + ".xlsx",
                               mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                               key="hm_excel_indir")
    if not kayitlar:
        st.markdown('<div style="text-align:center;padding:32px;color:#64748B;font-size:13px">Henuz kaydedilmis hesaplama yok.</div>', unsafe_allow_html=True)
        return

    headers = ["Urun / Kod", "Alis ($)", "Masraf (%)", "Masraf ($)", "Top. Maliyet ($)", "Tarih", "Islem"]
    th1, th2, th3, th4, th5, th6, th7 = st.columns([2, 1, 0.8, 0.8, 1.2, 1.5, 0.8])
    for col, h in zip([th1, th2, th3, th4, th5, th6, th7], headers):
        with col:
            st.markdown('<div class="hm-label">' + h + '</div>', unsafe_allow_html=True)

    for kayit in kayitlar:
        rid = kayit.get("id")
        uad = kayit.get("urun_adi") or "—"
        ali = kayit.get("alis_fiyati", 0)
        mas_yuz = kayit.get("masraflar", 0)
        mas_tut = ali * mas_yuz / 100
        top = kayit.get("toplam_maliyet", 0)
        tar_raw = kayit.get("olusturma_tarihi", "")
        try:
            tar = datetime.fromisoformat(tar_raw[:19]).strftime("%d.%m.%Y %H:%M")
        except Exception:
            tar = tar_raw[:16] if tar_raw else "—"
        rc1, rc2, rc3, rc4, rc5, rc6, rc7 = st.columns([2, 1, 0.8, 0.8, 1.2, 1.5, 0.8])
        with rc1:
            st.markdown('<div style="color:#E2E8F0;font-size:13px;padding:8px 0">' + uad + '</div>', unsafe_allow_html=True)
        with rc2:
            st.markdown('<div style="color:#CBD5E1;font-size:13px;padding:8px 0">$' + "{:.2f}".format(ali) + '</div>', unsafe_allow_html=True)
        with rc3:
            st.markdown('<div style="color:#CBD5E1;font-size:13px;padding:8px 0">%' + "{:.1f}".format(mas_yuz) + '</div>', unsafe_allow_html=True)
        with rc4:
            st.markdown('<div style="color:#CBD5E1;font-size:13px;padding:8px 0">$' + "{:.2f}".format(mas_tut) + '</div>', unsafe_allow_html=True)
        with rc5:
            st.markdown('<div style="color:#60A5FA;font-size:13px;font-weight:600;padding:8px 0">$' + "{:.2f}".format(top) + '</div>', unsafe_allow_html=True)
        with rc6:
            st.markdown('<div style="color:#94A3B8;font-size:12px;padding:8px 0">' + tar + '</div>', unsafe_allow_html=True)
        with rc7:
            detay_key = "hm_detay_ac_" + str(rid)
            if st.button("", key="hm_detay_" + str(rid), help="Detaylari goruntule"):
                st.session_state[detay_key] = not st.session_state.get(detay_key, False)
        if st.session_state.get("hm_detay_ac_" + str(rid), False):
            _kayit_detay_panel(kayit)
        st.markdown('<div class="hm-separator" style="margin:6px 0"></div>', unsafe_allow_html=True)


def _kayit_detay_panel(kayit):
    rid = kayit.get("id")
    senaryolar_raw = kayit.get("senaryolar", "[]")
    try:
        senaryolar = json.loads(senaryolar_raw) if isinstance(senaryolar_raw, str) else senaryolar_raw
    except Exception:
        senaryolar = []
    toplam_maliyet = kayit.get("toplam_maliyet", 0)
    st.markdown('<div style="background:rgba(99,102,241,0.05);border:1px solid rgba(99,102,241,0.2);border-radius:12px;padding:16px 20px;margin:8px 0 12px">', unsafe_allow_html=True)
    if senaryolar:
        st.markdown('<div style="color:#A5B4FC;font-size:12px;font-weight:700;margin-bottom:10px">Senaryolar</div>', unsafe_allow_html=True)
        for sen in senaryolar:
            sen_fiyat = sen.get("fiyat", 0)
            ind_fiyat = uygula_indirim(sen_fiyat, sen.get("indirim_yuzdesi", 0), sen.get("indirim_tutar", 0))
            ind_marj = hesapla_marj(toplam_maliyet, ind_fiyat) if ind_fiyat > 0 and toplam_maliyet > 0 else 0
            kar = hesapla_kar(toplam_maliyet, ind_fiyat)
            kar_renk = "#10B981" if kar > 0 else "#EF4444" if kar < 0 else "#F59E0B"
            sc1, sc2, sc3, sc4 = st.columns(4)
            with sc1:
                st.markdown('<div class="hm-label">' + sen.get("ad","?") + '</div><div style="color:#E2E8F0;font-size:14px;font-weight:600">$' + "{:.2f}".format(sen_fiyat) + '</div>', unsafe_allow_html=True)
            with sc2:
                if sen.get("indirim_tipi","Yok") != "Yok":
                    st.markdown('<div class="hm-label">Ind. Fiyat</div><div style="color:#F59E0B;font-size:14px;font-weight:600">$' + "{:.2f}".format(ind_fiyat) + '</div>', unsafe_allow_html=True)
                else:
                    st.markdown('<div class="hm-label">Indirim</div><div style="color:#64748B;font-size:12px">Yok</div>', unsafe_allow_html=True)
            with sc3:
                st.markdown('<div class="hm-label">Net Kar</div><div style="color:' + kar_renk + ';font-size:14px;font-weight:600">$' + "{:.2f}".format(kar) + '</div>', unsafe_allow_html=True)
            with sc4:
                mv = ind_marj if ind_marj else 0
                st.markdown('<div class="hm-label">Marj</div><div style="color:' + kar_renk + ';font-size:14px;font-weight:600">%' + "{:.1f}".format(mv) + '</div>', unsafe_allow_html=True)
        st.markdown('<div class="hm-separator" style="margin:12px 0"></div>', unsafe_allow_html=True)
    mevcut_not = kayit.get("notlar", "")
    yeni_not = st.text_area("Not / Yorum", value=mevcut_not, key="hm_not_edit_" + str(rid), height=80)
    dp1, dp2, dp3 = st.columns([1, 1, 3])
    with dp1:
        if st.button("Notu Kaydet", key="hm_not_kaydet_" + str(rid)):
            if _hesap_guncelle(rid, yeni_not):
                st.success("Not kaydedildi.")
                if "hm_gecmis_cache" in st.session_state:
                    del st.session_state["hm_gecmis_cache"]
                st.rerun()
    with dp2:
        if st.button("Kaydi Sil", key="hm_kayit_sil_" + str(rid), type="primary"):
            st.session_state["hm_sil_onay_" + str(rid)] = True
    if st.session_state.get("hm_sil_onay_" + str(rid), False):
        st.warning("Bu kaydi kalici olarak silmek istiyor musunuz?")
        eonay1, eonay2 = st.columns(2)
        with eonay1:
            if st.button("Evet, Sil", key="hm_sil_evet_" + str(rid)):
                if _hesap_sil(rid):
                    if "hm_gecmis_cache" in st.session_state:
                        del st.session_state["hm_gecmis_cache"]
                    st.session_state.pop("hm_detay_ac_" + str(rid), None)
                    st.session_state.pop("hm_sil_onay_" + str(rid), None)
                    st.rerun()
        with eonay2:
            if st.button("Iptal", key="hm_sil_iptal_" + str(rid)):
                st.session_state.pop("hm_sil_onay_" + str(rid), None)
                st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)


def _kayitlari_excel_olustur(kayitlar):
    try:
        import openpyxl
        from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
        from openpyxl.utils import get_column_letter
    except ImportError:
        lines = ["Urun Adi,Alis Fiyati,Masraflar (%),Masraf Tutari ($),Toplam Maliyet,Tarih,Notlar"]
        for k in kayitlar:
            ali = k.get("alis_fiyati", 0)
            mas_yuz = k.get("masraflar", 0)
            mas_tut = ali * mas_yuz / 100
            lines.append(",".join(str(x) for x in [k.get("urun_adi",""), ali, mas_yuz, round(mas_tut,2),
                                                    k.get("toplam_maliyet",0), k.get("olusturma_tarihi",""), k.get("notlar","")]))
        return "\n".join(lines).encode("utf-8")
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Karlilik Hesaplamalari"
    header_fill = PatternFill("solid", fgColor="1E293B")
    header_font = Font(bold=True, color="FFFFFF", size=11)
    border_side = Side(style="thin", color="374151")
    thin_border = Border(left=border_side, right=border_side, top=border_side, bottom=border_side)
    headers = ["Urun Adi/Kodu", "Alis Fiyati ($)", "Ek Masraflar (%)", "Masraf Tutari ($)", "Toplam Maliyet ($)",
               "Senaryo Adi", "Satis Fiyati ($)", "Indirimli Fiyat ($)", "Net Kar ($)", "Marj (%)", "Tarih", "Notlar"]
    for ci, h in enumerate(headers, 1):
        cell = ws.cell(row=1, column=ci, value=h)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center")
        cell.border = thin_border
    row_num = 2
    for kayit in kayitlar:
        sens_raw = kayit.get("senaryolar", "[]")
        try:
            sens = json.loads(sens_raw) if isinstance(sens_raw, str) else sens_raw
        except Exception:
            sens = []
        ali = kayit.get("alis_fiyati", 0)
        mas_yuz = kayit.get("masraflar", 0)
        mas_tut = ali * mas_yuz / 100
        toplam_maliyet = kayit.get("toplam_maliyet", 0)
        tar_raw = kayit.get("olusturma_tarihi", "")
        try:
            tar = datetime.fromisoformat(tar_raw[:19]).strftime("%d.%m.%Y %H:%M")
        except Exception:
            tar = tar_raw[:16] if tar_raw else ""
        if not sens:
            sens = [{"ad": "", "fiyat": 0, "indirim_tipi": "Yok", "indirim_yuzdesi": 0, "indirim_tutar": 0}]
        for sen in sens:
            sf = sen.get("fiyat", 0)
            inf = uygula_indirim(sf, sen.get("indirim_yuzdesi", 0), sen.get("indirim_tutar", 0))
            marj = hesapla_marj(toplam_maliyet, inf) if inf > 0 and toplam_maliyet > 0 else 0
            kar = hesapla_kar(toplam_maliyet, inf)
            row_data = [kayit.get("urun_adi",""), round(ali,2), round(mas_yuz,1), round(mas_tut,2),
                        round(toplam_maliyet,2), sen.get("ad",""), round(sf,2), round(inf,2),
                        round(kar,2), round(marj or 0, 2), tar, kayit.get("notlar","")]
            for ci, val in enumerate(row_data, 1):
                cell = ws.cell(row=row_num, column=ci, value=val)
                cell.border = thin_border
                if ci == 10 and isinstance(val, (int, float)):
                    cell.number_format = "0.00%"
                    cell.value = val / 100
            row_num += 1
    for col in ws.columns:
        max_len = max((len(str(c.value or "")) for c in col), default=10)
        ws.column_dimensions[get_column_letter(col[0].column)].width = min(max_len + 4, 40)
    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return buffer.getvalue()


def _breakeven_sidebar():
    with st.sidebar:
        st.markdown('<div class="hm-separator"></div>', unsafe_allow_html=True)
        st.markdown('<div style="font-size:10px;color:#F59E0B;letter-spacing:2px;font-weight:700;text-transform:uppercase;margin:4px 0 10px;padding-left:6px">KIRILMA NOKTASI</div>', unsafe_allow_html=True)
        if "be_senaryolar" not in st.session_state:
            st.session_state.be_senaryolar = [{"id": 1, "ad": "Senaryo 1",
                "gider_modu": "Toplam", "toplam_gider": 0.0, "kalemler": [],
                "ortalama_marj": 30.0, "mevcut_ciro": 0.0, "ort_urun_fiyati": 0.0, "periyot": "Aylik"}]
        if "be_sayac" not in st.session_state:
            st.session_state.be_sayac = 1
        if "be_aktif_idx" not in st.session_state:
            st.session_state.be_aktif_idx = 0
        aktif_idx = min(st.session_state.be_aktif_idx, len(st.session_state.be_senaryolar) - 1)

        if len(st.session_state.be_senaryolar) > 1:
            for si, sen in enumerate(st.session_state.be_senaryolar):
                btn_style = "primary" if si == aktif_idx else "secondary"
                if st.button(" " + sen["ad"], key="be_sen_sec_" + str(sen["id"]), type=btn_style, use_container_width=True):
                    st.session_state.be_aktif_idx = si
                    st.rerun()

        sen = st.session_state.be_senaryolar[aktif_idx]
        sen_id = sen["id"]
        sen_ad_be = st.text_input("Senaryo Adi", value=sen["ad"], key="be_sen_ad_" + str(sen_id))
        periyot_secenekler = ["Gunluk", "Haftalik", "Aylik", "Yillik"]
        periyot_mevcut = sen.get("periyot", "Aylik")
        if periyot_mevcut not in periyot_secenekler:
            periyot_mevcut = "Aylik"
        periyot = st.selectbox("Periyot", periyot_secenekler, index=periyot_secenekler.index(periyot_mevcut), key="be_periyot_" + str(sen_id))
        periyot_carpan = {"Gunluk": 1/30, "Haftalik": 1/4.33, "Aylik": 1, "Yillik": 12}
        carpan = periyot_carpan.get(periyot, 1)

        gider_secenekler = ["Toplam", "Kalem Kalem"]
        gider_mevcut = sen.get("gider_modu", "Toplam")
        if gider_mevcut not in gider_secenekler:
            gider_mevcut = "Toplam"
        gider_modu = st.selectbox("Gider Girisi", gider_secenekler, index=gider_secenekler.index(gider_mevcut), key="be_gider_modu_" + str(sen_id))

        if gider_modu == "Toplam":
            toplam_gider_be = st.number_input("Aylik Sabit Gider ($)", min_value=0.0, value=float(sen.get("toplam_gider",0)), step=10.0, format="%.2f", key="be_toplam_gider_" + str(sen_id))
            kalemler_be = sen.get("kalemler", [])
        else:
            kalemler_be = sen.get("kalemler", [{"ad": "Kira", "tutar": 0.0}, {"ad": "Maaslar", "tutar": 0.0}, {"ad": "Fatura", "tutar": 0.0}])
            yeni_kalemler = []
            for ki, kalem in enumerate(kalemler_be):
                ck1, ck2 = st.columns([2, 1])
                with ck1:
                    kalem_ad = st.text_input("Kalem", value=kalem.get("ad",""), key="be_kal_ad_" + str(sen_id) + "_" + str(ki))
                with ck2:
                    kalem_tut = st.number_input("$", min_value=0.0, value=float(kalem.get("tutar",0)), step=10.0, format="%.0f", key="be_kal_tut_" + str(sen_id) + "_" + str(ki))
                yeni_kalemler.append({"ad": kalem_ad, "tutar": kalem_tut})
            if st.button("+ Kalem Ekle", key="be_kalem_ekle_" + str(sen_id)):
                yeni_kalemler.append({"ad": "Yeni Kalem", "tutar": 0.0})
            kalemler_be = yeni_kalemler
            toplam_gider_be = sum(k.get("tutar", 0) for k in kalemler_be)

        gider_donem = toplam_gider_be * carpan
        st.markdown('<div class="hm-label">Donem Gideri (' + periyot + ')</div><div style="color:#F59E0B;font-size:16px;font-weight:700">$' + "{:,.0f}".format(gider_donem) + '</div>', unsafe_allow_html=True)
        st.markdown('<div style="height:8px"></div>', unsafe_allow_html=True)
        ort_marj = st.number_input("Ortalama Marj (%)", min_value=0.1, max_value=99.9, value=float(sen.get("ortalama_marj",30)), step=0.1, format="%.1f", key="be_marj_" + str(sen_id))
        mevcut_ciro = st.number_input("Mevcut " + periyot + " Cirom ($)", min_value=0.0, value=float(sen.get("mevcut_ciro",0)), step=100.0, format="%.2f", key="be_ciro_" + str(sen_id))
        ort_urun = st.number_input("Ort. Urun Fiyati ($)", min_value=0.0, value=float(sen.get("ort_urun_fiyati",0)), step=10.0, format="%.2f", key="be_urun_" + str(sen_id), help="Kac adet satmalisin hesabi icin")

        if ort_marj > 0 and gider_donem > 0:
            hedef_ciro = gider_donem / (ort_marj / 100)
            kalan = max(0, hedef_ciro - mevcut_ciro)
            ilerleme = min(1.0, mevcut_ciro / hedef_ciro) if hedef_ciro > 0 else 0
            st.markdown('<div class="hm-separator"></div>', unsafe_allow_html=True)
            st.markdown('<div style="color:#FFFFFF;font-size:12px;font-weight:700;margin-bottom:8px">Kirilma Noktasi</div>', unsafe_allow_html=True)
            st.markdown('<div class="hm-label">Hedef Ciro (' + periyot + ')</div><div style="color:#A5B4FC;font-size:18px;font-weight:800">$' + "{:,.0f}".format(hedef_ciro) + '</div>', unsafe_allow_html=True)
            if mevcut_ciro > 0:
                durum_renk = "#10B981" if mevcut_ciro >= hedef_ciro else "#EF4444"
                durum_ikon = "OK" if mevcut_ciro >= hedef_ciro else "!!"
                st.markdown('<div class="hm-label" style="margin-top:8px">Kalan</div><div style="color:' + durum_renk + ';font-size:16px;font-weight:700">' + durum_ikon + ' $' + "{:,.0f}".format(kalan) + '</div>', unsafe_allow_html=True)
            pct = "{:.1f}".format(ilerleme * 100)
            st.markdown('<div style="margin:10px 0 4px;height:8px;background:rgba(255,255,255,0.08);border-radius:4px;overflow:hidden"><div style="height:100%;width:' + pct + '%;background:linear-gradient(90deg,#6366F1,#10B981);border-radius:4px"></div></div>', unsafe_allow_html=True)
            st.markdown('<div style="color:#94A3B8;font-size:10px;text-align:right">%' + "{:.0f}".format(ilerleme * 100) + ' tamamlandi</div>', unsafe_allow_html=True)
            if ort_urun > 0:
                hedef_adet = hedef_ciro / ort_urun
                kalan_adet = max(0, kalan / ort_urun)
                st.markdown('<div class="hm-label" style="margin-top:8px">Hedef Adet</div><div style="color:#C4B5FD;font-size:16px;font-weight:700">' + "{:,.0f}".format(hedef_adet) + ' adet</div>', unsafe_allow_html=True)
                if mevcut_ciro > 0:
                    st.markdown('<div style="color:#94A3B8;font-size:11px">Kalan: ' + "{:,.0f}".format(kalan_adet) + ' adet</div>', unsafe_allow_html=True)
        else:
            st.markdown('<div style="color:#475569;font-size:12px;margin-top:8px">Gider ve marj girerek kirilma noktasini hesaplayin.</div>', unsafe_allow_html=True)

        st.session_state.be_senaryolar[aktif_idx] = {"id": sen_id, "ad": sen_ad_be,
            "gider_modu": gider_modu, "toplam_gider": toplam_gider_be, "kalemler": kalemler_be,
            "ortalama_marj": ort_marj, "mevcut_ciro": mevcut_ciro, "ort_urun_fiyati": ort_urun, "periyot": periyot}

        bcol1, bcol2 = st.columns(2)
        with bcol1:
            if st.button("+ Senaryo", key="be_senaryo_ekle", use_container_width=True):
                st.session_state.be_sayac += 1
                yid = st.session_state.be_sayac
                st.session_state.be_senaryolar.append({"id": yid, "ad": "Senaryo " + str(yid),
                    "gider_modu": "Toplam", "toplam_gider": 0.0, "kalemler": [],
                    "ortalama_marj": 30.0, "mevcut_ciro": 0.0, "ort_urun_fiyati": 0.0, "periyot": "Aylik"})
                st.session_state.be_aktif_idx = len(st.session_state.be_senaryolar) - 1
                st.rerun()
        with bcol2:
            if len(st.session_state.be_senaryolar) > 1:
                if st.button("Sil", key="be_senaryo_sil", use_container_width=True):
                    st.session_state.be_senaryolar.pop(aktif_idx)
                    st.session_state.be_aktif_idx = max(0, aktif_idx - 1)
                    st.rerun()

def run():
    st.markdown(_hm_css(), unsafe_allow_html=True)
    st.markdown(
        '<div style="margin-bottom:28px">'
        '<div style="display:inline-block;padding:6px 14px;background:rgba(245,158,11,0.12);border:1px solid rgba(245,158,11,0.3);border-radius:20px;margin-bottom:16px">'
        '<span style="color:#FCD34D;font-size:11px;font-weight:600;letter-spacing:1px;text-transform:uppercase">Hesap Makinesi</span>'
        '</div>'
        '<h1 style="font-family:Inter,sans-serif;font-size:clamp(22px,4vw,36px);font-weight:800;color:#FFFFFF;margin:0">Hesap Makinesi</h1>'
        '<p style="color:#94A3B8;font-size:13px;margin-top:6px">Urun karlilik analizi ve kirilma noktasi hesaplama araci</p>'
        '</div>',
        unsafe_allow_html=True
    )
    _breakeven_sidebar()
    _urun_karlilik_bolumu()
    _gecmis_hesaplamalar()
