# -*- coding: utf-8 -*-
"""İşlem göstergesi — sayfa yüklenirken ve kayıt sürerken görünür işaret (Ekim 2026).

Sorun: yavaş açılan sayfa (Stok yaşı) birkaç saniye boş görünüyor, kullanıcı çıkıyordu; kayıt
düğmesine basan kullanıcı işlem bitmeden sayfayı kapatıyor, sipariş kaydolmuyordu. Üstteki 2 px
çizgi gözden kaçıyordu.

Tek bileşen, app.py'de bir kez çizilir; düğme düğme kod gerekmez. Streamlit çalışırken uygulama
köküne data-test-script-state="running" yazar; bileşen bunu izler:
  • Düğmeye basınca ya da dosya seçince başlayan çalışma = İŞLEM: kapsül hemen çıkar
    ("İşlem sürüyor — lütfen sayfayı kapatma"), sürerken sekme kapatılır / yenilenirse tarayıcı
    "ayrılmak istiyor musun?" diye sorar; bitince 2 sn "İşlem tamamlandı". Kayıttan sonra gelen
    st.rerun aynı işlemin devamı sayılır (kısa ara verip yeniden başlarsa bitmiş sayılmaz).
  • Diğer çalışmalar (sayfa açılışı, filtre) = YÜKLEME: yarım saniyeden uzun sürerse "Yükleniyor…"
    kapsülü; kısa tıklamalarda hiçbir şey görünmez (eski kapsül her onay kutusunda çıkıyordu).
    Sayfadan ayrılma uyarısı YÜKLEMEDE çıkmaz (kullanıcı kararı, seçenek A).
"""
import streamlit as st

YUKLEME_GECIKME_MS = 500      # bundan kısa sürenler için kapsül çıkmaz
ISLEM_ARA_MS = 600            # işlem bitince bu kadar bekle: st.rerun gelirse aynı işlem
TAMAM_SURE_MS = 2000

METIN = {"islem": "İşlem sürüyor — lütfen sayfayı kapatma",
         "yukleme": "Yükleniyor…",
         "tamam": "İşlem tamamlandı"}

# Düğme sayılan öğeler: işlem başlatan her şey (kaydet, sil, içe aktar, form gönder) ve dosya seçimi.
# İndirme düğmesi sunucuda işlem başlatmaz, sayılmaz.
DUGME_SECICI = ('[data-testid="stButton"] button, [data-testid="stFormSubmitButton"] button, '
                '[data-testid="stBaseButton-primary"], [data-testid="stBaseButton-secondary"]')

_JS = """
export default function(component) {
  if (window.__kayranIslem) return;              // tek kurulum (her çalıştırmada yeniden çizilir)
  const A = __AYAR__;
  const S = {mod: null, bekleyen: 0, t: null, bitis: null};
  window.__kayranIslem = S;
  const host = document.createElement('div');
  host.setAttribute('data-kayran-islem', '');
  const kok = host.attachShadow({mode: 'open'});
  kok.innerHTML = `<style>
    .k{position:fixed;top:12px;left:50%;transform:translate(-50%,-8px);z-index:1000000;opacity:0;
       pointer-events:none;transition:opacity .18s ease,transform .18s ease;display:flex;align-items:center;gap:10px;
       padding:9px 18px;border-radius:999px;font:600 13px/1.2 Inter,system-ui,sans-serif;white-space:nowrap;
       background:var(--k-yuzey1,#0F172A);color:var(--k-metin,#E2E8F0);
       border:1px solid color-mix(in srgb,var(--k-mor,#818CF8) 60%,transparent);
       box-shadow:0 8px 28px rgba(0,0,0,.35)}
    .k.acik{opacity:1;transform:translate(-50%,0)}
    .k.islem{border-color:var(--k-amber,#FBBF24)}
    .k.tamam{border-color:var(--k-yesil,#34D399);color:var(--k-yesil,#34D399)}
    .d{width:14px;height:14px;border-radius:50%;border:2px solid currentColor;border-right-color:transparent;
       animation:don .8s linear infinite}
    .k.tamam .d{animation:none;border:0;width:auto;height:auto}
    .k.tamam .d::before{content:"✓";font-weight:800}
    @keyframes don{to{transform:rotate(360deg)}}
  </style><div class="k" role="status" aria-live="polite"><span class="d"></span><span class="m"></span></div>`;
  document.body.appendChild(host);
  const k = kok.querySelector('.k'), m = kok.querySelector('.m');

  function goster(tur) {
    k.className = 'k acik ' + tur; m.textContent = A.metin[tur];
  }
  function gizle() { k.className = 'k'; }
  function ayrilma(e) { e.preventDefault(); e.returnValue = ''; return ''; }
  function korumaAc() { window.addEventListener('beforeunload', ayrilma); }
  function korumaKapat() { window.removeEventListener('beforeunload', ayrilma); }

  document.addEventListener('click', (e) => {
    if (e.target && e.target.closest && e.target.closest(A.dugme)) S.bekleyen = Date.now();
  }, true);
  document.addEventListener('change', (e) => {
    if (e.target && e.target.type === 'file') S.bekleyen = Date.now();
  }, true);

  function basladi() {
    clearTimeout(S.t);
    if (S.bitis) { clearTimeout(S.bitis); S.bitis = null; S.mod = 'islem'; goster('islem'); return; }
    if (Date.now() - S.bekleyen < 3000) {
      S.mod = 'islem'; S.bekleyen = 0; goster('islem'); korumaAc();
    } else {
      S.mod = 'yukleme';
      S.t = setTimeout(() => { if (S.mod === 'yukleme') goster('yukleme'); }, A.gecikme);
    }
  }
  function bitti() {
    clearTimeout(S.t);
    if (S.mod === 'islem') {
      S.bitis = setTimeout(() => {          // kısa arada yeniden başlarsa (st.rerun) aynı işlem
        S.bitis = null; S.mod = null; korumaKapat(); goster('tamam');
        S.t = setTimeout(gizle, A.tamam);
      }, A.ara);
    } else { S.mod = null; gizle(); }
  }
  let calisiyor = false;
  function kontrol() {
    const app = document.querySelector('[data-testid="stApp"]');
    const simdi = !!app && app.getAttribute('data-test-script-state') === 'running';
    if (simdi !== calisiyor) { calisiyor = simdi; simdi ? basladi() : bitti(); }
  }
  new MutationObserver(kontrol).observe(document.documentElement,
    {subtree: true, attributes: true, attributeFilter: ['data-test-script-state']});
  kontrol();
}
"""


def _js():
    import json
    ayar = {"metin": METIN, "dugme": DUGME_SECICI, "gecikme": YUKLEME_GECIKME_MS, "ara": ISLEM_ARA_MS,
            "tamam": TAMAM_SURE_MS}
    return _JS.replace("__AYAR__", json.dumps(ayar, ensure_ascii=False))


_BILESEN = None


def _bilesen():
    global _BILESEN
    if _BILESEN is None:
        import streamlit.components.v2 as _v2
        _BILESEN = _v2.component("kayran_islem", js=_js())
    return _BILESEN


def kur():
    """app.py her çalıştırmada bir kez çağırır. Bileşen kurulamazsa sessiz geçer (gösterge yok,
    uygulama çalışır)."""
    try:
        _bilesen()(key="kayran_islem_gostergesi")
    except Exception:  # noqa: BLE001
        pass


def bekle(metin):
    """Ağır hesap için açıklamalı bekleme yazısı (boş ekran yerine)."""
    return st.spinner(metin, show_time=True)
