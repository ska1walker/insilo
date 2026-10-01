/**
 * Route template. Pages used to fade in here (`.page-in`); the AImighty
 * CI moves states, not whole pages, and never fades in running text
 * (ABGLEICH IN-R6, kern/nicht.md). Kept as a plain pass-through so the
 * route tree stays the same.
 */
export default function Template({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}
