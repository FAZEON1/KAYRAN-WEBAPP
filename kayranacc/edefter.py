# ══════════════════════════════════════════════════════════════════════
# 📚 e-DEFTER MODÜLÜ — GİB Yazılım Uyumluluk Onayı standartlarına göre
# ══════════════════════════════════════════════════════════════════════
# FAZ 1 (AKTİF): Çift taraflı kayıt çekirdeği — Tekdüzen Hesap Planı,
#   muhasebe fişi (borç=alacak), yevmiye (madde numaralı), kebir, mizan.
# SONRAKİ FAZLAR: XBRL-GL e-Defter/berat üretimi (Faz 2), mali mühür ve
#   GİB uyumluluk test süreci (Faz 3).
# NOT: GİB uyumluluk onayı alınana kadar buradaki kayıtlar YASAL DEFTER
#   YERİNE GEÇMEZ — iç kontrol ve hazırlık amaçlıdır.
# ══════════════════════════════════════════════════════════════════════

import streamlit as st
import pandas as pd
from datetime import date

from kayranacc.database import get_client
from shared.utils import metrik_satiri

# ── GİB standartları (Yazılım Uyumluluk Onayı Kılavuzu v1.6) ─────────────
EDEFTER_BELGE_TURLERI = {
    "Y":  "Yevmiye Defteri",
    "YB": "Yevmiye Defteri Beratı",
    "K":  "Büyük Defter (Defter-i Kebir)",
    "KB": "Büyük Defter Beratı",
}
EDEFTER_DOSYA_AD_KALIBI = "{vkn}-{donem}-{tur}-{parca:06d}.xml"
EDEFTER_GIB_ONEK = "GIB-"
EDEFTER_UNIQUEID_KALIBI = "YEV{donem}{sira:06d}"
EDEFTER_XSLT_DOSYALARI = ("berat.xslt", "kebir.xslt", "yevmiye.xslt")
EDEFTER_TEST_SENARYOLARI = [
    "S1: 10-30 maddelik yevmiye · ≥10 çeşit ana hesap · alt hesaplı · zip ≤1MB",
    "S2: 100-1000 madde · kapanış işlemleri (Aralık) · ≥15 ana hesap · zip ≤2MB",
    "S3: 100-1000 madde · açılış işlemleri (Ocak) · ≥15 ana hesap · zip ≤2MB",
    "S4: 5000-10000 madde · ≥20 ana hesap türü · zip ≤10MB",
    "S5: 2 parçalı defter — ilk parça · ≥10 ana hesap · zip ≤10MB",
    "S6: 2 parçalı defter — ikinci/son parça · zip ≤10MB",
    "S7: Şubeli kebir + berat · dosya adı/içerik şube tutarlılığı · zip ≤1MB",
]

FIS_TURLERI = ["Mahsup", "Tahsil", "Tediye", "Açılış", "Kapanış"]

