<template>
    <div v-if="isStudent">

        <h2 class="text-xl font-bold text-gray-800 sticky flex items-center justify-between top-0 z-10 border-b bg-surface-white px-3 py-2.5 sm:px-5">
        {{ __('My Transcripts') }}
        </h2>
	<div v-if="Object.keys(groupedData).length > 0" class="px-5 py-4">
	  <div v-for="(group, program) in sortedGroupedData" :key="program">
        <h2 class="text-lg font-bold text-gray-700">{{ program }}</h2>
        <br>

		<ListView :columns="tableData.columns" :rows="group" :options="{
		  selectable: false,
		  showTooltip: false,
		  onRowClick: () => { },
		}" row-key="id">
		  <ListHeader>
			<ListHeaderItem v-for="column in tableData.columns" :key="column.key" :item="column" />
		  </ListHeader>
		  <ListRow v-for="row in group" :key="row.id" :row="row" v-slot="{ column, item }">
			<ListRowItem :item="item" :align="column.align">
			</ListRowItem>
		  </ListRow>
		</ListView>
		<br>
	  </div>
	</div>
	<div v-else>
	  <MissingData message="No grades found" />
	</div>
  </div>
    <div v-else class="flex flex-col items-center justify-center">
		<p class="text-lg font-bold text-gray-500">{{ __('Individual Student Transcripts are only displayed for Students') }}</p>
	</div>
  </template>

<script setup>
import { Dropdown, FeatherIcon, ListView, createResource, createListResource, ListHeader, ListHeaderItem, ListRow, ListRowItem, Button } from 'frappe-ui';
import { reactive, ref, computed, inject } from 'vue';
import MissingData from '@/components/MissingData.vue';
import { usersStore} from '../stores/user'


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
      label: 'Course',
      key: 'course_name',
      width: 1,
    },
    {
      label: 'Academic Term',
      key: 'academic_term',
      width: 1,
    },
    {
      label: 'Credits',
      key: 'credits',
      width: 1,
    },
    {
      label: 'Grade Code',
      key: 'pec_finalgradecode',
      width: 1,
    },
    {
      label: 'Grade',
      key: 'pec_finalgradenum',
      width: 1,
    },
    {
      label: 'Status',
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