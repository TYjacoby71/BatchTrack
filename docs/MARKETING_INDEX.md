Marketing content workspace

This directory contains public-facing content for the BatchTrack marketing site. It is framework-agnostic Markdown/MDX so you can drop it into any site generator (Next.js App Router + MDX recommended).

Suggested tech stack
- Next.js 14 (App Router)
- Tailwind CSS
- MDX for content
- Vercel for hosting

Structure
- content/pages/* – Top-level marketing pages (landing, features, about)
- content/docs/* – Getting started docs
- content/help/* – Focused help articles
- content/legal/* – Privacy and Terms templates
- content/changelog/* – Changelog entries
- content/emails/* – Email sequences (plain text)
- content/social/* – Social media drafts
- content/specs/* – Planning specs (e.g., Whop integration)
- public/* – Static assets like robots.txt, sitemap.xml

How to integrate with Next.js (example)
1. Install MDX: @next/mdx and configure in next.config.mjs.
2. Create routes in app/(site)/ that read MDX files from marketing/content/*.
3. Optionally add a simple file loader to map content/pages/*.mdx to routes /, /features, /about.
4. Add Plausible/GA script and Open Graph metadata.

Notes
- Legal pages are templates; have counsel review before launch.
- Replace placeholder company details in legal docs and footer.
- Update public/sitemap.xml domain before deploying.
