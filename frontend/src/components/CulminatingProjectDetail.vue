<template>
  <div>
    <div v-if="cp.loading" class="flex justify-center py-12">
      <LoadingIndicator class="w-7 h-7" />
    </div>

    <div v-else-if="cp.data" class="space-y-5">
      <!-- Header -->
      <div>
        <div class="flex items-start justify-between gap-3 flex-wrap">
          <h2 class="text-xl font-bold text-ink-gray-9">{{ cp.data.project_title }}</h2>
          <div class="flex items-center gap-2 shrink-0">
            <Badge v-if="cp.data.project_type" theme="gray" :label="cp.data.project_type" />
            <Badge :theme="statusTheme(cp.data.workflow_state)" :label="cp.data.workflow_state" />
          </div>
        </div>
        <p class="text-sm text-ink-gray-5 mt-1">
          {{ cp.data.program }}<span v-if="cp.data.student_name"> · {{ cp.data.student_name }}</span>
        </p>
        <div class="mt-2 flex items-center gap-2 flex-wrap">
          <details v-if="cp.data.abstract">
            <summary class="text-xs text-ink-blue-3 cursor-pointer">{{ __('Abstract') }}</summary>
            <div class="prose prose-sm max-w-none mt-2 text-ink-gray-7" v-html="cp.data.abstract"></div>
          </details>
          <span v-else-if="!canEditAbstract" class="text-xs text-ink-gray-4">{{ __('No abstract yet.') }}</span>
          <Button v-if="canEditAbstract" size="sm" variant="ghost" @click="openAbstract">
            {{ cp.data.abstract ? __('Edit abstract') : __('Add abstract') }}
          </Button>
        </div>
      </div>

      <!-- Advisors -->
      <div v-if="cp.data.advisors.length" class="flex flex-wrap gap-6">
        <div v-for="a in cp.data.advisors" :key="a.name" class="flex flex-col items-center text-center">
          <InstructorAvatar :instructor="{ name: a.name, instructor_name: a.instructor_name, profileimage: a.profileimage }" size="xl" class="w-16 h-16 mb-1" />
          <div class="text-sm font-medium text-ink-gray-8">{{ a.instructor_name }}</div>
          <div class="text-xs text-ink-gray-4">{{ a.role }}</div>
          <div class="flex gap-2 mt-1">
            <ContactChannelIcons :channels="a.contact_channels" :instructor="a.name" />
          </div>
        </div>
      </div>

      <!-- Committee -->
      <div v-if="(cp.data.committee && cp.data.committee.length) || canManageCommittee"
        class="flex items-center gap-2 flex-wrap text-sm">
        <span class="text-ink-gray-5">{{ __('Committee') }}:</span>
        <span v-if="!cp.data.committee.length" class="text-ink-gray-4">{{ __('none yet') }}</span>
        <span v-for="c in cp.data.committee" :key="c.name"
          class="inline-flex items-center gap-1 rounded-full bg-surface-gray-2 px-2 py-0.5 text-xs text-ink-gray-7">
          {{ c.member_name }}<span v-if="c.is_external" class="text-ink-gray-4">&nbsp;({{ __('external') }})</span>
          <button v-if="canManageCommittee" @click="removeMember(c.name)" :title="__('Remove')"
            class="text-ink-gray-4 hover:text-ink-red-3"><X class="h-3 w-3" /></button>
        </span>
        <a v-if="canManageCommittee && committeeEmails" :href="`mailto:${committeeEmails}`"
          :title="__('Email all committee members')" class="text-ink-gray-4 hover:text-ink-blue-link">
          <Mail class="h-4 w-4" />
        </a>
        <Button v-if="canManageCommittee" size="sm" variant="ghost" @click="openAddMember">
          <template #prefix><Plus class="h-3.5 w-3.5" /></template>
          {{ __('Add') }}
        </Button>
      </div>

      <!-- Student contact (readers / staff) -->
      <div v-if="!cp.data.viewer.can_submit && cp.data.student_name" class="flex items-center gap-2 text-sm">
        <span class="text-ink-gray-5">{{ __('Student') }}:</span>
        <span class="text-ink-gray-8 font-medium">{{ cp.data.student_name }}</span>
        <a v-if="cp.data.student_email" :href="`mailto:${cp.data.student_email}`" :title="__('Email student')"
          class="text-ink-gray-4 hover:text-ink-blue-link"><Mail class="h-4 w-4" /></a>
      </div>

      <!-- Info card (student) -->
      <div v-if="cp.data.viewer.can_submit && cp.data.student_action"
        class="rounded-md px-3 py-2 text-sm font-medium" :class="infoCardClass">
        {{ cp.data.student_action.message }}
      </div>

      <!-- Milestones -->
      <div>
        <h3 class="text-md font-semibold text-ink-gray-7 mb-2">{{ __('Milestones') }}</h3>
        <p v-if="!cp.data.milestones.length" class="text-sm text-ink-gray-4">
          {{ __('No milestones yet. They appear once the project is activated.') }}
        </p>
        <Disclosure v-for="m in cp.data.milestones" :key="m.row" v-slot="{ open }"
          :defaultOpen="m.row === cp.data.active_milestone" as="div"
          class="border border-outline-gray-2 rounded-md mb-2 bg-surface-white">
          <DisclosureButton class="flex w-full items-center gap-2 p-3 text-left">
            <ChevronRight class="h-4 w-4 text-ink-gray-6 shrink-0" :class="{ 'rotate-90': open }" />
            <span class="font-medium text-ink-gray-8">
              {{ m.milestone_name }}<span v-if="m.mandatory" class="text-ink-red-3 ml-0.5">*</span>
            </span>
            <span v-if="m.description" @click.stop="openInfo(m)" :title="__('Instructions')"
              class="text-ink-gray-4 hover:text-ink-blue-link cursor-pointer shrink-0">
              <Info class="h-4 w-4" />
            </span>
            <Badge class="ml-auto shrink-0" :theme="statusTheme(m.status)" :label="m.status" />
            <span class="text-xs shrink-0" :class="isOverdue(m) ? 'text-ink-red-3 font-semibold' : 'text-ink-gray-4'">
              {{ m.due_date || '—' }}
            </span>
          </DisclosureButton>
          <DisclosurePanel class="px-4 pb-4 pt-1 space-y-3 border-t border-outline-gray-1">
            <!-- Sign-off requirements -->
            <div v-if="m.required_roles.length">
              <div class="text-xs font-medium text-ink-gray-5 mb-1">{{ __('Sign-offs') }}</div>
              <div v-for="role in m.required_roles" :key="role" class="flex items-start gap-2 text-sm py-0.5">
                <Badge :theme="signoffOf(m, role) ? 'green' : 'gray'"
                  :label="signoffOf(m, role) ? __('Approved') : __('Pending')" />
                <span class="text-ink-gray-7">{{ role }}</span>
                <span v-if="signoffOf(m, role)" class="text-ink-gray-5 text-xs">
                  — {{ signoffOf(m, role).signed_by }}<template v-if="signoffOf(m, role).comment">: {{ signoffOf(m, role).comment }}</template>
                  <a v-if="signoffOf(m, role).attachment" :href="signoffOf(m, role).attachment" target="_blank" class="text-ink-blue-3 ml-1 underline">{{ fileName(signoffOf(m, role).attachment) }}</a>
                </span>
              </div>
            </div>

            <!-- Submissions: latest round + collapsible history -->
            <div v-if="latestSub(m)" class="space-y-2">
              <CulminatingProjectSubmission :submission="latestSub(m)" />
              <details v-if="priorSubs(m).length" class="text-xs">
                <summary class="text-ink-blue-3 cursor-pointer">
                  {{ __('Previous rounds') }} ({{ priorSubs(m).length }})
                </summary>
                <div class="space-y-2 mt-2 pl-2 border-l-2 border-outline-gray-1">
                  <CulminatingProjectSubmission v-for="s in priorSubs(m)" :key="s.round" :submission="s" />
                </div>
              </details>
            </div>

            <!-- Actions -->
            <div class="flex flex-wrap gap-2 pt-1">
              <Button v-if="cp.data.viewer.can_submit && submittable(m) && m.status !== 'Approved' && m.status !== 'Waived'"
                size="sm" variant="solid" @click="openSubmit(m)">
                {{ latestSub(m) ? __('Resubmit') : __('Submit Work') }}
              </Button>
              <template v-if="cp.data.viewer.can_review && m.status !== 'Approved' && m.status !== 'Waived'">
                <Button v-if="m.submission && m.submission.reviewer_decision === 'Pending'"
                  size="sm" variant="outline" @click="openReview(m)">
                  {{ __('Review Submission') }}
                </Button>
                <Button v-if="canSignOff(m)" size="sm" variant="subtle" @click="openSignoff(m)">
                  {{ __('My Sign-off') }} ({{ cp.data.viewer.my_role }})
                </Button>
                <Button v-if="canSignCommittee(m)" size="sm" variant="subtle" @click="openSignoff(m, 'Committee')">
                  {{ __('Sign for Committee') }}
                </Button>
              </template>
              <template v-if="m.creates_event">
                <span v-if="m.event" class="text-xs text-ink-gray-5 self-center inline-flex items-center gap-1">
                  <CalendarCheck class="h-4 w-4 text-ink-green-3" />
                  {{ __('Defense scheduled') }}<template v-if="m.event_starts_on">: {{ m.event_starts_on.slice(0, 16) }}</template>
                </span>
                <Button v-else-if="cp.data.viewer.my_role === 'Advisor'" size="sm" variant="subtle" @click="openDefense(m)">
                  {{ __('Schedule Defense') }}
                </Button>
              </template>
            </div>
          </DisclosurePanel>
        </Disclosure>
      </div>
    </div>

    <!-- Submit dialog (student) -->
    <Dialog v-model="submitDialog" :options="{ title: __('Submit Work') }">
      <template #body-content>
        <p class="text-xs text-ink-gray-5 mb-3">
          {{ __('This will be recorded as a {0} for “{1}”.').format(submitTypeHint, submitForm.milestone_name) }}
        </p>
        <FormControl type="textarea" :label="__('Note (optional)')" v-model="submitForm.note" class="mb-3" />
        <FileUploader :upload-args="uploadArgs" :validate-file="validateFileSize"
          @success="(f) => (submitForm.file = f.file_url)">
          <template #default="{ uploading, openFileSelector }">
            <div class="flex items-center gap-2">
              <Button @click="openFileSelector" :loading="uploading" variant="outline" iconLeft="paperclip">
                {{ submitForm.file ? __('Replace file') : __('Attach file') }}
              </Button>
              <span v-if="uploadLimits.data?.max_upload_mb" class="text-sm text-ink-gray-5">
                {{ __('Max {0} MB').format(uploadLimits.data.max_upload_mb) }}
              </span>
            </div>
          </template>
        </FileUploader>
        <p v-if="submitForm.file" class="text-xs text-ink-gray-5 mt-1 break-all">{{ submitForm.file }}</p>
      </template>
      <template #actions>
        <Button variant="solid" :loading="busy" :disabled="!submitForm.file" @click="doSubmit">{{ __('Submit') }}</Button>
      </template>
    </Dialog>

    <!-- Review / Sign-off dialog (reader) -->
    <Dialog v-model="reviewDialog" :options="{ title: reviewTitle }">
      <template #body-content>
        <div v-if="reviewForm.role === 'Committee'"
          class="rounded-md bg-surface-blue-1 text-ink-blue-3 px-3 py-2 text-xs mb-3 flex items-start gap-2">
          <Info class="h-4 w-4 shrink-0 mt-0.5" />
          <span>
            {{ __('You are recording this sign-off on behalf of the committee.') }}
            <template v-if="committeeNames"><br />{{ committeeNames }}</template>
          </span>
        </div>
        <FormControl type="select" :label="__('Decision')" v-model="reviewForm.decision" :options="decisionOptions" class="mb-3" />
        <FormControl type="textarea" :label="__('Comment (optional)')" v-model="reviewForm.comment" class="mb-3" />
        <FileUploader :upload-args="uploadArgs" :validate-file="validateFileSize"
          @success="(f) => (reviewForm.file = f.file_url)">
          <template #default="{ uploading, openFileSelector }">
            <div class="flex items-center gap-2">
              <Button @click="openFileSelector" :loading="uploading" variant="outline" iconLeft="paperclip">
                {{ reviewForm.file ? __('Replace file') : __('Attach file (optional)') }}
              </Button>
              <span v-if="uploadLimits.data?.max_upload_mb" class="text-sm text-ink-gray-5">
                {{ __('Max {0} MB').format(uploadLimits.data.max_upload_mb) }}
              </span>
            </div>
          </template>
        </FileUploader>
        <p v-if="reviewForm.file" class="text-xs text-ink-gray-5 mt-1 break-all">{{ reviewForm.file }}</p>
      </template>
      <template #actions>
        <Button variant="solid" :loading="busy" @click="doReview">{{ __('Save') }}</Button>
      </template>
    </Dialog>

    <!-- Edit abstract (student, until defended) -->
    <Dialog v-model="abstractDialog" :options="{ title: __('Abstract'), size: '2xl' }">
      <template #body-content>
        <RichTextEditor :content="abstractDraft" :teleport="false"
          :placeholder="__('Write your abstract…')" @change="(html) => (abstractDraft = html)" />
      </template>
      <template #actions>
        <Button variant="solid" :loading="busy" @click="saveAbstract">{{ __('Save') }}</Button>
      </template>
    </Dialog>

    <!-- Schedule defense (advisor) -->
    <Dialog v-model="defenseDialog" :options="{ title: __('Schedule Defense') }">
      <template #body-content>
        <p class="text-xs text-ink-gray-5 mb-3">
          {{ __('Creates a calendar event with the student, readers and committee as participants.') }}
        </p>
        <FormControl type="datetime-local" :label="__('Date & time')" v-model="defenseForm.starts_on" class="mb-3" />
        <FormControl type="text" :label="__('Location (optional)')" v-model="defenseForm.location" />
      </template>
      <template #actions>
        <Button variant="solid" :loading="busy" :disabled="!defenseForm.starts_on" @click="doScheduleDefense">
          {{ __('Schedule') }}
        </Button>
      </template>
    </Dialog>

    <!-- Add committee member (advisor) -->
    <Dialog v-model="committeeDialog" :options="{ title: __('Add Committee Member') }">
      <template #body-content>
        <div class="flex gap-2 mb-3">
          <Button :variant="memberForm.kind === 'internal' ? 'solid' : 'subtle'" size="sm" @click="memberForm.kind = 'internal'">
            {{ __('Instructor') }}
          </Button>
          <Button :variant="memberForm.kind === 'external' ? 'solid' : 'subtle'" size="sm" @click="memberForm.kind = 'external'">
            {{ __('External') }}
          </Button>
        </div>
        <Link v-if="memberForm.kind === 'internal'" doctype="Instructor" :label="__('Instructor')"
          :value="memberForm.instructor" @change="(v) => (memberForm.instructor = v)" />
        <template v-else>
          <FormControl type="text" :label="__('Name')" v-model="memberForm.external_name" class="mb-3" />
          <FormControl type="text" :label="__('Email (optional)')" v-model="memberForm.email_external" />
        </template>
      </template>
      <template #actions>
        <Button variant="solid" :loading="busy"
          :disabled="memberForm.kind === 'internal' ? !memberForm.instructor : !memberForm.external_name"
          @click="addMember">{{ __('Add') }}</Button>
      </template>
    </Dialog>

    <!-- Milestone instructions (rich text) -->
    <Dialog v-model="infoDialog" :options="{ title: infoTitle, size: '2xl' }">
      <template #body-content>
        <div class="prose prose-sm max-w-none text-ink-gray-7" v-html="infoContent"></div>
      </template>
    </Dialog>
  </div>
