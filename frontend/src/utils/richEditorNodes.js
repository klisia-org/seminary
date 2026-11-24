/**
 * The rich-text editor's embeds, videos and text direction (decision 109).
 *
 * frappe-ui's iframe and video nodes save `<iframe>` and `<video>` as they are, and
 * the sanitisers remove the iframe and every <track>. These versions save what
 * survives, and the page builds the rest when it is shown (see embed.js):
 *
 *   embed  <figure data-embed="URL"><a href="URL">title</a></figure>      (§1)
 *   video  <video src="URL" data-captions='[{src, srclang, label}]'>       (§5)
 *
 * and give text blocks `dir="auto"`, so a line's own script sets its direction (§4).
 */
import { Extension } from '@tiptap/core'
import { reactive } from 'vue'
import { VueNodeViewRenderer } from '@tiptap/vue-3'
import { IframeExtension } from '../../node_modules/frappe-ui/src/components/TextEditor/extensions/iframe/iframe-extension'
import VideoExtension from '../../node_modules/frappe-ui/src/components/TextEditor/video-extension'
import RichTextVideo from '../components/RichTextVideo.vue'
import { safeEmbedUrl } from './urlPolicy.js'
import { readCaptions } from './embed.js'
import { VIDEO_ACCEPT, isVideo, fileType } from './mediaTypes.js'

/** Videos being uploaded, by the id on their placeholder node: { percent, name }. */
export const videoUploads = reactive({})

const showError = (message) =>
	import('frappe-ui').then(({ toast }) => toast.error(message)).catch(() => {})

function findUpload(doc, id) {
	let found = null
	doc.descendants((node, pos) => {
		if (found === null && node.type.name === 'video' && node.attrs.upload === id) found = pos
		return found === null
	})
	return found
}

const int = (value) => {
	const n = parseInt(value, 10)
	return Number.isFinite(n) ? n : null
}

export const RichEmbed = IframeExtension.extend({
	addOptions() {
		// Any site but this one, as the lesson iframe block allows: the address is
		// checked by safeEmbedUrl here, on save and when shown.
		return { ...this.parent?.(), allowedDomains: [] }
	},

	// Text direction rides on the embed: frappe-ui's TextEditor takes its node list as
	// it is, and the embed is the node every editor here has.
	addExtensions() {
		return [TextDirection]
	},

	parseHTML() {
		return [
			{
				tag: 'figure[data-embed]',
				priority: 100,
				getAttrs: (el) => {
					const src = safeEmbedUrl(el.getAttribute('data-embed'))
					if (!src) return false
					return {
						src,
						title: (el.querySelector('a')?.textContent || '').trim() || null,
						width: int(el.getAttribute('data-width')),
						height: int(el.getAttribute('data-height')),
						align: el.getAttribute('data-align') || 'center',
					}
				},
			},
			// Pasted embed codes, and content written before decision 109.
			...(this.parent?.() || []),
		]
	},

	renderHTML({ node }) {
		const { src, title, width, height, align } = node.attrs
		const attrs = { 'data-embed': src, 'data-align': align || 'center' }
		if (width) attrs['data-width'] = String(width)
		if (height) attrs['data-height'] = String(height)
		return ['figure', attrs, ['a', { href: src }, title || src]]
	},

	addCommands() {
		const parent = this.parent?.() || {}
		return {
			...parent,
			setIframe: (options) => (props) =>
				safeEmbedUrl(options?.src) && options?.title?.trim()
					? parent.setIframe({ ...options, title: options.title.trim() })(props)
					: false,
		}
	},
})

export const RichVideo = VideoExtension.extend({
	addAttributes() {
		return {
			src: { default: null },
			captions: {
				default: [],
				parseHTML: (el) => readCaptions(el.getAttribute('data-captions')),
				renderHTML: (attrs) =>
					attrs.captions?.length ? { 'data-captions': JSON.stringify(attrs.captions) } : {},
			},
			// A placeholder's upload id, while its file uploads. Never saved.
			upload: { default: null, parseHTML: () => null, renderHTML: () => ({}) },
		}
	},

	addCommands() {
		const parent = this.parent?.() || {}
		return {
			...parent,
			// A placeholder with the upload's progress, replaced by the video when it is in.
			// The upload function is called with { onProgress }; one that ignores it (frappe-ui's
			// own) still shows the placeholder, without a percentage.
			uploadVideo:
				(file) =>
				({ editor, commands }) => {
					const upload = this.options.uploadFunction
					if (!upload) return false
					if (!isVideo(fileType(file.name))) {
						showError(__('This video type can\'t be played here. Upload MP4, M4V, WebM, MOV or OGV.'))
						return false
					}
					const id = Math.random().toString(36).slice(2)
					videoUploads[id] = { percent: null, name: file.name }
					// In this command's own transaction: a separate one would be a mismatch.
					commands.insertContent({ type: this.name, attrs: { src: null, upload: id } })
					const settle = (src) => {
						delete videoUploads[id]
						const pos = findUpload(editor.state.doc, id)
						if (pos === null) return
						const node = editor.state.doc.nodeAt(pos)
						const tr = editor.state.tr
						if (src) tr.setNodeMarkup(pos, undefined, { ...node.attrs, src, upload: null })
						else tr.delete(pos, pos + node.nodeSize)
						editor.view.dispatch(tr)
					}
					Promise.resolve(
						upload(file, {
							onProgress: (percent) => {
								if (videoUploads[id]) videoUploads[id].percent = percent
							},
						})
					)
						.then((uploaded) => settle(uploaded?.file_url || null))
						.catch((err) => {
							settle(null)
							showError(err?.message || __('Error Uploading File'))
						})
					return true
				},

			// Only the types the page plays (§2).
			selectAndUploadVideo:
				() =>
				({ editor }) => {
					if (!this.options.uploadFunction) return false
					const input = document.createElement('input')
					input.type = 'file'
					input.accept = VIDEO_ACCEPT.join(',')
					input.onchange = () => {
						const file = input.files?.[0]
						if (file) editor.commands.uploadVideo(file)
					}
					input.click()
					return true
				},
		}
	},

	addNodeView() {
		return VueNodeViewRenderer(RichTextVideo)
	},
})

/** `dir="auto"` on every text block, while editing and in the saved HTML (§4). */
export const TextDirection = Extension.create({
	name: 'textDirection',
	addGlobalAttributes() {
		return [
			{
				types: ['paragraph', 'heading', 'listItem', 'taskItem', 'blockquote', 'tableCell', 'tableHeader'],
				attributes: {
					dir: {
						default: 'auto',
						parseHTML: (el) => {
							const dir = (el.getAttribute('dir') || '').toLowerCase()
							return ['ltr', 'rtl', 'auto'].includes(dir) ? dir : 'auto'
						},
						renderHTML: (attrs) => ({ dir: attrs.dir || 'auto' }),
					},
				},
			},
		]
	},
})