# ── TEKDÜZEN HESAP PLANI — yaygın ana hesaplar (çekirdek seed) ──────────
THP_ANA_HESAPLAR = [
    ("100", "KASA"), ("101", "ALINAN ÇEKLER"), ("102", "BANKALAR"),
    ("103", "VERİLEN ÇEKLER VE ÖDEME EMİRLERİ (-)"), ("108", "DİĞER HAZIR DEĞERLER"),
    ("120", "ALICILAR"), ("121", "ALACAK SENETLERİ"), ("126", "VERİLEN DEPOZİTO VE TEMİNATLAR"),
    ("128", "ŞÜPHELİ TİCARİ ALACAKLAR"), ("131", "ORTAKLARDAN ALACAKLAR"),
    ("136", "DİĞER ÇEŞİTLİ ALACAKLAR"), ("150", "İLK MADDE VE MALZEME"),
    ("153", "TİCARİ MALLAR"), ("157", "DİĞER STOKLAR"),
    ("159", "VERİLEN SİPARİŞ AVANSLARI"), ("180", "GELECEK AYLARA AİT GİDERLER"),
    ("190", "DEVREDEN KDV"), ("191", "İNDİRİLECEK KDV"), ("193", "PEŞİN ÖDENEN VERGİLER VE FONLAR"),
    ("195", "İŞ AVANSLARI"), ("196", "PERSONEL AVANSLARI"),
    ("220", "ALICILAR (UZUN VADELİ)"), ("242", "İŞTİRAKLER"),
    ("252", "BİNALAR"), ("253", "TESİS, MAKİNE VE CİHAZLAR"), ("254", "TAŞITLAR"),
    ("255", "DEMİRBAŞLAR"), ("257", "BİRİKMİŞ AMORTİSMANLAR (-)"),
    ("260", "HAKLAR"), ("264", "ÖZEL MALİYETLER"),
    ("300", "BANKA KREDİLERİ"), ("303", "UZUN VADELİ KREDİLERİN ANAPARA TAKSİTLERİ"),
    ("320", "SATICILAR"), ("321", "BORÇ SENETLERİ"), ("326", "ALINAN DEPOZİTO VE TEMİNATLAR"),
    ("331", "ORTAKLARA BORÇLAR"), ("335", "PERSONELE BORÇLAR"), ("336", "DİĞER ÇEŞİTLİ BORÇLAR"),
    ("340", "ALINAN SİPARİŞ AVANSLARI"), ("360", "ÖDENECEK VERGİ VE FONLAR"),
    ("361", "ÖDENECEK SOSYAL GÜVENLİK KESİNTİLERİ"), ("368", "VADESİ GEÇMİŞ ERTELENMİŞ VEYA TAKSİTLENDİRİLMİŞ VERGİ VE DİĞER YÜKÜMLÜLÜKLER"),
    ("369", "ÖDENECEK DİĞER YÜKÜMLÜLÜKLER"), ("391", "HESAPLANAN KDV"),
    ("397", "SAYIM VE TESELLÜM FAZLALARI"),
    ("400", "BANKA KREDİLERİ (UZUN VADELİ)"), ("420", "SATICILAR (UZUN VADELİ)"),
    ("500", "SERMAYE"), ("540", "YASAL YEDEKLER"), ("570", "GEÇMİŞ YILLAR KÂRLARI"),
    ("580", "GEÇMİŞ YILLAR ZARARLARI (-)"), ("590", "DÖNEM NET KÂRI"), ("591", "DÖNEM NET ZARARI (-)"),
    ("600", "YURTİÇİ SATIŞLAR"), ("601", "YURTDIŞI SATIŞLAR"), ("602", "DİĞER GELİRLER"),
    ("610", "SATIŞTAN İADELER (-)"), ("611", "SATIŞ İSKONTOLARI (-)"),
    ("621", "SATILAN TİCARİ MALLAR MALİYETİ (-)"),
    ("631", "PAZARLAMA, SATIŞ VE DAĞITIM GİDERLERİ (-)"), ("632", "GENEL YÖNETİM GİDERLERİ (-)"),
    ("642", "FAİZ GELİRLERİ"), ("646", "KAMBİYO KÂRLARI"), ("649", "DİĞER OLAĞAN GELİR VE KÂRLAR"),
    ("653", "KOMİSYON GİDERLERİ (-)"), ("656", "KAMBİYO ZARARLARI (-)"),
    ("659", "DİĞER OLAĞAN GİDER VE ZARARLAR (-)"), ("660", "KISA VADELİ BORÇLANMA GİDERLERİ (-)"),
    ("679", "DİĞER OLAĞANDIŞI GELİR VE KÂRLAR"), ("689", "DİĞER OLAĞANDIŞI GİDER VE ZARARLAR (-)"),
    ("690", "DÖNEM KÂRI VEYA ZARARI"), ("691", "DÖNEM KÂRI VERGİ VE DİĞER YASAL YÜKÜMLÜLÜK KARŞILIKLARI (-)"),
    ("692", "DÖNEM NET KÂRI VEYA ZARARI"),
    ("770", "GENEL YÖNETİM GİDERLERİ"), ("760", "PAZARLAMA, SATIŞ VE DAĞITIM GİDERLERİ"),
    ("780", "FİNANSMAN GİDERLERİ"),
]


def _f(v, d=0.0):
    try:
        return float(v or d)
    except Exception:
        return d


# ══════════════════════════ VERİ KATMANI ══════════════════════════════

def edf_hesap_plani():
    """Hesap planı (kod sıralı). Tablo yoksa boş liste."""
    try:
        r = get_client().table("edefter_hesap_plani").select("*").order("kod").execute()
        return r.data or []
    except Exception:
        return []


