"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import s from "./giris.module.css";

export default function GirisFormu() {
  const router = useRouter();
  const [hata, setHata] = useState("");
  const [bekliyor, setBekliyor] = useState(false);

  async function gonder(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    setBekliyor(true);
    setHata("");
    try {
      const r = await fetch("/api/giris", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ kullanici: f.get("kullanici"), sifre: f.get("sifre") }),
      });
      if (r.ok) {
        router.replace("/");
        router.refresh();
        return;
      }
      const v = await r.json().catch(() => ({}));
      setHata(typeof v.detail === "string" ? v.detail : "Giriş yapılamadı. Biraz sonra tekrar deneyin.");
    } catch {
      setHata("Sunucuya ulaşılamadı. İnternet bağlantınızı kontrol edip tekrar deneyin.");
    }
    setBekliyor(false);
  }

  return (
    <form className={s.form} onSubmit={gonder}>
      <label>
        Kullanıcı adı
        <input id="kullanici" name="kullanici" autoComplete="username" required autoFocus />
      </label>
      <label>
        Şifre
        <input id="sifre" name="sifre" type="password" autoComplete="current-password" required />
      </label>
      {hata && <p className={s.hata} role="alert">{hata}</p>}
      <button className="dug birincil" type="submit" disabled={bekliyor}>
        {bekliyor ? "Giriş yapılıyor…" : "Giriş yap"}
      </button>
    </form>
  );
}
