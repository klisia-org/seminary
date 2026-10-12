<template>
	<PageHeader :title="__('Reading Plans')">
		<template #actions>
			<FileUploader v-if="canAuthor" :fileTypes="['.zip']" :uploadArgs="{ private: true }" @success="importPack">
				<template v-slot="{ uploading, openFileSelector }">
					<Button variant="subtle" :label="__('Import')" :loading="uploading || importRes.loading" @click="openFileSelector">
						<template #prefix><Upload class="h-4 w-4" /></template>
					</Button>
				</template>
			</FileUploader>
			<Button v-if="canAuthor" variant="solid" :label="__('New plan')" @click="openEditor()">
				<template #prefix><Plus class="h-4 w-4" /></template>
			</Button>
		</template>
	</PageHeader>

	<div class="mx-auto flex w-full max-w-4xl flex-col gap-4 px-4 py-6">
		<div v-if="canAuthor" class="flex gap-2 text-sm">
			<button class="rounded-md px-3 py-1"
				:class="tab === 'runs' ? 'bg-surface-gray-3 text-ink-gray-9' : 'text-ink-gray-6'"
				@click="tab = 'runs'">{{ __('My cohorts') }}</button>
			<button class="rounded-md px-3 py-1"
				:class="tab === 'library' ? 'bg-surface-gray-3 text-ink-gray-9' : 'text-ink-gray-6'"
				@click="tab = 'library'">{{ __('Library') }}</button>
		</div>

		<!-- ===================== runs ===================== -->
		<template v-if="tab === 'runs'">
			<div v-if="runsRes.loading && !runs.length" class="py-10 text-center text-sm text-ink-gray-5">{{ __('Loading…') }}</div>
			<div v-else-if="!runs.length" class="py-10 text-center text-sm text-ink-gray-5">
				{{ canAuthor ? __('None of your cohorts is reading a plan yet. Start one from the Library.') : __('None of your cohorts is reading a plan yet.') }}
			</div>
			<div v-for="run in runs" :key="run.name" class="rounded-lg border border-outline-gray-2 bg-surface-white">
				<button class="flex w-full flex-wrap items-center gap-2 px-4 py-3 text-left" @click="toggleRun(run)">
					<component :is="openRun === run.name ? ChevronDown : ChevronRight" class="h-4 w-4 text-ink-gray-5" />
					<BookOpen class="h-4 w-4 text-ink-gray-6" />
					<span class="font-medium text-ink-gray-9">{{ run.title }}</span>
					<span class="text-sm text-ink-gray-5">· {{ run.cohort_name }}</span>
					<span v-if="run.status !== 'Active'" class="rounded bg-surface-gray-2 px-1.5 py-0.5 text-xs text-ink-gray-6">{{ __(run.status) }}</span>
					<span class="ml-auto flex items-center gap-2 text-xs">
						<span v-if="run.is_member" class="text-ink-gray-6">{{ __('{0} of {1} read').format(run.read_count, run.steps.length) }}</span>
						<span v-if="run.behind" class="rounded bg-surface-amber-2 px-1.5 py-0.5 text-ink-amber-3">{{ __('{0} behind').format(run.behind) }}</span>
					</span>
				</button>

				<div v-if="openRun === run.name" class="border-t border-outline-gray-1 px-4 py-3">
					<div class="mb-3 flex flex-wrap items-center gap-2 text-xs text-ink-gray-6">
						<CalendarDays class="h-3.5 w-3.5" />
						<span>{{ daysLabel(run.days) }}</span>
						<span v-if="run.skip_public_holidays">· {{ __('skips public holidays') }}</span>
						<div v-if="run.can_manage" class="ml-auto flex gap-2">
							<Button size="sm" variant="subtle" :label="__('Progress')" @click="openProgress(run)" />
							<Button size="sm" variant="subtle" :label="__('Schedule')" @click="openSchedule(run)" />
							<Button v-if="run.can_manage && canAuthor" size="sm" variant="subtle" :label="__('Plan')"
								@click="openEditor(run.reading_plan)" />
						</div>
					</div>

					<ol class="flex flex-col gap-2">
						<li v-for="s in run.steps" :key="s.step"
							class="rounded-md border px-3 py-2"
							:class="s.is_today ? 'border-outline-gray-4 bg-surface-gray-1' : 'border-outline-gray-1'">
							<div class="flex flex-wrap items-center gap-2">
								<input v-if="run.is_member && run.status !== 'Cancelled'" type="checkbox" class="rounded"
									:checked="s.read" :title="s.read ? __('Mark as unread') : __('Mark as read')"
									@change="toggleRead(run, s, $event.target.checked)" />
								<span class="w-14 shrink-0 text-xs text-ink-gray-5">{{ __('Step {0}').format(s.step) }}</span>
								<span class="text-sm font-medium" :class="s.read ? 'text-ink-gray-5 line-through' : 'text-ink-gray-9'">{{ s.label }}</span>
								<span v-if="s.is_today" class="rounded bg-surface-gray-3 px-1.5 py-0.5 text-xs text-ink-gray-8">{{ __('Today') }}</span>
								<span class="ml-auto text-xs text-ink-gray-5">{{ s.date ? formatDate(s.date) : '' }}</span>
							</div>
							<div class="mt-1 flex flex-wrap items-center gap-3 pl-0 text-sm sm:pl-20">
								<button v-if="s.resolved_ref" class="flex items-center gap-1 text-ink-blue-3 hover:underline" @click="openPassage(s)">
									<BookOpen class="h-3.5 w-3.5" />{{ __('Read') }}
								</button>
								<a v-if="s.attachment" :href="s.attachment" target="_blank" rel="noopener" class="flex items-center gap-1 text-ink-blue-3 hover:underline">
									<Paperclip class="h-3.5 w-3.5" />{{ __('Attachment') }}
								</a>
								<a v-if="s.link_url" :href="s.link_url" target="_blank" rel="noopener noreferrer" class="flex items-center gap-1 text-ink-blue-3 hover:underline">
									<LinkIcon class="h-3.5 w-3.5" />{{ __('Link') }}
								</a>
								<button v-if="run.is_member || run.can_manage" class="flex items-center gap-1 text-ink-gray-6 hover:text-ink-gray-9" @click="discuss(run, s)">
									<MessageCircle class="h-3.5 w-3.5" />{{ __('Discuss') }}
								</button>
							</div>
							<p v-if="s.reading_text && s.reading_text !== s.label" class="mt-1 whitespace-pre-line text-sm text-ink-gray-7 sm:pl-20">{{ s.reading_text }}</p>
							<SafeHtml v-if="s.message" :html="s.message" class="prose prose-sm mt-1 max-w-none text-ink-gray-8 sm:pl-20" />
						</li>
					</ol>
				</div>
			</div>
		</template>

		<!-- ===================== library ===================== -->
		<template v-else>
			<div v-if="!plans.length" class="py-10 text-center text-sm text-ink-gray-5">{{ __('No reading plans yet.') }}</div>
			<div v-for="p in plans" :key="p.name"
				class="flex flex-wrap items-center gap-2 rounded-lg border border-outline-gray-2 bg-surface-white px-4 py-3">
				<div class="min-w-0 flex-1">
					<div class="flex flex-wrap items-center gap-2">
						<span class="font-medium text-ink-gray-9">{{ p.title }}</span>
						<span class="rounded bg-surface-gray-2 px-1.5 py-0.5 text-xs text-ink-gray-6">{{ p.plan_type === 'Bible' ? __('Bible') : __('Other') }}</span>
						<span v-if="p.is_standard" class="rounded bg-surface-gray-2 px-1.5 py-0.5 text-xs text-ink-gray-6">{{ __('Standard') }}</span>
					</div>
					<div class="mt-0.5 text-xs text-ink-gray-5">
						{{ __('{0} steps').format(p.step_count) }}<span v-if="p.author_name"> · {{ p.author_name }}</span>
						<span v-if="p.description"> · {{ p.description }}</span>
					</div>
				</div>
				<div class="flex flex-wrap gap-1">
					<Button size="sm" variant="solid" :label="__('Start')" @click="openStart(p)" />
					<Button size="sm" variant="subtle" :label="p.can_edit ? __('Edit') : __('View')" @click="openEditor(p.name)" />
					<Button size="sm" variant="subtle" :title="__('Duplicate')" @click="duplicate(p)"><template #icon><Copy class="h-4 w-4" /></template></Button>
					<Button size="sm" variant="subtle" :title="__('Export')" @click="exportPlan(p)"><template #icon><Download class="h-4 w-4" /></template></Button>
					<Button v-if="p.can_delete" size="sm" variant="subtle" :title="__('Delete')" @click="removePlan(p)"><template #icon><Trash2 class="h-4 w-4" /></template></Button>
				</div>
			</div>
		</template>
	</div>

	<!-- passage -->
	<Dialog v-model="showPassage" :options="{ title: passageRes.data?.reference || __('Passage'), size: 'xl' }">
		<template #body-content>
			<div v-if="passageRes.loading" class="py-4 text-center text-sm text-ink-gray-5">{{ __('Loading…') }}</div>
			<p v-else class="max-h-[60vh] overflow-y-auto whitespace-pre-line text-sm leading-relaxed text-ink-gray-8">
				{{ passageRes.data?.text || __('Passage text unavailable.') }}
			</p>
		</template>
	</Dialog>

	<!-- progress grid -->
	<Dialog v-model="showProgress" :options="{ title: __('Who has read what'), size: '4xl' }">
		<template #body-content>
			<div v-if="progressRes.loading" class="py-4 text-center text-sm text-ink-gray-5">{{ __('Loading…') }}</div>
			<div v-else-if="progressRes.data" class="overflow-x-auto">
				<table class="text-sm">
					<thead>
						<tr class="text-xs text-ink-gray-5">
							<th class="sticky left-0 bg-surface-white px-2 py-1 text-left font-normal">{{ __('Member') }}</th>
							<th class="px-2 py-1 text-left font-normal">{{ __('Behind') }}</th>
							<th v-for="s in progressRes.data.steps" :key="s.step" class="px-1 py-1 text-center font-normal" :title="s.date ? formatDate(s.date) : ''">{{ s.step }}</th>
						</tr>
					</thead>
					<tbody>
						<tr v-for="m in progressRes.data.members" :key="m.person" class="border-t border-outline-gray-1">
							<td class="sticky left-0 whitespace-nowrap bg-surface-white px-2 py-1 text-ink-gray-8">
								{{ m.full_name }}<span v-if="m.is_leader" class="ml-1 text-xs text-ink-gray-5">({{ __('leader') }})</span>
							</td>
							<td class="px-2 py-1" :class="m.behind ? 'text-ink-amber-3' : 'text-ink-gray-5'">{{ m.behind || '—' }}</td>
							<td v-for="s in progressRes.data.steps" :key="s.step" class="px-1 py-1 text-center">
								<Check v-if="m.read.includes(s.step)" class="mx-auto h-3.5 w-3.5 text-ink-green-3" />
								<span v-else-if="isPast(s.date)" class="text-ink-amber-3">·</span>
							</td>
						</tr>
					</tbody>
				</table>
			</div>
		</template>
	</Dialog>

	<!-- start / schedule -->
	<Dialog v-model="showSchedule" :options="{ title: scheduleDraft.run ? __('Schedule') : __('Start {0}').format(scheduleDraft.title), size: 'lg' }">
		<template #body-content>
			<div class="flex flex-col gap-3">
				<label v-if="!scheduleDraft.run" class="flex flex-col gap-1 text-sm">
					<span class="text-ink-gray-6">{{ __('Cohort') }}</span>
					<select v-model="scheduleDraft.cohort" class="rounded-md border border-outline-gray-2 bg-surface-white px-2 py-1.5 text-sm">
						<option v-for="c in ledCohorts" :key="c.name" :value="c.name">{{ c.cohort_name }}</option>
					</select>
					<span v-if="!ledCohorts.length" class="text-xs text-ink-gray-5">{{ __('You do not lead an active cohort.') }}</span>
				</label>
				<label class="flex flex-col gap-1 text-sm">
					<span class="text-ink-gray-6">{{ __('Start date') }}</span>
					<input v-model="scheduleDraft.start_date" type="date" class="rounded-md border border-outline-gray-2 bg-surface-white px-2 py-1.5 text-sm" />
				</label>
				<div class="flex flex-col gap-1 text-sm">
					<span class="text-ink-gray-6">{{ __('Reading days') }}</span>
					<div class="flex flex-wrap gap-1">
						<button v-for="d in WEEKDAYS" :key="d.key" type="button"
							class="rounded-md border px-2 py-1 text-xs"
							:class="scheduleDraft.days.includes(d.key) ? 'border-outline-gray-4 bg-surface-gray-3 text-ink-gray-9' : 'border-outline-gray-2 text-ink-gray-6'"
							@click="toggleDay(d.key)">{{ d.label }}</button>
					</div>
				</div>
				<label class="flex items-center gap-2 text-sm text-ink-gray-8">
					<input v-model="scheduleDraft.skip_public_holidays" type="checkbox" class="rounded" />
					{{ __('Skip public holidays') }}
				</label>
				<label v-if="scheduleDraft.run" class="flex flex-col gap-1 text-sm">
					<span class="text-ink-gray-6">{{ __('Status') }}</span>
					<select v-model="scheduleDraft.status" class="rounded-md border border-outline-gray-2 bg-surface-white px-2 py-1.5 text-sm">
						<option value="Active">{{ __('Active') }}</option>
						<option value="Completed">{{ __('Completed') }}</option>
						<option value="Cancelled">{{ __('Cancelled') }}</option>
					</select>
				</label>
			</div>
		</template>
		<template #actions>
			<Button variant="solid" :label="scheduleDraft.run ? __('Save') : __('Start')"
				:loading="startRes.loading || updateRunRes.loading" @click="submitSchedule" />
		</template>
	</Dialog>

	<!-- plan editor -->
	<Dialog v-model="showEditor" :options="{ title: editor.name ? (editor.can_edit ? __('Edit plan') : editor.title) : __('New plan'), size: '4xl' }">
		<template #body-content>
			<div v-if="planRes.loading" class="py-4 text-center text-sm text-ink-gray-5">{{ __('Loading…') }}</div>
			<div v-else class="flex flex-col gap-3">
				<div v-if="editor.in_use && editor.can_edit" class="rounded-md bg-surface-gray-2 px-3 py-2 text-xs text-ink-gray-7">
					{{ __('A cohort has started this plan, so its readings are fixed. You can still edit the messages, or duplicate the plan to change the readings.') }}
				</div>
				<div class="grid gap-3 sm:grid-cols-3">
					<label class="flex flex-col gap-1 text-sm sm:col-span-2">
						<span class="text-ink-gray-6">{{ __('Title') }}</span>
						<input v-model="editor.title" :disabled="!editor.can_edit" type="text" :placeholder="__('Romans in 10 days')"
							class="rounded-md border border-outline-gray-2 bg-surface-white px-2 py-1.5 text-sm disabled:bg-surface-gray-1" />
					</label>
					<label class="flex flex-col gap-1 text-sm">
						<span class="text-ink-gray-6">{{ __('Type') }}</span>
						<select v-model="editor.plan_type" :disabled="!editor.can_edit || editor.in_use"
							class="rounded-md border border-outline-gray-2 bg-surface-white px-2 py-1.5 text-sm disabled:bg-surface-gray-1">
							<option value="Bible">{{ __('Bible') }}</option>
							<option value="Other">{{ __('Other') }}</option>
						</select>
					</label>
				</div>
				<label class="flex flex-col gap-1 text-sm">
					<span class="text-ink-gray-6">{{ __('Description') }}</span>
					<textarea v-model="editor.description" :disabled="!editor.can_edit" rows="2"
						class="rounded-md border border-outline-gray-2 bg-surface-white px-2 py-1.5 text-sm disabled:bg-surface-gray-1"></textarea>
				</label>

				<div class="flex flex-col gap-2">
					<div v-for="(s, i) in editor.steps" :key="s._key" class="rounded-md border border-outline-gray-2 p-3">
						<div class="mb-2 flex items-center gap-2">
							<span class="text-sm font-medium text-ink-gray-8">{{ __('Step {0}').format(i + 1) }}</span>
							<div v-if="editor.can_edit && !editor.in_use" class="ml-auto flex gap-1">
								<Button size="sm" variant="ghost" :disabled="i === 0" :title="__('Move up')" @click="moveStep(i, -1)"><template #icon><ArrowUp class="h-3.5 w-3.5" /></template></Button>
								<Button size="sm" variant="ghost" :disabled="i === editor.steps.length - 1" :title="__('Move down')" @click="moveStep(i, 1)"><template #icon><ArrowDown class="h-3.5 w-3.5" /></template></Button>
								<Button size="sm" variant="ghost" :title="__('Remove')" @click="editor.steps.splice(i, 1)"><template #icon><Trash2 class="h-3.5 w-3.5" /></template></Button>
							</div>
						</div>

						<div v-if="editor.plan_type === 'Bible'" class="grid grid-cols-2 gap-2 sm:grid-cols-6">
							<label class="col-span-2 flex flex-col gap-0.5 text-xs text-ink-gray-6">{{ __('From') }}
								<select v-model="s.from_book" :disabled="readingsLocked" class="rounded-md border border-outline-gray-2 bg-surface-white px-2 py-1 text-sm disabled:bg-surface-gray-1">
									<option value=""></option>
									<option v-for="b in books" :key="b.osis" :value="b.osis">{{ b.name }}</option>
								</select>
							</label>
							<label class="flex flex-col gap-0.5 text-xs text-ink-gray-6">{{ __('Chapter') }}
								<input v-model.number="s.from_chapter" :disabled="readingsLocked" type="number" min="1" class="rounded-md border border-outline-gray-2 bg-surface-white px-2 py-1 text-sm disabled:bg-surface-gray-1" />
							</label>
							<label class="flex flex-col gap-0.5 text-xs text-ink-gray-6">{{ __('Verse') }}
								<input v-model.number="s.from_verse" :disabled="readingsLocked" type="number" min="1" :placeholder="__('start')" class="rounded-md border border-outline-gray-2 bg-surface-white px-2 py-1 text-sm disabled:bg-surface-gray-1" />
							</label>
							<div class="hidden sm:block sm:col-span-2"></div>
							<label class="col-span-2 flex flex-col gap-0.5 text-xs text-ink-gray-6">{{ __('To') }}
								<select v-model="s.to_book" :disabled="readingsLocked" class="rounded-md border border-outline-gray-2 bg-surface-white px-2 py-1 text-sm disabled:bg-surface-gray-1">
									<option value="">{{ __('Same book') }}</option>
									<option v-for="b in books" :key="b.osis" :value="b.osis">{{ b.name }}</option>
								</select>
							</label>
							<label class="flex flex-col gap-0.5 text-xs text-ink-gray-6">{{ __('Chapter') }}
								<input v-model.number="s.to_chapter" :disabled="readingsLocked" type="number" min="1" :placeholder="__('same')" class="rounded-md border border-outline-gray-2 bg-surface-white px-2 py-1 text-sm disabled:bg-surface-gray-1" />
							</label>
							<label class="flex flex-col gap-0.5 text-xs text-ink-gray-6">{{ __('Verse') }}
								<input v-model.number="s.to_verse" :disabled="readingsLocked" type="number" min="1" :placeholder="__('end')" class="rounded-md border border-outline-gray-2 bg-surface-white px-2 py-1 text-sm disabled:bg-surface-gray-1" />
							</label>
						</div>

						<div v-else class="flex flex-col gap-2">
							<label class="flex flex-col gap-0.5 text-xs text-ink-gray-6">{{ __('What to read') }}
								<textarea v-model="s.reading_text" :disabled="readingsLocked" rows="2" :placeholder="__('For example: Chapter 1 of Life Together')"
									class="rounded-md border border-outline-gray-2 bg-surface-white px-2 py-1 text-sm disabled:bg-surface-gray-1"></textarea>
							</label>
							<div class="grid gap-2 sm:grid-cols-2">
								<div class="flex flex-col gap-0.5 text-xs text-ink-gray-6">{{ __('Attachment') }}
									<div class="flex items-center gap-2">
										<a v-if="s.attachment" :href="s.attachment" target="_blank" rel="noopener" class="truncate text-sm text-ink-blue-3">{{ fileName(s.attachment) }}</a>
										<template v-if="!readingsLocked">
											<Button v-if="s.attachment" size="sm" variant="ghost" :title="__('Remove')" @click="s.attachment = ''"><template #icon><X class="h-3.5 w-3.5" /></template></Button>
											<FileUploader v-else :uploadArgs="{ private: true }" :validateFile="validateFileSize" @success="(f) => (s.attachment = f.file_url)">
												<template v-slot="{ uploading, openFileSelector }">
													<Button size="sm" :loading="uploading" :label="__('Upload')" @click="openFileSelector" />
												</template>
											</FileUploader>
										</template>
									</div>
								</div>
								<label class="flex flex-col gap-0.5 text-xs text-ink-gray-6">{{ __('Link') }}
									<input v-model="s.link_url" :disabled="readingsLocked" type="url" placeholder="https://"
										class="rounded-md border border-outline-gray-2 bg-surface-white px-2 py-1 text-sm disabled:bg-surface-gray-1" />
								</label>
							</div>
						</div>

						<div class="mt-2 text-xs text-ink-gray-6">{{ __('Message') }}</div>
						<div v-if="editor.can_edit" class="mt-1 rounded-md border border-outline-gray-2 px-2 py-1">
							<RichTextEditor :key="s._key" :content="s.message || ''" :teleport="false"
								:placeholder="__('Comments or questions for the cohort')" @change="(v) => (s.message = v)" />
						</div>
						<SafeHtml v-else-if="s.message" :html="s.message" class="prose prose-sm mt-1 max-w-none text-ink-gray-8" />
					</div>
					<Button v-if="editor.can_edit && !editor.in_use" variant="subtle" :label="__('Add step')" @click="addStep">
						<template #prefix><Plus class="h-4 w-4" /></template>
					</Button>
				</div>
			</div>
		</template>
		<template #actions>
			<Button v-if="editor.can_edit" variant="solid" :label="__('Save')" :loading="saveRes.loading" @click="savePlan" />
		</template>
	</Dialog>
