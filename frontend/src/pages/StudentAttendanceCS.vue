<template>
       <header
			class="sticky top-0 z-10 flex items-center justify-between border-b bg-surface-white px-3 py-2.5 sm:px-5"
		>
			<Breadcrumbs class="h-7" :items="breadcrumbs" />
			
		</header>
  <div class="flex flex-row h-full">
    <!-- Left Side: Course Schedule Meeting Dates -->
    <div class="w-1/4 p-4 border-r">
      <h2 class="text-lg font-semibold mb-4">{{ __('Course Schedule') }}</h2>
      <div class="flex flex-col space-y-2">
  <button
    v-for="meeting in meetingDates.data"
    :key="meeting.name"
    :disabled="new Date(meeting.cs_meetdate) > today"
    class="p-2 border rounded-md text-left flex justify-between items-center"
    :class="{ 'bg-gray-200': new Date(meeting.cs_meetdate) > today, 'bg-blue-100': selectedDate?.name === meeting.name }"
    @click="selectDate(meeting)"
    :title="new Date(meeting.cs_meetdate) > today ? __('Cannot set attendance of future dates') : ''"
  >
    <span>{{ formatDate(meeting.cs_meetdate) }}</span>
    <span v-if="meeting.attendance === 1" class="text-green-500">
      <Check class="h-5 w-5 text-green-500" />
    </span>
  </button>
</div>
    </div>

    <!-- Right Side: Attendance for Selected Date -->
    
    <div class="w-3/4 p-4">
      <div v-if ="!students.data || students.data.length === 0" class="text-gray-500 text-lg font-semibold mb-4">
        {{ __('There are no students enrolled in this course.') }}
      </div>
      <div v-else class="w-3/4 p-4">
      <h2 class="text-lg font-semibold mb-4">
        {{ __('Attendance for: ') }} {{ selectedDate?.cs_meetdate || __('Select a date') }}
      </h2>

      <!-- Edit Attendance Button -->
      <div v-if="attendanceTaken && !editing" class="mb-4">
        <button
          class="p-2 bg-yellow-200 border rounded-md"
          @click="editAttendance"
          :title="__('All changes will be recorded for audit purposes')"
          
        >
          {{ __('Edit Attendance') }}

        </button>
      </div>

      <!-- Students Table -->
      <table v-if="selectedDate" class="min-w-full table-auto border-collapse">
        <thead>
          <tr>
            <th class="p-2 border">{{ __('Image') }}</th>
            <th class="p-2 border">{{ __('Student Name') }}</th>
            <th class="p-2 border">{{ __('Present') }}</th>
          </tr>
        </thead>
        <tbody >
          <tr v-for="student in students.data" :key="student.student">
            <td class="p-2 border">
              <div class="flex items-center justify-center space-x-4">
              <Avatar :image="student.stuimage" :label="student.stuname_roster" size="md" class="avatar border border-outline-gray-2 cursor-auto" />
              <Tooltip :text="`Send Email to ${student.stuname_roster}`" placement="bottom" arrow-class="fill-surface-white">
                <a :href="`mailto:${student.stuemail_rc}`">
                <Send class="w-5 h-5 text-blue-300" />
                </a>
              </Tooltip>
              </div>
            </td>
            <td class="p-2 border">{{ student.stuname_roster }}</td>
            <td class="p-2 border text-center">
              <template v-if="attendanceTaken && !editing">
                <span v-if="attendance[student.student]" class="text-green-500 font-semibold">{{ __('Present') }}</span>
                <span v-else class="text-red-500 font-semibold">{{ __('Absent') }}</span>
              </template>
              <template v-else>
                <input
                  type="checkbox"
                  v-model="attendance[student.student]"
                />
              </template>
            </td>
          </tr>
        </tbody>
      </table>

      <!-- Summary Above the Mark Attendance Button -->
      <div v-if="selectedDate" class="mb-4">
        <p class="text-lg font-semibold mt-4">
          <span class="text-green-500">{{ presentCount }}</span> {{ __('Present') }},
          <span class="text-red-500">{{ absentCount }}</span> {{ __('Absent') }}
        </p>
      </div>

      <!-- Mark Attendance Button -->
      <div v-if="selectedDate && (!attendanceTaken || attendanceTaken && editing)" class="mt-4">
        <button
          class="p-2 bg-blue-500 text-white rounded-md"
          @click="markAttendance"
          
        >
          {{ __('Mark Attendance') }}
        </button>
      </div>
    </div>
  </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue';
import { Avatar, createResource, Breadcrumbs, Tooltip, toast } from 'frappe-ui';
import { useRouter, useRoute } from 'vue-router'
import { Check, Send } from 'lucide-vue-next'
import dayjs from 'dayjs'

const router = useRouter()
const route = useRoute()

const props = defineProps({
  courseName: {
    type: String,
    required: true,
  },
});

const today = new Date();
const selectedDate = ref(null);
const attendance = ref({});
const attendanceTaken = ref(false);
const editing = ref(false);
const tableRef = ref(null);

