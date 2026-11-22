import type { ReactNode } from 'react';

/** Original 32px sprites sharing the sprout's wood, parchment and leaf palette. */
type IconProps = { size?: number; className?: string };
function Sprite({ size = 32, className = '', children }: IconProps & { children: ReactNode }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 32 32"
      className={`pixel-icon ${className}`}
      aria-hidden="true"
      focusable="false"
      shapeRendering="crispEdges"
    >
      {children}
    </svg>
  );
}

export function PixelBook(props: IconProps) {
  return (
    <Sprite {...props}>
      <path fill="#684424" d="M2 6h11v2h6V6h11v21H19v2h-6v-2H2z" />
      <path fill="#719447" d="M4 9h9v2h6V9h9v16H19v2h-6v-2H4z" />
      <path fill="#fff5d5" d="M5 5h7v2h3v17h-3v-2H5zM17 7h3V5h7v17h-7v2h-3z" />
      <path fill="#d5bc83" d="M7 10h5v2H7zM7 15h5v2H7zM20 10h5v2h-5zM20 15h5v2h-5z" />
      <path fill="#bf6750" d="M22 5h3v9l-2-2-1 2z" />
    </Sprite>
  );
}

export function PixelMap(props: IconProps) {
  return (
    <Sprite {...props}>
      <path fill="#684424" d="M2 5h9v2h10V5h9v22h-9v2H11v-2H2z" />
      <path fill="#f3dca5" d="M4 7h7v2h10V7h7v18h-7v2H11v-2H4z" />
      <path fill="#d6b776" d="M10 7h2v18h-2zM20 9h2v18h-2z" />
      <path fill="#7f9f4c" d="M6 10h3v3H6zM14 20h4v3h-4zM24 10h2v3h-2z" />
      <path fill="#b27b42" d="M8 15h3v2H8zM12 17h3v2h-3zM16 14h3v2h-3zM20 12h3v2h-3z" />
      <path fill="#b95140" d="M22 17h2v2h2v2h-2v2h-2v-2h-2v-2h2z" />
    </Sprite>
  );
}

export function PixelCalendar(props: IconProps) {
  return (
    <Sprite {...props}>
      <path fill="#684424" d="M4 5h24v24H4z" />
      <path fill="#fff3ce" d="M6 12h20v15H6z" />
      <path fill="#b8664c" d="M6 7h20v5H6z" />
      <path fill="#d8bf89" d="M9 16h3v3H9zM15 16h3v3h-3zM21 16h3v3h-3zM9 22h3v3H9z" />
      <path fill="#6d913f" d="M16 21h2v2h2v-2h2v-2h2v4h-2v2h-4v-2h-2z" />
      <path fill="#684424" d="M9 3h3v6H9zM20 3h3v6h-3z" />
      <path fill="#e5b95b" d="M10 3h1v4h-1zM21 3h1v4h-1z" />
    </Sprite>
  );
}

export function PixelScroll(props: IconProps) {
  return (
    <Sprite {...props}>
      <path fill="#684424" d="M7 3h20v3h2v6h-5v16H5v-3H3v-6h4z" />
      <path fill="#f5dfaa" d="M9 5h14v19H8v-3H5v3h2v2h15V8h5V6H9z" />
      <path fill="#be9455" d="M11 9h8v2h-8zM11 14h8v2h-8zM11 19h5v2h-5z" />
      <path fill="#a6503e" d="M23 19h5v2h2v5h-2v2h-5v-2h-2v-5h2z" />
      <path fill="#edbf65" d="M24 21h3v4h-3z" />
    </Sprite>
  );
}

export function PixelGlobe(props: IconProps) {
  return (
    <Sprite {...props}>
      <path
        fill="#684424"
        d="M10 2h12v2h4v4h2v12h-2v4h-4v2h-4v3h6v2H8v-2h6v-3h-4v-2H6v-4H4V8h2V4h4z"
      />
      <path fill="#82b5bb" d="M10 4h12v2h2v4h2v8h-2v4h-4v2h-8v-2H8v-4H6v-8h2V6h2z" />
      <path fill="#6d914a" d="M10 5h7v3h-3v4h-4v4H7V9h3zM18 14h6v4h-3v5h-4v-5h-2v-2h3z" />
      <path fill="#d0e4ce" d="M18 5h3v2h-3zM8 17h2v3H8z" />
    </Sprite>
  );
}