def edf_hesap_ekle(kod, ad):
    """Hesap planına hesap ekler. kod: '100' (ana) veya '100.01' (alt)."""
    kod = str(kod or "").strip()
    ad = str(ad or "").strip().upper()
    if not kod or not ad:
        return False, "Kod ve ad zorunlu."
    _p = kod.split(".")
    if not (_p[0].isdigit() and len(_p[0]) == 3) or any(not x.isdigit() for x in _p[1:]):
        return False, "Kod formatı: 100 (ana) ya da 100.01 (alt hesap)."
    try:
        _var = get_client().table("edefter_hesap_plani").select("kod").eq("kod", kod).execute()
        if _var.data:
            return False, f"{kod} zaten tanımlı."
        get_client().table("edefter_hesap_plani").insert({"kod": kod, "ad": ad}).execute()
        return True, f"✅ {kod} — {ad} eklendi."
    except Exception as e:
        return False, f"❌ {str(e)[:150]}"


def edf_plan_seed():
    """Tekdüzen ana hesaplarını yükler (yalnız eksik olanları)."""
    try:
        mevcut = {h["kod"] for h in edf_hesap_plani()}
        yeni = [{"kod": k, "ad": a} for k, a in THP_ANA_HESAPLAR if k not in mevcut]
        if yeni:
            get_client().table("edefter_hesap_plani").insert(yeni).execute()
        return True, f"✅ {len(yeni)} hesap yüklendi ({len(mevcut)} zaten vardı)."
    except Exception as e:
        return False, f"❌ {str(e)[:150]}"


def _sonraki_madde_no(yil):
    """Yevmiye madde numarası: yıl içinde 1'den başlar, kesintisiz artar
    (GİB entryNumberCounter mantığı)."""
    try:
        r = (get_client().table("edefter_fisler").select("yevmiye_madde_no")
             .gte("tarih", f"{yil}-01-01").lte("tarih", f"{yil}-12-31")
             .order("yevmiye_madde_no", desc=True).limit(1).execute())
        if r.data:
            return int(r.data[0].get("yevmiye_madde_no") or 0) + 1
    except Exception:
        pass
    return 1


def edf_fis_dogrula(satirlar):
    """Fiş satırlarını doğrular. Döner: (ok, mesaj, temiz_satirlar, toplam)."""
    temiz = []
    for i, s in enumerate(satirlar or [], 1):
        kod = str(s.get("hesap_kodu") or "").strip()
        borc = round(_f(s.get("borc")), 2)
        alacak = round(_f(s.get("alacak")), 2)
        if not kod and borc == 0 and alacak == 0:
            continue  # boş satır
        if not kod:
            return False, f"{i}. satır: hesap kodu boş.", [], 0.0
        if borc < 0 or alacak < 0:
            return False, f"{i}. satır: negatif tutar olamaz.", [], 0.0
        if borc > 0 and alacak > 0:
            return False, f"{i}. satır: bir satırda HEM borç HEM alacak olamaz.", [], 0.0
        if borc == 0 and alacak == 0:
            return False, f"{i}. satır ({kod}): tutar girilmemiş.", [], 0.0
        temiz.append({"hesap_kodu": kod,
                      "hesap_adi": str(s.get("hesap_adi") or "").strip(),
                      "aciklama": str(s.get("aciklama") or "").strip(),
                      "borc": borc, "alacak": alacak})
    if len(temiz) < 2:
        return False, "Fişte en az 2 dolu satır olmalı (çift taraflı kayıt).", [], 0.0
    t_borc = round(sum(x["borc"] for x in temiz), 2)
    t_alacak = round(sum(x["alacak"] for x in temiz), 2)
    if t_borc != t_alacak:
        return False, (f"DENGE YOK: borç {t_borc:,.2f} ≠ alacak {t_alacak:,.2f} "
                       f"(fark {abs(t_borc - t_alacak):,.2f}). Yevmiye maddesi dengede olmalı."), [], 0.0
    if t_borc == 0:
        return False, "Fiş toplamı 0 olamaz.", [], 0.0
    return True, "", temiz, t_borc


