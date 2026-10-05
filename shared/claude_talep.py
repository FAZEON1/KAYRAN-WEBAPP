# -*- coding: utf-8 -*-
"""Talepten Claude'a — onaylı geliştirme akışı (Ekim 2026, seçenek A: tek onay).

  1. Çalışan Talep Merkezi'nden talep gönderir (bugünkü gibi).
  2. Onaycı (İbrahim) talebi açar, isterse not yazar, "Claude'a gönder"e basar
     → claude_durum = 'onaylandi'. Onaysız talebe Claude dokunmaz.
  3. claude.ai'deki görev (rutin) en eski onaylı talebi üstlenir ('calisiyor'),
     otonom/claude_talep_gorevi.md'deki kurallarla kodlar, PR açar. "Claude'a gönder" rutini API ile
     ANINDA başlatır (rutini_tetikle; Streamlit secrets [claude_rutin] url + token); ayar yoksa ya da
     tetikleme tutmazsa saat başı çalışma yedektir. Rakam değiştiren ya da belirsiz işte kod yazmaz,
     soru yazar ('soru'); onaycı cevabı nota yazıp yeniden gönderir.
  4. PR açılınca / birleşince GitHub iş akışı (talep-pr.yml → otonom/talep_pr.py) durumu günceller
     ve mail atar: PR hazır → onaycıya; yayında → talep sahibine. PR'ı birleştirmek kullanıcıdadır.

PR başlığı "Talep #<id>: ..." biçimindedir; iş akışı talebi buradan bulur (oturum dalının adı
Claude oturumuna göre değişir, ona güvenilmez).
"""
import re

ONAYCILAR = {"ibrahim"}

CLAUDE_DURUM_AD = {
    "onaylandi": "Claude'a gönderildi",
    "calisiyor": "Claude çalışıyor",
    "soru": "Claude'un sorusu var",
    "pr_hazir": "PR hazır, onay bekliyor",
    "yayinda": "Yayında",
    "kapandi": "PR kapatıldı",
    "hata": "Claude tamamlayamadı",
}

# Bu durumlarda talep yeniden gönderilebilir (cevap / yeni not ile).
YENIDEN_GONDERILIR = {"", "soru", "hata", "kapandi"}

SQL_EKSIK = ("Talepler tablosunda Claude alanları yok — veritabani/19_talep_claude.sql "
             "Supabase SQL Editor'de bir kez çalıştırılmalı.")

_BASLIK = re.compile(r"Talep\s*#\s*(\d+)", re.IGNORECASE)


def onaylayabilir_mi(kullanici, ozel_yetki=None):
    """Talebi Claude'a gönderebilir mi? Sabit onaycılar + (varsa) 'claude_onay' özel yetkisi."""
    k = str(kullanici or "").strip().lower()
    if not k:
        return False
    if k in ONAYCILAR:
        return True
    try:
        return bool(ozel_yetki and ozel_yetki(k, "claude_onay"))
    except Exception:  # noqa: BLE001
        return False


def claude_durumu(talep):
    return str((talep or {}).get("claude_durum") or "").strip()


def gonderilebilir_mi(talep):
    return claude_durumu(talep) in YENIDEN_GONDERILIR


def etiket(talep):
    """Ekranda gösterilecek Claude durumu ('' = Claude'a hiç gönderilmemiş)."""
    d = claude_durumu(talep)
    return CLAUDE_DURUM_AD.get(d, d)


def onay_kaydi(kullanici, not_, simdi):
    return {"claude_durum": "onaylandi", "claude_onay_notu": str(not_ or "").strip(),
            "claude_onaylayan": str(kullanici or "").strip().lower(),
            "claude_onay_tarihi": simdi.isoformat(), "claude_guncelleme": simdi.isoformat(),
            "claude_not": "", "durum": "inceleniyor"}