</template>

<script setup>
import { computed, reactive, ref } from 'vue'
import { Badge, Button, Dialog, FileUploader, FormControl, LoadingIndicator, call, createResource, toast } from 'frappe-ui'
import { Disclosure, DisclosureButton, DisclosurePanel } from '@headlessui/vue'
import { ChevronRight, Mail, Info, X, Plus, CalendarCheck } from 'lucide-vue-next'
import Link from '@/components/Controls/Link.vue'
import RichTextEditor from '@/components/RichTextEditor.vue'
import InstructorAvatar from '@/components/InstructorAvatar.vue'
import ContactChannelIcons from '@/components/ContactChannelIcons.vue'
import CulminatingProjectSubmission from '@/components/CulminatingProjectSubmission.vue'
import { statusTheme } from '@/utils/statusTheme'
import { fileName } from '@/utils/file'
import { uploadLimits, validateFileSize } from '@/utils'

const props = defineProps({ name: { type: String, required: true } })
// Announce that this project changed, so a parent list/badge can refresh.
const emit = defineEmits(['changed'])

const cp = createResource({
  url: 'seminary.seminary.doctype.culminating_project.culminating_project.get_culminating_project',
  makeParams() {
    return { name: props.name }
  },
  auto: true,
})

// Upload unattached (a private File owned by the uploader) — students only have
// read on Culminating Project, so binding the upload to it would 403. The server
// (add_submission / review_submission / record_signoff) re-attaches the File to
// the project so advisors/staff inherit read access.
const uploadArgs = { private: 1, folder: 'Home/Attachments' }

