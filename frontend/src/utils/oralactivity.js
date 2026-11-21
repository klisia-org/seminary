import { Mic } from 'lucide-vue-next'
import { createApp, h } from 'vue'
import AssessmentPlugin from '@/components/AssessmentPlugin.vue'
import OralActivityBlock from '@/components/OralActivityBlock.vue'
import translationPlugin from '../translation'
import { usersStore } from '@/stores/user'
import router from '../router'
import { FrappeUI, setConfig, frappeRequest, pageMetaPlugin } from 'frappe-ui'

// An oral activity in a lesson (decisions/100b).
export class OralActivity {
	constructor({ data, api, readOnly, config }) {
		this.data = data
		this.readOnly = readOnly
		this.course = config?.course || null
		this.courseName = config?.courseName || null
		this._app = null
	}

	static get toolbox() {
		const app = createApp({
			render: () =>
				h(Mic, { size: 18, strokeWidth: 1.5, color: 'black' }),
		})

		const div = document.createElement('div')
		app.mount(div)

		return {
			title: __('Oral Activity'),
			icon: div.innerHTML,
		}
	}

	static get isReadOnlySupported() {
		return true
	}

	render() {
		this.wrapper = document.createElement('div')
		if (Object.keys(this.data).length) {
			this.renderOralActivity(this.data.oral)
		} else {
			this.renderOralActivityModal()
		}
		return this.wrapper
	}

	renderOralActivity(oral) {
		if (!oral) {
			this.renderOralActivityModal()
			return
		}
		if (this.readOnly) {
			const app = createApp(OralActivityBlock, {
				activity: oral,
				courseName: this.courseName,
			})
			app.use(translationPlugin)
			app.use(FrappeUI)
			app.use(router)
			const { userResource } = usersStore()
			app.provide('$user', userResource)
			app.mount(this.wrapper)
			this._app = app
			return
		}
		// Built node by node (p008 F3/F13): the docname was interpolated into an
		// `innerHTML` template, so a record named with markup wrote that markup
		// into the lesson. `textContent` has no parse step to escape out of.
		const box = document.createElement('div')
		box.className = 'border rounded-md p-10 text-center bg-surface-menu-bar mb-2'
		const label = document.createElement('span')
		label.className = 'font-medium'
		label.textContent = `${__('Oral Activity')}: ${oral}`
		box.appendChild(label)
		this.wrapper.replaceChildren(box)
		return
	}

	renderOralActivityModal() {
		if (this.readOnly) {
			return
		}
		const app = createApp(AssessmentPlugin, {
			type: 'oralactivity',
			course: this.course,  // pass course to the modal component
			onAddition: (oral) => {
				this.data.oral = oral
				this.renderOralActivity(oral)
			},

		})
		app.use(translationPlugin)
		app.use(FrappeUI)
		app.use(router) // Explicitly provide the router
		app.mount(this.wrapper)
	}

	destroy() {
		if (this._app) {
			this._app.unmount()
			this._app = null
		}
	}

	save(blockContent) {
		return {
			oral: this.data.oral,
		}
	}
}