</template>

<script setup>
import PageHeader from '@/components/PageHeader.vue'
import RichTextEditor from '@/components/RichTextEditor.vue'
import SafeHtml from '@/components/SafeHtml.vue'
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Button, Dialog, FileUploader, createResource } from 'frappe-ui'
import {
	ArrowDown, ArrowUp, BookOpen, CalendarDays, Check, ChevronDown, ChevronRight, Copy, Download,
	Link as LinkIcon, MessageCircle, Paperclip, Plus, Trash2, Upload, X,
} from 'lucide-vue-next'
import { createToast, formatDate, validateFileSize } from '@/utils'

const route = useRoute()
const router = useRouter()

const API = 'seminary.seminary.discipleship.reading_plans.'
const PACK = 'seminary.seminary.discipleship.reading_plan_pack.'
const WEEKDAYS = [
	{ key: 'monday', label: __('Mon') },
	{ key: 'tuesday', label: __('Tue') },
	{ key: 'wednesday', label: __('Wed') },
	{ key: 'thursday', label: __('Thu') },
	{ key: 'friday', label: __('Fri') },
	{ key: 'saturday', label: __('Sat') },
	{ key: 'sunday', label: __('Sun') },
]

const tab = ref('runs')
const openRun = ref(route.query.run || null)
const showPassage = ref(false)
const showProgress = ref(false)
const showSchedule = ref(false)
const showEditor = ref(false)
const scheduleDraft = reactive({ run: null, reading_plan: null, title: '', cohort: '', start_date: '', days: [], skip_public_holidays: false, status: 'Active' })
const editor = reactive({ name: null, title: '', plan_type: 'Bible', description: '', steps: [], can_edit: true, in_use: false })
let stepKey = 0

