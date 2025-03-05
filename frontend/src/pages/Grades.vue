<template>
	<div v-if="Object.keys(groupedData).length > 0" class="px-5 py-4">
	  <div v-for="(group, program) in sortedGroupedData" :key="program">
		<h2>{{ program }}</h2>
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
  </template>

<script setup>
import { Dropdown, FeatherIcon, ListView, createResource, createListResource, ListHeader, ListHeaderItem, ListRow, ListRowItem, Button } from 'frappe-ui';
import { studentStore } from '@/stores/student';
import { reactive, ref, computed } from 'vue';
import MissingData from '@/components/MissingData.vue';

const { getCurrentProgram, getStudentInfo } = studentStore();

let studentInfo = getStudentInfo().value;
let currentProgram = getCurrentProgram().value;

const allPrograms = ref([]);
const selectedProgram = ref("");

const initialTableData = ref({
  columns: [
    {
      label: 'Course',
      key: 'course',
    },
    {
      label: 'Academic Term',
      key: 'academic_term',
    }
  ],
  rows: [],
});

const student_programs = createResource({
  url: "seminary.seminary.api.get_student_programs",
  makeParams() {
    return {
      student: studentInfo.name
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
