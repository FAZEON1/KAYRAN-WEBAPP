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

    tab_fis, tab_yev, tab_keb, tab_miz, tab_plan, tab_xml, tab_ayar = st.tabs(
        ["🧾 Fiş Girişi", "📒 Yevmiye", "📖 Kebir", "⚖️ Mizan", "🗂 Hesap Planı",
         "📤 e-Defter XML", "⚙️ Kurum Ayarları"])

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

    # ── 📤 e-DEFTER XML (Yevmiye üretimi) ──
    with tab_xml:
        _render_edefter_xml()

    # ── ⚙️ KURUM AYARLARI ──
    with tab_ayar:
        _render_kurum_ayarlari()


# ══════════════════════════════════════════════════════════════════════
# FAZ 2a — KURUM AYARLARI + YEVMİYE (Y) XBRL-GL ÜRETİCİSİ
# GİB e-Defter Paketi örnek Y dosyasıyla alan-alan ve sıra-sıra eşleşir.
# Şema sırası XSD'de zorunlu olduğundan alan sırası birebir korunmalıdır.
# ══════════════════════════════════════════════════════════════════════

EDEFTER_NS = {
    "edefter": "http://www.edefter.gov.tr",
    "xbrli": "http://www.xbrl.org/2003/instance",
    "gl-cor": "http://www.xbrl.org/int/gl/cor/2006-10-25",
    "gl-bus": "http://www.xbrl.org/int/gl/bus/2006-10-25",
    "gl-plt": "http://www.xbrl.org/int/gl/plt/2006-10-25",
    "iso4217": "http://www.xbrl.org/2003/iso4217",
    "iso639": "http://www.xbrl.org/2005/iso639",
    "link": "http://www.xbrl.org/2003/linkbase",
    "xlink": "http://www.w3.org/1999/xlink",
    "ds": "http://www.w3.org/2000/09/xmldsig#",
    "xades": "http://uri.etsi.org/01903/v1.3.2#",
    "xsi": "http://www.w3.org/2001/XMLSchema-instance",
}

# Kurum kimlik ayarları — tek satırlık kayıt (id=1). entityInformation'ı besler.
EDEFTER_AYAR_ALANLAR = [
    "vkn", "unvan", "telefon", "faks", "eposta",
    "adres_bina", "adres_cadde", "adres_cadde2", "adres_il", "adres_posta", "adres_ulke",
    "website", "nace_kodu", "mali_yil_baslangic", "mali_yil_bitis",
    "smmm_ad", "smmm_bina", "smmm_cadde", "smmm_il",
    "program_ad", "program_versiyon", "sube_kodu",
]


def edf_ayar_getir():
    """Kurum ayarlarını döndürür (tek kayıt). Yoksa boş sözlük."""
    try:
        r = get_client().table("edefter_ayarlar").select("*").eq("id", 1).execute()
        return (r.data[0] if r.data else {}) or {}
    except Exception:
        return {}


def edf_ayar_kaydet(data):
    """Kurum ayarlarını upsert eder (id=1)."""
    try:
        _p = {k: (str(data.get(k) or "").strip()) for k in EDEFTER_AYAR_ALANLAR}
        _p["id"] = 1
        try:
            get_client().table("edefter_ayarlar").upsert(_p, on_conflict="id").execute()
        except Exception:
            # upsert yoksa: sil + ekle
            try:
                get_client().table("edefter_ayarlar").delete().eq("id", 1).execute()
            except Exception:
                pass
            get_client().table("edefter_ayarlar").insert(_p).execute()
        return True, "✅ Kurum ayarları kaydedildi."
    except Exception as e:
        return False, f"❌ {str(e)[:150]}"


def edf_ayar_eksikler(ayar):
    """XML üretimi için zorunlu alanların eksik olanlarını döndürür."""
    zorunlu = {
        "vkn": "VKN/TCKN", "unvan": "Unvan", "adres_il": "İl",
        "nace_kodu": "NACE (faaliyet) kodu",
        "mali_yil_baslangic": "Mali yıl başlangıç", "mali_yil_bitis": "Mali yıl bitiş",
        "smmm_ad": "SMMM adı", "program_ad": "Program adı", "program_versiyon": "Program versiyonu",
    }
    return [ad for k, ad in zorunlu.items() if not str(ayar.get(k) or "").strip()]


def _sub(parent, tag, text=None, ctx="journal_context", **attr):
    """Namespace'li alt element ekler. tag: 'gl-cor:entryNumber' gibi."""
    from lxml import etree
    pre, local = tag.split(":")
    el = etree.SubElement(parent, f"{{{EDEFTER_NS[pre]}}}{local}")
    if ctx is not None:
        el.set("contextRef", ctx)
    for k, v in attr.items():
        el.set(k, str(v))
    if text is not None:
        el.text = str(text)
    return el


