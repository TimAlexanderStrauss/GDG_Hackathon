import type { SimpleIcon } from "simple-icons";

/** Real brand mark from simple-icons (CC0), in its own colour; black marks follow the text colour. */
export function BrandIcon({ icon, size = 20 }: { icon: SimpleIcon; size?: number }) {
  const fill = icon.hex === "000000" ? "currentColor" : `#${icon.hex}`;
  return (
    <svg role="img" aria-hidden viewBox="0 0 24 24" width={size} height={size} fill={fill} className="shrink-0">
      <path d={icon.path} />
    </svg>
  );
}
