<template>
  <div class="Folder">
    <h3>{{ __('Manage Course Folders') }}</h3>
    <div>
      <label>
        <input type="radio" v-model="folderAction" value="select" />
        {{ __('Select Existing Folder') }}
      </label>
      <label class="ml-4">
        <input type="radio" v-model="folderAction" value="create" />
        {{ __('Create New Folder') }}
      </label>
    </div>

    <!--
      A block saved before folders were referenced by docname only has a name.
      Names are no longer unique across scopes, so it is not resolved here; the
      instructor picks the right folder and the block is saved with its docname.
    -->
    <div v-if="needsRelink" class="mt-4 rounded border border-outline-amber-1 bg-surface-amber-1 px-3 py-2 text-sm text-ink-amber-3">
      {{ __('This block refers to folder "{0}" by name and needs re-linking. Select it below to fix it.').format(props.initialFolder) }}
    </div>

    <div v-if="folderAction === 'select'" class="mt-4 mb-4">
      <FormControl
        type="select"
        v-model="selectedFolder"
        :label="__('Select a folder')"
        :options="folderOptions"
        :placeholder="folders.length ? __('Choose a folder') : __('No folders available')"
        :disabled="!folders.length"
      />
    </div>

    <div v-if="folderAction === 'create'" class="mt-4 space-y-3">
      <input type="text" v-model="newFolderName" :placeholder="__('Enter folder name')" />
      <FormControl
        type="select"
        v-model="scope"
        :label="__('Folder belongs to')"
        :options="scopeOptions"
      />
      <p class="text-sm text-ink-gray-6">{{ scopeHelp }}</p>
      <Link v-if="scope !== 'School'" v-model="course" doctype="Course" :label="__('Course')" />
      <FormControl
        v-if="scope === 'Instructor'"
        type="text"
        :label="__('Instructor')"
        :modelValue="folderContext.instructor || __('You have no Instructor record')"
        disabled
      />
      <FormControl
        v-if="scope === 'Section'"
        type="text"
        :label="__('Section')"
        :modelValue="folderContext.course_schedule || __('No section in this context')"
        disabled
      />
      <button @click="createFolder">{{ __('Create Folder') }}</button>
    </div>

    <div v-if="selectedFolder" class="block mt-6 space-y-6">
      <div>
        <div class="text-sm font-medium text-ink-gray-9">{{ __('Current Folder') }}</div>
        <div class="mt-1 flex flex-wrap items-center gap-1 text-sm text-ink-gray-6">
          <template v-for="(crumb, index) in breadcrumbStack" :key="crumb.id || `${crumb.label}-${index}`">
            <button type="button"
              class="rounded px-1.5 py-0.5 text-ink-gray-7 transition hover:bg-ink-gray-2 hover:text-ink-gray-9"
              @click="navigateToBreadcrumb(index)">
              {{ crumb.label }}
            </button>
            <span v-if="index < breadcrumbStack.length - 1">/</span>
          </template>
        </div>
      </div>

      <div class="flex flex-wrap items-center gap-2">
        <input type="text" v-model="newSubfolderName" :placeholder="__('New sub-folder name')"
          class="flex-1 rounded border border-outline-gray-3 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none" />
        <Button size="sm" @click="createSubfolder">
          {{ __('Create Sub-folder') }}
        </Button>
      </div>

      <div>
        <h5 class="mb-2 text-sm font-semibold text-ink-gray-9">{{ __('Sub-folders') }}</h5>
        <div v-if="!subfolders.length" class="text-sm text-ink-gray-5">
          {{ __('No sub-folders yet.') }}
        </div>
        <ul v-else class="space-y-2">
          <li v-for="folder in subfolders" :key="folder.name"
            class="flex items-center justify-between rounded border border-outline-gray-2 px-3 py-2 transition hover:border-outline-gray-3">
            <button type="button" class="flex-1 text-left text-sm font-medium text-ink-blue-link hover:underline"
              @click="openSubfolder(folder)">
              {{ folder.file_name }}
            </button>
          </li>
        </ul>
      </div>

      <div>
        <h5 class="mb-2 text-sm font-semibold text-ink-gray-9">{{ __('Files') }}</h5>
        <div v-if="!files.length" class="text-sm text-ink-gray-5">
          {{ __('No files found in this folder.') }}
        </div>
        <ul v-else class="space-y-2">
          <li v-for="file in files" :key="file.name"
            class="flex items-center gap-3 rounded border border-outline-gray-2 px-3 py-2 transition hover:border-outline-gray-3">
            <a :href="file.file_url" download class="flex-1 truncate text-sm text-ink-blue-link hover:underline">
              {{ file.file_name }}
            </a>
            <Tooltip :text="__('Delete File')" placement="bottom">
              <Trash2 @click.prevent="removeFile(file)" class="h-4 w-4 cursor-pointer text-red-500" />
            </Tooltip>
          </li>
        </ul>
      </div>

      <!--
        Shown instead of the drop zone while uploading. Without it the tab looks
        frozen for as long as the whole batch takes, which on a slow connection is
        minutes — long enough for someone to reasonably conclude it has hung and
        reload, losing the files already sent.
      -->
      <div v-if="upload.active" class="rounded-md border border-outline-gray-3 p-4 text-sm">
        <div class="flex items-center justify-between gap-3">
          <span class="truncate font-medium text-ink-gray-8">{{ upload.fileName }}</span>
          <span class="shrink-0 text-ink-gray-6">
            {{ __('{0} of {1}').format(upload.index, upload.total) }}
          </span>
        </div>
        <div class="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-surface-gray-2">
          <div
            class="h-full rounded-full bg-surface-gray-7 transition-[width] duration-150"
            :style="{ width: upload.percent + '%' }"
          ></div>
        </div>
        <p class="mt-2 text-ink-gray-6">
          <!-- Byte counts, not just a percentage: on a slow link the percentage can
               sit still long enough to look stalled, while the transferred figure
               still moves. -->
          {{ upload.percent }}% · {{ formatMb(upload.sentBytes) }} / {{ formatMb(upload.totalBytes) }} MB
          <span v-if="upload.attempt > 1"> · {{ __('retrying…') }}</span>
        </p>
      </div>

      <div
        v-else
        class="rounded-md border-2 border-dashed border-outline-gray-3 p-6 text-center text-sm transition-colors duration-200 hover:border-outline-gray-4"
        :class="{ 'bg-surface-blue-1 border-outline-blue-1 text-ink-blue-2': isDragActive }" @dragenter.prevent.stop="onDragEnter"
        @dragover.prevent.stop="onDragOver" @dragleave.prevent.stop="onDragLeave" @drop.prevent.stop="onDrop"
        @click="triggerFileSelect">
        <p class="font-medium">{{ __('Drop files here or click to upload') }}</p>
        <p class="mt-1 text-ink-gray-6">
          {{ __('Files will be added to ') }} {{ currentFolderName }}
        </p>
        <input ref="fileInputRef" type="file" class="hidden" multiple @change="uploadFiles" />
      </div>
    </div>
  </div>
