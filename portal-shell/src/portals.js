/**
 * The canonical seminary-ecosystem portal registry (ADR 074).
 *
 * A portal is a **separately-deployed SPA with its own base path**. Anything
 * reachable without leaving the current SPA is navigation and belongs in that
 * app's sidebar, not here — which is why `/seminary/alumni`, `/seminary/partner`,
 * `/seminary/community` and `/seminary/culminating-project` are absent: they are
 * routes of the seminary SPA, and listing them here cost a full page reload to
 * reach a view the sidebar already linked to.
 *
 * This list is exported from portal-shell (rather than copied into each
 * consumer's `main.js`) because the three hand-maintained copies had drifted:
 * aretenic pointed `partner` at `/seminary/alumni` and frappe_giving labelled
 * Academics "Courses". ADR 011 accepted the duplication "for three portals" and
 * flagged it as a residual risk; this retires it without the `Portal Shell
 * Settings` doctype ADR 011 proposed, which three static entries don't justify.
 *
 * Optional apps carry a `when(session)` predicate backed by an installed-apps
 * flag from the consumer's session fetcher. A tile is justified by
 * *reachability*, not by role alone: gating Donate on a role would still have
 * pointed at a 404 on a site without frappe_giving, because an uninstalled app
 * is an absent route, not a permissions question.
 */
export const SEMINARY_PORTALS = [
  {
    id: 'student',
    label: 'Academics',
    description: 'Academic Portal',
    url: '/seminary',
  },
  {
    id: 'aretenic',
    label: 'Aretenic',
    description: 'Quality Management',
    url: '/aretenic',
    // Roles per ADR 034's taxonomy. 'Academics User' was renamed to
    // 'Program Chair'; gating on the old name silently hid this tile from every
    // chair who wasn't also an Instructor.
    roles: ['Program Chair', 'Instructor', 'Seminary Manager'],
    when: (s) => !!s?.has_aretenic,
  },
  {
    id: 'donor',
    label: 'Donate',
    description: 'Donor Portal',
    url: '/donate/donorportal',
    // No role gate — anyone may donate.
    when: (s) => !!s?.has_giving,
  },
]
