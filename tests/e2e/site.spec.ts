import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import { isolate, sitePaths, watchForErrors } from "./helpers";

const paths = sitePaths();

test.beforeEach(async ({ page }) => {
  await isolate(page);
});

// ---------------------------------------------------------------------------
// @smoke: read-only checks. These also run against the LIVE site right after
// every deploy, so they must never submit a form or change anything.
// ---------------------------------------------------------------------------
test.describe("every page @smoke", () => {
  for (const p of paths) {
    test(`loads cleanly: ${p}`, async ({ page, baseURL }) => {
      const watcher = watchForErrors(page, new URL(baseURL!).origin);
      const res = await page.goto(p);
      expect(res?.status(), `HTTP status for ${p}`).toBeLessThan(400);
      await expect(page).toHaveTitle(/Catherine R\. Bell/);
      await expect(page.locator("header")).toBeVisible();
      await expect(page.locator("main")).not.toBeEmpty();
      await expect(page.locator("#newsletter-form")).toBeVisible();

      // Every image actually loaded (no broken image icons).
      const broken = await page.$$eval("main img", (imgs) =>
        (imgs as HTMLImageElement[])
          .filter((i) => i.loading !== "lazy" && i.complete && i.naturalWidth === 0)
          .map((i) => i.src),
      );
      expect(broken, "broken images").toEqual([]);

      // No sideways scrolling (the classic mobile layout break).
      const overflow = await page.evaluate(
        () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
      );
      expect(overflow, "horizontal overflow in px").toBeLessThanOrEqual(1);

      watcher.assertClean();
    });
  }

  test("feed.xml is valid and lists posts", async ({ request }) => {
    const res = await request.get("/feed.xml");
    expect(res.ok()).toBeTruthy();
    const xml = await res.text();
    expect(xml).toContain("<feed");
    expect((xml.match(/<entry>/g) ?? []).length).toBeGreaterThan(0);
  });

  test("sitemap.xml lists the main pages", async ({ request }) => {
    const xml = await (await request.get("/sitemap.xml")).text();
    for (const p of ["/book/", "/about/", "/coaching/", "/contact/", "/blog/"]) {
      expect(xml).toContain(`catherinerbell.com${p}`);
    }
  });

  test("Search Console verification tag is present", async ({ page }) => {
    await page.goto("/");
    await expect(page.locator('meta[name="google-site-verification"]')).toHaveCount(1);
  });

  test("book page countdown runs and retailer links are live https", async ({ page }) => {
    await page.goto("/book/");
    await expect(page.locator('[data-unit="days"]')).not.toHaveText("\u2014");
    const hrefs = await page.$$eval("#pre-order a[href]", (as) =>
      (as as HTMLAnchorElement[]).map((a) => a.href),
    );
    expect(hrefs.length).toBeGreaterThan(0);
    for (const h of hrefs) expect(h, "retailer link").toMatch(/^https:\/\//);
  });
});

// ---------------------------------------------------------------------------
// Interactive flows. Local only: third-party endpoints are faked.
// ---------------------------------------------------------------------------
test.describe("interactive flows", () => {
  test.skip(!!process.env.BASE_URL, "never submit real forms on the live site");

  test("header navigation reaches every section", async ({ page, isMobile }) => {
    test.skip(isMobile, "desktop nav");
    await page.goto("/");
    for (const [label, url] of [
      ["The Book", "/book/"],
      ["About", "/about/"],
      ["Work With Catherine", "/coaching/"],
      ["Media", "/media/"],
      ["Blog", "/blog/"],
      ["Contact", "/contact/"],
    ]) {
      await page.locator("header").getByRole("link", { name: label, exact: true }).first().click();
      await expect(page).toHaveURL(new RegExp(`${url}$`));
    }
  });

  test("contact form submits to Formspree and shows success", async ({ page }) => {
    let posted: string | undefined;
    await page.route("https://formspree.io/**", async (route) => {
      posted = route.request().postData() ?? "";
      await route.fulfill({ status: 200, contentType: "application/json", body: '{"ok":true}' });
    });
    await page.goto("/contact/");
    await page.fill("#name", "Playwright Test");
    await page.fill("#cemail", "test@example.com");
    await page.fill("#subject", "CI check");
    await page.fill("#message", "Automated test, please ignore.");
    await page.getByRole("button", { name: "Send message" }).click();
    await expect(page.locator(".contact-status")).toContainText("Thank you");
    expect(posted).toContain("Playwright Test");
  });

  test("contact form shows an error if Formspree fails", async ({ page }) => {
    await page.route("https://formspree.io/**", (r) => r.fulfill({ status: 500, body: "" }));
    await page.goto("/contact/");
    await page.fill("#name", "x");
    await page.fill("#cemail", "x@example.com");
    await page.fill("#subject", "x");
    await page.fill("#message", "x");
    await page.getByRole("button", { name: "Send message" }).click();
    await expect(page.locator(".contact-status")).toContainText("Something went wrong");
  });

  test("newsletter signup posts to Mailchimp", async ({ page }) => {
    let hit = false;
    await page.route(/list-manage\.com/, async (route) => {
      hit = true;
      await route.fulfill({ status: 200, body: "" });
    });
    await page.goto("/");
    await page.fill("#mce-EMAIL", "test@example.com");
    await page.locator("#newsletter-form button[type=submit]").click();
    await expect(page.locator(".newsletter-status")).toContainText("on the list");
    expect(hit).toBe(true);
  });

  test("newsletter rejects an invalid email", async ({ page }) => {
    await page.goto("/");
    await page.fill("#mce-EMAIL", "not-an-email");
    await page.locator("#newsletter-form button[type=submit]").click();
    await expect(page.locator(".newsletter-status")).toContainText("valid email");
  });

  test("Find Your Point game plays through to a result", async ({ page }) => {
    await page.goto("/find-your-point/");
    for (let round = 1; round <= 9; round++) {
      await expect(page.locator("#fyp-progress")).toHaveText(`Round ${round} of 9`);
      await page.locator("#fyp-opts .fyp-opt").first().click();
    }
    await expect(page.locator("#fyp-results")).toBeVisible();
    await expect(page.locator('[id^="fyp-reveal-"]:visible')).toHaveCount(1);
    await page.locator("#fyp-restart").click();
    await expect(page.locator("#fyp-progress")).toHaveText("Round 1 of 9");
  });
});

// ---------------------------------------------------------------------------
// Accessibility: blocks serious/critical WCAG problems on key pages.
// ---------------------------------------------------------------------------
test.describe("accessibility", () => {
  test.skip(!!process.env.BASE_URL, "local only");
  for (const p of ["/", "/book/", "/contact/", "/coaching/", "/find-your-point/"]) {
    test(`no critical a11y violations: ${p}`, async ({ page }) => {
      await page.goto(p);
      const results = await new AxeBuilder({ page })
        .withTags(["wcag2a", "wcag2aa"])
        .disableRules(["color-contrast"]) // tracked separately; design decision
        .analyze();
      const blocking = results.violations.filter((v) => v.impact === "critical");
      expect(
        blocking.map((v) => `${v.id}: ${v.help} (${v.nodes.length} element(s))`),
      ).toEqual([]);
    });
  }
});
