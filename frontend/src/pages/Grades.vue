<template>
  <div v-if="isStudent">

    <h2
      class="text-xl font-bold text-ink-gray-8 sticky flex items-center justify-between top-0 z-10 border-b bg-surface-white px-3 py-2.5 sm:px-5">
      {{ __('My Transcripts') }}
      <!-- Only offered once there is something to see: the profile is empty
           and confusing for a student on a numerically graded programme. -->
      <router-link v-if="hasCompetencies" :to="{ name: 'CompetencyProfile' }">
        <Button variant="subtle" size="sm">{{ __('My Formation') }}</Button>
      </router-link>
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
            <template v-for="row in group" :key="row.id">
              <tr class="border-b" :class="competenciesFor(row).length ? 'border-b-0' : ''">
                <td class="py-2 px-3">
                  <div class="text-ink-gray-9">{{ row.course_name }}</div>
                  <div class="text-xs text-ink-gray-5">{{ row.academic_term }}</div>
                </td>
                <td class="py-2 px-3">{{ row.credits || '—' }}</td>
                <td class="py-2 px-3">
                  <span class="text-ink-gray-9">{{ row.pec_finalgradecode || '—' }}</span>
                  <!-- A competency course's numeric value is a level, not a
                       percentage, so printing it beside the code would read as
                       a score out of 100. -->
                  <span v-if="row.pec_finalgradenum && !competenciesFor(row).length"
                    class="text-xs text-ink-gray-5 ml-1">
                    ({{ row.pec_finalgradenum }})
                  </span>
                </td>
                <td class="py-2 px-3">
                  <Badge :theme="statusTheme(row.status)" :label="row.status" />
                </td>
              </tr>
              <!-- Competency standing belongs under its course, not in a
                   separate table: it is the same result, told in detail. -->
              <tr v-if="competenciesFor(row).length" class="border-b">
                <td colspan="4" class="px-3 pb-3">
                  <div class="flex flex-wrap gap-2">
                    <div v-for="c in competenciesFor(row)" :key="c.course_competency"
                      class="rounded-md border border-outline-gray-2 px-3 py-2">
                      <div class="flex items-center gap-2">
                        <span class="text-sm text-ink-gray-8">{{ c.competency_name }}</span>
                        <Badge v-if="c.final_code" :label="c.final_code"
                          :theme="c.status === 'Competent' ? 'green' : 'orange'" />
                      </div>
                      <div v-if="c.dimensions?.length"
                        class="mt-1 flex flex-wrap gap-x-3 gap-y-0.5 text-xs text-ink-gray-5">
                        <span v-for="d in c.dimensions" :key="d.dimension_code">
                          {{ d.dimension }}: {{ d.final_code || '—' }}
                        </span>
                      </div>
                    </div>
                  </div>
                </td>
              </tr>
            </template>
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
import { Badge, Button, createResource } from 'frappe-ui';
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

// Optional feature: an ordinary transcript never sees this resource resolve to
// anything, and a failure here must not take the transcript down with it.
const competencies = createResource({
  url: 'seminary.seminary.cbe_api.get_competency_transcript',
  auto: true,
  onError: () => { },
});

const competenciesFor = (row) =>
  competencies.data?.[row.course_schedule]?.competencies || [];

const hasCompetencies = computed(
  () => Object.keys(competencies.data || {}).length > 0
);

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