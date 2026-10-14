"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { aktifModul, baglanti, gorunenAd, gruplara } from "@/lib/menu.ts";
import type { Ben } from "@/lib/tipler.ts";
import Ikon from "./Ikon.tsx";
import s from "./kabuk.module.css";

const DAR_ANAHTAR = "kayran.menu.dar";

export default function Kabuk({ ben, children }: { ben: Ben; children: React.ReactNode }) {
  const yol = usePathname();
  const router = useRouter();
  const aktif = aktifModul(yol);
  const [acik, setAcik] = useState<string>(aktif);
  const [dar, setDar] = useState(false);
  const [mobil, setMobil] = useState(false);

  useEffect(() => {
    try { setDar(localStorage.getItem(DAR_ANAHTAR) === "1"); } catch { /* gizli pencere */ }
  }, []);
  useEffect(() => { setAcik(aktif); setMobil(false); }, [aktif]);

  function daralt() {
    const v = !dar;
    setDar(v);
    try { localStorage.setItem(DAR_ANAHTAR, v ? "1" : "0"); } catch { /* yok say */ }
  }

  async function cikis() {
    await fetch("/api/cikis", { method: "POST" }).catch(() => null);
    router.replace("/giris");
    router.refresh();
  }

  const aktifMod = ben.menu.find((m) => m.kod === aktif);

  return (
    <div className={`${s.kabuk} ${dar ? s.dar : ""}`}>
      <aside className={`${s.menu} ${mobil ? s.mobilAcik : ""}`} aria-label="Ana menü">
        <div className={s.marka}>
          <span className="logo" aria-hidden="true">
            <i /><i /><i /><i /><i className="t" /><i className="b" /><i /><i className="b" /><i />
          </span>
          <b className={s.yazi}>KAYRAN</b>
          <button className={s.daralt} onClick={daralt} aria-label={dar ? "Menüyü genişlet" : "Menüyü daralt"}>
            <Ikon ad={dar ? "chevron_right" : "chevron_left"} />
          </button>
        </div>
        <nav className={s.nav}>
          {ben.menu.map((m) => {
            const ust = baglanti(m);
            const cokSayfa = m.sayfalar.length > 0;
            const acikMi = cokSayfa && acik === m.kod && !dar;
            const icerik = (
              <>
                <Ikon ad={m.ikon} />
                <span className={s.yazi}>{m.ad}</span>
                {cokSayfa && <Ikon ad={acikMi ? "keyboard_arrow_up" : "keyboard_arrow_down"} boyut={18} className={`${s.ok} ${s.yazi}`} />}
              </>
            );
            return (
              <div key={m.kod}>
                {cokSayfa ? (
                  <button className={`${s.mod} ${aktif === m.kod ? s.aktif : ""}`} title={m.ad}
                    aria-expanded={acikMi} onClick={() => setAcik(acikMi ? "" : m.kod)}>
                    {icerik}
                  </button>
                ) : ust.eski ? (
                  <a className={s.mod} href={ust.href} title={`${m.ad} (eski uygulamada açılır)`}>{icerik}</a>
                ) : (
                  <Link className={`${s.mod} ${aktif === m.kod ? s.aktif : ""}`} href={ust.href} title={m.ad}
                    aria-current={aktif === m.kod ? "page" : undefined}>{icerik}</Link>
                )}
                {acikMi && (
                  <div className={s.alt}>
                    {gruplara(m.sayfalar).map((g, i) => (
                      <div key={i}>
                        {g.grup && <span className={s.grup}>{g.grup}</span>}
                        {g.sayfalar.map((p) => {
                          const b = baglanti(m, p);
                          const secili = !b.eski && yol === b.href;
                          return b.eski ? (
                            <a key={p.kod} href={b.href} className={s.sayfa} title="Eski uygulamada açılır">
                              {p.ad}<Ikon ad="north_east" boyut={14} className={s.dis} />
                            </a>
                          ) : (
                            <Link key={p.kod} href={b.href} className={`${s.sayfa} ${secili ? s.secili : ""}`}
                              aria-current={secili ? "page" : undefined}>{p.ad}</Link>
                          );
                        })}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            );
          })}
        </nav>
        <div className={s.kisi}>
          <span className={s.avatar}>{gorunenAd(ben.kullanici).charAt(0)}</span>
          <div className={s.yazi}>
            {gorunenAd(ben.kullanici)}
            <small>{ben.salt_okur ? "Salt okur" : "Kullanıcı"}</small>
          </div>
          <button className={`${s.cikis} ${s.yazi}`} onClick={cikis} title="Çıkış yap" aria-label="Çıkış yap">
            <Ikon ad="logout" />
          </button>
        </div>
      </aside>
      {mobil && <button className={s.perde} aria-label="Menüyü kapat" onClick={() => setMobil(false)} />}

      <div className={s.sag}>
        <header className={s.ust}>
          <button className={`dug ${s.menuAc}`} onClick={() => setMobil(true)} aria-label="Menüyü aç">
            <Ikon ad="menu" />
          </button>
          <div className={s.yol}>
            <b>{aktifMod?.ad ?? "Ana sayfa"}</b>
          </div>
          <span className={s.etiket} title="Yeni uygulama yapım aşamasında; hazır olmayan sayfalar eski uygulamada açılır">
            Önizleme
          </span>
        </header>
        <main className={s.icerik}>{children}</main>
      </div>
    </div>
  );
}
