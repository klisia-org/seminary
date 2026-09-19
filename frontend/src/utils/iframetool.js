import { h, createApp } from 'vue'
import { Code2 } from 'lucide-vue-next'
import { safeEmbedUrl } from './urlPolicy.js'

/**
 * EditorJS block for embedding arbitrary iframe/HTML content (e.g. Genially,
 * H5P, custom widgets) that the built-in Embed tool's service whitelist does
 * not cover.
 *
 * The author pastes either a full `<iframe …>` embed snippet or a bare URL into
 * a textarea. **Only the URL is ever used.** The tool extracts the iframe's `src`
 * (or takes the bare URL), checks it, and builds its own responsive iframe with
 * `createElement` -- the author's markup is never written to the DOM.
 *
 * p005a A05-10: this block used to keep `div/iframe/span/p/a/br/img` WITH ALL
 * THEIR ATTRIBUTES through EditorJS's save sanitizer, return any input
 * containing `<iframe` or `<div` verbatim, and assign it to `innerHTML`. That
 * does not run `<script>`, but it does run `onerror`/`onload` -- and the
 * read-only lesson view instantiates this same tool, so one instructor's block
 * executed in every enrolled student's session. Lesson content is EditorJS JSON,
 * which Frappe's server sanitiser skips entirely, so nothing else stood in the way.
 */
export class IframeEmbed {
	static get toolbox() {
		const app = createApp({
			render: () => h(Code2, { size: 18, strokeWidth: 1.5, color: 'black' }),
		})
		const div = document.createElement('div')
		app.mount(div)

		return {
			title: 'Embed (iframe / HTML)',
			icon: div.innerHTML,
		}
	}

	static get isReadOnlySupported() {
		return true
	}

	// What is SAVED is a bare URL (see save()), so no tag needs to survive
	// EditorJS's save sanitizer. `false` strips all markup from the field.
	static get sanitize() {
		return { html: false }
	}

	constructor({ data, readOnly }) {
		this.data = data && typeof data === 'object' ? data : {}
		this.readOnly = readOnly
		this.wrapper = undefined
	}

	render() {
		this.wrapper = document.createElement('div')
		this.wrapper.classList.add('iframe-embed-block')

		if (this.readOnly) {
			this.renderPreview(this.wrapper)
			return this.wrapper
		}

		this.renderEditor()
		return this.wrapper
	}

	/**
	 * The one thing taken from the author's input: a URL. A bare http(s) URL is
	 * used as is; from a pasted snippet only the first iframe's `src` is read,
	 * through DOMParser -- whose document is inert: nothing in it loads or runs.
	 * The URL must be absolute http(s) and on ANOTHER origin, so an embed can
	 * never point back at a file uploaded to this site.
	 */
	static embedUrl(value) {
		const trimmed = (value || '').trim()
		if (!trimmed) return ''
		let src = trimmed
		if (/<\s*iframe/i.test(trimmed)) {
			const doc = new DOMParser().parseFromString(trimmed, 'text/html')
			const frame = doc.querySelector('iframe')
			src = (frame && frame.getAttribute('src')) || ''
		}
		return safeEmbedUrl(src)
	}

	/** The responsive 16:9 shell, built node by node. */
	static buildEmbed(url) {
		const outer = document.createElement('div')
		outer.style.width = '100%'
		const ratio = document.createElement('div')
		ratio.style.position = 'relative'
		ratio.style.paddingBottom = '56.25%'
		ratio.style.height = '0'
		const frame = document.createElement('iframe')
		frame.setAttribute('src', url)
		frame.setAttribute('frameborder', '0')
		frame.setAttribute('scrolling', 'yes')
		frame.setAttribute('allowfullscreen', 'true')
		frame.setAttribute('loading', 'lazy')
		frame.setAttribute('referrerpolicy', 'strict-origin-when-cross-origin')
		frame.style.position = 'absolute'
		frame.style.top = '0'
		frame.style.left = '0'
		frame.style.width = '100%'
		frame.style.height = '100%'
		ratio.appendChild(frame)
		outer.appendChild(ratio)
		return outer
	}

	fillPreview(container, value) {
		container.replaceChildren()
		const url = IframeEmbed.embedUrl(value)
		if (url) {
			container.appendChild(IframeEmbed.buildEmbed(url))
		} else if ((value || '').trim() && !this.readOnly) {
			const note = document.createElement('p')
			note.style.fontSize = '13px'
			note.style.color = '#b45309'
			note.textContent = __(
				'Nothing to embed: paste an https:// link, or an <iframe> code whose src is an https:// link on another site.'
			)
			container.appendChild(note)
		}
	}

	renderPreview(target) {
		const container = document.createElement('div')
		container.classList.add('iframe-embed-preview')
		this.fillPreview(container, this.data.html)
		if (container.childNodes.length) target.appendChild(container)
	}

	renderEditor() {
		this.wrapper.replaceChildren()

		const textarea = document.createElement('textarea')
		textarea.classList.add('iframe-embed-input')
		textarea.value = this.data.html || ''
		textarea.placeholder = __(
			'Paste an embed code (<iframe …>) or a URL — e.g. a Genially share link'
		)
		textarea.style.width = '100%'
		textarea.style.minHeight = '6rem'
		textarea.style.padding = '0.5rem'
		textarea.style.fontFamily = 'monospace'
		textarea.style.fontSize = '13px'
		textarea.style.border = '1px solid #D3D3D3'
		textarea.style.borderRadius = '8px'

		const preview = document.createElement('div')
		preview.classList.add('iframe-embed-preview')
		preview.style.marginTop = '0.75rem'

		const updatePreview = () => {
			this.fillPreview(preview, textarea.value)
		}

		textarea.addEventListener('input', () => {
			this.data.html = textarea.value
			updatePreview()
		})

		updatePreview()
		this.wrapper.appendChild(textarea)
		this.wrapper.appendChild(preview)
	}

	save() {
		// One normal form: the checked URL. A pasted snippet is reduced to its
		// src here, so what is stored can be rendered by anything without trust.
		return {
			html: IframeEmbed.embedUrl(this.data.html),
		}
	}

	validate(savedData) {
		return Boolean(savedData.html && savedData.html.trim())
	}
}