def _para(v):
    """Tutarı GİB formatına çevirir: tam sayıysa ondalıksız, değilse nokta ile."""
    v = round(float(v or 0), 2)
    return str(int(v)) if v == int(v) else f"{v:.2f}"


def edf_yevmiye_xml(yil, ay, parca=0):
    """Bir aya ait fişlerden GİB uyumlu Yevmiye (Y) XBRL-GL XML üretir.
    Döner: (ok, xml_bytes|mesaj, dosya_adi). Mali mühür imzası İÇERMEZ
    (Faz 3'te imzalanır) — imza yerine HashValue placeholder konur."""
    from lxml import etree
    ayar = edf_ayar_getir()
    eksik = edf_ayar_eksikler(ayar)
    if eksik:
        return False, "❌ Kurum Ayarları eksik: " + ", ".join(eksik), ""

    _ay = f"{int(ay):02d}"
    donem = f"{yil}{_ay}"
    bas = f"{yil}-{_ay}-01"
    # ayın son günü
    import calendar
    son = f"{yil}-{_ay}-{calendar.monthrange(int(yil), int(ay))[1]:02d}"
    fisler = edf_get_fisler(bas, son)
    if not fisler:
        return False, f"❌ {donem} döneminde fiş yok.", ""

    vkn = str(ayar["vkn"]).strip()
    E = lambda p: f"{{{EDEFTER_NS[p]}}}"

    # Kök
    root = etree.Element(E("edefter") + "defter", nsmap={
        "edefter": EDEFTER_NS["edefter"], "ds": EDEFTER_NS["ds"],
        "xades": EDEFTER_NS["xades"], "xsi": EDEFTER_NS["xsi"]})
    root.set(f"{E('xsi')}schemaLocation",
             "http://www.edefter.gov.tr ../xsd/edefter.xsd")

    xbrl = etree.SubElement(root, E("xbrli") + "xbrl", nsmap={
        "gl-bus": EDEFTER_NS["gl-bus"], "gl-cor": EDEFTER_NS["gl-cor"],
        "gl-plt": EDEFTER_NS["gl-plt"], "iso4217": EDEFTER_NS["iso4217"],
        "iso639": EDEFTER_NS["iso639"], "link": EDEFTER_NS["link"],
        "xbrli": EDEFTER_NS["xbrli"], "xlink": EDEFTER_NS["xlink"]})
    xbrl.set(f"{E('xsi')}schemaLocation",
             "http://www.xbrl.org/int/gl/plt/2006-10-25 "
             "../xsd/2006-10-25/plt/case-c-b/gl-plt-2006-10-25.xsd")

    sref = etree.SubElement(xbrl, E("link") + "schemaRef")
    sref.set(f"{E('xlink')}href", "../xsd/2006-10-25/plt/case-c-b/gl-plt-2006-10-25.xsd")
    sref.set(f"{E('xlink')}type", "simple")

    # context
    ctx = etree.SubElement(xbrl, E("xbrli") + "context", id="journal_context")
    ent = etree.SubElement(ctx, E("xbrli") + "entity")
    idf = etree.SubElement(ent, E("xbrli") + "identifier",
                           scheme="http://www.gib.gov.tr")
    idf.text = vkn
    per = etree.SubElement(ctx, E("xbrli") + "period")
    etree.SubElement(per, E("xbrli") + "instant").text = bas

    u1 = etree.SubElement(xbrl, E("xbrli") + "unit", id="try")
    etree.SubElement(u1, E("xbrli") + "measure").text = "iso4217:TRY"
    u2 = etree.SubElement(xbrl, E("xbrli") + "unit", id="countable")
    etree.SubElement(u2, E("xbrli") + "measure").text = "xbrli:pure"

    ae = etree.SubElement(xbrl, E("gl-cor") + "accountingEntries")

    # documentInfo
    di = etree.SubElement(ae, E("gl-cor") + "documentInfo")
    _sub(di, "gl-cor:entriesType", "journal")
    _sub(di, "gl-cor:uniqueID", EDEFTER_UNIQUEID_KALIBI.format(donem=donem, sira=parca + 1))
    _sub(di, "gl-cor:language", "iso639:tr")
    _sub(di, "gl-cor:creationDate", date.today().isoformat())
    _sub(di, "gl-bus:creator", ayar.get("smmm_ad") or ayar.get("unvan"))
    _sub(di, "gl-cor:entriesComment",
         f"{bas} - {son} arası {ayar['unvan']} yevmiye defteri.")
    _sub(di, "gl-cor:periodCoveredStart", bas)
    _sub(di, "gl-cor:periodCoveredEnd", son)
    _src = f"{vkn}##{ayar['unvan']}##{ayar['program_ad']}##{ayar['program_versiyon']}"
    _sub(di, "gl-bus:sourceApplication", _src)

    # entityInformation
    ei = etree.SubElement(ae, E("gl-cor") + "entityInformation")
    if ayar.get("telefon"):
        ph = etree.SubElement(ei, E("gl-bus") + "entityPhoneNumber")
        _sub(ph, "gl-bus:phoneNumberDescription", "main")
        _sub(ph, "gl-bus:phoneNumber", ayar["telefon"])
    if ayar.get("faks"):
        fx = etree.SubElement(ei, E("gl-bus") + "entityFaxNumberStructure")
        _sub(fx, "gl-bus:entityFaxNumber", ayar["faks"])
    if ayar.get("eposta"):
        em = etree.SubElement(ei, E("gl-bus") + "entityEmailAddressStructure")
        _sub(em, "gl-bus:entityEmailAddress", ayar["eposta"])
    oi = etree.SubElement(ei, E("gl-bus") + "organizationIdentifiers")
    _sub(oi, "gl-bus:organizationIdentifier", ayar["unvan"])
    # tüzel (10 hane) → "Kurum Unvanı", gerçek (11 hane) → "Adı Soyadı"
    _sub(oi, "gl-bus:organizationDescription",
         "Kurum Unvanı" if len(vkn) == 10 else "Adı Soyadı")
    oa = etree.SubElement(ei, E("gl-bus") + "organizationAddress")
    if ayar.get("adres_bina"):
        _sub(oa, "gl-bus:organizationBuildingNumber", ayar["adres_bina"])
    if ayar.get("adres_cadde"):
        _sub(oa, "gl-bus:organizationAddressStreet", ayar["adres_cadde"])
    if ayar.get("adres_cadde2"):
        _sub(oa, "gl-bus:organizationAddressStreet2", ayar["adres_cadde2"])
    _sub(oa, "gl-bus:organizationAddressCity", ayar["adres_il"])
    if ayar.get("adres_posta"):
        _sub(oa, "gl-bus:organizationAddressZipOrPostalCode", ayar["adres_posta"])
    _sub(oa, "gl-bus:organizationAddressCountry", ayar.get("adres_ulke") or "Türkiye")
    if ayar.get("website"):
        ws = etree.SubElement(ei, E("gl-bus") + "entityWebSite")
        _sub(ws, "gl-bus:webSiteURL", ayar["website"])
    _sub(ei, "gl-bus:businessDescription", ayar["nace_kodu"])
    _sub(ei, "gl-bus:fiscalYearStart", ayar["mali_yil_baslangic"])
    _sub(ei, "gl-bus:fiscalYearEnd", ayar["mali_yil_bitis"])
    ai = etree.SubElement(ei, E("gl-bus") + "accountantInformation")
    _sub(ai, "gl-bus:accountantName", ayar["smmm_ad"])
    aa = etree.SubElement(ai, E("gl-bus") + "accountantAddress")
    if ayar.get("smmm_bina"):
        _sub(aa, "gl-bus:accountantBuildingNumber", ayar["smmm_bina"])
    if ayar.get("smmm_cadde"):
        _sub(aa, "gl-bus:accountantStreet", ayar["smmm_cadde"])
    _sub(aa, "gl-bus:accountantCity", ayar.get("smmm_il") or ayar["adres_il"])

    # entryHeader'lar (her fiş = bir yevmiye maddesi)
    ln_counter = 0
    for f in fisler:
        eh = etree.SubElement(ae, E("gl-cor") + "entryHeader")
        _sub(eh, "gl-cor:enteredBy", f.get("personel") or ayar.get("smmm_ad") or "-")
        _sub(eh, "gl-cor:enteredDate", str(f.get("tarih"))[:10])
        _sub(eh, "gl-cor:entryNumber", f"{int(f.get('yevmiye_madde_no')):06d}")
        if f.get("aciklama"):
            _sub(eh, "gl-cor:entryComment", f.get("aciklama"))
        _sub(eh, "gl-bus:totalDebit", _para(f.get("toplam")),
             unitRef="try", decimals="INF")
        _sub(eh, "gl-bus:totalCredit", _para(f.get("toplam")),
             unitRef="try", decimals="INF")
        _sub(eh, "gl-cor:entryNumberCounter", str(int(f.get("yevmiye_madde_no"))),
             unitRef="countable", decimals="INF")

        for s in f.get("satirlar", []):
            ln_counter += 1
            ed = etree.SubElement(eh, E("gl-cor") + "entryDetail")
            _sub(ed, "gl-cor:lineNumber", str(s.get("sira")))
            _sub(ed, "gl-cor:lineNumberCounter", str(ln_counter),
                 unitRef="countable", decimals="INF")
            acc = etree.SubElement(ed, E("gl-cor") + "account")
            kod = str(s.get("hesap_kodu") or "")
            ana = kod.split(".")[0]
            _sub(acc, "gl-cor:accountMainID", ana)
            _sub(acc, "gl-cor:accountMainDescription", s.get("hesap_adi") or "")
            if "." in kod:
                asub = etree.SubElement(acc, E("gl-cor") + "accountSub")
                _sub(asub, "gl-cor:accountSubDescription", s.get("hesap_adi") or "")
                _sub(asub, "gl-cor:accountSubID", kod)
            borc = round(_f(s.get("borc")), 2)
            alacak = round(_f(s.get("alacak")), 2)
            tutar = borc if borc > 0 else alacak
            _sub(ed, "gl-cor:amount", _para(tutar), unitRef="try", decimals="INF")
            _sub(ed, "gl-cor:debitCreditCode", "D" if borc > 0 else "C")
            _sub(ed, "gl-cor:postingDate", str(f.get("tarih"))[:10])
            if f.get("belge_no"):
                _sub(ed, "gl-cor:documentReference", f.get("belge_no"))
            if s.get("aciklama"):
                _sub(ed, "gl-cor:detailComment", s.get("aciklama"))

    # İmza yerine HashValue (Faz 3'te mali mühürle değişecek).
    # Şema HashValue'yu namespace'SİZ bekler (ds:Signature'ın alternatifi).
    hv = etree.SubElement(root, "HashValue")
    hv.text = "FAZ3_MALI_MUHUR_ILE_IMZALANACAK"

    xml = etree.tostring(root, xml_declaration=True, encoding="UTF-8", pretty_print=True)
    # stylesheet PI ekle
    xml = b'<?xml version="1.0" encoding="UTF-8"?>\n<?xml-stylesheet type="text/xsl" href="yevmiye.xslt"?>\n' \
          + xml.split(b"\n", 1)[1]
    dosya_adi = EDEFTER_DOSYA_AD_KALIBI.format(vkn=vkn, donem=donem, tur="Y", parca=parca)
    return True, xml, dosya_adi