function fail(e, fallback) {
	createToast({ title: e?.messages?.[0] || fallback, icon: 'alert-circle', iconClasses: 'text-ink-red-3' })
}

const runsRes = createResource({ url: API + 'my_reading_plans', auto: true })
const plansRes = createResource({ url: API + 'list_plans', auto: true, onError: () => {} })
const booksRes = createResource({ url: API + 'bible_books', auto: true, cache: 'reading-plan-books' })
const cohortsRes = createResource({ url: 'seminary.seminary.discipleship.feed_api.my_cohorts_list', auto: true })
const passageRes = createResource({ url: 'seminary.seminary.integrations.bible.passage_text' })
const progressRes = createResource({ url: API + 'run_progress' })
const planRes = createResource({ url: API + 'get_plan' })
const saveRes = createResource({ url: API + 'save_plan' })
const markRes = createResource({ url: API + 'mark_step' })
const startRes = createResource({ url: API + 'start_plan' })
const updateRunRes = createResource({ url: API + 'update_run' })
const duplicateRes = createResource({ url: API + 'duplicate_plan' })
const deleteRes = createResource({ url: API + 'delete_plan' })
const importRes = createResource({ url: PACK + 'import_plan' })

const runs = computed(() => runsRes.data || [])
const plans = computed(() => plansRes.data || [])
const canAuthor = computed(() => Array.isArray(plansRes.data))
const books = computed(() => booksRes.data || [])
const ledCohorts = computed(() => (cohortsRes.data || []).filter((c) => c.is_leader))
const readingsLocked = computed(() => !editor.can_edit || editor.in_use)

