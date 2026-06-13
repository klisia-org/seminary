<template>
       <header
			class="sticky top-0 z-10 flex items-center justify-between border-b bg-surface-white px-3 py-2.5 sm:px-5"
		>
			<Breadcrumbs class="h-7" :items="breadcrumbs" />

		</header>
  <div v-if="!meetingDates.loading && (!meetingDates.data || meetingDates.data.length === 0)" class="px-5 py-10">
    <p class="text-ink-gray-5">{{ __('This course does not have meeting dates set for attendance.') }}</p>
  </div>
  <div v-else class="flex flex-row h-full">
    <!-- Left Side: Course Schedule Meeting Dates -->
    <div class="w-1/4 p-4 border-r">
      <h2 class="text-lg font-semibold mb-4">{{ __('Course Schedule') }}</h2>
      <div class="flex flex-col space-y-2">
  <button
    v-for="meeting in meetingDates.data"
    :key="meeting.name"
    :disabled="new Date(meeting.cs_meetdate) > today"
    class="p-2 border border-outline-gray-2 rounded-md text-left flex justify-between items-center transition-colors"
    :class="{
      'bg-surface-gray-3 text-ink-gray-5 cursor-not-allowed': new Date(meeting.cs_meetdate) > today,
      'bg-surface-blue-2 text-ink-blue-2 border-outline-blue-1 font-semibold': selectedDate?.name === meeting.name,
    }"
    @click="selectDate(meeting)"
    :title="new Date(meeting.cs_meetdate) > today ? __('Cannot set attendance of future dates') : ''"
  >
    <span>
      {{ formatDate(meeting.cs_meetdate) }}
      <span v-if="meeting.cs_fromtime" class="text-xs text-ink-gray-5">· {{ hhmm(meeting.cs_fromtime) }}</span>
      <span v-if="meeting.online" class="text-xs text-ink-gray-5">· {{ __('Online') }}</span>
      <span v-else-if="meeting.room_label" class="text-xs text-ink-gray-5">· {{ meeting.room_label }}</span>
    </span>
    <span v-if="meeting.attendance === 1" class="text-green-500">
      <Check class="h-5 w-5 text-green-500" />
    </span>
  </button>
