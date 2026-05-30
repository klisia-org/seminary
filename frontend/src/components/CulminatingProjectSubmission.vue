<template>
  <div class="text-sm border border-outline-gray-1 rounded-md p-2">
    <div class="flex items-center gap-2 flex-wrap">
      <FileText class="h-4 w-4 text-ink-gray-5 shrink-0" />
      <span class="text-ink-gray-7">{{ submission.submission_type }} · {{ __('round') }} {{ submission.round }}:</span>
      <a :href="submission.attachment" target="_blank" class="text-ink-blue-3 underline">
        {{ fileName(submission.attachment) }}
      </a>
      <span v-if="submission.submitted_on" class="text-xs text-ink-gray-4">{{ submission.submitted_on.slice(0, 10) }}</span>
      <Badge v-if="submission.reviewer_decision" class="ml-auto" :theme="statusTheme(submission.reviewer_decision)"
        :label="submission.reviewer_decision" />
    </div>
    <p v-if="submission.student_note" class="text-xs text-ink-gray-5 mt-1">{{ submission.student_note }}</p>
    <p v-if="submission.reviewer_comment || submission.reviewer_attachment" class="text-xs text-ink-gray-6 mt-1">
      <span class="font-medium">{{ submission.reviewer_name || submission.reviewer }}:</span>
      <span v-if="submission.reviewer_comment" v-html="submission.reviewer_comment"></span>
      <a v-if="submission.reviewer_attachment" :href="submission.reviewer_attachment" target="_blank"
        class="text-ink-blue-3 ml-1 underline">{{ fileName(submission.reviewer_attachment) }}</a>
    </p>
  </div>
</template>

<script setup>
import { Badge } from 'frappe-ui'
import { FileText } from 'lucide-vue-next'
import { statusTheme } from '@/utils/statusTheme'
import { fileName } from '@/utils/file'

defineProps({ submission: { type: Object, required: true } })
</script>