onMounted(() => {
	if (route.query.run) openRun.value = route.query.run
})

function toggleRun(run) {
	openRun.value = openRun.value === run.name ? null : run.name
	router.replace({ query: openRun.value ? { run: openRun.value } : {} })
}

function daysLabel(days) {
	if (days.length === 7) return __('Every day')
	return WEEKDAYS.filter((d) => days.includes(d.key)).map((d) => d.label).join(', ')
}

function isPast(date) {
	if (!date) return false
	return date < new Date().toISOString().slice(0, 10)
}

function fileName(url) {
	return decodeURIComponent((url || '').split('/').pop().split('?')[0])
}

function openPassage(step) {
	showPassage.value = true
	passageRes.submit({ resolved_ref: step.resolved_ref }).catch(() => {})
}

function toggleRead(run, step, read) {
	markRes
		.submit({ run: run.name, step: step.step, read: read ? 1 : 0 })
		.then(() => runsRes.reload())
		.catch((e) => { fail(e, __('Could not save.')); runsRes.reload() })
}

function discuss(run, step) {
	router.push({ path: '/community', query: { cohort: run.cohort, discuss: run.name, step: step.step } })
}

function openProgress(run) {
	showProgress.value = true
	progressRes.submit({ run: run.name })
}

function openSchedule(run) {
	Object.assign(scheduleDraft, {
		run: run.name, reading_plan: run.reading_plan, title: run.title, cohort: run.cohort,
		start_date: run.start_date, days: [...run.days], skip_public_holidays: !!run.skip_public_holidays, status: run.status,
	})
	showSchedule.value = true
}

