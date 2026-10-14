import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { benOku } from "@/lib/sunucu.ts";
import GirisFormu from "./GirisFormu.tsx";
import s from "./giris.module.css";

export const metadata: Metadata = { title: "Oturum aç" };

export default async function GirisSayfasi() {
  if (await benOku().catch(() => null)) redirect("/");
  return (
    <main className={s.sayfa}>
      <section className={s.kart} aria-labelledby="giris-baslik">
        <div className={s.marka}>
          <span className="logo" aria-hidden="true">
            <i /><i /><i /><i /><i className="t" /><i className="b" /><i /><i className="b" /><i />
          </span>
          <b>KAYRAN</b>
        </div>
        <h1 id="giris-baslik">Oturum aç</h1>
        <p className={s.alt}>Eski uygulamadaki kullanıcı adın ve şifrenle gir.</p>
        <GirisFormu />
        <ul className={s.guven}>
          <li>Şifreler PBKDF2 ile şifrelenerek saklanır</li>
          <li>Art arda hatalı denemede hesap geçici kilitlenir</li>
        </ul>
      </section>
    </main>
  );
}
