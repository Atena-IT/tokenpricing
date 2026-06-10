import type { ReactNode } from "react";

const ATENA_REPLY_URL =
  "https://www.reply.com/atena-reply/en?utm_source=tokenpricing&utm_medium=referral&utm_campaign=dashboard-footer";

export function Footer() {
  return (
    <footer className="border-t">
      <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-x-8 gap-y-4 px-4 py-6 md:px-6">
        <div className="flex flex-col gap-1.5 text-xs text-muted-foreground">
          <p className="m-0">
            Canonical pricing database synchronized every six hours from{" "}
            <FooterLink href="https://openrouter.ai">OpenRouter</FooterLink> and{" "}
            <FooterLink href="https://github.com/BerriAI/litellm">LiteLLM</FooterLink>.
          </p>
          <p className="m-0">
            Raw data:{" "}
            <FooterLink href="https://raw.githubusercontent.com/Atena-IT/tokenpricing/main/database/current/prices.json">
              prices.json
            </FooterLink>{" "}
            ·{" "}
            <FooterLink href="https://raw.githubusercontent.com/Atena-IT/tokenpricing/main/database/changelog/latest.json">
              changelog.json
            </FooterLink>
          </p>
          <p className="m-0">
            Built on <FooterLink href="https://github.com/Atena-IT/tokenpricing">tokenpricing</FooterLink> · inspired
            by <FooterLink href="https://mrunreal.github.io/LLMTracker/">LLMTracker</FooterLink>
          </p>
        </div>
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
          <span className="inline-flex items-center rounded-lg border bg-white px-3 py-2 shadow-sm transition-shadow group-hover:shadow-md">
            <img src={`${import.meta.env.BASE_URL}atena-reply.png`} alt="Atena Reply" className="h-7 w-auto" />
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