function openStart(plan) {
	Object.assign(scheduleDraft, {
		run: null, reading_plan: plan.name, title: plan.title, cohort: ledCohorts.value[0]?.name || '',
		start_date: new Date().toISOString().slice(0, 10), days: WEEKDAYS.map((d) => d.key), skip_public_holidays: false, status: 'Active',
	})
	showSchedule.value = true
}

function toggleDay(key) {
	const i = scheduleDraft.days.indexOf(key)
	if (i >= 0) scheduleDraft.days.splice(i, 1)
	else scheduleDraft.days.push(key)
}

function submitSchedule() {
	if (!scheduleDraft.days.length) return fail(null, __('Choose at least one reading day.'))
	const common = { start_date: scheduleDraft.start_date, days: scheduleDraft.days, skip_public_holidays: scheduleDraft.skip_public_holidays ? 1 : 0 }
	const req = scheduleDraft.run
		? updateRunRes.submit({ run: scheduleDraft.run, status: scheduleDraft.status, ...common })
		: startRes.submit({ cohort: scheduleDraft.cohort, reading_plan: scheduleDraft.reading_plan, ...common })
	req.then((name) => {
		showSchedule.value = false
		tab.value = 'runs'
		openRun.value = name
		runsRes.reload()
		plansRes.reload()
	}).catch((e) => fail(e, __('Could not save.')))
}

