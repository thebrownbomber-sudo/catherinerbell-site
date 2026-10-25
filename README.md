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

Pushing to `main` on GitHub, with GitHub Pages enabled for this repo
(Settings -> Pages -> Deploy from a branch -> main), rebuilds and
publishes the site automatically. A custom domain and HTTPS are also
configured under Settings -> Pages.
