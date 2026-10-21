// Mikro eşitlemesini aktarımın hemen ardından başlatır (Ekim 2026). Supabase Edge Function, JWT doğrulaması
// KAPALI (aktarıcının yeni tip anahtarı JWT değil); kimlik aşağıda doğrulanır.
// Kaynak: repo veritabani/fonksiyonlar/mikro-tetik/index.ts
//
// Neden: GitHub'ın zamanlanmış işleri bu depoda saatlerce gecikiyor (02:00'lık gece yedeği 06:51–08:48'de
// çalışıyor); saatlik Mikro eşitlemesi 21.10.2026'da kendi zamanında hiç çalışmadı. Artık:
//   mod "esitle"  — aktarıcı yeni veri getirdiği turun sonunda çağırır. Çağıranın anahtarı yalnız service_role'ün
//                   okuyabildiği mikro_senk_durum'u okuyabilmeli (anon anahtar boş liste alır → reddedilir).
//                   En fazla 4 dakikada bir GitHub işi başlatılır.
//   mod "kontrol" — Supabase zamanlayıcısı (pg_cron, 30 dk) çağırır; anahtar gerekmez. Fonksiyon aktarıcının
//                   45 dakikadır yazmadığını KENDİSİ doğrular, öyleyse en fazla 3 saatte bir GitHub işini başlatır
//                   (o iş sağlık denetimiyle Telegram'a uyarı yazar). Aksi hâlde hiçbir şey yapmaz.
// GitHub anahtarı: telegram-webhook ile aynı GH_DISPATCH_TOKEN (yalnız bu deponun dispatches ucu).

const REPO = "FAZEON1/KAYRAN-WEBAPP";
const URL = Deno.env.get("SUPABASE_URL") ?? "";
const SERVIS = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") ?? "";
const ESITLE_ARALIK_SN = 240;
const KONTROL_ARALIK_SN = 3 * 3600;
const AKTARICI_GECIKME_SN = 45 * 60;

function yanit(govde: Record<string, unknown>, durum = 200): Response {
  return new Response(JSON.stringify(govde), { status: durum, headers: { "Content-Type": "application/json" } });
}

function servisBaslik(): Record<string, string> {
  return { apikey: SERVIS, Authorization: `Bearer ${SERVIS}`, "Content-Type": "application/json" };
}

async function cagiranYetkili(req: Request): Promise<boolean> {
  const apikey = req.headers.get("apikey") ?? "";
  if (!apikey) return false;
  const h: Record<string, string> = { apikey };
  const auth = req.headers.get("Authorization");
  if (auth) h["Authorization"] = auth;
  const r = await fetch(`${URL}/rest/v1/mikro_senk_durum?select=tablo&limit=1`, { headers: h });
  if (!r.ok) return false;
  const satir = await r.json();
  return Array.isArray(satir) && satir.length > 0;
}

async function ayarOku(anahtar: string): Promise<Record<string, unknown>> {
  const r = await fetch(`${URL}/rest/v1/sistem_ayarlari?select=deger&anahtar=eq.${anahtar}`, { headers: servisBaslik() });
  if (!r.ok) return {};
  const satir = await r.json();
  try {
    return JSON.parse(satir?.[0]?.deger ?? "{}") ?? {};
  } catch {
    return {};
  }
}

async function ayarYaz(anahtar: string, deger: Record<string, unknown>): Promise<void> {
  const simdi = new Date(Date.now() + 3 * 3600 * 1000).toISOString().replace("T", " ").slice(0, 19);
  await fetch(`${URL}/rest/v1/sistem_ayarlari?on_conflict=anahtar`, {
    method: "POST",
    headers: { ...servisBaslik(), Prefer: "resolution=merge-duplicates,return=minimal" },
    body: JSON.stringify({ anahtar, deger: JSON.stringify(deger), guncelleme_tarihi: simdi }),
  });
}

function gecenSn(zaman: unknown): number {
  const t = Date.parse(String(zaman ?? ""));
  return Number.isNaN(t) ? Infinity : (Date.now() - t) / 1000;
}

async function aktariciGecikmeSn(): Promise<number> {
  const r = await fetch(`${URL}/rest/v1/mikro_senk_durum?select=guncelleme&order=guncelleme.desc&limit=1`,
    { headers: servisBaslik() });
  if (!r.ok) return 0;          // okunamadıysa "durmuş" deme
  const satir = await r.json();
  return gecenSn(satir?.[0]?.guncelleme);
}

async function githubBaslat(neden: string): Promise<number> {
  const anahtar = Deno.env.get("GH_DISPATCH_TOKEN") ?? "";
  if (!anahtar) return 0;
  const r = await fetch(`https://api.github.com/repos/${REPO}/dispatches`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${anahtar}`,
      Accept: "application/vnd.github+json",
      "X-GitHub-Api-Version": "2022-11-28",
      "User-Agent": "kayran-mikro-tetik",
    },
    body: JSON.stringify({ event_type: "mikro_esitle", client_payload: { neden } }),
  });
  if (r.status !== 204) console.log("GitHub dispatch:", r.status, (await r.text()).slice(0, 200));
  return r.status;
}

Deno.serve(async (req) => {
  if (req.method !== "POST") return yanit({ durum: "yalnız POST" }, 405);
  let govde: Record<string, unknown> = {};
  try {
    govde = await req.json();
  } catch {
    govde = {};
  }
  const mod = String(govde.mod ?? "esitle");

  if (mod === "kontrol") {
    const gecikme = await aktariciGecikmeSn();
    if (gecikme < AKTARICI_GECIKME_SN) return yanit({ durum: "aktarıcı çalışıyor" });
    const son = await ayarOku("mikro_saglik_tetik");
    if (gecenSn(son.zaman) < KONTROL_ARALIK_SN) return yanit({ durum: "yakın zamanda tetiklendi" });
    const kod = await githubBaslat("aktarici_durdu");
    const kayit = { zaman: new Date().toISOString(), mod, durum: kod, neden: "aktarici_durdu" };
    await ayarYaz("mikro_saglik_tetik", kayit);
    await ayarYaz("mikro_tetik_son", kayit);
    return yanit({ durum: kod === 204 ? "tetiklendi" : "tetiklenemedi", github: kod });
  }

  if (!(await cagiranYetkili(req))) return yanit({ durum: "yetkisiz" }, 401);
  const son = await ayarOku("mikro_tetik_son");
  if (son.mod === "esitle" && son.durum === 204 && gecenSn(son.zaman) < ESITLE_ARALIK_SN) {
    return yanit({ durum: "yakın zamanda tetiklendi" });
  }
  const neden = String(govde.neden ?? "yeni_veri").slice(0, 60);
  const kod = await githubBaslat(neden);
  await ayarYaz("mikro_tetik_son", { zaman: new Date().toISOString(), mod: "esitle", durum: kod, neden });
  return yanit({ durum: kod === 204 ? "tetiklendi" : "tetiklenemedi", github: kod });
});
