// API'nin /ben cevabı (api/main.py → ben) — iki taraf aynı biçimi kullanır.
export type Sayfa = {
  kod: string;
  ad: string;
  grup: string | null;
  yeni: boolean; // yeni uygulamada hazır mı
  eski: string | null; // hazır değilse eski uygulamadaki adresi
};

export type Modul = {
  kod: string;
  ad: string;
  ikon: string; // Material Symbols adı (eski uygulamayla aynı)
  yeni: boolean;
  eski: string | null;
  sayfalar: Sayfa[];
};

export type Ben = {
  kullanici: string;
  salt_okur: boolean;
  moduller: Record<string, boolean>;
  ozel: string[];
  menu: Modul[];
};
