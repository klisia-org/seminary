// Course page tabs another installed app adds (privatedocs p028 §1). The server says which
// keys a section has; each key names the component that renders it here. A key with no
// component is skipped, so an app can ship its tab before the portal knows it.
export const courseTabComponents = {
	readings: () => import('@/components/extensions/ReadingsTab.vue'),
	syllabus: () => import('@/components/extensions/SyllabusTab.vue'),
}
