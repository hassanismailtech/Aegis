export function BrandMark({ className = "size-8" }: { className?: string }) {
  return (
    <svg viewBox="0 0 32 32" fill="none" className={className} aria-hidden="true">
      <path d="M25 6H13L6 13V16H19L26 23V26H7" stroke="currentColor" strokeWidth="4" strokeLinecap="square" strokeLinejoin="miter" />
    </svg>
  );
}