</template>

<script setup>
import { createResource, Button, Tooltip, FormControl } from 'frappe-ui';
import { computed, onMounted, ref, watch } from 'vue';
import Link from '@/components/Controls/Link.vue';
import { FolderTool } from '@/utils/foldertool'; // Corrected to named import
import { uploadLimits, validateFileSize } from '@/utils';
import { useRoute } from 'vue-router';
import { Trash2 } from 'lucide-vue-next';

const route = useRoute();

const props = defineProps({
  onAddition: {
    type: Function,
    required: false,
  },
  // Course Folder docname stored in the block; the API resolves this.
  initialFolderRef: {
    type: String,
    default: null,
  },
  // Display label stored in the block. On its own (no docname) it marks a
  // block that predates docname references and needs re-linking.
  initialFolder: {
    type: String,
    default: null,
  },
})

const folderAction = ref('select');
const selectedFolder = ref(null); // Course Folder docname
const foldername = ref(''); // display label of the selected Course Folder
const newFolderName = ref('');
const files = ref([]);
const folders = ref([]);
const course = ref(null);
const scope = ref('Course');
const currentFolderId = ref(null);
const currentFolderName = ref('');
const breadcrumbStack = ref([]);
const subfolders = ref([]);
const isDragActive = ref(false);
const newSubfolderName = ref('');
const fileInputRef = ref(null);