const today = new Date().toISOString().slice(0, 10)
function isOverdue(m) {
  return m.due_date && m.due_date < today && m.status !== 'Approved' && m.status !== 'Waived'
}
function signoffOf(m, role) {
  return (m.signoffs || []).find((s) => s.role === role && s.decision === 'Approved')
}
function canSignOff(m) {
  const role = cp.data?.viewer?.my_role
  return ['Advisor', 'Second Reader', 'Third Reader'].includes(role) && m.required_roles.includes(role)
}
// The advisor (or staff) records the committee's sign-off on its behalf.
function canSignCommittee(m) {
  return !!cp.data?.viewer?.can_sign_committee && m.required_roles.includes('Committee') && !signoffOf(m, 'Committee')
}
const committeeNames = computed(() =>
  (cp.data?.committee || []).map((c) => c.member_name).filter(Boolean).join(', ')
)
// The advisor owns the committee — creates it and signs on its behalf.
const canManageCommittee = computed(() => !!cp.data?.viewer?.can_sign_committee)
const committeeEmails = computed(() =>
  (cp.data?.committee || []).map((c) => c.email).filter(Boolean).join(',')
)
// A milestone expects student work when it requires a submission or has reader
// sign-offs (you can't sign off on nothing). Mirrors the backend _student_action.
function submittable(m) {
  return !!(m.requires_submission || (m.required_roles && m.required_roles.length))
}
function latestSub(m) {
  const s = m.submissions || []
  return s.length ? s[s.length - 1] : null
}
function priorSubs(m) {
  const s = m.submissions || []
  return s.length > 1 ? s.slice(0, -1).reverse() : []
}

