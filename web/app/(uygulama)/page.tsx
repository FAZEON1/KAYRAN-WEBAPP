import type { Metadata } from "next";
import { gorunenAd, selam } from "@/lib/menu.ts";
import { benOku } from "@/lib/sunucu.ts";
import Ikon from "@/bilesen/Ikon.tsx";
import s from "./anasayfa.module.css";

export const metadata: Metadata = { title: "Ana sayfa" };

const AYLAR = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"];
const GUNLER = ["Pazar", "Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi"];

function turkiyeSaati(): Date {
  // Sunucu UTC'de çalışır; Türkiye UTC+3 (yaz saati yok).
  return new Date(Date.now() + 3 * 3600 * 1000);
}

export default async function AnaSayfa() {
  const ben = await benOku();
  if (!ben) return null;
  const t = turkiyeSaati();
  const moduller = ben.menu.filter((m) => m.kod !== "anasayfa");
  return (
    <div className={s.sayfa}>
      <div className={s.bas}>
        <h1>{selam(t.getUTCHours())}, {gorunenAd(ben.kullanici)}</h1>
        <span className={s.tarih}>{t.getUTCDate()} {AYLAR[t.getUTCMonth()]} {t.getUTCFullYear()}, {GUNLER[t.getUTCDay()]}</span>
      </div>

      <section className={s.bilgi} aria-labelledby="yeni-baslik">
        <Ikon ad="construction" className={s.bilgiIk} />
        <div>
          <h2 id="yeni-baslik">Yeni KAYRAN yapım aşamasında</h2>
          <p>
            Ekranlar sırayla bu yeni uygulamaya taşınıyor; ilki Muhasebe › Bu hafta ödeme masası. Henüz taşınmamış bir
            sayfaya tıkladığınızda eski uygulamada açılır. İkisi aynı veriyi kullanır, birinde yaptığınız işlem diğerinde
            görünür.
          </p>
        </div>
      </section>

      <h2 className={s.altBaslik}>Modüller</h2>
      <div className={s.izgara}>
        {moduller.map((m) => (
          <a key={m.kod} className={s.kart} href={m.sayfalar[0]?.eski ?? m.eski ?? "#"}>
            <Ikon ad={m.ikon} boyut={22} className={s.kartIk} />
            <b>{m.ad}</b>
            <small>{m.sayfalar.length ? `${m.sayfalar.length} sayfa` : "tek sayfa"} · eski uygulamada</small>
          </a>
        ))}
      </div>
    </div>
  );
}