function blankStep(values = {}) {
	return {
		_key: ++stepKey, from_book: '', from_chapter: null, from_verse: null, to_book: '', to_chapter: null, to_verse: null,
		reading_text: '', attachment: '', link_url: '', message: '', ...values,
	}
}

function addStep() {
	const last = editor.steps[editor.steps.length - 1]
	// Most plans read on through one book, so the next step starts where the last ended.
	const next = last && editor.plan_type === 'Bible' && last.from_book
		? { from_book: last.to_book || last.from_book, from_chapter: (last.to_chapter || last.from_chapter || 0) + 1 }
		: {}
	editor.steps.push(blankStep(next))
}

function moveStep(i, delta) {
	const [row] = editor.steps.splice(i, 1)
	editor.steps.splice(i + delta, 0, row)
}

function openEditor(name = null) {
	Object.assign(editor, { name, title: '', plan_type: 'Bible', description: '', steps: [], can_edit: true, in_use: false })
	showEditor.value = true
	if (!name) {
		editor.steps.push(blankStep())
		return
	}
	planRes.submit({ plan: name }).then((p) => {
		Object.assign(editor, {
			name: p.name, title: p.title, plan_type: p.plan_type, description: p.description || '',
			can_edit: !!p.can_edit, in_use: !!p.in_use,
			steps: p.steps.map((s) => blankStep({
				from_book: s.from_book || '', from_chapter: s.from_chapter || null, from_verse: s.from_verse || null,
				to_book: s.to_book && s.to_book !== s.from_book ? s.to_book : '', to_chapter: s.to_chapter || null, to_verse: s.to_verse || null,
				reading_text: s.reading_text || '', attachment: s.attachment || '', link_url: s.link_url || '', message: s.message || '',
			})),
		})
	}).catch((e) => { showEditor.value = false; fail(e, __('Could not open the plan.')) })
}

