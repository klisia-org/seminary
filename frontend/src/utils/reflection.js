import ReflectionBlock from '@/components/ReflectionBlock.vue'
import { createApp } from 'vue'
import { usersStore } from '../stores/user'
import translationPlugin from '../translation'
import router from '@/router'

// Reflection blocks: a self-assessment or a development plan placed in a
// lesson by the course's Competency Framework (ADR 079 decisions 1-3).
//
// Neither tool has a `toolbox` entry, so an instructor cannot add one: the
// framework places them, and a hand-placed copy would be a reflection the
// policy knows nothing about. The lesson editor shows a fixed card, and the
// server refuses a save that removes or changes the block.
class Reflection {
	constructor({ data, readOnly, config }) {
		this.data = data || {}
		this.readOnly = readOnly
		this.lesson = config?.lesson || null
	}

	static get isReadOnlySupported() {
		return true
	}

	render() {
		this.wrapper = document.createElement('div')
		if (this.readOnly && this.lesson) {
			const app = createApp(ReflectionBlock, { lesson: this.lesson })
			app.use(translationPlugin)
			app.use(router)
			const { userResource } = usersStore()
			app.provide('$user', userResource)
			app.mount(this.wrapper)
			return this.wrapper
		}
		// Built node by node, as the other activity tools are (p008 F3/F13).
		const box = document.createElement('div')
		box.className = 'mb-2 rounded-md border border-dashed p-6 text-center bg-surface-menu-bar'
		const title = document.createElement('div')
		title.className = 'font-medium'
		title.textContent = this.title()
		const note = document.createElement('div')
		note.className = 'mt-1 text-sm text-ink-gray-5'
		note.textContent = __('Placed by the Competency Framework. Students complete it here.')
		box.append(title, note)
		this.wrapper.replaceChildren(box)
		return this.wrapper
	}

	save() {
		return this.data
	}
}

export class SelfAssessment extends Reflection {
	title() {
		if (this.data.stage === 'Baseline') return __('Self-assessment: where I am starting')
		return this.data.scope === 'course'
			? __('Self-assessment: every competency in this course')
			: __('Self-assessment: this chapter’s competency')
	}
}

export class DevelopmentPlan extends Reflection {
	title() {
		return __('Development plan')
	}
}
