// Frappe used to vendor the PostHog browser client at
// `frappe/public/js/lib/posthog.js`, which this module reached into with a
// relative path that escaped the app directory. Frappe v16 removed the whole
// integration (`refactor!: Drop posthog integration`, #39990) and replaced it
// with `frappe.utils.telemetry.pulse`, so that file no longer exists and the
// import broke the build outright — first surfaced by a Press image build,
// because our bench is pinned to an older frappe that still carried it.
//
// Nothing here is lost: every function below already no-ops unless
// `posthog_host` and `posthog_project_id` are set in site config, which they
// never are. `window.posthog` is now simply always undefined, so the guards
// that were previously vestigial are the ones doing the work. Whether we adopt
// pulse or drop product analytics altogether is an open decision.
import { createResource } from 'frappe-ui'

declare global {
  interface Window {
    posthog: any
  }
}

type PosthogSettings = {
  posthog_project_id: string
  posthog_host: string
  enable_telemetry: boolean
  telemetry_site_age: number
}

interface CaptureOptions {
  data: {
    user: string
    [key: string]: string | number | boolean | object
  }
}

let posthog: typeof window.posthog = window.posthog

// Posthog Settings
let posthogSettings = createResource({
  url: 'seminary.seminary.telemetry.get_posthog_settings',
  cache: 'posthog_settings',
  onSuccess: (ps: PosthogSettings) => initPosthog(ps),
})

let isTelemetryEnabled = () => {
  if (!posthogSettings.data) return false

  return (
    posthogSettings.data.enable_telemetry &&
    posthogSettings.data.posthog_project_id &&
    posthogSettings.data.posthog_host
  )
}

// Posthog Initialization
function initPosthog(ps: PosthogSettings) {
  if (!isTelemetryEnabled()) return
  // No client is loaded any more (see the note at the top of this file), so
  // bail rather than throwing if a site ever does set the posthog config keys.
  if (!posthog?.init) return

  posthog.init(ps.posthog_project_id, {
    api_host: ps.posthog_host,
    person_profiles: 'identified_only',
    autocapture: false,
    capture_pageview: true,
    capture_pageleave: true,
    enable_heatmaps: false,
    disable_session_recording: false,
    loaded: (ph: typeof posthog) => {
      window.posthog = ph
      ph.identify(window.location.hostname)
    },
  })
}

// Posthog Functions
function capture(
  event: string,
  options: CaptureOptions = { data: { user: '' } },
) {
  if (!isTelemetryEnabled()) return
  window.posthog.capture(`lms_${event}`, options)
}

function startRecording() {
}

function stopRecording() {
}

// Posthog Plugin
function posthogPlugin(app: any) {
    app.config.globalProperties.posthog = posthog
    if (!window.posthog?.length) posthogSettings.fetch()
}

export {
  posthog,
  posthogSettings,
  posthogPlugin,
  capture,
  startRecording,
  stopRecording,
}