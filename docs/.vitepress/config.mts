import { defineConfig } from "vitepress";

export default defineConfig({
  title: "tokenpricing",
  description:
    "Canonical AI model pricing — CLI, SDKs, webhook notifications, and a live dashboard for 3,000+ models.",
  base: process.env.GITHUB_PAGES ? "/tokenpricing/docs/" : "/",
  head: [
    ["link", { rel: "icon", type: "image/svg+xml", href: "/favicon.svg" }],
    // Fonts shared with the dashboard: Inter + JetBrains Mono (Google Fonts),
    // Sentient (Fontshare, same source the dashboard uses).
    ["link", { rel: "preconnect", href: "https://fonts.googleapis.com" }],
    ["link", { rel: "preconnect", href: "https://fonts.gstatic.com", crossorigin: "" }],
    ["link", { rel: "preconnect", href: "https://api.fontshare.com", crossorigin: "" }],
    [
      "link",
      {
        rel: "stylesheet",
        href: "https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600;700&display=swap",
      },
    ],
    [
      "link",
      {
        rel: "stylesheet",
        href: "https://api.fontshare.com/v2/css?f[]=sentient@400,700&display=swap",
      },
    ],
  ],
  themeConfig: {
    logo: "/favicon.svg",
    nav: [
      { text: "Quickstart", link: "/quickstart" },
      { text: "CLI", link: "/cli" },
      { text: "SDKs", link: "/sdks" },
      { text: "Notifications", link: "/notifications" },
      { text: "Dashboard", link: "https://atena-it.github.io/tokenpricing/" },
    ],
    sidebar: [
      {
        text: "Getting started",
        items: [
          { text: "Quickstart", link: "/quickstart" },
          { text: "CLI reference", link: "/cli" },
          { text: "Python & TypeScript SDKs", link: "/sdks" },
        ],
      },
      {
        text: "Services",
        items: [
          { text: "Webhook notifications", link: "/notifications" },
          { text: "Canonical database", link: "/database" },
        ],
      },
      {
        text: "Architecture decisions",
        items: [
          { text: "Overview", link: "/adr/" },
          {
            text: "0001 · SQLite read layer",
            link: "/adr/0001-canonical-pricing-database-storage",
          },
        ],
      },
    ],
    socialLinks: [{ icon: "github", link: "https://github.com/Atena-IT/tokenpricing" }],
    search: { provider: "local" },
    footer: {
      message: "Pricing data synchronized from OpenRouter and LiteLLM every six hours.",
      copyright:
        'A project by <a href="https://www.atenareply.com/?utm_source=tokenpricing&utm_medium=referral&utm_campaign=docs-footer">Atena Reply</a>',
    },
  },
});