export function PixelCrop(props: IconProps) {
  return (
    <Sprite {...props}>
      <path fill="#765132" d="M13 4h9v3h4v4h2v11h-3v4h-4v3H10v-3H6v-4H4V12h3V8h6z" />
      <path fill="#c9a16a" d="M13 6h8v3h4v12h-3v4h-3v2h-8v-3H8v-4H6v-7h3v-3h4z" />
      <path fill="#e9c58a" d="M12 9h7v3h-5v3h-4v-3h2z" />
      <path fill="#967044" d="M19 15h3v3h-3zM10 20h2v2h-2zM17 23h2v2h-2z" />
    </Sprite>
  );
}

export function PixelSeeds(props: IconProps) {
  return (
    <Sprite {...props}>
      <path fill="#684424" d="M6 3h20v27H6z" />
      <path fill="#f0d59a" d="M8 5h16v23H8z" />
      <path fill="#a8ba66" d="M8 8h16v3H8zM8 24h16v4H8z" />
      <path fill="#567835" d="M15 15h2v7h-2zM10 12h4v2h2v3h-4v-2h-2zM18 12h4v3h-2v2h-3v-3h1z" />
      <path fill="#a57740" d="M12 22h8v2h-8z" />
    </Sprite>
  );
}

export function PixelJar(props: IconProps) {
  return (
    <Sprite {...props}>
      <path fill="#684424" d="M9 3h14v6h3v3h2v15h-3v3H7v-3H4V12h2V9h3z" />
      <path fill="#d9a54e" d="M11 5h10v3H11z" />
      <path fill="#c97a4b" d="M9 10h14v3h3v13h-3v2H9v-2H6V13h3z" />
      <path fill="#f6e5bd" d="M7 16h18v8H7zM9 11h3v4H9z" />
      <path fill="#719348" d="M15 17h2v2h3v3h-7v-3h2z" />
    </Sprite>
  );
}

export function PixelBundle(props: IconProps) {
  return (
    <Sprite {...props}>
      <path fill="#684424" d="M11 3h10v5h5v3h3v16h-3v3H6v-3H3V11h3V8h5z" />
      <path fill="#aa7650" d="M13 5h6v4h-6zM8 10h16v3h3v12h-3v3H8v-3H5V13h3z" />
      <path fill="#73944b" d="M8 11h16v8H8z" />
      <path fill="#e3bd67" d="M14 15h4v7h-4zM10 23h12v3H10z" />
    </Sprite>
  );
}

export function PixelBarrel(props: IconProps) {
  return (
    <Sprite {...props}>
      <path fill="#684424" d="M8 2h16v3h3v5h2v13h-2v5h-3v2H8v-2H5v-5H3V10h2V5h3z" />
      <path fill="#b98549" d="M9 4h14v3h2v18h-2v3H9v-3H7V7h2z" />
      <path fill="#e0ac61" d="M10 6h3v20h-3zM17 6h2v20h-2z" />
      <path fill="#797b61" d="M5 9h22v4H5zM5 21h22v4H5z" />
      <path fill="#c6bf94" d="M7 10h18v1H7zM7 22h18v1H7z" />
    </Sprite>
  );
}

export function PixelFlower(props: IconProps) {
  return (
    <Sprite {...props}>
      <path fill="#567835" d="M15 14h3v15h-3zM8 21h5v2h3v3h-5v-2H8zM19 20h6v3h-3v2h-4v-3h1z" />
      <path fill="#b86870" d="M12 2h8v3h5v5h3v7h-6v4H11v-4H5v-7h3V5h4z" />
      <path fill="#edabb0" d="M14 4h4v5h-4zM8 11h6v4H8zM19 11h6v4h-6zM14 15h5v4h-5z" />
      <path fill="#f3ca62" d="M13 10h7v5h-7z" />
    </Sprite>
  );
}