def _render_kurum_ayarlari():
    st.caption("e-Defter XML'lerine yazılacak kurum kimlik bilgileri. Bir kez doldur; "
               "her defter/berat bu bilgileri otomatik kullanır. ⚠️ **sourceApplication** "
               "unvanı, GİB'e vereceğin taahhütnamedeki unvanla **harfiyen aynı** olmalı.")
    a = edf_ayar_getir()
    with st.form("edf_ayar_form"):
        st.markdown("**Kurum Kimliği**")
        c1, c2 = st.columns(2)
        vkn = c1.text_input("VKN / TCKN *", a.get("vkn", ""), help="Tüzel 10 hane, gerçek kişi 11 hane")
        unvan = c2.text_input("Unvan *", a.get("unvan", ""))
        c3, c4, c5 = st.columns(3)
        telefon = c3.text_input("Telefon", a.get("telefon", ""))
        faks = c4.text_input("Faks", a.get("faks", ""))
        eposta = c5.text_input("E-posta", a.get("eposta", ""))
        website = st.text_input("Web sitesi", a.get("website", ""))
        nace = st.text_input("NACE (faaliyet) kodu *", a.get("nace_kodu", ""),
                             help="businessDescription alanı — örn. 46.51.01")

        st.markdown("**Adres**")
        b1, b2, b3 = st.columns(3)
        adres_bina = b1.text_input("Bina No", a.get("adres_bina", ""))
        adres_cadde = b2.text_input("Cadde/Sokak", a.get("adres_cadde", ""))
        adres_cadde2 = b3.text_input("Cadde/Sokak 2", a.get("adres_cadde2", ""))
        b4, b5, b6 = st.columns(3)
        adres_il = b4.text_input("İl *", a.get("adres_il", ""))
        adres_posta = b5.text_input("Posta Kodu", a.get("adres_posta", ""))
        adres_ulke = b6.text_input("Ülke", a.get("adres_ulke", "") or "Türkiye")

        st.markdown("**Mali Yıl**")
        d1, d2 = st.columns(2)
        _mb = a.get("mali_yil_baslangic", "") or f"{date.today().year}-01-01"
        _me = a.get("mali_yil_bitis", "") or f"{date.today().year}-12-31"
        mali_bas = d1.text_input("Başlangıç * (YYYY-AA-GG)", _mb)
        mali_bit = d2.text_input("Bitiş * (YYYY-AA-GG)", _me)

        st.markdown("**SMMM / Mali Müşavir**")
        e1, e2, e3 = st.columns(3)
        smmm_ad = e1.text_input("SMMM Adı *", a.get("smmm_ad", ""))
        smmm_bina = e2.text_input("SMMM Bina No", a.get("smmm_bina", ""))
        smmm_cadde = e3.text_input("SMMM Cadde", a.get("smmm_cadde", ""))
        smmm_il = st.text_input("SMMM İl", a.get("smmm_il", ""))

        st.markdown("**Yazılım Kimliği** (sourceApplication)")
        f1, f2, f3 = st.columns(3)
        prog_ad = f1.text_input("Program Adı *", a.get("program_ad", "") or "KAYRAN e-Defter")
        prog_ver = f2.text_input("Program Versiyonu *", a.get("program_versiyon", "") or "1.0")
        sube = f3.text_input("Şube Kodu (4 hane)", a.get("sube_kodu", ""),
                             help="Şubesiz ise boş bırak")

        if st.form_submit_button("💾 Kurum Ayarlarını Kaydet", type="primary",
                                 use_container_width=True):
            ok, msg = edf_ayar_kaydet({
                "vkn": vkn, "unvan": unvan, "telefon": telefon, "faks": faks, "eposta": eposta,
                "adres_bina": adres_bina, "adres_cadde": adres_cadde, "adres_cadde2": adres_cadde2,
                "adres_il": adres_il, "adres_posta": adres_posta, "adres_ulke": adres_ulke,
                "website": website, "nace_kodu": nace, "mali_yil_baslangic": mali_bas,
                "mali_yil_bitis": mali_bit, "smmm_ad": smmm_ad, "smmm_bina": smmm_bina,
                "smmm_cadde": smmm_cadde, "smmm_il": smmm_il, "program_ad": prog_ad,
                "program_versiyon": prog_ver, "sube_kodu": sube})
            (st.success if ok else st.error)(msg)