const infoCardClass = computed(() => {
  const s = cp.data?.student_action?.state
  if (s === 'work') return 'bg-surface-amber-2 text-ink-amber-3'
  if (s === 'waiting') return 'bg-surface-blue-1 text-ink-blue-3'
  return 'bg-surface-green-1 text-ink-green-3'
})

const busy = ref(false)

// Abstract — the student may edit it until the project is defended.
const canEditAbstract = computed(() => !!cp.data?.viewer?.can_submit && !cp.data?.defended_on)
const abstractDialog = ref(false)
const abstractDraft = ref('')
function openAbstract() {
  abstractDraft.value = cp.data?.abstract || ''
  abstractDialog.value = true
}
async function saveAbstract() {
  busy.value = true
  try {
    await call('seminary.seminary.doctype.culminating_project.culminating_project.save_abstract', {
      name: props.name,
      abstract: abstractDraft.value,
    })
    toast.success(__('Abstract saved'))
    abstractDialog.value = false
    cp.reload()
    emit('changed')
  } catch (e) {
    toast.error(e.messages?.[0] || e.message || __('Could not save abstract'))
  } finally {
    busy.value = false
  }
}

// Milestone instructions popup (rich-text description from the type template)
const infoDialog = ref(false)
const infoTitle = ref('')
const infoContent = ref('')
function openInfo(m) {
  infoTitle.value = m.milestone_name
  infoContent.value = m.description || ''
  infoDialog.value = true
}

