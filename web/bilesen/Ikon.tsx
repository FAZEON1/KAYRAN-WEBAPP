import { IKONLAR } from "@/lib/ikonlar.ts";

/** Material Symbols ikonu (gömülü SVG). Bilinmeyen ad → "apps". Renk yazı renginden gelir. */
export default function Ikon({ ad, boyut = 20, className }: { ad: string; boyut?: number; className?: string }) {
  return (
    <svg className={className} width={boyut} height={boyut} viewBox="0 -960 960 960" fill="currentColor"
      aria-hidden="true" focusable="false" style={{ flexShrink: 0 }}>
      <path d={IKONLAR[ad] ?? IKONLAR.apps} />
    </svg>
  );
}
