// Ekranda tek sayı dili (eski uygulamadaki shared/tasarim.tr_sayi ile aynı kural): 1.234,56 · %31,1
const tr = (n: number, ondalik: number) =>
  n.toLocaleString("tr-TR", { minimumFractionDigits: ondalik, maximumFractionDigits: ondalik });

export function sayi(n: number, ondalik = 0): string {
  return tr(n, ondalik);
}

/** "₺1.234,56" · "$1.234,56"; büyük özet rakamında kuruşsuz = ondalik 0. Eksi işaret sembolden önce. */
export function para(n: number, birim: "TL" | "USD", ondalik = 2): string {
  const s = birim === "TL" ? "₺" : "$";
  return (n < 0 ? "-" : "") + s + tr(Math.abs(n), ondalik);
}

export function yuzde(n: number, ondalik = 1): string {
  return "%" + tr(n, ondalik);
}