function savePlan() {
	if (!editor.title.trim()) return fail(null, __('A title is required.'))
	if (!editor.steps.length) return fail(null, __('Add at least one step.'))
	const steps = editor.steps.map(({ _key, ...s }) => s)
	saveRes
		.submit({ plan: editor.name, title: editor.title, plan_type: editor.plan_type, description: editor.description, steps })
		.then(() => {
			showEditor.value = false
			createToast({ title: __('Plan saved.'), icon: 'check', iconClasses: 'text-ink-green-3' })
			plansRes.reload()
			runsRes.reload()
		})
		.catch((e) => fail(e, __('Could not save the plan.')))
}

function duplicate(plan) {
	duplicateRes.submit({ plan: plan.name }).then((name) => {
		plansRes.reload()
		openEditor(name)
	}).catch((e) => fail(e, __('Could not duplicate the plan.')))
}

function removePlan(plan) {
	if (!window.confirm(__('Delete {0}?').format(plan.title))) return
	deleteRes.submit({ plan: plan.name }).then(() => plansRes.reload()).catch((e) => fail(e, __('Could not delete the plan.')))
}

function exportPlan(plan) {
	window.location.href = `/api/method/${PACK}export_plan?plan=${encodeURIComponent(plan.name)}`
}

function importPack(file) {
	importRes.submit({ file_url: file.file_url }).then((name) => {
		tab.value = 'library'
		plansRes.reload()
		openEditor(name)
		createToast({ title: __('Plan imported.'), icon: 'check', iconClasses: 'text-ink-green-3' })
	}).catch((e) => fail(e, __('Could not import the plan.')))
}
</script>