// Schedule defense (advisor)
const defenseDialog = ref(false)
const defenseForm = reactive({ milestone: null, starts_on: '', location: '' })
function openDefense(m) {
  Object.assign(defenseForm, { milestone: m.row, starts_on: '', location: '' })
  defenseDialog.value = true
}
async function doScheduleDefense() {
  busy.value = true
  try {
    await call('seminary.seminary.doctype.culminating_project.culminating_project.create_milestone_event', {
      culminating_project: props.name,
      milestone_row: defenseForm.milestone,
      starts_on: defenseForm.starts_on.replace('T', ' '),
      location: defenseForm.location || null,
    })
    toast.success(__('Defense scheduled'))
    defenseDialog.value = false
    cp.reload()
    emit('changed')
  } catch (e) {
    toast.error(e.messages?.[0] || e.message || __('Could not schedule defense'))
  } finally {
    busy.value = false
  }
}

// Committee management (advisor)
const committeeDialog = ref(false)
const memberForm = reactive({ kind: 'internal', instructor: '', external_name: '', email_external: '' })
function openAddMember() {
  Object.assign(memberForm, { kind: 'internal', instructor: '', external_name: '', email_external: '' })
  committeeDialog.value = true
}
async function addMember() {
  busy.value = true
  try {
    await call('seminary.seminary.doctype.culminating_project.culminating_project.add_committee_member', {
      culminating_project: props.name,
      instructor: memberForm.kind === 'internal' ? memberForm.instructor : null,
      external_name: memberForm.kind === 'external' ? memberForm.external_name : null,
      email_external: memberForm.kind === 'external' ? memberForm.email_external || null : null,
    })
    toast.success(__('Committee updated'))
    committeeDialog.value = false
    cp.reload()
    emit('changed')
  } catch (e) {
    toast.error(e.messages?.[0] || e.message || __('Could not add member'))
  } finally {
    busy.value = false
  }
}
async function removeMember(row) {
  busy.value = true
  try {
    await call('seminary.seminary.doctype.culminating_project.culminating_project.remove_committee_member', {
      culminating_project: props.name,
      row,
    })
    toast.success(__('Member removed'))
    cp.reload()
    emit('changed')
  } catch (e) {
    toast.error(e.messages?.[0] || e.message || __('Could not remove member'))
  } finally {
    busy.value = false
  }
}

