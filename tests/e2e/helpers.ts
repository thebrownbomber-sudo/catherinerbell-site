import { type Page, expect } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";

/** Every page Google knows about, read from the built sitemap. */
export function sitePaths(): string[] {
  const fallback = ["/", "/book/", "/about/", "/coaching/", "/media/", "/blog/", "/contact/", "/find-your-point/"];
  const sitemap = path.join(__dirname, "..", "..", "_site", "sitemap.xml");
  if (!fs.existsSync(sitemap)) return fallback;
  const xml = fs.readFileSync(sitemap, "utf8");
  const paths = [...xml.matchAll(/<loc>https?:\/\/[^/]+(\/[^<]*)<\/loc>/g)].map((m) => m[1]);
  return paths.length ? paths : fallback;
}

/**
 * Blocks analytics (so tests never count as real visitors) and lets the
 * caller fake third-party form endpoints. Third-party fonts/CDNs are allowed
 * through but their failures are ignored, so a slow font CDN can't fail CI.
 */
export async function isolate(page: Page) {
  await page.route(/plausible\.io/, (r) => r.abort());
}

/** Collects console errors and failed same-origin requests while a page runs. */
export function watchForErrors(page: Page, origin: string) {
  const errors: string[] = [];
  page.on("console", (msg) => {
    if (msg.type() === "error" && !/plausible|fonts\.g|net::ERR_FAILED/i.test(msg.text())) {
      errors.push(`console: ${msg.text()}`);
    }
  });
  page.on("pageerror", (err) => errors.push(`js error: ${err.message}`));
  page.on("response", (res) => {
    if (res.url().startsWith(origin) && res.status() >= 400) {
      errors.push(`${res.status()} ${res.url()}`);
    }
  });
  return {
    assertClean: () => expect(errors, errors.join("\n")).toEqual([]),
  };
}