// Who the session user is in this lesson: the Course, the Course Schedule the
// editor is open in, the user's Instructor record (or null) and whether they
// may create School-wide folders. Filled by `folder_context`.
const folderContext = ref({
  course: null,
  course_schedule: null,
  instructor: null,
  can_school: false,
});

// Progress for the file currently in flight. `index`/`total` count files,
// `sentBytes`/`totalBytes` count bytes within the current one.
const upload = ref({
  active: false,
  index: 0,
  total: 0,
  fileName: '',
  percent: 0,
  sentBytes: 0,
  totalBytes: 0,
  attempt: 1,
});

const formatMb = (bytes) => ((bytes || 0) / (1024 * 1024)).toFixed(1);

const getCsrfToken = () => {
  if (typeof window === 'undefined') {
    return null;
  }
  return (
    window.csrf_token ||
    window.frappe?.csrf_token ||
    document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') ||
    null
  );
};

// The lesson routes carry the Course Schedule docname as `courseName`
// (`/courses/:courseName/...`). The backend derives the catalogue Course.
const contextParams = () => {
  const params = {};
  if (route.params.courseName) {
    params.course_schedule = route.params.courseName;
  } else if (course.value) {
    params.course = course.value;
  }
  return params;
};

const needsRelink = computed(() => !!props.initialFolder && !props.initialFolderRef);

const scopeOptions = computed(() => {
  const options = [
    { label: __('Course (shared by every offering)'), value: 'Course' },
    {
      label: __('Instructor (mine, follows me across sections)'),
      value: 'Instructor',
      disabled: !folderContext.value.instructor,
    },
    {
      label: __('Section (this offering only)'),
      value: 'Section',
      disabled: !folderContext.value.course_schedule,
    },
  ];
  if (folderContext.value.can_school) {
    options.push({ label: __('School (every course)'), value: 'School' });
  }
  return options;
});

const scopeHelp = computed(() => {
  switch (scope.value) {
    case 'Instructor':
      return __('Only you can edit it; students of every section you teach of this course can read it.');
    case 'Section':
      return __('Only students enrolled in this section can read it.');
    case 'School':
      return __('Readable by every student and grader; use it for school-wide policies.');
    default:
      return __('Shared by every offering of this course, whoever teaches it.');
  }
});

// One label per folder that says whose it is, so "Readings (Course)" and
// "Readings (mine)" can be told apart in a flat list.
const folderLabel = (folder) => {
  const ctx = folderContext.value;
  let suffix;
  switch (folder.scope) {
    case 'Instructor':
      suffix =
        folder.instructor && folder.instructor === ctx.instructor
          ? __('mine')
          : __('Instructor: {0}').format(folder.instructor || '');
      break;
    case 'Section':
      suffix =
        folder.course_schedule && folder.course_schedule === ctx.course_schedule
          ? __('this section')
          : __('Section: {0}').format(folder.course_schedule || '');
      break;
    case 'School':
      suffix = __('School');
      break;
    case 'Course':
      suffix = __('Course');
      break;
    default:
      // Reached only for a block whose folder is not in the embeddable list.
      suffix = __('not in your list');
  }
  return `${folder.foldername} (${suffix})`;
};

const folderOptions = computed(() =>
  folders.value.map((folder) => ({ label: folderLabel(folder), value: folder.name }))
);

const fetchContext = async () => {
  try {
    const resource = createResource({
      url: 'seminary.seminary.doctype.course_folder.course_folder.folder_context',
      makeParams() {
        return contextParams();
      },
    });
    const result = await resource.fetch();
    folderContext.value = {
      course: result?.course || null,
      course_schedule: result?.course_schedule || null,
      instructor: result?.instructor || null,
      can_school: !!result?.can_school,
    };
    if (!course.value && folderContext.value.course) {
      course.value = folderContext.value.course;
    }
  } catch (error) {
    console.error('Error fetching folder context:', error);
  }
};

