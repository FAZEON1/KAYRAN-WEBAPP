import type { Modul, Sayfa } from "./tipler.ts";

/** Modülün sayfalarını gruplarına ayırır, sırayı korur: [{grup, sayfalar}]. Grupsuz sayfalar grup=null.
 *  Tek sayfalı ve sayfayla aynı adlı grubun başlığı yazılmaz ("Genel bakış › Genel bakış" olmasın). */
export function gruplara(sayfalar: Sayfa[]): { grup: string | null; sayfalar: Sayfa[] }[] {
  const out: { grup: string | null; sayfalar: Sayfa[] }[] = [];
  for (const s of sayfalar) {
    const son = out[out.length - 1];
    if (son && son.grup === s.grup) son.sayfalar.push(s);
    else out.push({ grup: s.grup, sayfalar: [s] });
  }
  for (const g of out) {
    if (g.sayfalar.length === 1 && g.grup && g.grup.toLocaleLowerCase("tr-TR") === g.sayfalar[0].ad.toLocaleLowerCase("tr-TR")) g.grup = null;
  }
  return out;
}

/** Sayfanın bağlantısı: yeni uygulamada hazırsa iç yol, değilse eski uygulama adresi. */
export function baglanti(mod: Modul, sayfa?: Sayfa): { href: string; eski: boolean } {
  if (!sayfa) {
    if (mod.kod === "anasayfa" || mod.yeni) return { href: mod.kod === "anasayfa" ? "/" : `/${mod.kod}`, eski: false };
    return { href: mod.eski ?? "#", eski: true };
  }
  if (sayfa.yeni) return { href: `/${mod.kod}/${sayfa.kod}`, eski: false };
  return { href: sayfa.eski ?? "#", eski: true };
}

/** Adres çubuğundaki yoldan açık modül kodu ("/" → anasayfa). */
export function aktifModul(yol: string): string {
  const parca = yol.split("?")[0].split("/").filter(Boolean)[0];
  return parca || "anasayfa";
}

/** "ibrahim" → "İbrahim" (Türkçe büyük harf). */
export function gorunenAd(kullanici: string): string {
  const k = kullanici.trim();
  return k ? k.charAt(0).toLocaleUpperCase("tr-TR") + k.slice(1) : k;
}

/** Saate göre selam (Türkiye saati verilir). */
export function selam(saat: number): string {
  if (saat < 6) return "İyi geceler";
  if (saat < 12) return "Günaydın";
  if (saat < 18) return "İyi günler";
  return "İyi akşamlar";
}