def edf_fis_ekle(tarih, tur, aciklama, belge_no, satirlar, personel=""):
    """Muhasebe fişi ekler (yevmiye maddesi). Borç=alacak dengesi zorunlu.
    Yarım kayıt oluşmaz: satırlar yazılamazsa fiş geri alınır."""
    ok, msg, temiz, toplam = edf_fis_dogrula(satirlar)
    if not ok:
        return False, "❌ " + msg, None
    try:
        sb = get_client()
        _t = str(tarih)[:10]
        _yil = _t[:4]
        madde_no = _sonraki_madde_no(_yil)
        fis = {"tarih": _t, "tur": tur or "Mahsup",
               "aciklama": str(aciklama or "").strip(),
               "belge_no": str(belge_no or "").strip(),
               "yevmiye_madde_no": madde_no, "toplam": toplam,
               "personel": personel or "", "kilitli": False}
        r = sb.table("edefter_fisler").insert(fis).execute()
        fid = r.data[0]["id"] if r.data else None
        if not fid:
            return False, "❌ Fiş oluşturulamadı.", None
        rows = [dict(s, fis_id=fid, sira=i + 1) for i, s in enumerate(temiz)]
        try:
            sb.table("edefter_fis_satirlari").insert(rows).execute()
        except Exception as ke:
            sb.table("edefter_fisler").delete().eq("id", fid).execute()
            return False, f"❌ Satırlar yazılamadı, fiş geri alındı: {str(ke)[:120]}", None
        return True, f"✅ Fiş kaydedildi — Yevmiye Madde No: {madde_no} · {toplam:,.2f} ₺", madde_no
    except Exception as e:
        return False, f"❌ {type(e).__name__}: {str(e)[:150]}", None


def edf_fis_sil(fis_id):
    """Fişi ve satırlarını siler (kilitli fiş silinemez)."""
    try:
        sb = get_client()
        r = sb.table("edefter_fisler").select("kilitli").eq("id", fis_id).execute()
        if r.data and r.data[0].get("kilitli"):
            return False, "🔒 Kilitli fiş silinemez (dönem kapanmış)."
        sb.table("edefter_fis_satirlari").delete().eq("fis_id", fis_id).execute()
        sb.table("edefter_fisler").delete().eq("id", fis_id).execute()
        return True, "✅ Fiş silindi."
    except Exception as e:
        return False, f"❌ {str(e)[:150]}"


def edf_get_fisler(bas=None, bit=None):
    """Dönem fişleri (madde no sıralı) + satırları."""
    try:
        sb = get_client()
        q = sb.table("edefter_fisler").select("*")
        if bas:
            q = q.gte("tarih", str(bas)[:10])
        if bit:
            q = q.lte("tarih", str(bit)[:10])
        fisler = (q.order("yevmiye_madde_no").execute()).data or []
        if not fisler:
            return []
        ids = [f["id"] for f in fisler]
        sat = []
        for i in range(0, len(ids), 100):
            r = (sb.table("edefter_fis_satirlari").select("*")
                 .in_("fis_id", ids[i:i + 100]).order("sira").execute())
            sat.extend(r.data or [])
        by_fis = {}
        for s in sat:
            by_fis.setdefault(s["fis_id"], []).append(s)
        for f in fisler:
            f["satirlar"] = by_fis.get(f["id"], [])
        return fisler
    except Exception:
        return []


def edf_mizan(bas=None, bit=None):
    """Mizan: hesap bazında toplam borç/alacak + bakiye. Döner (satirlar, denge_ok)."""
    fisler = edf_get_fisler(bas, bit)
    agg = {}
    for f in fisler:
        for s in f.get("satirlar", []):
            k = str(s.get("hesap_kodu") or "")
            o = agg.setdefault(k, {"hesap_adi": s.get("hesap_adi") or "", "borc": 0.0, "alacak": 0.0})
            o["borc"] = round(o["borc"] + _f(s.get("borc")), 2)
            o["alacak"] = round(o["alacak"] + _f(s.get("alacak")), 2)
            if not o["hesap_adi"] and s.get("hesap_adi"):
                o["hesap_adi"] = s["hesap_adi"]
    rows = []
    for kod in sorted(agg):
        o = agg[kod]
        fark = round(o["borc"] - o["alacak"], 2)
        rows.append({"Hesap Kodu": kod, "Hesap Adı": o["hesap_adi"],
                     "Borç": o["borc"], "Alacak": o["alacak"],
                     "Borç Bakiyesi": fark if fark > 0 else 0.0,
                     "Alacak Bakiyesi": -fark if fark < 0 else 0.0})
    t_borc = round(sum(r["Borç"] for r in rows), 2)
    t_alacak = round(sum(r["Alacak"] for r in rows), 2)
    return rows, (t_borc == t_alacak), t_borc, t_alacak


