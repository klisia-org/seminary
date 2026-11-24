// frappe-ui's suggestion popups (the / menu, mentions, emoji), placed inside an open dialog.
//
// frappe-ui appends them to <body>. A modal dialog turns pointer events off outside itself,
// so in a dialog the menu showed but couldn't be clicked; and a click outside the dialog
// would close it anyway. Inside the dialog both work. Elsewhere it is still <body>.
import { createSuggestionExtension as original } from 'frappe-ui/src/components/TextEditor/extensions/suggestion/createSuggestionExtension'

const host = () => document.activeElement?.closest?.('[role="dialog"]') || document.body

export function createSuggestionExtension(options) {
	return original({ ...options, tippyOptions: { appendTo: host, ...(options.tippyOptions || {}) } })
}

export * from 'frappe-ui/src/components/TextEditor/extensions/suggestion/createSuggestionExtension'
