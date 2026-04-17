<template>
  <div v-if="isStudent">

    <h2
      class="text-xl font-bold text-ink-gray-8 sticky flex items-center justify-between top-0 z-10 border-b bg-surface-white px-3 py-2.5 sm:px-5">
      {{ __('My Transcripts') }}
    </h2>
    <div v-if="Object.keys(groupedData).length > 0" class="px-5 py-4">
      <div v-for="(group, program) in sortedGroupedData" :key="program" class="mb-6">
        <h3 class="text-lg font-bold text-ink-gray-7">{{ program }}</h3>
        <!-- Credit summary -->
        <div v-if="group[0] && group[0].credits_complete" class="flex flex-wrap gap-4 mt-1 mb-3 text-sm text-ink-gray-6">
          <span class="font-medium">
            {{ group[0].totalcredits || 0 }} / {{ group[0].credits_complete }} {{ __('credits') }}
          </span>
          <span v-for="emph in (group[0].emphases || [])" :key="emph.track_name" class="text-ink-gray-5">
            | {{ emph.track_name }}: {{ emph.trackcredits }} / {{ emph.credits_required }}
          </span>
        </div>

        <table class="w-full text-sm">
          <thead>
            <tr class="border-b text-left text-ink-gray-6">
              <th class="py-2 px-3 font-medium">{{ __('Course') }}</th>
              <th class="py-2 px-3 font-medium">{{ __('Credits') }}</th>
              <th class="py-2 px-3 font-medium">{{ __('Grade') }}</th>
              <th class="py-2 px-3 font-medium">{{ __('Status') }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in group" :key="row.id" class="border-b">
              <td class="py-2 px-3">
                <div class="text-ink-gray-9">{{ row.course_name }}</div>
                <div class="text-xs text-ink-gray-5">{{ row.academic_term }}</div>
              </td>
              <td class="py-2 px-3">{{ row.credits || '—' }}</td>
              <td class="py-2 px-3">
                <span class="text-ink-gray-9">{{ row.pec_finalgradecode || '—' }}</span>
                <span v-if="row.pec_finalgradenum" class="text-xs text-ink-gray-5 ml-1">
                  ({{ row.pec_finalgradenum }})
                </span>
              </td>
              <td class="py-2 px-3">
                <Badge :theme="statusTheme(row.status)" :label="row.status" />
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
    <div v-else>
      <MissingData message="No grades found" />
    </div>
  </div>
  <div v-else class="flex flex-col items-center justify-center">
    <p class="text-lg font-bold text-ink-gray-5">{{ __('Individual Student Transcripts are only displayed for Students')
      }}</p>
  </div>
</template>

<script setup>
import { Badge, createResource } from 'frappe-ui';
import { reactive, ref, computed, inject } from 'vue';
import MissingData from '@/components/MissingData.vue';
import { usersStore } from '../stores/user'
import { statusTheme } from '@/utils/statusTheme'


let studentInfo = usersStore()


const user = inject('$user')

const start = ref(0)

let userResource = usersStore()

let isStudent = user.data.is_student

let student = user.data.student

const allPrograms = ref([]);
const selectedProgram = ref("");

const initialTableData = ref({
  columns: [
    {
      label: __('Course'),
      key: 'course',
    },
    {
      label: __('Academic Term'),
      key: 'academic_term',
    }
  ],
  rows: [],
});

const student_programs = createResource({
  url: "seminary.seminary.api.get_student_programs",
  makeParams() {
    return {
      student: student
    }
  },
  onSuccess: (response) => {

    tableData.rows = response.sort((a, b) => {
      if (a.academic_term < b.academic_term) return -1;
      if (a.academic_term > b.academic_term) return 1;
      if (a.course_name < b.course_name) return -1;
      if (a.course_name > b.course_name) return 1;
      return 0;
    });
  },
  auto: true
});

const tableData = reactive({
  rows: [],
  columns: [

    {
      label: __('Course'),
      key: 'course_name',
      width: 1,
    },
    {
      label: __('Academic Term'),
      key: 'academic_term',
      width: 1,
    },
    {
      label: __('Credits'),
      key: 'credits',
      width: 1,
    },
    {
      label: __('Grade Code'),
      key: 'pec_finalgradecode',
      width: 1,
    },
    {
      label: __('Grade'),
      key: 'pec_finalgradenum',
      width: 1,
    },
    {
      label: __('Status'),
      key: 'status',
      width: 1,
    },
  ],
});

const groupedData = computed(() => {
  const grouped = tableData.rows.reduce((acc, row) => {
    const program = row.program;
    if (!acc[program]) {
      acc[program] = [];
    }
    acc[program].push(row);
    return acc;
  }, {});

  return grouped;
});
const sortedGroupedData = computed(() => {
  const sorted = Object.entries(groupedData.value).sort(([programA, groupA], [programB, groupB]) => {
    const activeA = groupA[0].pgmenrol_active;
    const activeB = groupB[0].pgmenrol_active;
    if (activeA > activeB) return -1;
    if (activeA < activeB) return 1;
    if (programA < programB) return -1;
    if (programA > programB) return 1;
    return 0;
  });
  return Object.fromEntries(sorted);
});
</script>