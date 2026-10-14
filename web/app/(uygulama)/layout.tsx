import { redirect } from "next/navigation";
import Kabuk from "@/bilesen/Kabuk.tsx";
import { benOku } from "@/lib/sunucu.ts";

// Oturum gerektiren bütün sayfalar bu düzenin içinde: oturum yoksa giriş sayfasına.
export default async function UygulamaDuzeni({ children }: { children: React.ReactNode }) {
  const ben = await benOku();
  if (!ben) redirect("/giris");
  return <Kabuk ben={ben}>{children}</Kabuk>;
}
