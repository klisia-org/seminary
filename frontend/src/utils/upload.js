import AudioBlock from '@/components/AudioBlock.vue'
import VideoBlock from '@/components/VideoBlock.vue'
import UploadPlugin from '@/components/UploadPlugin.vue'
import { h, createApp } from 'vue'
import { Upload as UploadIcon } from 'lucide-vue-next'
import translationPlugin from '../translation'
import { FrappeUI } from 'frappe-ui'
import { Button } from 'frappe-ui'

export class Upload {
	constructor({ data, api, readOnly }) {
		this.data = data
		this.readOnly = readOnly
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
		if (this.isVideo(file.file_type)) {
			const app = createApp(VideoBlock, {
				file: file.file_url,
			})
			app.mount(this.wrapper)
			return
		} else if (this.isAudio(file.file_type)) {
			const app = createApp(AudioBlock, {
				file: file.file_url,
			})
			app.mount(this.wrapper)
			return
		} else if (file.file_type == 'PDF') {
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
		} else {
			this.wrapper.innerHTML = `<img class="mb-4" src=${encodeURI(
				file.file_url
			)} width='100%'>`
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
		return {
			file_url: this.data.file_url,
			file_type: this.data.file_type,
		}
	}

	isVideo(type) {
		return ['mov', 'mp4', 'avi', 'mkv', 'webm'].includes(type.toLowerCase())
	}

	isAudio(type) {
		return ['mp3', 'wav', 'ogg'].includes(type.toLowerCase())
	}
}
