import { h, createApp } from 'vue'
import { Code2 } from 'lucide-vue-next'

/**
 * EditorJS block for embedding arbitrary iframe/HTML content (e.g. Genially,
 * H5P, custom widgets) that the built-in Embed tool's service whitelist does
 * not cover.
 *
 * The author pastes either a full `<iframe …>` embed snippet or a bare URL into
 * a textarea; it is rendered live while editing and as the real iframe in the
 * read-only lesson view. The raw markup is preserved through EditorJS's save
 * sanitizer via the `sanitize` getter below (a tag rule of `true` keeps the tag
 * and all of its attributes).
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

	// Keep the embed markup intact when EditorJS sanitizes the saved block data.
	// A tag mapped to `true` is preserved together with all of its attributes.
	static get sanitize() {
		return {
			html: {
				div: true,
				iframe: true,
				span: true,
				p: true,
				a: true,
				br: true,
				img: true,
			},
		}
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
	 * Normalise the author's input into renderable HTML. A full iframe/HTML
	 * snippet is used as-is; a bare URL is wrapped in a responsive 16:9 iframe.
	 */
	toEmbedHtml(value) {
		const trimmed = (value || '').trim()
		if (!trimmed) return ''
		if (trimmed.includes('<iframe') || trimmed.includes('<div')) return trimmed
		if (/^https?:\/\//i.test(trimmed)) {
			return (
				'<div style="width: 100%;"><div style="position: relative; padding-bottom: 56.25%; height: 0;">' +
				`<iframe src="${trimmed}" ` +
				'style="position: absolute; top: 0; left: 0; width: 100%; height: 100%;" ' +
				'frameborder="0" scrolling="yes" allowfullscreen="true" allownetworking="all"></iframe>' +
				'</div></div>'
			)
		}
		return ''
	}

	renderPreview(target) {
		const html = this.toEmbedHtml(this.data.html)
		if (!html) return
		const container = document.createElement('div')
		container.classList.add('iframe-embed-preview')
		container.innerHTML = html
		target.appendChild(container)
	}

	renderEditor() {
		this.wrapper.innerHTML = ''

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
			preview.innerHTML = this.toEmbedHtml(textarea.value)
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
		return {
			html: (this.data.html || '').trim(),
		}
	}

	validate(savedData) {
		return Boolean(savedData.html && savedData.html.trim())
	}
}
