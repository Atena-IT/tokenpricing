import { defineConfig } from "vitepress";

export default defineConfig({
  title: "tokenpricing",
  description:
    "Canonical AI model pricing — CLI, SDKs, webhook notifications, and a live dashboard for 3,000+ models.",
  base: process.env.GITHUB_PAGES ? "/tokenpricing/docs/" : "/",
  head: [["link", { rel: "icon", type: "image/svg+xml", href: "/favicon.svg" }]],
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