// Submit (student) — the type is derived server-side, never chosen here.
const submitDialog = ref(false)
const submitForm = reactive({ milestone: null, milestone_name: '', note: '', file: '' })
const submitTypeHint = computed(() => {
  const m = (cp.data?.milestones || []).find((x) => x.row === submitForm.milestone)
  if (!m) return __('Draft')
  if (m.kind === 'Proposal') return __('Proposal')
  return latestSub(m) ? __('Revision') : __('Draft')
})
function openSubmit(m) {
  submitForm.milestone = m.row
  submitForm.milestone_name = m.milestone_name
  submitForm.note = ''
  submitForm.file = ''
  submitDialog.value = true
}
async function doSubmit() {
  busy.value = true
  try {
    await call('seminary.seminary.doctype.culminating_project.culminating_project.add_submission', {
      name: props.name,
      attachment: submitForm.file,
      student_note: submitForm.note || null,
      milestone_row: submitForm.milestone,
    })
    toast.success(__('Submitted'))
    submitDialog.value = false
    cp.reload()
    emit('changed')
  } catch (e) {
    toast.error(e.messages?.[0] || e.message || __('Could not submit'))
  } finally {
    busy.value = false
  }
}

// Review submission OR milestone sign-off (reader)
const reviewDialog = ref(false)
const reviewMode = ref('signoff') // 'signoff' | 'submission'
const reviewForm = reactive({ milestone: null, round: null, role: '', decision: '', comment: '', file: '' })
const reviewTitle = computed(() => {
  if (reviewMode.value !== 'signoff') return __('Review Submission')
  return reviewForm.role === 'Committee' ? __('Committee Sign-off') : __('Milestone Sign-off')
})
const decisionOptions = computed(() =>
  reviewMode.value === 'signoff'
    ? ['Approved', 'Revisions Required']
    : ['Accepted', 'Revisions Required', 'Rejected']
)
function openSignoff(m, role) {
  reviewMode.value = 'signoff'
  Object.assign(reviewForm, {
    milestone: m.row,
    round: null,
    role: role || cp.data.viewer.my_role,
    decision: 'Approved',
    comment: '',
    file: '',
  })
  reviewDialog.value = true
}
function openReview(m) {
  reviewMode.value = 'submission'
  Object.assign(reviewForm, { milestone: m.row, round: m.submission.round, role: '', decision: 'Accepted', comment: '', file: '' })
  reviewDialog.value = true
}
async function doReview() {
  busy.value = true
  try {
    if (reviewMode.value === 'signoff') {
      await call('seminary.seminary.doctype.culminating_project.culminating_project.record_signoff', {
        culminating_project: props.name,
        milestone_row: reviewForm.milestone,
        role: reviewForm.role,
        decision: reviewForm.decision,
        comment: reviewForm.comment || null,
        attachment: reviewForm.file || null,
      })
    } else {
      await call('seminary.seminary.doctype.culminating_project.culminating_project.review_submission', {
        culminating_project: props.name,
        round: reviewForm.round,
        decision: reviewForm.decision,
        comment: reviewForm.comment || null,
        attachment: reviewForm.file || null,
      })
    }
    toast.success(__('Saved'))
    reviewDialog.value = false
    cp.reload()
    emit('changed')
  } catch (e) {
    toast.error(e.messages?.[0] || e.message || __('Could not save'))
  } finally {
    busy.value = false
  }
}
</script>