const addFolder = () => {
  if (!selectedFolder.value) {
    return;
  }

  if (typeof props.onAddition === 'function') {
    props.onAddition({
      folder_ref: selectedFolder.value,
      folder: foldername.value,
    });
  }
};

const fetchFolders = async () => {
  const foldersResource = createResource({
    url: 'seminary.seminary.doctype.course_folder.course_folder.list_embeddable_folders',
    makeParams() {
      return contextParams();
    },
  });

  try {
    const result = await foldersResource.fetch();
    folders.value = Array.isArray(result) ? result : [];
  } catch (error) {
    console.error('Error listing folders:', error);
    folders.value = [];
  }
  return folders.value;
};

const createFolder = async () => {
  if (!newFolderName.value) {
    alert(__('Folder name is required'));
    return;
  }

  if (scope.value !== 'School' && !course.value) {
    await fetchContext();
  }

  if (scope.value !== 'School' && !course.value) {
    alert(__('Please select a course before creating a folder.'));
    return;
  }
  if (scope.value === 'Instructor' && !folderContext.value.instructor) {
    alert(__('You have no Instructor record, so you cannot create an Instructor folder.'));
    return;
  }
  if (scope.value === 'Section' && !folderContext.value.course_schedule) {
    alert(__('Open the lesson from a section to create a Section folder.'));
    return;
  }

  try {
    const tool = new FolderTool({ data: {}, readOnly: false });
    const folder = await tool.createCourseFolder({
      course: course.value,
      folderName: newFolderName.value,
      scope: scope.value,
      instructor: folderContext.value.instructor,
      courseSchedule: folderContext.value.course_schedule,
    });

    folders.value.push({
      name: folder.name,
      foldername: folder.foldername,
      scope: folder.scope || scope.value,
      instructor: folder.instructor || null,
      course_schedule: folder.course_schedule || null,
      file_reference: folder.file_reference,
      parent_folder: folder.parent_folder,
    });
    folderAction.value = 'select';
    newFolderName.value = '';
    // The selectedFolder watcher loads the root and stores the reference.
    selectedFolder.value = folder.name;
  } catch (error) {
    console.error('Error creating folder:', error);
    alert(error.message || __('Failed to create folder.'));
  }
};

// The root of a Course Folder is addressed by its docname (`course_folder`);
// everything below it by the File docname the listing returned (`folder_id`).
const fetchFiles = async ({ folderId, courseFolder, folderLabel } = {}) => {
  const targetFolderId = folderId ?? currentFolderId.value;
  const targetCourseFolder = courseFolder ?? selectedFolder.value;
  const targetFolderLabel = folderLabel ?? currentFolderName.value ?? foldername.value;

  if (!targetFolderId && !targetCourseFolder) {
    console.warn('No folder selected for fetching files.');
    return;
  }

  const params = targetFolderId
    ? { folder_id: targetFolderId }
    : { course_folder: targetCourseFolder };

  try {
    const FilesInFolder = createResource({
      url: 'seminary.api.folder_upload.get_files_in_folder',
      params,
      auto: true,
    });
    const result = await FilesInFolder.fetch();
    const entries = result?.entries || [];

    subfolders.value = entries.filter((entry) => entry.is_folder);
    files.value = entries.filter((entry) => !entry.is_folder);

    currentFolderId.value = result?.folder_id || targetFolderId || null;
    currentFolderName.value = result?.folder_name || targetFolderLabel || '';

  } catch (error) {
    console.error('Error fetching files:', error);
    subfolders.value = [];
    files.value = [];
  }
};