def edf_kebir(hesap_kodu, bas=None, bit=None):
    """Defter-i kebir: bir hesabın hareketleri + yürüyen bakiye."""
    fisler = edf_get_fisler(bas, bit)
    rows, bakiye = [], 0.0
    for f in fisler:
        for s in f.get("satirlar", []):
            if str(s.get("hesap_kodu")) != str(hesap_kodu):
                continue
            b, a = _f(s.get("borc")), _f(s.get("alacak"))
            bakiye = round(bakiye + b - a, 2)
            rows.append({"Tarih": f.get("tarih"), "Madde No": f.get("yevmiye_madde_no"),
                         "Fiş Açıklama": f.get("aciklama") or "",
                         "Satır Açıklama": s.get("aciklama") or "",
                         "Borç": b, "Alacak": a, "Bakiye": bakiye})
    return rows


# ══════════════════════════ ARAYÜZ ═════════════════════════════════════

def _uyari_banner():
    st.markdown(
        '<div style="background:rgba(251,146,60,0.08);border:1px solid rgba(251,146,60,0.35);'
        'border-radius:10px;padding:10px 14px;margin:4px 0 14px;font-size:12.5px;color:#FDBA74">'
        '🚧 <b>Faz 1 — Çift Taraflı Kayıt Çekirdeği (aktif)</b> · GİB uyumluluk onayı '
        'alınana kadar buradaki kayıtlar <b>yasal defter yerine geçmez</b>; iç kontrol '
        've e-Defter hazırlık amaçlıdır. Sıradaki fazlar: XBRL-GL üretimi → mali mühür → GİB testleri.'
        '</div>', unsafe_allow_html=True)