// Fetch meeting dates
const meetingDates = createResource({
  url: 'seminary.seminary.utils.get_course_meetingdates',
  makeParams() {
    return {
      course: props.courseName, // Pass the course name to the server-side method
    };
  },
  auto: true,
});
console.log("Meeting dates: ", meetingDates)

// Fetch active students who are not auditing the course
const students = createResource({
  url: 'frappe.client.get_list',
  makeParams() {
    return {
      doctype: 'Scheduled Course Roster',
      filters: {
        course_sc: props.courseName,
        audit_bool: 0,
        active: 1,
      },
      fields: ['student', 'stuname_roster', 'stuimage', 'stuemail_rc'],
      order_by: 'stuname_roster asc',
    };
  },
  auto: true,
});

const formatDate = (dateStr) => {
  return dayjs(dateStr).format('MMM D') // e.g., "Apr 5"
}

// Fetch attendance for the selected date
const attendanceResource = createResource({
  url: 'frappe.client.get_list',
  makeParams() {
    return {
      doctype: 'Student Attendance',
      filters: {
        course_schedule: props.courseName,
        date: selectedDate.value?.cs_meetdate, // Filter by selected date
      },
      fields: ['student', 'status', 'date'],
    };
  },
  auto: false, // Do not fetch automatically; fetch when a date is selected
});

onMounted(() => {
  if (presentCount.value === 0) {
    editing.value = true; // Allow editing if no students are marked as present
  }
});

// Watch attendanceResource.data to populate attendance data
watch(
  () => attendanceResource.data,
  (data) => {
    if (data) {
      attendance.value = {};
      data.forEach((record) => {
        if (record.date === selectedDate.value?.cs_meetdate) { // Ensure filtering by date
          attendance.value[record.student] = record.status === 'Present'; // Populate "Present" as true
        } else {
          attendance.value[record.student] = false; // Populate "Absent" as false
        }
      });
      attendanceTaken.value = Object.keys(attendance.value).length > 0;
    }
  }
);

watch(
  () => selectedDate.value,
  async (newDate) => {
    if (newDate) {
      attendanceResource.data = await attendanceResource.reload(); // Fetch attendance for the selected date
      console.log("Attendance data reloaded: ", attendanceResource.data)
      console.log("Selected date: ", selectedDate.value)
      if (attendanceResource.data.length === 0) {
        attendance.value = {};
        students.data.forEach((student) => {
          attendance.value[student.student] = false;
        });
      }
      
    }
  }
);

// Select a date
const selectDate = async (meeting) => {
  selectedDate.value = meeting;
  editing.value = false;
  await attendanceResource.reload(); // Fetch attendance for the selected date
};

// Edit attendance
const editAttendance = () => {
  editing.value = true;
};

const presentCount = computed(() =>
  Object.values(attendance.value).filter((status) => status).length
);

const absentCount = computed(() =>
  Object.values(attendance.value).filter((status) => !status).length
);

watch(presentCount, (newCount) => {
  if (newCount === 0) {
    editing.value = true; // Allow editing if no students are marked as present
  }
});

// Mark attendance
const markAttendance = async () => {


  //console.log("Attendance Value:", attendance.value);
  //console.log("Students Data:", students.data);

  const studentsPresent = Object.keys(attendance.value)
    .filter((student) => attendance.value[student])
    .map((student) => {
      const studentData = students.data.find((s) => s.student === student);
      if (!studentData) {
        console.error(`Student not found in students.data: ${student}`);
        return null;
      }
      return {
        student,
        stuname_roster: studentData.stuname_roster,
      };
    })
    .filter((student) => student !== null);

  const studentsAbsent = Object.keys(attendance.value)
    .filter((student) => !attendance.value[student])
    .map((student) => {
      const studentData = students.data.find((s) => s.student === student);
      if (!studentData) {
        console.error(`Student not found in students.data: ${student}`);
        return null;
      }
      return {
        student,
        stuname_roster: studentData.stuname_roster,
      };
    })
    .filter((student) => student !== null);

  //console.log("Students Present:", studentsPresent);

 
    const response = await fetch("/api/method/seminary.seminary.api.mark_attendance", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        course_schedule: props.courseName,
        date: selectedDate.value.cs_meetdate,
        students_present: studentsPresent,
        students_absent: studentsAbsent,
      }),
    })

    .then(response => response.json())
    .then(data => {
      if (data.message) {
        toast.success(__('Attendance updated successfully'));
        meetingDates.reload();
        attendanceResource.reload();
      }
    })
    .catch((error) => {
      console.error('Error:', error);
    });
}

const course = createResource({
	url: 'seminary.seminary.utils.get_course_details',
	cache: ['course', props.courseName],
	params: {
		course: props.courseName,
	},
	auto: true,
}) //Neded for the breadcrumbs

const breadcrumbs = computed(() => {
	let items = [{ label: 'Courses', route: { name: 'Courses' } }]
	items.push({
		label: course?.data?.course,
		route: { name: 'CourseDetail', params: { courseName: props.courseName } },
	})
    items.push({
        label: 'Attendance',
        route: { name: 'StudentAttendanceCS', params: { courseName: props.courseName} },
    })
	return items
})
</script>

<style scoped>
/* Add any necessary styles here */
</style>
