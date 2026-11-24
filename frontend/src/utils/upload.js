import AudioBlock from '@/components/AudioBlock.vue'
import VideoBlock from '@/components/VideoBlock.vue'
import UploadPlugin from '@/components/UploadPlugin.vue'
import { h, createApp } from 'vue'
import { Upload as UploadIcon } from 'lucide-vue-next'
import translationPlugin from '../translation'
import { FrappeUI } from 'frappe-ui'
import { Button } from 'frappe-ui'
import { isAudio, isImage, isPdf, isVideo } from './mediaTypes.js'

export class Upload {
	constructor({ data, api, readOnly, config }) {
		this.data = data
		this.readOnly = readOnly
		// The lesson's caption tracks, handed to every video it plays (102 §6).
		this.captions = config?.captions || []
	}

	static get toolbox() {
		const app = createApp({
			render: () =>
				h(UploadIcon, { size: 18, strokeWidth: 1.5, color: 'black' }),
		})

		const div = document.createElement('div')
		app.mount(div)

		return {
			title: 'Upload',
			icon: div.innerHTML,
		}
	}

	static get isReadOnlySupported() {
		return true
	}

	render() {
		this.wrapper = document.createElement('div')

		if (this.data && this.data.file_url) {
			this.renderFile(this.data)
		} else {
			this.renderFileUploader()
		}

		return this.wrapper
	}

	renderFile(file) {
		if (isVideo(file.file_type)) {
			const app = createApp(VideoBlock, {
				file: file.file_url,
				captions: this.captions,
			})
			app.use(translationPlugin)
			app.mount(this.wrapper)
			return
		} else if (isAudio(file.file_type)) {
			const app = createApp(AudioBlock, {
				file: file.file_url,
			})
			app.mount(this.wrapper)
			return
		} else if (isPdf(file.file_type)) {
			// Rendered by the browser on our own origin. This used to go through Google
			// Docs Viewer, which fetches the URL from Google's servers without the
			// user's session: private files came back 403 (a blank viewer), and public
			// ones were handed to a third party on every view. Same-origin framing
			// sends the session cookie, so Frappe's file permission check applies.
			const src = encodeURI(file.file_url)
			const frame = document.createElement('iframe')
			frame.src = `${src}#view=FitH`
			frame.width = '100%'
			frame.height = '700px'
			frame.className = 'mb-2'
			frame.title = file.file_url.split('/').pop()
			// Many mobile browsers don't render PDFs inside iframes; give them a way out.
			const link = document.createElement('a')
			link.href = src
			link.target = '_blank'
			link.rel = 'noopener'
			link.className = 'mb-4 inline-block text-sm text-ink-gray-7 underline'
			link.textContent = __('Open PDF')
			this.wrapper.replaceChildren(frame, link)
			return
		} else if (!isImage(file.file_type)) {
			// A type the page can't play or show (an mkv or avi from before decision
			// 109 §2): a download link with the file's name, never a broken image.
			const link = document.createElement('a')
			link.href = encodeURI(file.file_url)
			link.setAttribute('download', '')
			link.className = 'mb-4 inline-block text-sm text-ink-gray-7 underline'
			link.textContent = __('Download {0}').format(
				decodeURIComponent(file.file_url.split('?')[0].split('/').pop())
			)
			this.wrapper.replaceChildren(link)
			return
		} else {
			// Built node by node, like the PDF branch above (p008 F3). This was an
			// `innerHTML` template with an UNQUOTED `src=${encodeURI(...)}`, and
			// `encodeURI` leaves `'` and `<` alone -- so a crafted file_url could
			// close the attribute and add its own. `setAttribute` has no parse step
			// to escape out of.
			const image = document.createElement('img')
			image.className = 'mb-4'
			image.setAttribute('src', file.file_url)
			image.setAttribute('width', '100%')
			// Alt text the instructor gives below the image while editing (102 §7).
			image.setAttribute('alt', this.data.alt || '')
			if (this.readOnly) {
				this.wrapper.replaceChildren(image)
				return
			}
			const alt = document.createElement('input')
			alt.type = 'text'
			alt.className = 'form-input mb-4 w-full text-sm'
			alt.value = this.data.alt || ''
			alt.placeholder = __('Describe the image for students who can\'t see it')
			alt.setAttribute('aria-label', __('Image description (alt text)'))
			// Keys typed here are the field's: editorjs would read Enter as "new
			// block" and Backspace in an empty field as "delete this one".
			alt.addEventListener('keydown', (event) => {
				event.stopPropagation()
				if (event.key === 'Enter') event.preventDefault()
			})
			alt.addEventListener('input', () => {
				this.data.alt = alt.value
				image.setAttribute('alt', alt.value)
			})
			image.className = 'mb-1'
			this.wrapper.replaceChildren(image, alt)
			return
		}
	}

	renderFileUploader() {
		const app = createApp(UploadPlugin, {
			onFileUploaded: (file) => {
				this.data.file_url = file.file_url
				this.data.file_type = file.file_type
				this.renderFile(file)
			},
		})
		app.use(translationPlugin)
		app.use(FrappeUI)
		app.component('Button', Button)
		app.mount(this.wrapper)
	}

	validate(savedData) {
		if (!savedData.file_url || !savedData.file_type) {
			return false
		}
		return true
	}

	save(blockContent) {
		const saved = {
			file_url: this.data.file_url,
			file_type: this.data.file_type,
		}
		if (this.data.alt) saved.alt = this.data.alt
		return saved
	}
}
