# ══════════════════════════════════════════════════════════════════════
# 📚 e-DEFTER MODÜLÜ — GİB Yazılım Uyumluluk Onayı standartlarına göre
# ══════════════════════════════════════════════════════════════════════
# DURUM: GELİŞTİRME AŞAMASI (pasif). Kullanıcılar yalnızca bilgilendirme
# ekranı görür. Altyapı, GİB "e-Defter Uygulaması Yazılım Uyumluluk Onayı"
# kılavuzu (v1.6) esas alınarak fazlar halinde bu modülde inşa edilecektir.
#
# Kaynak kılavuzdan çıkarılan ÇEKİRDEK STANDARTLAR aşağıda sabit olarak
# belgelenmiştir — gelecek fazlar bu sabitlere göre geliştirilecek.
# ══════════════════════════════════════════════════════════════════════

import streamlit as st

# ── GİB standartları (Yazılım Uyumluluk Onayı Kılavuzu v1.6) ─────────────

# e-Defter belge türleri: her test senaryosunda 4 belge gönderilir
EDEFTER_BELGE_TURLERI = {
    "Y":  "Yevmiye Defteri",
    "YB": "Yevmiye Defteri Beratı",
    "K":  "Büyük Defter (Defter-i Kebir)",
    "KB": "Büyük Defter Beratı",
}

# Dosya adlandırma: VKN-YYYYAA-TÜR-PARÇANO.xml
#   örn. 1234567890-201101-Y-000000.xml  (tek parça)
#        1234567890-201605-000001 / -000002 (çok parçalı defter bölme)
#   Berat GİB onayı dönüşünde "GIB-" önekiyle: GIB-VKN-YYYYAA-YB-000000.xml
EDEFTER_DOSYA_AD_KALIBI = "{vkn}-{donem}-{tur}-{parca:06d}.xml"
EDEFTER_GIB_ONEK = "GIB-"

# Kontrol numarası (uniqueID): YEV + YYYYAA + 6 haneli sıra → YEV201605000001
EDEFTER_UNIQUEID_KALIBI = "YEV{donem}{sira:06d}"

# Dizin yapısı: <kök>/VKN/<hesap dönemi: 01.01.YYYY-31.12.YYYY>/<ay: 01..12>/
#   Ay klasörü içeriği: Y/K/YB/KB xml'leri + GIB-...-YB/KB xml'leri
#   + berat.xslt, kebir.xslt, yevmiye.xslt (görüntüleme şablonları)
EDEFTER_XSLT_DOSYALARI = ("berat.xslt", "kebir.xslt", "yevmiye.xslt")

# XBRL-GL zorunlu bağlam alanları (kılavuz örneklerinden):
#   gl-bus:fiscalYearStart / fiscalYearEnd        → mali yıl başlangıç/bitiş
#   gl-cor:periodCoveredStart / periodCoveredEnd  → defter dönemi
#   gl-cor:lineNumber / lineNumberCounter         → yevmiye satır sayaçları
#   gl-cor:entryNumberCounter                     → yevmiye madde sayacı
#   gl-cor:uniqueID                               → kontrol numarası
# Tasfiye halinde: tasfiye tarihi itibarıyla dönem bölünür, sayaçlar 1'den
# başlar, dizinde iki ayrı hesap dönemi klasörü tutulur.

# Uyumluluk test senaryoları (7 senaryo — kılavuz 4.2/4.3 özetinden):
EDEFTER_TEST_SENARYOLARI = [
    "S1: 10-30 maddelik yevmiye · ≥10 çeşit ana hesap · alt hesaplı · zip ≤1MB",
    "S2: 100-1000 madde · kapanış işlemleri (Aralık) · ≥15 ana hesap · zip ≤2MB",
    "S3: 100-1000 madde · açılış işlemleri (Ocak) · ≥15 ana hesap · zip ≤2MB",
    "S4: 5000-10000 madde · ≥20 ana hesap türü · zip ≤10MB",
    "S5: 2 parçalı defter — ilk parça · ≥10 ana hesap · zip ≤10MB",
    "S6: 2 parçalı defter — ikinci/son parça · zip ≤10MB",
    "S7: Şubeli kebir + berat · dosya adı/içerik şube tutarlılığı · zip ≤1MB",
]

# Süreç: Test Aracı (edefter.gov.tr) → test planı → 7 senaryo × 4 adım
# (Y → YB → K → KB sırayla; önceki adım bitmeden sonrakine geçilemez) →
# "Başkanlığa İlet" → taahhütname + uyumluluk tanıtım raporu → onay/duyuru.


def render():
    """e-Defter sayfası — şimdilik pasif bilgilendirme ekranı."""
    st.markdown('<div class="baslik"><span class="baslik-ikon">📚</span>e-Defter (Genel Muhasebe)</div>',
                unsafe_allow_html=True)
    st.markdown('<div class="alt-baslik">GİB Yazılım Uyumluluk Onayı standartlarına göre geliştirilmektedir</div>',
                unsafe_allow_html=True)

    st.markdown(
        '<div style="background:linear-gradient(135deg,rgba(139,92,246,0.10),rgba(30,41,59,0.5));'
        'border:1px solid rgba(167,139,250,0.35);border-radius:16px;padding:28px 32px;margin:18px 0">'
        '<div style="font-size:34px;margin-bottom:10px">🚧</div>'
        '<div style="font-size:19px;font-weight:800;color:#E9D5FF;margin-bottom:10px">'
        'Bu modül geliştirme aşamasındadır</div>'
        '<div style="font-size:14px;color:#CBD5E1;line-height:1.75">'
        'e-Defter modülü, Gelir İdaresi Başkanlığı\'nın <b>e-Defter Uygulaması Yazılım '
        'Uyumluluk Onayı</b> kılavuzunda tanımlanan format ve standartlara '
        '(XBRL-GL yevmiye/kebir üretimi, berat dosyaları, GİB dosya adlandırma ve '
        'dizin yapısı, uyumluluk test senaryoları) uygun olarak inşa edilmektedir. '
        'Tamamlanıp GİB uyumluluk onay süreci sonuçlanana kadar bu ekran '
        '<b>bilgilendirme amaçlıdır</b>; herhangi bir yasal defter kaydı '
        'oluşturmaz.</div>'
        '<div style="margin-top:16px;font-size:12px;color:#94A3B8">'
        'Planlanan kapsam: Tekdüzen Hesap Planı · çift taraflı kayıt (yevmiye/kebir) · '
        'mizan · XBRL-GL e-Defter ve berat üretimi · GİB test senaryoları uyumu · '
        'mali mühür imzalama entegrasyonu</div>'
        '</div>',
        unsafe_allow_html=True)

    st.caption("ℹ️ Sorular ve öncelik talepleri için yönetici ile iletişime geçin. "
               "Bu ekran, modül aktif edilene kadar salt-okunur bilgilendirmedir.")
