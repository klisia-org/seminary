const GREEN = new Set(['pass', 'passed', 'completed', 'paid', 'fulfilled', 'waived', 'approved', 'accepted'])
const BLUE = new Set(['enrolled', 'in progress', 'submitted', 'active', 'under review'])
const RED = new Set(['fail', 'failed', 'overdue', 'rejected'])
const ORANGE = new Set(['withdrawn', 'draft', 'pending', 'unpaid', 'not started', 'awaiting payment', 'revisions required'])

export function statusTheme(status) {
	const s = (status || '').toString().trim().toLowerCase()
	if (GREEN.has(s)) return 'green'
	if (BLUE.has(s)) return 'blue'
	if (RED.has(s)) return 'red'
	if (ORANGE.has(s)) return 'orange'
	return 'gray'
}
