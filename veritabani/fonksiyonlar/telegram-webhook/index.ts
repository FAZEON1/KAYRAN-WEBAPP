// Telegram asistanı — gelen mesaj kapısı (Ekim 2026). Supabase Edge Function, JWT doğrulaması KAPALI
// (Telegram anahtar göndermez; kimliği aşağıdaki gizli başlıkla doğrulanır).
// Kaynak burada tutulur; Supabase'e "telegram-webhook" adıyla, JWT doğrulaması kapalı yüklenir (kök dizinde supabase/
// klasörü açılmaz: Python'daki supabase paketini gölgeler).
//
// Telegram her mesajı buraya POST eder. Fonksiyon:
//   1. X-Telegram-Bot-Api-Secret-Token başlığını sistem_ayarlari 'telegram_webhook_gizli' ile karşılaştırır;
//      tutmazsa 401 (sahte istek GitHub'ı tetikleyemez).
//   2. Metin mesajını GitHub'a repository_dispatch 'telegram_soru' olarak iletir; cevabı GitHub'daki iş
//      (otonom/telegram_soru.py) programın soru kutusuyla üretir. Burada veri okunmaz, cevap üretilmez.
//   3. Telegram'a hemen "yazıyor…" gösterir.
// Sırlar (Supabase → Edge Functions → Secrets): GH_DISPATCH_TOKEN (yalnız bu repoda Contents: Read and
// write yetkili GitHub anahtarı). SUPABASE_URL ve SUPABASE_SERVICE_ROLE_KEY Supabase'in kendi değerleridir.

const REPO = "FAZEON1/KAYRAN-WEBAPP";

async function gizliDeger(): Promise<string> {
  const url = Deno.env.get("SUPABASE_URL") + "/rest/v1/sistem_ayarlari?select=deger&anahtar=eq.telegram_webhook_gizli";
  const key = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") ?? "";
  const r = await fetch(url, { headers: { apikey: key, Authorization: `Bearer ${key}` } });
  if (!r.ok) return "";
  const satir = await r.json();
  return (satir?.[0]?.deger ?? "") as string;
}

function esit(a: string, b: string): boolean {
  if (!a || !b || a.length !== b.length) return false;
  let fark = 0;
  for (let i = 0; i < a.length; i++) fark |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return fark === 0;
}

function telegramYaniti(govde: Record<string, unknown>): Response {
  // Telegram, webhook cevabındaki yöntemi kendisi çalıştırır (ek anahtar gerekmez).
  return new Response(JSON.stringify(govde), { headers: { "Content-Type": "application/json" } });
}

Deno.serve(async (req) => {
  if (req.method !== "POST") return new Response("ok");
  const gelen = req.headers.get("X-Telegram-Bot-Api-Secret-Token") ?? "";
  if (!esit(gelen, await gizliDeger())) return new Response("yetkisiz", { status: 401 });

  let guncelleme: any;
  try {
    guncelleme = await req.json();
  } catch {
    return new Response("ok");
  }
  const m = guncelleme?.message;
  const metin = typeof m?.text === "string" ? m.text.slice(0, 500) : "";
  if (!m?.chat?.id || !metin) return new Response("ok");

  const anahtar = Deno.env.get("GH_DISPATCH_TOKEN") ?? "";
  let tamam = false;
  if (anahtar) {
    const r = await fetch(`https://api.github.com/repos/${REPO}/dispatches`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${anahtar}`,
        Accept: "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "kayran-telegram",
      },
      body: JSON.stringify({
        event_type: "telegram_soru",
        client_payload: { chat_id: m.chat.id, kimlik: m.from?.id ?? m.chat.id, metin, mesaj_id: m.message_id },
      }),
    });
    tamam = r.status === 204;
    if (!tamam) console.log("GitHub dispatch:", r.status, (await r.text()).slice(0, 200));
  }
  if (tamam) return telegramYaniti({ method: "sendChatAction", chat_id: m.chat.id, action: "typing" });
  return telegramYaniti({
    method: "sendMessage",
    chat_id: m.chat.id,
    text: "Şu an cevap veremiyorum: asistanın kurulumu tamamlanmamış (GitHub anahtarı). Yöneticine haber ver.",
  });
});
