import type { ReactNode } from "react";

const ATENA_REPLY_URL =
  "https://www.atenareply.com/?utm_source=tokenpricing&utm_medium=referral&utm_campaign=dashboard-footer";

export function Footer() {
  return (
    <footer className="border-t">
      <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-x-8 gap-y-4 px-4 py-6 md:px-6">
        <p className="m-0 text-xs text-muted-foreground">
          Built on <FooterLink href="https://github.com/Atena-IT/tokenpricing">tokenpricing</FooterLink> · inspired
          by <FooterLink href="https://mrunreal.github.io/LLMTracker/">LLMTracker</FooterLink>
        </p>
        <a
          href={ATENA_REPLY_URL}
          target="_blank"
          rel="noreferrer"
          className="group flex items-center gap-3"
          aria-label="Atena Reply — visit our main website"
        >
          <span className="text-xs text-muted-foreground transition-colors group-hover:text-foreground">
            A project by
          </span>
          <span className="inline-flex items-center rounded-lg border bg-white px-4 py-2.5 shadow-sm transition-shadow group-hover:shadow-md">
            <img src={`${import.meta.env.BASE_URL}atenareply.png`} alt="Atena Reply" className="h-10 w-auto" />
          </span>
        </a>
      </div>
    </footer>
  );
}

function FooterLink({ href, children }: { href: string; children: ReactNode }) {
  return (
    <a
      href={href}
      target="_blank"
      rel="noreferrer"
      className="font-medium text-foreground underline decoration-border underline-offset-2 transition-colors hover:decoration-foreground"
    >
      {children}
    </a>
  );
}
