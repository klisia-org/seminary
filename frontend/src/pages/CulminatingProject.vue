<template>
  <div>
    <PageHeader :title="__('Culminating Project')">
      <template v-if="tabs.length > 1" #tabs>
        <PageTabs :tabs="tabs" v-model="view" :label="__('Project views')" />
      </template>
    </PageHeader>

    <div class="px-3 py-4 sm:px-5">
      <div v-if="projects.loading" class="flex justify-center py-12">
        <LoadingIndicator class="w-8 h-8" />
      </div>

      <template v-else-if="projects.data">
        <!-- STUDENT VIEW -->
        <div v-if="view === 'student'">
          <p v-if="!studentProjects.length" class="text-sm text-ink-gray-5">
            {{ __('You don\'t have a culminating project yet.') }}
            <router-link to="/program-audit" class="text-ink-blue-3 underline">{{ __('Program Audit') }}</router-link>
          </p>
          <template v-else>
            <div v-if="studentProjects.length > 1" class="mb-4">
              <label class="text-sm font-medium text-ink-gray-6 mb-1 block">{{ __('Project') }}</label>
              <select v-model="selectedStudent"
                class="border border-outline-gray-2 bg-surface-white text-ink-gray-9 rounded-md px-3 py-2 text-sm w-full max-w-md">
                <option v-for="p in studentProjects" :key="p.name" :value="p.name">{{ p.project_title }}</option>
              </select>
            </div>
            <CulminatingProjectDetail v-if="selectedStudent" :name="selectedStudent" @changed="projects.reload()" />
          </template>
        </div>

        <!-- INSTRUCTOR VIEW -->
        <div v-else>
          <div v-if="selectedAdvisor">
            <Button variant="subtle" iconLeft="arrow-left" class="mb-3" @click="selectedAdvisor = null">
              {{ __('Back to list') }}
            </Button>
            <CulminatingProjectDetail :name="selectedAdvisor" @changed="projects.reload()" />
          </div>
          <template v-else>
            <p v-if="!advisorProjects.length" class="text-sm text-ink-gray-5">
              {{ __('You are not advising any culminating projects.') }}
            </p>
            <template v-else>
              <!-- Filters -->
              <div class="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
                <select v-for="f in filterDefs" :key="f.key" v-model="filters[f.key]"
                  class="border border-outline-gray-2 bg-surface-white text-ink-gray-9 rounded-md px-2 py-1.5 text-sm">
                  <option value="">{{ f.label }}</option>
                  <option v-for="opt in f.options.value" :key="opt" :value="opt">{{ opt }}</option>
                </select>
              </div>

              <table class="w-full text-sm">
                <thead>
                  <tr class="border-b text-left text-ink-gray-6">
                    <th class="py-2 px-2 font-medium">{{ __('Program') }}</th>
                    <th class="py-2 px-2 font-medium">{{ __('Student') }}</th>
                    <th class="py-2 px-2 font-medium">{{ __('Type') }}</th>
                    <th class="py-2 px-2 font-medium">{{ __('Title') }}</th>
                    <th class="py-2 px-2 font-medium">{{ __('Active Milestone') }}</th>
                    <th class="py-2 px-2 font-medium">{{ __('Due') }}</th>
                    <th class="py-2 px-2 font-medium">{{ __('Status') }}</th>
                    <th class="py-2 px-2 font-medium">{{ __('My Role') }}</th>
                    <th class="py-2 px-2 font-medium">{{ __('Action') }}</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="p in filteredAdvisor" :key="p.name"
                    class="border-b hover:bg-surface-gray-1 cursor-pointer" @click="selectedAdvisor = p.name">
                    <td class="py-2 px-2 text-ink-gray-7">{{ p.program }}</td>
                    <td class="py-2 px-2 text-ink-gray-7">{{ p.student_name }}</td>
                    <td class="py-2 px-2 text-ink-gray-5">{{ p.project_type }}</td>
                    <td class="py-2 px-2 text-ink-gray-8">{{ p.project_title }}</td>
                    <td class="py-2 px-2 text-ink-gray-5">{{ p.active_milestone || '—' }}</td>
                    <td class="py-2 px-2 text-xs" :class="overdue(p) ? 'text-ink-red-3 font-semibold' : 'text-ink-gray-5'">
                      {{ p.due || '—' }}
                    </td>
                    <td class="py-2 px-2"><Badge :theme="statusTheme(p.status)" :label="p.status" /></td>
                    <td class="py-2 px-2 text-ink-gray-6">{{ p.my_role }}</td>
                    <td class="py-2 px-2">
                      <Badge v-if="p.needs_action" theme="red" :label="__('Needs you')" />
                      <span v-else class="text-ink-gray-4">—</span>
                    </td>
                  </tr>
                </tbody>
              </table>
            </template>
          </template>
        </div>
      </template>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { Badge, Button, LoadingIndicator, createResource } from 'frappe-ui'