def render():
    st.markdown('<div class="baslik"><span class="baslik-ikon">📚</span>e-Defter (Genel Muhasebe)</div>',
                unsafe_allow_html=True)
    st.markdown('<div class="alt-baslik">Faz 1: hesap planı · muhasebe fişi · yevmiye · kebir · mizan</div>',
                unsafe_allow_html=True)
    _uyari_banner()

    plan = edf_hesap_plani()
    plan_map = {h["kod"]: h["ad"] for h in plan}

    tab_fis, tab_yev, tab_keb, tab_miz, tab_plan = st.tabs(
        ["🧾 Fiş Girişi", "📒 Yevmiye", "📖 Kebir", "⚖️ Mizan", "🗂 Hesap Planı"])

    # ── 🗂 HESAP PLANI ──
    with tab_plan:
        if not plan:
            st.info("Hesap planı boş. Tekdüzen ana hesapları tek tıkla yükleyebilirsin.")
        c1, c2 = st.columns([1, 2])
        if c1.button("📥 Tekdüzen Ana Hesapları Yükle", use_container_width=True, key="edf_seed"):
            ok, msg = edf_plan_seed()
            (st.success if ok else st.error)(msg)
            if ok:
                st.rerun()
        with c2.expander("➕ Hesap ekle (ana / alt)"):
            e1, e2, e3 = st.columns([1, 2, 1])
            _kod = e1.text_input("Kod", key="edf_hk", placeholder="100.01")
            _ad = e2.text_input("Ad", key="edf_ha", placeholder="MERKEZ KASA TL")
            e3.markdown('<div style="height:28px"></div>', unsafe_allow_html=True)
            if e3.button("Ekle", use_container_width=True, key="edf_hekle"):
                ok, msg = edf_hesap_ekle(_kod, _ad)
                (st.success if ok else st.error)(msg)
                if ok:
                    st.rerun()
        if plan:
            _pdf = pd.DataFrame([{"Kod": h["kod"], "Hesap Adı": h["ad"]} for h in plan])
            st.dataframe(_pdf, hide_index=True, use_container_width=True,
                         height=min(60 + len(_pdf) * 35, 520))

    # ── 🧾 FİŞ GİRİŞİ ──
    with tab_fis:
        if not plan:
            st.warning("Önce **Hesap Planı** sekmesinden Tekdüzen hesaplarını yükle.")
        f1, f2, f3, f4 = st.columns([1, 1, 2, 1])
        fis_tarih = f1.date_input("Tarih", value=date.today(), key="edf_ft")
        fis_tur = f2.selectbox("Fiş Türü", FIS_TURLERI, key="edf_ftur")
        fis_acik = f3.text_input("Fiş Açıklaması", key="edf_facik",
                                 placeholder="örn. Temmuz kira ödemesi")
        fis_belge = f4.text_input("Belge No", key="edf_fbelge", placeholder="ops.")

        _hesap_opts = [f"{k} — {a}" for k, a in sorted(plan_map.items())]
        _bos = pd.DataFrame([{"Hesap": None, "Açıklama": "", "Borç": 0.0, "Alacak": 0.0}
                             for _ in range(4)])
        _kdf = st.data_editor(
            _bos, num_rows="dynamic", use_container_width=True, key="edf_fis_kdf",
            column_config={
                "Hesap": st.column_config.SelectboxColumn("Hesap", options=_hesap_opts,
                                                          required=False, width="large"),
                "Açıklama": st.column_config.TextColumn("Satır Açıklaması"),
                "Borç": st.column_config.NumberColumn("Borç", min_value=0.0, step=0.01, format="%.2f"),
                "Alacak": st.column_config.NumberColumn("Alacak", min_value=0.0, step=0.01, format="%.2f"),
            })

        # canlı denge göstergesi
        _tb = round(sum(_f(r.get("Borç")) for _, r in _kdf.iterrows()), 2)
        _ta = round(sum(_f(r.get("Alacak")) for _, r in _kdf.iterrows()), 2)
        _fark = round(_tb - _ta, 2)
        metrik_satiri([
            {"label": "Toplam Borç", "value": f"{_tb:,.2f}", "renk": "#60A5FA"},
            {"label": "Toplam Alacak", "value": f"{_ta:,.2f}", "renk": "#34D399"},
            {"label": "Fark", "value": f"{_fark:,.2f}",
             "renk": "#34D399" if _fark == 0 and _tb > 0 else "#F87171",
             "alt": "✓ dengede" if _fark == 0 and _tb > 0 else "borç = alacak olmalı"},
        ])

        if st.button("💾 Fişi Kaydet", type="primary", use_container_width=True,
                     key="edf_fkaydet", disabled=not plan):
            satirlar = []
            for _, r in _kdf.iterrows():
                _h = str(r.get("Hesap") or "")
                kod = _h.split(" — ")[0].strip() if _h else ""
                satirlar.append({"hesap_kodu": kod,
                                 "hesap_adi": plan_map.get(kod, ""),
                                 "aciklama": str(r.get("Açıklama") or ""),
                                 "borc": _f(r.get("Borç")), "alacak": _f(r.get("Alacak"))})
            ok, msg, madde = edf_fis_ekle(fis_tarih, fis_tur, fis_acik, fis_belge, satirlar,
                                          personel=st.session_state.get("aktif_kullanici", ""))
            if ok:
                st.session_state.pop("edf_fis_kdf", None)
                st.success(msg)
                st.rerun()
            else:
                st.error(msg)

    # ── 📒 YEVMİYE ──
    with tab_yev:
        y1, y2 = st.columns(2)
        _yb = y1.date_input("Başlangıç", value=date.today().replace(day=1), key="edf_yb")
        _ye = y2.date_input("Bitiş", value=date.today(), key="edf_ye")
        fisler = edf_get_fisler(_yb, _ye)
        if not fisler:
            st.info("Bu dönemde fiş yok.")
        else:
            t_top = round(sum(_f(f.get("toplam")) for f in fisler), 2)
            metrik_satiri([
                {"label": "Madde Sayısı", "value": f"{len(fisler):,}", "renk": "#818CF8"},
                {"label": "Dönem Toplamı (borç=alacak)", "value": f"{t_top:,.2f}", "renk": "#34D399"},
            ])
            for f in fisler:
                with st.expander(f"Madde {f['yevmiye_madde_no']} · {str(f.get('tarih'))[:10]} · "
                                 f"{f.get('tur')} · {f.get('aciklama') or '—'} · {_f(f.get('toplam')):,.2f}"):
                    _sdf = pd.DataFrame([{
                        "Hesap": f"{s.get('hesap_kodu')} — {s.get('hesap_adi') or ''}",
                        "Açıklama": s.get("aciklama") or "",
                        "Borç": _f(s.get("borc")), "Alacak": _f(s.get("alacak")),
                    } for s in f.get("satirlar", [])])
                    st.dataframe(_sdf, hide_index=True, use_container_width=True,
                                 height=min(60 + len(_sdf) * 35, 300))
                    if st.button("🗑 Fişi Sil", key=f"edf_sil_{f['id']}"):
                        ok, msg = edf_fis_sil(f["id"])
                        (st.success if ok else st.error)(msg)
                        if ok:
                            st.rerun()

    # ── 📖 KEBİR ──
    with tab_keb:
        if not plan:
            st.info("Önce hesap planını yükle.")
        else:
            k1, k2, k3 = st.columns([2, 1, 1])
            _ksec = k1.selectbox("Hesap", [f"{k} — {a}" for k, a in sorted(plan_map.items())],
                                 key="edf_khesap")
            _kb = k2.date_input("Başlangıç", value=date.today().replace(month=1, day=1), key="edf_kb")
            _ke = k3.date_input("Bitiş", value=date.today(), key="edf_ke")
            _kod = _ksec.split(" — ")[0]
            rows = edf_kebir(_kod, _kb, _ke)
            if not rows:
                st.info("Bu hesapta hareket yok.")
            else:
                _kdf2 = pd.DataFrame(rows)
                son_bakiye = rows[-1]["Bakiye"]
                metrik_satiri([
                    {"label": "Hareket", "value": f"{len(rows):,}", "renk": "#818CF8"},
                    {"label": "Toplam Borç", "value": f"{sum(r['Borç'] for r in rows):,.2f}", "renk": "#60A5FA"},
                    {"label": "Toplam Alacak", "value": f"{sum(r['Alacak'] for r in rows):,.2f}", "renk": "#34D399"},
                    {"label": "Bakiye", "value": f"{son_bakiye:,.2f}",
                     "renk": "#34D399" if son_bakiye >= 0 else "#F87171",
                     "alt": "borç bakiyesi" if son_bakiye >= 0 else "alacak bakiyesi"},
                ])
                st.dataframe(_kdf2, hide_index=True, use_container_width=True,
                             height=min(60 + len(_kdf2) * 35, 520))

    # ── ⚖️ MİZAN ──
    with tab_miz:
        m1, m2 = st.columns(2)
        _mb = m1.date_input("Başlangıç", value=date.today().replace(month=1, day=1), key="edf_mb")
        _me = m2.date_input("Bitiş", value=date.today(), key="edf_me")
        rows, denge, t_borc, t_alacak = edf_mizan(_mb, _me)
        if not rows:
            st.info("Bu dönemde kayıt yok.")
        else:
            metrik_satiri([
                {"label": "Toplam Borç", "value": f"{t_borc:,.2f}", "renk": "#60A5FA"},
                {"label": "Toplam Alacak", "value": f"{t_alacak:,.2f}", "renk": "#34D399"},
                {"label": "Denge", "value": "✓ DENGEDE" if denge else "✗ DENGESİZ",
                 "renk": "#34D399" if denge else "#F87171",
                 "alt": "borç = alacak" if denge else f"fark {abs(t_borc - t_alacak):,.2f}"},
                {"label": "Hesap Sayısı", "value": f"{len(rows):,}", "renk": "#818CF8"},
            ])
            _mdf = pd.DataFrame(rows)
            st.dataframe(_mdf, hide_index=True, use_container_width=True,
                         height=min(60 + len(_mdf) * 35, 560),
                         column_config={c: st.column_config.NumberColumn(c, format="%.2f")
                                        for c in ["Borç", "Alacak", "Borç Bakiyesi", "Alacak Bakiyesi"]})
            st.download_button("⬇️ Mizan CSV",
                               _mdf.to_csv(index=False).encode("utf-8-sig"),
                               "mizan.csv", "text/csv", key="edf_mizan_csv")