def _render_edefter_xml():
    st.caption("Bir aya ait fişlerden **Yevmiye Defteri (Y)** XBRL-GL XML'i üretir. "
               "Üretilen dosya GİB resmi şemasına (edefter.xsd) uygundur. "
               "⚠️ Mali mühür imzası içermez (Faz 3) — bu haliyle GİB'e yüklenemez, "
               "yapı/doğrulama testi ve önizleme amaçlıdır.")
    ayar = edf_ayar_getir()
    eksik = edf_ayar_eksikler(ayar)
    if eksik:
        st.warning("⚠️ Önce **⚙️ Kurum Ayarları** sekmesini doldur. Eksik: " + ", ".join(eksik))
        return

    c1, c2, c3 = st.columns([1, 1, 1])
    _yil = c1.number_input("Yıl", min_value=2015, max_value=2100,
                           value=date.today().year, step=1, key="edf_xml_yil")
    _ay = c2.selectbox("Ay", list(range(1, 13)),
                       index=date.today().month - 1, key="edf_xml_ay",
                       format_func=lambda m: f"{m:02d}")
    _parca = c3.number_input("Parça No", min_value=0, value=0, step=1, key="edf_xml_parca",
                             help="Defter bölünmediyse 0")

    if st.button("🔧 Yevmiye XML Üret", type="primary", use_container_width=True, key="edf_xml_uret"):
        ok, sonuc, ad = edf_yevmiye_xml(str(int(_yil)), str(int(_ay)), int(_parca))
        if not ok:
            st.error(sonuc)
        else:
            st.success(f"✅ Üretildi: `{ad}` ({len(sonuc):,} bayt)")
            # Özet
            fisler = edf_get_fisler(f"{int(_yil)}-{int(_ay):02d}-01",
                                    f"{int(_yil)}-{int(_ay):02d}-28")
            st.download_button("⬇️ Yevmiye XML İndir", sonuc, ad, "application/xml",
                               use_container_width=True, key="edf_xml_dl")
            with st.expander("👁 XML önizleme (ilk 3000 karakter)"):
                st.code(sonuc.decode("utf-8")[:3000], language="xml")
            st.caption("📁 GİB dizin yapısı: `VKN/hesap-dönemi/ay/` altında Y/K/YB/KB dosyaları "
                       "+ XSLT'ler. Kebir, berat ve paketleme sonraki adımlarda (Faz 2b-2e).")
