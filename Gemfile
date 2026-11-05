source "https://rubygems.org"

gem "github-pages", group: :jekyll_plugins
gem "jekyll-feed"
gem "jekyll-sitemap"

# CI-only: validates the built site (broken links, missing images, bad HTML).
group :test do
  gem "html-proofer", "~> 5.0"
end

# Ruby 3+ no longer bundles webrick, which `jekyll serve` needs locally.
gem "webrick", "~> 1.8"

# Windows and JRuby does not include zoneinfo files
install_if -> { RUBY_PLATFORM =~ %r!mingw|mswin|java! } do
  gem "tzinfo", ">= 1", "< 3"
  gem "tzinfo-data"
end

gem "wdm", "~> 0.2.0", install_if: Gem.win_platform?
