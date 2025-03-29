import ExamBlock from '@/components/ExamBlock.vue'
import AssessmentPlugin from '@/components/AssessmentPlugin.vue'
import { createApp, h } from 'vue'
import { usersStore } from '../stores/user'
import translationPlugin from '../translation'
import { BookOpenCheck } from 'lucide-vue-next'
import router from '@/router'

export class Exam {
	constructor({ data, api, readOnly }) {
		this.data = data
		this.readOnly = readOnly
	}

	static get toolbox() {
		const app = createApp({
			render: () =>
				h(BookOpenCheck, { size: 18, strokeWidth: 1.5, color: 'black' }),
		})

		const div = document.createElement('div')
		app.mount(div)

		return {
			title: __('Exam'),
			icon: div.innerHTML,
		}
	}

	static get isReadOnlySupported() {
		return true
	}

	render() {
		this.wrapper = document.createElement('div')
		if (Object.keys(this.data).length) {
			this.renderExam(this.data.exam)
		} else {
			this.renderExamModal()
		}
		return this.wrapper
	}

	renderExam(exam) {
		if (this.readOnly) {
			const app = createApp(ExamBlock, {
				exam: exam,
			})
			app.use(translationPlugin)
			app.use(router)
			const { userResource } = usersStore()
			app.provide('$user', userResource)
			app.mount(this.wrapper)
			return
		}
		this.wrapper.innerHTML = `<div class='border rounded-md p-10 text-center bg-surface-menu-bar mb-2'>
            <span class="font-medium">
                Exam: ${exam}
            </span>
        </div>`
		return
	}

	renderExamModal() {
		if (this.readOnly) {
			return
		}
		const app = createApp(AssessmentPlugin, {
			type: 'exam',
			onAddition: (exam) => {
				this.data.exam = exam
				this.renderExam(exam)
			},
		})
		app.use(translationPlugin)
		app.use(router); // Explicitly provide the router
		app.mount(this.wrapper)
	}

	save(blockContent) {
		return {
			exam: this.data.exam,
		}
	}
}