def onaya_gonder(client, talep_id, kullanici, not_, simdi, tetikle=None):
    """Döner (ok, mesaj). Sütunlar yoksa (SQL 19 kurulmamış) anlaşılır uyarı döner.
    tetikle(talep_id) → (ok, açıklama): kayıttan sonra rutini hemen başlatır (rutini_tetikle)."""
    try:
        client.table("talepler").update(onay_kaydi(kullanici, not_, simdi)).eq("id", talep_id).execute()
    except Exception as e:  # noqa: BLE001
        if "claude_" in str(e):
            return False, SQL_EKSIK
        return False, f"Kaydedilemedi: {type(e).__name__}"
    basladi, sebep = False, ""
    if tetikle is not None:
        try:
            basladi, sebep = tetikle(talep_id)[:2]
        except Exception as e:  # noqa: BLE001 — tetikleme tutmazsa saat başı çalışma alır
            basladi, sebep = False, f"tetiklenemedi ({type(e).__name__})"
    if basladi:
        return True, "Talep Claude'a gönderildi, Claude şimdi başlıyor; PR hazır olunca mail gelir."
    msj = "Talep Claude'a gönderildi. Bir saat içinde başlar; PR hazır olunca mail gelir."
    if sebep:                                         # kurulum hatası görünsün (anahtar asla yazılmaz)
        if sebep == "rutin ayarı yok":
            sebep = "Streamlit Secrets'ta [claude_rutin] ayarı bulunamadı"
        msj += f" Anında başlatılamadı: {sebep}."
    return True, msj


# ── Rutini anında tetikleme (Claude Code routines · API tetikleyici) ─────────
# Belge: https://code.claude.com/docs/en/routines (Add an API trigger). Adres ve anahtar rutinin
# claude.ai'deki düzenleme ekranında üretilir; Streamlit Cloud → Settings → Secrets:
#   [claude_rutin]
#   url = "https://api.anthropic.com/v1/claude_code/routines/<rutin kimliği>/fire"
#   token = "<Generate token ile üretilen anahtar>"
# Anahtar yalnız bu rutini başlatabilir; hiçbir yere (ekran, kayıt, hata metni) yazılmaz.
RUTIN_BETA = "experimental-cc-routine-2026-04-01"
_RUTIN_ADRES = re.compile(r"^https://api\.anthropic\.com/v1/claude_code/routines/[A-Za-z0-9_]+/fire$")


def _kucuk_anahtarli(d):
    try:
        return {str(k).strip().lower(): v for k, v in dict(d).items()}
    except Exception:  # noqa: BLE001
        return {}


def rutin_ayari_coz(secrets=None):
    """Döner ({'url', 'token'} | None, sorun). sorun: ayar okunamadıysa kullanıcıya gösterilecek kısa
    sebep (anahtarın kendisi asla geçmez); ayar hiç yoksa "rutin ayarı yok".
    Küçük yazım farkları tolere edilir: bölüm / alan adında büyük harf, anahtarın başında "Bearer ",
    adres yerine yalnız rutin kimliği (trig_...)."""
    try:
        if secrets is None:
            import streamlit as st
            secrets = st.secrets
        ust = _kucuk_anahtarli(secrets)
    except Exception:  # noqa: BLE001 — secrets dosyası yok
        return None, "rutin ayarı yok"
    if "claude_rutin" not in ust:
        if any("rutin" in k for k in ust):
            return None, "Secrets'ta bölüm adı tam olarak [claude_rutin] olmalı"
        return None, "rutin ayarı yok"
    b = _kucuk_anahtarli(ust["claude_rutin"])
    if not b:
        return None, "[claude_rutin] bölümü boş ya da biçimi bozuk (url = \"...\" ve token = \"...\" satırları)"
    url = str(b.get("url") or "").strip().strip('"').strip("'").rstrip("/")
    token = str(b.get("token") or "").strip().strip('"').strip("'")
    if token.lower().startswith("bearer "):
        token = token[7:].strip()
    if re.fullmatch(r"trig_[A-Za-z0-9]+", url):
        url = f"https://api.anthropic.com/v1/claude_code/routines/{url}/fire"
    if not url:
        return None, "[claude_rutin] içinde url satırı yok"
    if not _RUTIN_ADRES.match(url):
        return None, ("url tanınmadı: https://api.anthropic.com/v1/claude_code/routines/<trig_...>/fire "
                      "biçiminde olmalı")
    if not token:
        return None, "[claude_rutin] içinde token satırı yok"
    if not token.startswith("sk-ant-"):
        return None, "token tanınmadı: Generate token ile üretilen sk-ant-... anahtarı olmalı"
    return {"url": url, "token": token}, ""


