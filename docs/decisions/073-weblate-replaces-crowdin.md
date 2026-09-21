# 073 — Weblate replaces Crowdin for translation hosting

**Date:** 2026-09-21
**Status:** Accepted

## Context

Translations were hosted on a [Crowdin](https://crowdin.com/project/seminary-erp) project and moved
in and out of the repository by `.github/workflows/crowdin.yml`: a push to `main` touching
`seminary/locale/main.pot` uploaded sources, and a 04:00 UTC cron downloaded translations onto
`l10n_crowdin_translations` and opened a PR.

Two things pushed us off it.

The first is the word budget. [`crowdin.yml`](../../crowdin.yml) carried a large commented-out block
disabling documentation translation entirely, with the reason stated inline: *"The docs corpus does
not fit the Crowdin free-tier word budget, so the app strings in main.pot get the whole
allowance."* The `docs/en/**/*.md` path trigger in the workflow was commented out to match. So the
Tier 3 operational docs that [ADR 001](001-documentation-architecture.md) says Crowdin manages have
in fact never been translated through it — the free tier could not hold both them and the 6,923
strings in `main.pot`. Any growth in either corpus made that worse, and the paid tier prices per
word on a corpus that grows with every doctype we add.

The second is that the hosted service owns the data. The `.po` files are committed, so the
translation *content* was never at risk, but translator accounts, glossary, translation memory and
review history lived somewhere we do not control and could not back up with the rest of the system.

Weblate is the same shape of tool — a web UI over gettext that talks git — but self-hostable, and
we already run a Lightsail host with headroom. The decisive detail for migration cost is that
`seminary/locale/*.po` is the real state: whatever Crowdin knew that mattered is already in the
repository, so switching platforms is a matter of pointing a new tool at the same files rather than
exporting anything.

## Decision

Self-host Weblate at **translate.seminaryerp.org** and retire the Crowdin project.

- The stack runs in Docker under `/opt/weblate` (Weblate pinned at `2026.9.1.2`, PostgreSQL 17,
  Redis 7), isolated from the Frappe bench that owns the host — it does not touch the bench's
  MariaDB, Redis or `conf.d/frappeb.conf`. Weblate binds to `127.0.0.1:8080`; the host nginx
  terminates TLS and reverse-proxies from a vhost in `sites-enabled/`, which `bench setup nginx`
  does not regenerate.
- A component per app under one `klisia` project, configured to mirror exactly what `crowdin.yml`
  declared: bilingual gettext, `filemask` `<app>/locale/*.po`, `new_base` `<app>/locale/main.pot`.
- Registration is closed and login is required. Translators are invited by an admin rather than
  self-registering, which is how the Crowdin project was actually run.
- Translations return to GitHub as **pull requests against `main`**, preserving the review step the
  Crowdin workflow had. Nothing writes to `main` unattended.
- `crowdin.yml` and `.github/workflows/crowdin.yml` are deleted rather than left disabled, so there
  is one translation pipeline and no second job that can open competing PRs against the same `.po`
  files.

Documentation translation stays **out of scope for now**. Self-hosting removes the word budget that
forced it off, but turning the docs corpus on is a separate decision with its own review burden, and
this ADR does not make it.

## Consequences

Easier: the word budget disappears, so adding doctypes no longer competes with docs for a
translation allowance, and the docs corpus becomes a decision we can make on its merits.
Translation memory and glossary become ours, and land in whatever backs up the host. Because the
component reads the repository directly, `git log` on `seminary/locale/` remains the full history of
what changed — the same property that made the migration cheap keeps the platform swappable.

Harder: we now operate it. Weblate is pinned deliberately — it ships CalVer releases frequently and
an unattended jump migrates the database — so upgrades are a maintenance task somebody has to
schedule, and the PostgreSQL volume needs to enter the backup story. A hosted service absorbed both.

Open questions:

- **Backups.** The `weblate_postgres-data` and `weblate_weblate-data` volumes hold everything that
  is not in git — accounts, memory, glossary, review history. Nothing backs them up yet.
- **Mail.** No SMTP relay is configured, so Weblate cannot send invitations, password resets or
  notifications. Translators cannot be onboarded until this is settled.
- **Docs corpus.** Whether to translate `docs/en/**/*.md` now that the budget no longer forbids it.
  [ADR 001](001-documentation-architecture.md) and
  [ADR 020](020-workspace-and-dashboard-localization-workaround.md) describe the pipeline as
  "Crowdin"; both are accurate about the mechanism and wrong only about the vendor name.
