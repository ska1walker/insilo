// Der Titel einer Seite: 28 px, halbfett (CI --am-seitentitel, ABGLEICH
// Paket 5), und derselbe Text vorn im Browser-Tab („Archiv · Insilo“).

import type { ReactNode } from "react";
import { TabTitel } from "@/components/tab-titel";

export function Seitentitel({
  children,
  tab,
  className = "",
}: {
  children: ReactNode;
  /** Text im Tab, wenn er vom sichtbaren Titel abweicht. */
  tab?: string;
  className?: string;
}) {
  return (
    <>
      <TabTitel seite={tab ?? (typeof children === "string" ? children : "")} />
      <h1
        className={`text-[length:var(--am-seitentitel)] font-semibold leading-tight text-text-primaer ${className}`.trim()}
      >{children}</h1>
    </>
  );
}