def rutin_ayari(secrets=None):
    """{'url', 'token'} ya da None (ayar yok / biçim yanlış)."""
    return rutin_ayari_coz(secrets)[0]


def rutini_tetikle(talep_id, ayar, post=None):
    """Rutini hemen başlatır. Döner (ok, açıklama); açıklamada anahtar geçmez.
    Rutinin kendi istemi talebi veritabanından seçer; gönderilen metin yalnız bilgi amaçlıdır."""
    if not ayar:
        return False, "rutin ayarı yok"
    if isinstance(ayar, tuple):              # rutin_ayari_coz sonucu: (ayar, sorun)
        if not ayar[0]:
            return False, ayar[1] or "rutin ayarı yok"
        ayar = ayar[0]
    if post is None:
        import requests
        post = requests.post
    try:
        r = post(ayar["url"], timeout=10, json={"text": f"Talep #{talep_id} Claude'a gönderildi."},
                 headers={"Authorization": f"Bearer {ayar['token']}", "anthropic-beta": RUTIN_BETA,
                          "anthropic-version": "2023-06-01", "Content-Type": "application/json"})
    except Exception as e:  # noqa: BLE001
        return False, f"bağlanılamadı ({type(e).__name__})"
    kod = getattr(r, "status_code", 0)
    if 200 <= kod < 300:
        return True, "başladı"
    return False, f"HTTP {kod}"


def baslik_talep_id(baslik):
    m = _BASLIK.search(str(baslik or ""))
    return int(m.group(1)) if m else None


def pr_guncellemesi(olay, birlesti, pr_url, simdi):
    """GitHub PR olayı → talep kaydına yazılacak alanlar (None = yapılacak bir şey yok)."""
    t = simdi.isoformat()
    if olay in ("opened", "reopened", "ready_for_review"):
        return {"claude_durum": "pr_hazir", "claude_pr_url": pr_url, "claude_guncelleme": t}
    if olay == "closed" and birlesti:
        return {"claude_durum": "yayinda", "claude_pr_url": pr_url, "claude_guncelleme": t,
                "durum": "tamamlandi"}
    if olay == "closed":
        return {"claude_durum": "kapandi", "claude_guncelleme": t}
    return None


def pr_mailleri(talep, yeni_durum, pr_url):
    """[(kullanici, konu, govde_html)] — PR hazır → onaycıya; yayında → talep sahibine
    (sahibi onaycıysa bir kez); kapandı → onaycıya."""
    from shared import eposta as E
    konu = (talep or {}).get("konu") or "Talep"
    tid = (talep or {}).get("id")
    onayci = str((talep or {}).get("claude_onaylayan") or "ibrahim").strip().lower()
    sahip = str((talep or {}).get("gonderen") or "").strip().lower()
    if yeni_durum == "pr_hazir":
        govde = (f"<p><b>Talep #{tid} · {E._e(konu)}</b> için PR hazır. İnceleyip birleştirdiğinde "
                 f"yayına çıkar.</p><p><a href=\"{E._e(pr_url)}\">{E._e(pr_url)}</a></p>")
        return [(onayci, f"[KAYRAN Talep] PR hazır · {konu}",
                 E.sablon("PR hazır", govde, "PR'ı aç", pr_url))]
    if yeni_durum == "yayinda":
        govde = (f"<p><b>{E._e(konu)}</b> başlıklı talebin geliştirildi ve yayına alındı.</p>"
                 "<p>Uygulamayı yenilediğinde görürsün.</p>")
        return [(k, f"[KAYRAN Talep] {konu} — Yayında",
                 E.sablon("Talebin yayında", govde, "Uygulamayı aç", E.baglanti()))
                for k in dict.fromkeys([sahip, onayci]) if k]
    if yeni_durum == "kapandi":
        govde = f"<p><b>Talep #{tid} · {E._e(konu)}</b> için açılan PR birleştirilmeden kapatıldı.</p>"
        return [(onayci, f"[KAYRAN Talep] PR kapatıldı · {konu}",
                 E.sablon("PR kapatıldı", govde, "Talep Merkezi'ni aç", E.baglanti("anasayfa")))]
    return []