const uploadFiles = async (event, droppedFiles = null) => {
  const fileList = Array.from(droppedFiles || event?.target?.files || []);
  if (!fileList.length) {
    return;
  }

  if (!currentFolderId.value) {
    alert(__('Please select a folder first.'));
    return;
  }

  const csrfToken = getCsrfToken();
  if (!csrfToken) {
    alert(__('Session expired. Refresh the page and try again.'));
    isDragActive.value = false;
    return;
  }

  // Check everything before sending anything, so an oversized file is reported
  // immediately rather than after the user has waited through the ones before it.
  // Course Folder uploads always go through a worker, so they are bound by the
  // worker cap even where a direct upload would have allowed more.
  const rejected = [];
  const accepted = [];
  for (const file of fileList) {
    const tooBig = validateFileSize(file, { allowDirect: false });
    if (tooBig) {
      rejected.push(`${file.name} — ${tooBig}`);
    } else {
      accepted.push(file);
    }
  }

  const failed = [];
  let uploaded = 0;

  try {
    // One request per file: batching them made the *total* hit the server's
    // request-size ceiling, so a handful of small files failed together with a
    // 413 naming none of them. Sequential rather than parallel, because these
    // uploads are for people on slow connections, where several concurrent
    // transfers mostly means several that time out together.
    for (const [position, file] of accepted.entries()) {
      upload.value = {
        active: true,
        index: position + 1,
        total: accepted.length,
        fileName: file.name,
        percent: 0,
        sentBytes: 0,
        totalBytes: file.size,
        attempt: 1,
      };

      try {
        const stored = await putFile(file, csrfToken);
        uploaded += 1;
        // Show each file the moment it lands, using what the server just told us,
        // rather than re-listing the folder after every upload. The list fills in
        // progressively and a slow connection carries one extra request at the
        // end instead of one per file.
        if (stored?.files?.length) {
          files.value = [...files.value, ...stored.files];
        }
      } catch (error) {
        console.error('Error uploading file:', file.name, error);
        failed.push(`${file.name} — ${error.message || __('Upload failed.')}`);
      }
    }

    if (event?.target) {
      event.target.value = '';
    }

    // Reconcile once against the server, so the list is authoritative rather than
    // whatever the optimistic appends left behind.
    if (uploaded) {
      await fetchFiles();
    }

    // One summary rather than an alert per file: naming every file that did not
    // make it, and why, is what lets the user fix it.
    const problems = [...rejected, ...failed];
    if (problems.length) {
      alert(
        __('{0} of {1} files uploaded.').format(uploaded, fileList.length) +
          '\n\n' +
          problems.join('\n')
      );
    }
  } finally {
    upload.value = { ...upload.value, active: false };
    isDragActive.value = false;
  }
};

/**
 * Send one file, reporting progress.
 *
 * XHR rather than fetch because only XHR exposes upload progress, and a slow
 * upload with no progress is indistinguishable from a hung page.
 *
 * A dropped connection is retried once. These uploads happen on links that fail
 * mid-transfer as a matter of course, and losing a finished 8 MB upload to one
 * blip is worth one automatic attempt. Only transport failures are retried — an
 * answer from the server, including a refusal, is final.
 */
const putFile = (file, csrfToken, attempt = 1) => {
  return new Promise((resolve, reject) => {
    const formData = new FormData();
    formData.append('file', file, file.name);
    // Frappe's own upload endpoint, with our handler as its `method=` callback.
    // Posting to a seminary endpoint directly caps the request body at a value no
    // Desk setting can raise — only a `/api/method/upload_file` path gets the
    // ceiling that honours System Settings → Max File Size.
    formData.append('method', 'seminary.api.folder_upload.upload_to_folder');
    formData.append('is_private', '1');
    formData.append('folder_id', currentFolderId.value);
    // Which section the lesson was open in, for the folder's activity log.
    if (folderContext.value.course_schedule) {
      formData.append('course_schedule', folderContext.value.course_schedule);
    }

    const xhr = new XMLHttpRequest();
    xhr.open('POST', '/api/method/upload_file', true);
    xhr.withCredentials = true;
    xhr.setRequestHeader('X-Frappe-CSRF-Token', csrfToken);

    xhr.upload.onprogress = (e) => {
      if (!e.lengthComputable) return;
      upload.value = {
        ...upload.value,
        sentBytes: e.loaded,
        totalBytes: e.total,
        percent: Math.round((e.loaded / e.total) * 100),
      };
    };

    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        try {
          // `{folder_id, folder_name, files: [...]}` — the caller shows the
          // returned entry straight away instead of re-listing the folder.
          return resolve(JSON.parse(xhr.responseText).message);
        } catch (e) {
          return resolve(null);
        }
      }
      reject(new Error(uploadErrorMessage(xhr)));
    };

    const onTransportFailure = () => {
      if (attempt < 2) {
        upload.value = { ...upload.value, attempt: attempt + 1, percent: 0, sentBytes: 0 };
        putFile(file, csrfToken, attempt + 1).then(resolve, reject);
        return;
      }
      reject(new Error(__('Connection lost. Please check your network and try again.')));
    };
    xhr.onerror = onTransportFailure;
    xhr.ontimeout = onTransportFailure;

    xhr.send(formData);
  });
};

