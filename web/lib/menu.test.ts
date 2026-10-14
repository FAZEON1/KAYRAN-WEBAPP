import { test } from "node:test";
import assert from "node:assert/strict";
import { aktifModul, baglanti, gorunenAd, gruplara, selam } from "./menu.ts";
import { para, sayi, yuzde } from "./bicim.ts";
import type { Modul, Sayfa } from "./tipler.ts";

const s = (kod: string, grup: string | null, yeni = false): Sayfa => ({
  kod, ad: kod, grup, yeni, eski: yeni ? null : `https://eski/?s=kayranacc&p=${kod}`,
});
const acc: Modul = { kod: "kayranacc", ad: "Muhasebe", ikon: "x", yeni: false, eski: "https://eski/?s=kayranacc", sayfalar: [] };

test("gruplar sırayı korur, ardışık aynı grup birleşir", () => {
  const g = gruplara([s("a", "Ödemeler"), s("b", "Ödemeler"), s("c", "Nakit"), s("d", null)]);
  assert.deepEqual(g.map((x) => [x.grup, x.sayfalar.map((y) => y.kod)]), [
    ["Ödemeler", ["a", "b"]], ["Nakit", ["c"]], [null, ["d"]],
  ]);
});

test("tek sayfalı, sayfayla aynı adlı grubun başlığı yok", () => {
  const g = gruplara([{ ...s("genel_bakis", "Genel bakış"), ad: "Genel bakış" }, s("b", "Ödemeler")]);
  assert.deepEqual(g.map((x) => x.grup), [null, "Ödemeler"]);
});

test("hazır sayfa içeride, hazır olmayan eski uygulamada açılır", () => {
  assert.deepEqual(baglanti(acc, s("bu_hafta", "Ödemeler", true)), { href: "/kayranacc/bu_hafta", eski: false });
  assert.deepEqual(baglanti(acc, s("cekler", "Ödemeler")), { href: "https://eski/?s=kayranacc&p=cekler", eski: true });
  assert.deepEqual(baglanti({ ...acc, kod: "anasayfa", yeni: true }), { href: "/", eski: false });
  assert.deepEqual(baglanti(acc), { href: "https://eski/?s=kayranacc", eski: true });
});

test("aktif modül yoldan", () => {
  assert.equal(aktifModul("/"), "anasayfa");
  assert.equal(aktifModul("/kayranacc/bu_hafta?x=1"), "kayranacc");
});

test("ad ve selam Türkçe", () => {
  assert.equal(gorunenAd("ibrahim"), "İbrahim");
  assert.equal(selam(9), "Günaydın");
  assert.equal(selam(14), "İyi günler");
  assert.equal(selam(20), "İyi akşamlar");
});

test("sayı dili eski uygulamayla aynı", () => {
  assert.equal(para(4109380.82, "TL"), "₺4.109.380,82");
  assert.equal(para(4109380.82, "TL", 0), "₺4.109.381");
  assert.equal(para(-1234.5, "USD"), "-$1.234,50");
  assert.equal(sayi(1401), "1.401");
  assert.equal(yuzde(31.06), "%31,1");
});
