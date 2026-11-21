/** Small original vector sprites. No remote assets or game files are required. */
export function Sprout({ className = '' }: { className?: string }) {
  return (
    <svg
      className={`pixel-art ${className}`}
      viewBox="0 0 32 32"
      aria-hidden="true"
      shapeRendering="crispEdges"
    >
      <path fill="#77502b" d="M7 27h18v3H7zM10 25h12v2H10z" />
      <path fill="#b4763e" d="M10 27h12v1H10z" />
      <path
        fill="#365b25"
        d="M15 15h3v11h-3zM4 9h8v2h4v3h2v-3h4V9h7v8h-3v3h-7v3h-4v-3H9v-2H6v-3H4z"
      />
      <path fill="#6ba834" d="M6 11h6v2h3v5H9v-3H6zM19 13h4v-2h4v5h-3v2h-5z" />
      <path fill="#a7ce4a" d="M7 11h4v2H7zM22 12h4v2h-4z" />
      <path fill="#e1a334" d="M15 1h2v5h-2zM6 3h2v2H6zM8 5h2v2H8zM25 3h2v2h-2zM23 5h2v2h-2z" />
    </svg>
  );
}

export function Pelican({ className = '' }: { className?: string }) {
  return (
    <svg
      className={`pixel-art ${className}`}
      viewBox="0 0 32 36"
      aria-hidden="true"
      shapeRendering="crispEdges"
    >
      <path fill="#684424" d="M15 2h9v2h2v6h-2v7h-3v3h2v9h-4v3H4v-3H2v-6h3v-3h4v-4h4V5h2z" />
      <path fill="#fffbe7" d="M16 4h7v7h-3v8h-3v3h3v6h-3v2H5v-3H4v-3h5v-4h5V8h2z" />
      <path fill="#e8d8ab" d="M6 25h4v-3h5v4h-3v3H6z" />
      <path
        fill="#b97630"
        d="M22 8h5v2h4v4h-8v-2h-2zM8 32h3v2h5v2H6v-2h2zM17 32h3v2h5v2H15v-2h2z"
      />
      <path fill="#f6b744" d="M23 9h4v2h3v2h-7z" />
      <path fill="#392b20" d="M20 6h2v2h-2z" />
    </svg>
  );
}