/**
 * Pull a readable sentence out of a Frappe error body.
 *
 * Frappe buries the real message two levels deep in `_server_messages` — a JSON
 * string holding an array of JSON strings — and writes it as HTML. A caller that
 * does not unwrap it shows the user nothing useful.
 */
const frappeErrorMessage = (responseText, fallback) => {
  let payload = {};
  try {
    payload = JSON.parse(responseText);
  } catch (e) {
    /* fall through */
  }
  try {
    const messages = JSON.parse(payload._server_messages || '[]');
    if (messages.length) {
      const text = JSON.parse(messages[0]).message;
      if (text) {
        // Frappe's messages carry markup; flatten it to plain text.
        const el = document.createElement('div');
        el.innerHTML = text;
        return (el.textContent || '').trim();
      }
    }
  } catch (e) {
    /* fall through */
  }
  return payload.exception || payload.message || fallback;
};

/** Turn a failed upload response into something the user can act on. */
const uploadErrorMessage = (xhr) => {
  // The server refuses an oversized body before any app code runs, so the reply
  // is a bare werkzeug page with no Frappe message in it. `validateFileSize`
  // should have caught this first; name the limit anyway so the rare case that
  // slips through is still actionable.
  if (xhr.status === 413) {
    const mb = uploadLimits.data?.max_upload_mb;
    return mb
      ? __('This file exceeds the maximum size of {0} MB.').format(mb)
      : __('This file is too large for the server to accept.');
  }
  return frappeErrorMessage(xhr.responseText, __('Upload failed.'));
};

const removeFile = async (file) => {
  const csrfToken = getCsrfToken();
  if (!csrfToken) {
    alert(__('Session expired. Refresh the page and try again.'));
    return;
  }
  if (
    !window.confirm(__('Delete {0}? This cannot be undone.').format(file.file_name))
  ) {
    return;
  }

  try {
    const response = await fetch('/api/method/seminary.api.folder_upload.delete_file', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Frappe-CSRF-Token': csrfToken,
      },
      // The document name, not the URL: two files can share a URL once identical
      // bytes are stored once and referenced twice.
      body: JSON.stringify({
        file_id: file.name,
        file_url: file.file_url,
        folder_id: currentFolderId.value || undefined,
        course_schedule: folderContext.value.course_schedule || undefined,
      }),
      credentials: 'include',
    });
    if (!response.ok) {
      throw new Error(
        frappeErrorMessage(await response.text(), __('Could not delete this file.'))
      );
    }
    // Drop it from the list immediately; the refetch below only reconciles.
    files.value = files.value.filter((f) => f.name !== file.name);
  } catch (error) {
    console.error('Error deleting file:', file.file_name, error);
    alert(error.message || __('Could not delete this file.'));
  }

  await fetchFiles();
};

const onDragEnter = (event) => {
  event.preventDefault();
  event.stopPropagation();
  if (!currentFolderId.value) {
    return;
  }
  isDragActive.value = true;
};

const onDragOver = (event) => {
  if (!currentFolderId.value) {
    return;
  }
  event.preventDefault();
  event.stopPropagation();
  event.dataTransfer.dropEffect = 'copy';
  isDragActive.value = true;
};

const onDragLeave = (event) => {
  event.preventDefault();
  event.stopPropagation();
  isDragActive.value = false;
};

const onDrop = async (event) => {
  event.preventDefault();
  event.stopPropagation();
  if (!currentFolderId.value) {
    alert(__('Please select a folder before uploading.'));
    return;
  }
  const droppedFiles = event.dataTransfer?.files;
  if (droppedFiles?.length) {
    await uploadFiles(null, droppedFiles);
  }
  isDragActive.value = false;
};

