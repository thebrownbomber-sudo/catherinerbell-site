# catherinerbell.com

Jekyll source for Catherine R. Bell's website.

## Local preview

```
bundle install
bundle exec jekyll serve
```

Then open http://localhost:4000

## Adding a blog post

Add a new file to `_posts/`, named `YYYY-MM-DD-slug.html` (or `.md`), with
front matter like:

```
---
layout: post
title: "Post title"
author: "Catherine R. Bell"
description: "One or two sentences for search/social previews."
---

Post content goes here.
```

For a post written by the Ninth Moment AI agent, use:

```
---
layout: post
title: "Post title"
author: "The Ninth Moment"
ai_drafted: true
description: "..."
---
```

## Site config

Nav links, social links, analytics domain, and the book's pub date all live
in `_config.yml`.

## Deploying

Changes go through a pull request into `master`. Six automated checks
(lint, build, HTML and links, content guard, secret scan, Playwright
end-to-end tests) must pass before a PR can merge, and the deploy workflow
re-runs them before publishing to GitHub Pages. A failing check means the
live site is never touched.

Full details, required GitHub settings, and rollback steps:
[SECURITY-AND-CI.md](SECURITY-AND-CI.md).
