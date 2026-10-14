import "server-only";
import { cookies } from "next/headers";
import type { Ben } from "./tipler.ts";

const API = process.env.API_URL || "http://127.0.0.1:8000";
export const CEREZ = "kayran_oturum";

/** Sunucu bileşenlerinden API'ye: tarayıcının oturum çerezini aktarır. Oturum yoksa null. */
export async function benOku(): Promise<Ben | null> {
  const c = (await cookies()).get(CEREZ);
  if (!c) return null;
  const r = await fetch(`${API}/ben`, { headers: { cookie: `${CEREZ}=${c.value}` }, cache: "no-store" });
  if (r.status === 401) return null;
  if (!r.ok) throw new Error(`API cevap vermedi (${r.status})`);
  return (await r.json()) as Ben;
}
