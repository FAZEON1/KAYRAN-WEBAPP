// Kullanılan Material Symbols ikonlarını lib/ikonlar.ts içine gömer (3,9 MB yazı tipi yerine birkaç KB).
// Yeni ikon gerekince LISTE'ye ekle ve çalıştır:  node scripts/ikonlari-uret.mjs
// Modül ikonları API'den gelir (shared/gezinme.MODULLER); api/tests hepsinin burada olduğunu denetler.
import { readFileSync, writeFileSync } from "node:fs";

const LISTE = [
  // modüller (shared/gezinme.py MODULLER ikon)
  "home", "monitoring", "account_balance_wallet", "directions_boat", "inventory_2", "warehouse",
  "point_of_sale", "construction", "groups", "calculate",
  // arayüz
  "apps", "chevron_left", "chevron_right", "keyboard_arrow_down", "keyboard_arrow_up", "north_east", "logout", "menu",
];

const out = LISTE.map((ad) => {
  const svg = readFileSync(new URL(`../node_modules/@material-symbols/svg-400/outlined/${ad}.svg`, import.meta.url), "utf8");
  const d = svg.match(/ d="([^"]+)"/)?.[1];
  if (!d) throw new Error(`${ad}: path bulunamadı`);
  return `  ${JSON.stringify(ad)}: ${JSON.stringify(d)},`;
});

writeFileSync(
  new URL("../lib/ikonlar.ts", import.meta.url),
  `// OTOMATİK ÜRETİLDİ — elle değiştirme: node scripts/ikonlari-uret.mjs\n` +
    `// Kaynak: @material-symbols/svg-400 (Apache-2.0), outlined, viewBox "0 -960 960 960".\n` +
    `export const IKONLAR: Record<string, string> = {\n${out.join("\n")}\n};\n`,
);
console.log(`${LISTE.length} ikon yazıldı`);
