/**
 * `dir="auto"` on the lesson's text blocks, while editing and when shown (decision
 * 109 §4), so a Hebrew line in an English lesson is laid out right to left.
 *
 * EditorJS builds its blocks itself and saves no attributes, so the direction is set on
 * the blocks as they appear rather than stored. An author's own `dir` is left alone.
 */
const TEXT_BLOCKS = [
	'.ce-paragraph',
	'.ce-header',
	'.cdx-nested-list__item-content',
	'.tc-cell',
	'blockquote',
].join(', ')

const watched = new WeakSet()

export function autoDirection(holder) {
	// A page renders its editor again into the same holder: one observer is enough.
	if (!holder || watched.has(holder)) return
	watched.add(holder)
	const apply = () => {
		holder.querySelectorAll(TEXT_BLOCKS).forEach((el) => {
			if (!el.hasAttribute('dir')) el.setAttribute('dir', 'auto')
		})
	}
	apply()
	new MutationObserver(apply).observe(holder, { childList: true, subtree: true })
}