</div>
    </div>

    <!-- Right Side: Attendance for Selected Date -->

    <div class="w-3/4 p-4">
      <div v-if ="!students.data || students.data.length === 0" class="text-ink-gray-5 text-lg font-semibold mb-4">
        {{ __('There are no students enrolled in this course.') }}
      </div>
      <div v-else class="w-3/4 p-4">
      <div class="flex items-center justify-between mb-4">
        <h2 class="text-lg font-semibold">
          {{ __('Attendance for: ') }} {{ selectedDate?.cs_meetdate || __('Select a date') }}
          <span v-if="selectedDate?.online" class="text-sm font-normal text-ink-gray-5">· {{ __('Online') }}</span>
          <span v-else-if="selectedDate?.room_label" class="text-sm font-normal text-ink-gray-5">· {{ selectedDate.room_label }}</span>
        </h2>
        <div v-if="selectedDate" class="flex items-center gap-2">
          <Button variant="subtle" @click="printBlankSheet">
            <template #prefix><Printer class="w-4 h-4" /></template>
            {{ __('Print blank sheet') }}
          </Button>
          <Button variant="subtle" @click="showCheckinCode">
            <template #prefix><QrCode class="w-4 h-4" /></template>
            {{ __('Show check-in code') }}
          </Button>
        </div>
      </div>

      <!-- Edit Attendance Button -->
      <div v-if="attendanceTaken && !editing" class="mb-4">
        <button
          class="p-2 bg-surface-amber-2 text-ink-amber-3 border border-outline-amber-1 rounded-md"
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
            <th class="p-2 border">{{ __('Attendance') }}</th>
            <th v-if="hasAbsenceLimits" class="p-2 border">{{ __('Absences') }}</th>
          </tr>
        </thead>
        <tbody >
          <tr v-for="student in students.data" :key="student.student">
            <td class="p-2 border">
              <div class="flex items-center justify-center space-x-4">
              <Avatar :image="student.stuimage" :label="student.stuname_roster" size="md" class="avatar border border-outline-gray-2 cursor-auto" />
              <Tooltip :text="`Send Email to ${student.stuname_roster}`" placement="bottom" arrow-class="fill-surface-white">
                <a :href="`mailto:${student.stuemail_rc}`">
                <Send class="w-5 h-5 text-ink-blue-2" />
                </a>
              </Tooltip>
              </div>
            </td>
            <td class="p-2 border">
              <div>{{ student.stuname_roster }}</div>
              <button
                v-if="canReportDisc && atRisk(student.student)"
                class="mt-1 text-xs text-ink-red-3 hover:underline"
                @click="openDisciplinary(student)"
              >
                {{ __('Report Disciplinary Incident') }}
              </button>
            </td>
            <td class="p-2 border text-center">
              <template v-if="attendanceTaken && !editing">
                <span :class="statusClass(attendance[student.student])" class="font-semibold">
                  {{ statusLabel(attendance[student.student]) }}
                </span>
              </template>
              <template v-else>
                <div class="inline-flex rounded-md border border-outline-gray-2 overflow-hidden">
                  <button
                    v-for="opt in statusOptions"
                    :key="opt.value"
                    type="button"
                    class="px-3 py-1 text-sm border-l first:border-l-0 border-outline-gray-2"
                    :class="(attendance[student.student] || 'Absent') === opt.value
                      ? opt.activeClass
                      : 'bg-surface-white text-ink-gray-6 hover:bg-surface-gray-2'"
                    @click="attendance[student.student] = opt.value"
                  >
                    {{ opt.label }}
                  </button>
                </div>
              </template>
            </td>
            <td v-if="hasAbsenceLimits" class="p-2 border text-center">
              <span v-if="standingFor(student.student)?.absence_limit"
                class="font-semibold"
                :class="absenceClass(standingFor(student.student))">
                {{ standingFor(student.student).effective_absences }} /
                {{ standingFor(student.student).absence_limit }}
              </span>
              <span v-else class="text-ink-gray-4">—</span>
            </td>
          </tr>
        </tbody>
      </table>

      <!-- Summary Above the Mark Attendance Button -->
      <div v-if="selectedDate" class="mb-4">
        <p class="text-lg font-semibold mt-4">
          <span class="text-green-500">{{ presentCount }}</span> {{ __('Present') }},
          <span class="text-ink-amber-3">{{ tardyCount }}</span> {{ __('Tardy') }},
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

  <!-- Check-in code / QR dialog -->
  <Dialog v-model="showCodeDialog" :options="{ title: __('Self Check-in Code') }">
    <template #body-content>
      <div v-if="codeLoading" class="flex justify-center py-8">
        <LoadingIndicator class="w-6 h-6 text-ink-gray-5" />
      </div>
      <div v-else class="flex flex-col items-center text-center gap-4 py-2">
        <p class="text-sm text-ink-gray-6">
          {{ __('Students can self-record attendance by entering this code or scanning the QR while class is open.') }}
        </p>
        <div class="text-5xl font-bold tracking-[0.3em] text-ink-gray-9">{{ checkinCode }}</div>
        <img v-if="qrDataUrl" :src="qrDataUrl" alt="Check-in QR code" class="w-56 h-56" />
        <p class="text-xs text-ink-gray-5 break-all">{{ checkinUrl }}</p>
      </div>
    </template>
  </Dialog>

  <!-- Disciplinary incident (attendance), scoped to the selected student -->
  <ReportDisciplinaryIncidentModal
    v-if="canReportDisc"
    v-model="showDiscModal"
    mode="course"
    :course="courseName"
    :prefillCei="discCei"
    :prefillStudentName="discStudentName"
  />

  <!-- Printable blank attendance sheet (rendered to body; visible only when printing) -->
  <Teleport to="body">
    <div class="attendance-print-root">
      <div class="ap-header">
        <h1>{{ course?.data?.course || courseName }}</h1>
        <div class="ap-meta">
          <span>{{ __('Date') }}: {{ selectedDate?.cs_meetdate || '________________' }}</span>
          <span v-if="selectedDate?.cs_fromtime"> &nbsp;|&nbsp; {{ selectedDate.cs_fromtime }}–{{ selectedDate.cs_totime }}</span>
        </div>
        <div class="ap-meta">{{ __('Instructor') }}: ____________________________</div>
      </div>
      <table class="ap-table">
        <thead>
          <tr>
            <th class="ap-num">#</th>
            <th class="ap-name-h">{{ __('Student') }}</th>
            <th>{{ __('Present') }}</th>
            <th>{{ __('Tardy') }}</th>
            <th>{{ __('Absent') }}</th>
            <th class="ap-sig">{{ __('Signature') }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(student, i) in students.data" :key="student.student">
            <td class="ap-num">{{ i + 1 }}</td>
            <td class="ap-name">{{ student.stuname_roster }}</td>
            <td class="ap-box"></td>
            <td class="ap-box"></td>
            <td class="ap-box"></td>
            <td></td>
          </tr>
        </tbody>
      </table>
      <div class="ap-footer">
        {{ __('Present') }}: ______ &nbsp; {{ __('Tardy') }}: ______ &nbsp; {{ __('Absent') }}: ______
        <br /><br />
        {{ __('Instructor signature') }}: ______________________________
      </div>
    </div>
  </Teleport>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { Avatar, Button, createResource, Breadcrumbs, Dialog, LoadingIndicator, Tooltip, call, toast } from 'frappe-ui';
import { useRouter, useRoute } from 'vue-router'
import { Check, Printer, QrCode, Send } from 'lucide-vue-next'
import QRCode from 'qrcode'
import dayjs from 'dayjs'
import { usePortalDisciplinary } from '@/composables/usePortalDisciplinary'
import ReportDisciplinaryIncidentModal from '@/components/Modals/ReportDisciplinaryIncidentModal.vue'

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

const statusOptions = [
  { value: 'Present', label: __('Present'), activeClass: 'bg-surface-green-2 text-ink-green-3 font-semibold' },
  { value: 'Tardy', label: __('Tardy'), activeClass: 'bg-surface-amber-2 text-ink-amber-3 font-semibold' },
  { value: 'Absent', label: __('Absent'), activeClass: 'bg-surface-red-2 text-ink-red-3 font-semibold' },
];

const statusLabel = (s) => ({ Present: __('Present'), Tardy: __('Tardy') }[s] || __('Absent'));
const statusClass = (s) =>
  ({ Present: 'text-green-500', Tardy: 'text-ink-amber-3' }[s] || 'text-red-500');

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

// "6:49:00" / "06:49:00" → "6:49" (slice(0,5) leaves a dangling colon on
// single-digit hours).
const hhmm = (t) => (t ? String(t).split(':').slice(0, 2).join(':') : '')

// Per-student attendance standing (absences vs allowed), keyed by student id.
const standings = createResource({
  url: 'seminary.seminary.attendance.get_course_attendance_standings',
  makeParams() {
    return { course_schedule: props.courseName };
  },
  auto: true,
});

const standingFor = (student) => standings.data?.[student];

const hasAbsenceLimits = computed(() =>
  Object.values(standings.data || {}).some((s) => s.absence_limit > 0)
);

const absenceClass = (s) => {
  if (!s) return 'text-ink-gray-6';
  if (s.attendance_alert_level >= 2) return 'text-ink-red-4';
  if (s.attendance_alert_level === 1) return 'text-ink-amber-3';
  return 'text-ink-gray-7';
};

// --- Disciplinary incident (attendance) -----------------------------------
const { portalDisciplinary } = usePortalDisciplinary();

// Is there an instructor-portal Disciplinary Reason in the Attendance category?
const attendanceReason = createResource({
  url: 'frappe.client.get_list',
  makeParams() {
    return {
      doctype: 'Disciplinary Reason',
      filters: { category: 'Attendance', instructor_portal: 1 },
      fields: ['name'],
      limit_page_length: 1,
    };
  },
  auto: true,
});

const canReportDisc = computed(
  () => portalDisciplinary.value && (attendanceReason.data?.length > 0)
);

const atRisk = (student) => (standingFor(student)?.attendance_alert_level || 0) >= 1;

const showDiscModal = ref(false);
const discCei = ref('');
const discStudentName = ref('');

const openDisciplinary = async (student) => {
  try {
    const res = await call('frappe.client.get_value', {
      doctype: 'Course Enrollment Individual',
      filters: {
        coursesc_ce: props.courseName,
        student_ce: student.student,
        docstatus: 1,
        withdrawn: 0,
      },
      fieldname: 'name',
    });
    const cei = res?.name;
    if (!cei) {
      toast.error(__('No active enrollment found for this student.'));
      return;
    }
    discCei.value = cei;
    discStudentName.value = student.stuname_roster;
    showDiscModal.value = true;
  } catch (e) {
    toast.error(e?.message || __('Could not open the disciplinary form'));
  }
};

// Fetch attendance for the selected date
const attendanceResource = createResource({
  url: 'frappe.client.get_list',
  makeParams() {
    return {
      doctype: 'Student Attendance',
      filters: {
        course_schedule: props.courseName,
        meeting: selectedDate.value?.name, // Filter by the specific meeting
      },
      fields: ['student', 'status', 'date', 'meeting'],
    };
  },
  auto: false, // Do not fetch automatically; fetch when a date is selected
});

// Watch attendanceResource.data to populate attendance data
watch(
  () => attendanceResource.data,
  (data) => {
    if (!data) return;
    attendance.value = {};
    // Default everyone to Absent, then overlay recorded statuses.
    (students.data || []).forEach((s) => {
      attendance.value[s.student] = 'Absent';
    });
    data.forEach((record) => {
      if (record.meeting === selectedDate.value?.name) {
        attendance.value[record.student] = record.status || 'Absent';
      }
    });
    attendanceTaken.value = data.length > 0;
    editing.value = !attendanceTaken.value;
  }
);

watch(
  () => selectedDate.value,
  async (newDate) => {
    if (newDate) {
      await attendanceResource.reload();
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
  Object.values(attendance.value).filter((s) => s === 'Present').length
);
const tardyCount = computed(() =>
  Object.values(attendance.value).filter((s) => s === 'Tardy').length
);
const absentCount = computed(() =>
  Object.values(attendance.value).filter((s) => s !== 'Present' && s !== 'Tardy').length
);

// Mark attendance
const markAttendance = async () => {
  const bucket = (status) =>
    Object.keys(attendance.value)
      .filter((student) => attendance.value[student] === status)
      .map((student) => {
        const studentData = students.data.find((s) => s.student === student);
        if (!studentData) return null;
        return { student, stuname_roster: studentData.stuname_roster };
      })
      .filter(Boolean);

  try {
    const response = await fetch("/api/method/seminary.seminary.api.mark_attendance", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Frappe-CSRF-Token": getCsrfToken(),
      },
      body: JSON.stringify({
        course_schedule: props.courseName,
        date: selectedDate.value.cs_meetdate,
        meeting: selectedDate.value.name,
        students_present: bucket('Present'),
        students_tardy: bucket('Tardy'),
        students_absent: bucket('Absent'),
      }),
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) {
      const message = payload?._server_messages
        ? JSON.parse(payload._server_messages)
            .map((m) => {
              try { return JSON.parse(m).message; } catch { return m; }
            })
            .join('\n')
        : payload?.exception || payload?.message || `HTTP ${response.status}`;
      throw new Error(message);
    }
    if (payload.message) {
      toast.success(__('Attendance updated successfully'));
      meetingDates.reload();
      attendanceResource.reload();
      standings.reload();
    }
  } catch (error) {
    console.error('Error:', error);
    toast.error(error?.message || String(error));
  }
}

const getCsrfToken = () =>
  window.csrf_token ||
  window.frappe?.csrf_token ||
  document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') ||
  ''

// --- Self check-in code / QR ---------------------------------------------
const showCodeDialog = ref(false);
const codeLoading = ref(false);
const checkinCode = ref('');
const checkinUrl = ref('');
const qrDataUrl = ref('');

const showCheckinCode = async () => {
  if (!selectedDate.value) return;
  codeLoading.value = true;
  showCodeDialog.value = true;
  qrDataUrl.value = '';
  try {
    const res = await call('seminary.seminary.course_checkin.ensure_meeting_checkin_code', {
      course_schedule: props.courseName,
      meeting_date: selectedDate.value.cs_meetdate,
      meeting: selectedDate.value.name,
    });
    checkinCode.value = res.checkin_code;
    checkinUrl.value =
      `${window.location.origin}/seminary/attendance-checkin` +
      `?course=${encodeURIComponent(props.courseName)}` +
      `&date=${encodeURIComponent(selectedDate.value.cs_meetdate)}` +
      `&code=${encodeURIComponent(res.checkin_code)}`;
    qrDataUrl.value = await QRCode.toDataURL(checkinUrl.value, { width: 320, margin: 1 });
  } catch (error) {
    toast.error(error?.message || __('Could not generate the check-in code'));
    showCodeDialog.value = false;
  } finally {
    codeLoading.value = false;
  }
};

// --- Printable blank sheet ------------------------------------------------
const clearPrintFlag = () => document.body.classList.remove('printing-attendance');

const printBlankSheet = () => {
  document.body.classList.add('printing-attendance');
  // Defer so the teleported sheet is laid out before the print dialog opens.
  setTimeout(() => window.print(), 50);
};

onMounted(() => window.addEventListener('afterprint', clearPrintFlag));
onBeforeUnmount(() => {
  window.removeEventListener('afterprint', clearPrintFlag);
  clearPrintFlag();
});

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

<!-- Global (un-scoped) print styles: show only the blank sheet when printing. -->
<style>
.attendance-print-root {
  display: none;
}
@media print {
  body.printing-attendance > *:not(.attendance-print-root) {
    display: none !important;
  }
  body.printing-attendance .attendance-print-root {
    display: block !important;
    padding: 24px;
    color: #000;
    font-family: Georgia, 'Times New Roman', serif;
  }
  .attendance-print-root .ap-header {
    margin-bottom: 16px;
  }
  .attendance-print-root .ap-header h1 {
    font-size: 20px;
    font-weight: 700;
    margin: 0 0 6px;
  }
  .attendance-print-root .ap-meta {
    font-size: 13px;
    margin: 2px 0;
  }
  .attendance-print-root .ap-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 13px;
  }
  .attendance-print-root .ap-table th,
  .attendance-print-root .ap-table td {
    border: 1px solid #000;
    padding: 6px 8px;
    text-align: center;
  }
  .attendance-print-root .ap-table .ap-name,
  .attendance-print-root .ap-table .ap-name-h {
    text-align: left;
  }
  .attendance-print-root .ap-table .ap-num {
    width: 32px;
  }
  .attendance-print-root .ap-table .ap-box {
    width: 56px;
  }
  .attendance-print-root .ap-table .ap-sig {
    width: 180px;
  }
  .attendance-print-root .ap-footer {
    margin-top: 18px;
    font-size: 13px;
  }
}
</style>
