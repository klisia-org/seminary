import { h, createApp } from 'vue'
import { Video as VideoIcon } from 'lucide-vue-next'
import { FrappeUI, Button } from 'frappe-ui'
import VideoBlock from '@/components/VideoBlock.vue'
import RecorderPlugin from '@/components/RecorderPlugin.vue'
import translationPlugin from '../translation'

/**
 * EditorJS block that lets an instructor record a short video straight from the
 * browser (webcam + microphone) and embed it in the lesson — no external tool,
 * no manual upload. The recording is captured with MediaRecorder, uploaded as a
 * normal Frappe file attachment, then rendered with the shared VideoBlock both
 * while editing and in the read-only lesson view.
 */
export class VideoRecord {
	constructor({ data, readOnly }) {
		this.data = data && typeof data === 'object' ? data : {}
		this.readOnly = readOnly
		this.wrapper = undefined
		this.app = null
	}

	static get toolbox() {
		const app = createApp({
			render: () => h(VideoIcon, { size: 18, strokeWidth: 1.5, color: 'black' }),
		})
		const div = document.createElement('div')
		app.mount(div)

		return {
			title: 'Record Video',
			icon: div.innerHTML,
		}
	}

	static get isReadOnlySupported() {
		return true
	}

	render() {
		this.wrapper = document.createElement('div')

		if (this.data && this.data.file_url) {
			this.renderVideo(this.data)
		} else {
			this.renderRecorder()
		}

		return this.wrapper
	}

	renderVideo(file) {
		this.unmount()
		this.app = createApp(VideoBlock, {
			file: file.file_url,
			type: file.file_type === 'mp4' ? 'video/mp4' : 'video/webm',
		})
		this.app.use(translationPlugin)
		this.app.use(FrappeUI)
		this.app.component('Button', Button)
		this.app.mount(this.wrapper)
	}

	renderRecorder() {
		// Recording UI only makes sense while authoring.
		if (this.readOnly) return
		this.unmount()
		this.app = createApp(RecorderPlugin, {
			onRecorded: (file) => {
				this.data.file_url = file.file_url
				this.data.file_type = file.file_type
				this.renderVideo(file)
			},
		})
		this.app.use(translationPlugin)
		this.app.use(FrappeUI)
		this.app.component('Button', Button)
		this.app.mount(this.wrapper)
	}

	unmount() {
		if (this.app) {
			this.app.unmount()
			this.app = null
		}
		if (this.wrapper) this.wrapper.innerHTML = ''
	}

	validate(savedData) {
		return Boolean(savedData.file_url && savedData.file_type)
	}

	save() {
		return {
			file_url: this.data.file_url,
			file_type: this.data.file_type,
		}
	}

	destroy() {
		this.unmount()
	}
}