const triggerFileSelect = () => {
  if (!currentFolderId.value) {
    alert(__('Please select a folder first.'));
    return;
  }
  fileInputRef.value?.click();
};

const openSubfolder = async (folder) => {
  if (!folder?.name) {
    return;
  }
  breadcrumbStack.value = [
    ...breadcrumbStack.value,
    {
      id: folder.name,
      label: folder.file_name,
    },
  ];
  currentFolderId.value = folder.name;
  currentFolderName.value = folder.file_name;
  await fetchFiles({ folderId: folder.name, folderLabel: folder.file_name });
};

const navigateToBreadcrumb = async (index) => {
  if (index < 0 || index >= breadcrumbStack.value.length) {
    return;
  }
  const target = breadcrumbStack.value[index];
  breadcrumbStack.value = breadcrumbStack.value.slice(0, index + 1);
  currentFolderId.value = target.id;
  currentFolderName.value = target.label;
  if (target.id) {
    await fetchFiles({ folderId: target.id, folderLabel: target.label });
  } else {
    await fetchFiles({ courseFolder: selectedFolder.value, folderLabel: target.label });
  }
};

const createSubfolder = async () => {
  if (!newSubfolderName.value) {
    alert(__('Sub-folder name is required.'));
    return;
  }

  if (!currentFolderId.value) {
    alert(__('Please select a folder first.'));
    return;
  }

  try {
    const tool = new FolderTool({ data: {}, readOnly: false });
    await tool.createSubfolder({
      parentFolderId: currentFolderId.value,
      subfolderName: newSubfolderName.value,
      courseSchedule: folderContext.value.course_schedule,
    });

    newSubfolderName.value = '';
    await fetchFiles();
  } catch (error) {
    console.error('Error creating sub-folder:', error);
    alert(error.message || __('Failed to create sub-folder.'));
  }
};

// Watch selectedFolder and update folder state
watch(selectedFolder, async (newFolder) => {
  if (newFolder) {
    const entry = folders.value.find((folder) => folder.name === newFolder);
    foldername.value = entry?.foldername || '';
    currentFolderId.value = entry?.file_reference || null;
    currentFolderName.value = foldername.value;
    // Root listing by docname; the response carries the File id and label, which
    // covers a folder whose `file_reference` is missing from the list entry.
    await fetchFiles({
      folderId: currentFolderId.value,
      courseFolder: newFolder,
      folderLabel: foldername.value,
    });
    if (!foldername.value) {
      foldername.value = currentFolderName.value;
    }
    breadcrumbStack.value = [
      {
        id: currentFolderId.value,
        label: currentFolderName.value || foldername.value,
      },
    ];
    addFolder();
  } else {
    foldername.value = '';
    currentFolderId.value = null;
    currentFolderName.value = '';
    breadcrumbStack.value = [];
    subfolders.value = [];
    files.value = [];
  }
});

const initializeFromFolderRef = async (folderRef) => {
  if (!folderRef) {
    return;
  }
  if (!folders.value.length) {
    await fetchFolders();
  }
  // A folder the user may no longer embed is still opened by docname so the
  // block keeps its reference; the listing call decides whether it is readable.
  if (!folders.value.some((folder) => folder.name === folderRef)) {
    folders.value.push({
      name: folderRef,
      foldername: props.initialFolder || folderRef,
      scope: null,
      instructor: null,
      course_schedule: null,
      file_reference: null,
      parent_folder: null,
    });
  }
  if (selectedFolder.value !== folderRef) {
    selectedFolder.value = folderRef;
  }
};

let hasMounted = false;

onMounted(async () => {
  hasMounted = true;
  await fetchContext();
  await fetchFolders();
  if (props.initialFolderRef) {
    await initializeFromFolderRef(props.initialFolderRef);
  }
});

watch(
  () => props.initialFolderRef,
  async (newValue, oldValue) => {
    if (!hasMounted) {
      return;
    }
    if (!newValue || newValue === oldValue) {
      return;
    }
    await initializeFromFolderRef(newValue);
  }
);
</script>

<style scoped>
.Folder {
  margin: 20px;
  border: 2px solid #ccc;
  padding: 10px;
  border-radius: 5px;
}
</style>
