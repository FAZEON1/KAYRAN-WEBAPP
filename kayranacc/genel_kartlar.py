# -*- coding: utf-8 -*-
"""Muhasebe › Genel bakış kartları (Ekim 2026) — SAF; ortak kart bileşenine
(shared.utils.metrik_satiri → shared.tasarim.kart_hucresi) giden liste.

Ana kart: hafta sonu kalan / nakit açığı. Renk yalnız açık varsa (kırmızı).
"""


def haftalik_ozet_kartlari(*, tl_toplam, odendi_tl, usd_toplam, kur, odendi_cnt, toplam_cnt,
                           bekleyen_tl, hafta_sonu_tl, fmt):
    acik = hafta_sonu_tl < 0
    pct = int(odendi_cnt / toplam_cnt * 100) if toplam_cnt else 0
    cubuk = ('<div style="background:var(--k-ortu2);border-radius:4px;height:5px;margin:6px 0 4px;overflow:hidden">'
             f'<div style="background:var(--k-soluk);height:100%;width:{pct}%"></div></div>%{pct} tamamlandı')
    return [
        {"label": "Nakit açığı" if acik else "Hafta sonu kalan", "value": f"₺{fmt(abs(hafta_sonu_tl))}",
         "vurgu": True, "anlam": "kotu" if acik else None,
         "alt": "Tahmini açık · banka − bekleyen ödemeler" if acik else "Tahmini bakiye · banka − bekleyen ödemeler"},
        {"label": "Bekleyen TL", "value": f"₺{fmt(bekleyen_tl)}", "alt": "Ödenmesi gereken"},
        {"label": "İlerleme", "value": f"{odendi_cnt} / {toplam_cnt}", "alt": cubuk},
        {"label": "Toplam TL", "value": f"₺{fmt(tl_toplam)}", "alt": f"Ödendi: ₺{fmt(odendi_tl)}"},
        {"label": "Toplam USD", "value": f"${fmt(usd_toplam)}", "alt": f"≈ ₺{fmt(usd_toplam * kur)}"},
    ]


def bugun_kartlari(*, bugun_kalan_tl, bugun_kalan_usd, fmt):
    return [
        {"label": "Bugün kalan TL", "value": f"₺{fmt(bugun_kalan_tl)}" if bugun_kalan_tl else "—",
         "alt": "Ödenmemiş TL"},
        {"label": "Bugün kalan USD", "value": f"${fmt(bugun_kalan_usd)}" if bugun_kalan_usd else "—",
         "alt": "Ödenmemiş USD"},
    ]