import { statusTheme } from '@/utils/statusTheme'
import CulminatingProjectDetail from '@/components/CulminatingProjectDetail.vue'
import PageHeader from '@/components/PageHeader.vue'
import PageTabs from '@/components/PageTabs.vue'
import { useTabParam } from '@/composables/useTabParam'

// `?project=` deep-links straight into one project's detail, so the Faculty
// Worklist's Project Reviews section can hand a reader the thing that needs
// them rather than dropping them at a table to find it again (ADR 074).
const route = useRoute()

const projects = createResource({
  url: 'seminary.seminary.doctype.culminating_project.culminating_project.get_my_culminating_projects',
  auto: true,
  onSuccess(data) {
    const wanted = route.query.project
    const isMine = wanted && (data?.advisor_projects || []).some((p) => p.name === wanted)
    // A ?project= deep link is an explicit choice of the reader view, even for
    // someone who also has projects of their own as a student. Only open what
    // the server actually returned — an unknown or unauthorised id falls through
    // to the normal list instead of a blank detail.
    if (isMine) {
      if (view.value !== 'advisor') view.value = 'advisor'
      if (!selectedAdvisor.value) selectedAdvisor.value = wanted
    }
    if (data?.student_projects?.length && !selectedStudent.value) {
      selectedStudent.value = data.student_projects[0].name
    }
  },
})

const studentProjects = computed(() => projects.data?.student_projects || [])
const advisorProjects = computed(() => projects.data?.advisor_projects || [])
const hasStudent = computed(() => studentProjects.value.length > 0)
const hasAdvisor = computed(() => advisorProjects.value.length > 0)

// The two roles are areas of the page, not a mode: a reader and a student see
// different work. Addressable, so a link can point at either (ADR 075).
const tabs = computed(() => [
  ...(hasStudent.value ? [{ key: 'student', label: __('My Project') }] : []),
  ...(hasAdvisor.value
    ? [{ key: 'advisor', label: __('Projects I Advise / Read'), count: advisorProjects.value.length }]
    : []),
])
const defaultView = computed(() => (hasStudent.value ? 'student' : 'advisor'))
const view = useTabParam(['student', 'advisor'], defaultView, 'view')
const selectedStudent = ref(null)
const selectedAdvisor = ref(null)

const today = new Date().toISOString().slice(0, 10)
function overdue(p) {
  return p.due && p.due < today
}

// Instructor table filters. Default the status to Active so withdrawn/completed
// projects (people no longer on a prof's plate) don't clutter the list — pick
// "All Statuses" to see everyone.
const filters = ref({ program: '', project_type: '', status: 'Active', my_role: '' })
const distinct = (key) => computed(() => [...new Set(advisorProjects.value.map((p) => p[key]).filter(Boolean))].sort())
const filterDefs = [
  { key: 'program', label: __('All Programs'), options: distinct('program') },
  { key: 'project_type', label: __('All Types'), options: distinct('project_type') },
  { key: 'status', label: __('All Statuses'), options: distinct('status') },
  { key: 'my_role', label: __('All Roles'), options: distinct('my_role') },
]
const filteredAdvisor = computed(() =>
  advisorProjects.value.filter((p) =>
    Object.entries(filters.value).every(([k, v]) => !v || p[k] === v)
  )
)

// Reset the open detail when switching views.
watch(view, () => {
  selectedAdvisor.value = null
})
</script>
