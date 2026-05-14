/**
 * Wraps every page in a fade-in container. Next.js App Router remounts
 * this template on every route change, so the `.page-in` animation
 * re-fires — giving navigation a smooth 220ms cross-fade instead of
 * a hard snap. `prefers-reduced-motion` is respected via globals.css.
 */
export default function Template({ children }: { children: React.ReactNode }) {
  return <div className="page-in">{children}</div>;
}
