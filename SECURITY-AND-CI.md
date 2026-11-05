# Security and CI/CD for catherinerbell.com

How code gets from a change to the live site, which checks protect it, and
where the secrets live. Branch: `master` (GitHub Pages deploys from it).

## 1. Pipeline at a glance

```
edit on a branch ──► pull request ──► 6 required checks ──► merge to master
                                                                │
              live site keeps last good version ◄── fail ──┐    ▼
                                                           │  Deploy workflow
                                                           │  re-runs all 6 checks
                                                           │  on the merged code
                                                           └─ pass ─► GitHub Pages
                                                                        │
                                                                        ▼
                                                           smoke test https://catherinerbell.com
```

Rule: `deployed = build(master) only if all 6 checks pass`. A failed check
means no deploy, so a bad push cannot take the site down.

## 2. The six required checks (every PR)

| # | Check | What it blocks | Tool |
|---|-------|----------------|------|
| 1 | **Lint** | Python bugs, broken YAML, unsafe or invalid workflows, invalid CSS | ruff, yamllint, actionlint, stylelint |
| 2 | **Build** | Anything that would fail the Jekyll build (incl. bad front matter) | `github-pages` gem, `--strict_front_matter` |
| 3 | **HTML & links** | Invalid HTML, broken internal links, missing images/scripts | html-validate, html-proofer |
| 4 | **Content guard** | Em dashes, "Types" instead of "Points", scripts/iframes in posts, deleted CNAME / Search Console tag / analytics, committed keys or `.env` files | `.github/scripts/content_guard.py` |
| 5 | **Secret scan** | Any credential anywhere in git history (full history, every PR) | gitleaks |
| 6 | **E2E (Playwright)** | Real browser, desktop + mobile: every sitemap page loads with no JS errors, broken images or sideways scroll; nav works; contact form success and failure paths; newsletter signup; Find Your Point game plays to a result; book countdown; feed and sitemap; WCAG critical issues (axe) | Playwright + axe-core |

Plus **after every deploy**: read-only `@smoke` tests run against the live
domain. Forms are never submitted on the live site, and analytics calls are
blocked so tests never count as visitors.

## 3. Where secrets live, and who can reach them

The site has exactly **one real secret**: `ANTHROPIC_API_KEY` (weekly AI
draft). Everything else in the HTML (Formspree form ID, Mailchimp list ID,
Google verification tag, Plausible domain) is public by design: browsers
download it, and it grants no read access. Audit on Nov 5, 2026: **no
secret has ever been committed** in any commit or branch.

| Protection | Effect |
|------------|--------|
| Stored as a GitHub **environment** secret (`ninth-moment`), encrypted | Can't be viewed again by anyone, including admins; only replaced |
| Environment limited to the `master` branch | A workflow edited on any other branch or PR gets nothing |
| Not passed to fork PRs or Dependabot PRs (GitHub default) | Outsiders can't trigger a run that sees it |
| Masked in logs | Shows as `***` if ever printed |
| Only the read-only `draft` job holds it | The job that can push code never sees the key |
| AI output passed via env vars, never `${{ }}` in shell | Malicious AI text can't run commands (this was a real hole, now fixed) |
| AI HTML sanitized + content guard | No script, iframe or event handler can reach a post |
| All third-party Actions pinned to commit SHAs | A hijacked Action tag can't inject code |
| `permissions: {}` default, per-job least privilege | Each job gets only what it needs |
| CODEOWNERS on `.github/` | Workflow changes need the owner's review |

Honest limit: anyone with **write access** to the repo can change a workflow
through a PR and, once merged, it could use the key. So the real perimeter is
(a) who has write access and (b) 2FA on those accounts. Keep collaborators
to the minimum.

## 4. One-time GitHub settings (owner account `thebrownbomber-sudo`)

Do these in order. About 15 minutes.

| Step | Where | Set to |
|------|-------|--------|
| 1 | Open the PR with these files | Wait for all 6 checks to go green |
| 2 | Settings → Pages → Build and deployment → **Source** | **GitHub Actions** (the live site stays up; it switches on the next deploy) |
| 3 | Merge the PR | Actions tab → "Deploy site" goes green, site still loads |
| 4 | console.anthropic.com → API keys | Create a new key named `catherinerbell-ninth-moment`; set a monthly **spend limit**; delete the old key |
| 5 | Settings → Environments → **New environment** `ninth-moment` | Deployment branches: **Selected branches** → `master`. Add secret `ANTHROPIC_API_KEY` = the new key |
| 6 | Settings → Secrets and variables → Actions | **Delete** the old repo-level `ANTHROPIC_API_KEY` (the environment one replaces it) |
| 7 | Settings → Environments → `github-pages` | Deployment branches: **Selected branches** → `master` only |
| 8 | Settings → Rules → Rulesets → New → **Import a ruleset** | Upload `.github/rulesets/protect-master.json` (requires PR + all 6 checks, blocks force-push and deletion, no bypass) |
| 9 | Settings → Code security | Turn ON: Dependabot alerts, Dependabot security updates, **Secret scanning**, **Push protection**, Private vulnerability reporting |
| 10 | Settings → Actions → General | Workflow permissions: **Read repository contents**; keep "Allow GitHub Actions to create and approve pull requests" **checked**; Fork PR workflows: **Require approval for all external contributors** |
| 11 | Settings → Collaborators; Settings → Deploy keys | Remove anyone/anything not needed |
| 12 | github.com/settings/security on every account with write access | **2FA on** (passkey or authenticator app) |

## 5. What changes day to day

| Task | Before | Now |
|------|--------|-----|
| Small fix in GitHub's web editor | Commit straight to `master` | Pencil → edit → **Commit changes...** → choose **"Create a new branch and start a pull request"** → wait ~4 min for green checks → **Merge** |
| Weekly AI post | PR → merge | Same, plus checks run on the PR automatically |
| Dependency updates | None | Dependabot opens weekly PRs; merge when green |

## 6. When something goes wrong

| Symptom | Do this |
|---------|---------|
| A PR check is red | Click **Details** on the check. Content guard and lint failures point at the exact file and line. Playwright failures upload a report with screenshots (Actions run → Artifacts → `playwright-report`) |
| Deploy smoke test red (site live but broken) | Roll back: on the merged PR click **Revert** → merge the revert PR. The previous good version deploys automatically |
| Need to redeploy without changes | Actions → Deploy site → **Run workflow** |
| A key ever lands in git | Treat it as leaked even if deleted: **rotate it first** (step 4), then remove it. Git history and forks keep old copies |

## 7. Running checks locally (optional)

```
bundle install && npm ci && pip install -r requirements-dev.txt
JEKYLL_ENV=production bundle exec jekyll build
python .github/scripts/content_guard.py
npx playwright install chromium && npx playwright test
```
