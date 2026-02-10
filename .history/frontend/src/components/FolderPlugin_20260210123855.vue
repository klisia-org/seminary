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

    <div v-if="folderAction === 'select'" class="mt-4 mb-4">
      <Link
        v-model="selectedFolder"
        doctype="Course Folder"
        options="foldername"
        :label="__('Select a folder')"


        />
    </div>

    <div v-if="folderAction === 'create'">
      <input type="text" v-model="newFolderName" :placeholder="__('Enter folder name')" />
      <Link
        v-model="course"
        doctype="Course"
        :label="__('Select a course')"
        />
      <button @click="createFolder">{{ __('Create Folder') }}</button>
    </div>

    <div v-if="selectedFolder" class="block mt-6 space-y-6">
      <div>
        <div class="text-sm font-medium text-ink-gray-9">{{ __('Current Folder') }}</div>
        <div class="mt-1 flex flex-wrap items-center gap-1 text-sm text-ink-gray-6">
          <template v-for="(crumb, index) in breadcrumbStack" :key="crumb.id || `${crumb.label}-${index}`">
            <button
              type="button"
              class="rounded px-1.5 py-0.5 text-ink-gray-7 transition hover:bg-ink-gray-2 hover:text-ink-gray-9"
              @click="navigateToBreadcrumb(index)"
            >
              {{ crumb.label }}
            </button>
            <span v-if="index < breadcrumbStack.length - 1">/</span>
          </template>
        </div>
      </div>

      <div class="flex flex-wrap items-center gap-2">
        <input
          type="text"
          v-model="newSubfolderName"
          :placeholder="__('New sub-folder name')"
          class="flex-1 rounded border border-outline-gray-3 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
        />
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
          <li
            v-for="folder in subfolders"
            :key="folder.name"
            class="flex items-center justify-between rounded border border-outline-gray-2 px-3 py-2 transition hover:border-outline-gray-3"
          >
            <button
              type="button"
              class="flex-1 text-left text-sm font-medium text-blue-600 hover:underline"
              @click="openSubfolder(folder)"
            >
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
          <li
            v-for="file in files"
            :key="file.file_url || file.name"
            class="flex items-center gap-3 rounded border border-outline-gray-2 px-3 py-2 transition hover:border-outline-gray-3"
          >
            <a
              :href="file.file_url"
              download
              class="flex-1 truncate text-sm text-blue-600 hover:underline"
            >
              {{ file.file_name }}
            </a>
            <Tooltip :text="__('Delete File')" placement="bottom">
              <Trash2
                @click.prevent="removeFile(file.file_url)"
                class="h-4 w-4 cursor-pointer text-red-500"
              />
            </Tooltip>
          </li>
        </ul>
      </div>

      <div
        class="rounded-md border-2 border-dashed border-outline-gray-3 p-6 text-center text-sm transition-colors duration-200 hover:border-outline-gray-4"
        :class="{ 'bg-blue-50 border-blue-500 text-blue-700': isDragActive }"
        @dragenter.prevent.stop="onDragEnter"
        @dragover.prevent.stop="onDragOver"
        @dragleave.prevent.stop="onDragLeave"
        @drop.prevent.stop="onDrop"
        @click="triggerFileSelect"
      >
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
import { createResource, Button, Tooltip } from 'frappe-ui';
import { onMounted, ref, watch } from 'vue';
import Link from '@/components/Controls/Link.vue';
import { FolderTool } from '@/utils/foldertool'; // Corrected to named import
import { useRoute } from 'vue-router';
import { Trash2 } from 'lucide-vue-next';

const route = useRoute();

const folderAction = ref('select');
const selectedFolder = ref(null);
const foldername = ref(''); // Declare foldername globally
const newFolderName = ref('');
const files = ref([]);
const folders = ref([]);
const course = ref(null);
const currentFolderId = ref(null);
const currentFolderName = ref('');
const breadcrumbStack = ref([]);
const subfolders = ref([]);
const isDragActive = ref(false);
const newSubfolderName = ref('');
const fileInputRef = ref(null);

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

const fetchCourse = async () => {
  const courseName = route.params.courseName;
  console.log("Course Name: ", courseName);
  if (courseName) {
    const resource = createResource({
      url: 'frappe.client.get_value',
      makeParams(values) {
        return {
          doctype: 'Course Schedule',
          fieldname: 'course',
          filters: {
            name: courseName,
          },
        };
      },
    });
    const result = await resource.fetch(); // Wait for the resource to fetch data
    course.value = result.course; // Assign the fetched course value
    console.log("Fetched Course: ", course.value);
  } else {
    console.error("Course name not found in route params");
  return null;
}};

const props = defineProps({
  onAddition: {
    type: Function,
    required: false,
  },
  initialFolder: {
    type: String,
    default: null,
  },
})

const addFolder = () => {
  if (!foldername.value) {
    return;
  }

  const folder = foldername.value;
  if (typeof props.onAddition === 'function') {
    props.onAddition(folder);
  }
};

const initializeFromFolder = async (folderLabel, { refreshFolders = true } = {}) => {
  const targetFolder = folderLabel?.trim();
  if (!targetFolder) {
    return;
  }

  if (refreshFolders || !folders.value.length) {
    await fetchFolders();
  }

  const matchingFolder = folders.value.find(
    (folder) => folder.foldername === targetFolder || folder.name === targetFolder
  );

  if (matchingFolder) {
    if (selectedFolder.value !== matchingFolder.name) {
      selectedFolder.value = matchingFolder.name;
    }
    return;
  }

  foldername.value = targetFolder;
  currentFolderName.value = targetFolder;
  breadcrumbStack.value = [
    {
      id: null,
      label: targetFolder,
      folderName: targetFolder,
    },
  ];
  await fetchFiles({ folderLabel: targetFolder });
  breadcrumbStack.value = [
    {
      id: currentFolderId.value,
      label: currentFolderName.value || targetFolder,
      folderName: foldername.value || targetFolder,
    },
  ];
};

const fetchFolders = async () => {
  if (!course.value) {
    await fetchCourse();
  }

  if (!course.value) {
    return [];
  }

  const foldersResource = createResource({
    url: 'frappe.client.get_list',
    makeParams() {
      return {
        doctype: 'Course Folder',
        filters: {
          course: course.value,
        },
        fields: ['name', 'foldername', 'file_reference', 'parent_folder'],
      };
    },
  });

  const result = await foldersResource.fetch();
  folders.value = result;
  return folders.value;
};

const createFolder = async () => {
  if (!newFolderName.value) {
    alert(__('Folder name is required'));
    return;
  }

  if (!course.value) {
    await fetchCourse();
  }

  if (!course.value) {
    alert(__('Please select a course before creating a folder.'));
    return;
  }

  try {
    const tool = new FolderTool({ data: {}, readOnly: false });
    const folder = await tool.createCourseFolder(course.value, newFolderName.value);

    folders.value.push({
      name: folder.name,
      foldername: folder.foldername,
      file_reference: folder.file_reference,
      parent_folder: folder.parent_folder,
    });
    foldername.value = folder.foldername;
    currentFolderId.value = folder.file_reference;
    currentFolderName.value = folder.foldername;
    selectedFolder.value = folder.name;
    breadcrumbStack.value = [
      {
        id: currentFolderId.value,
        label: currentFolderName.value,
        folderName: folder.foldername,
      },
    ];
    folderAction.value = 'select';
    newFolderName.value = '';
    await fetchFiles({ folderId: currentFolderId.value, folderLabel: currentFolderName.value });
  } catch (error) {
    console.error('Error creating folder:', error);
    alert(error.message || __('Failed to create folder.'));
  }
};

const fetchFiles = async ({ folderId, folderLabel } = {}) => {
  const targetFolderId = folderId ?? currentFolderId.value;
  const targetFolderLabel = folderLabel ?? currentFolderName.value ?? foldername.value;

  if (!targetFolderId && !targetFolderLabel) {
    console.warn('No folder selected for fetching files.');
    return;
  }

  try {
    const FilesInFolder = createResource({
      url: 'seminary.api.folder_upload.get_files_in_folder',
      params: {
        folder_id: targetFolderId,
        foldername: targetFolderLabel,
      },
      auto: true,
    });
    const result = await FilesInFolder.fetch();
    const entries = result?.entries || [];

    subfolders.value = entries.filter((entry) => entry.is_folder);
    files.value = entries.filter((entry) => !entry.is_folder);

    currentFolderId.value = result?.folder_id || targetFolderId;
    currentFolderName.value = result?.folder_name || targetFolderLabel;
  foldername.value = currentFolderName.value;

  } catch (error) {
    console.error('Error fetching files:', error);
    subfolders.value = [];
    files.value = [];
  }
};

const uploadFiles = async (event, droppedFiles = null) => {
  const fileList = droppedFiles || event?.target?.files;
  if (!fileList || !fileList.length) {
    return;
  }

  if (!currentFolderId.value && !currentFolderName.value) {
    alert(__('Please select a folder first.'));
    return;
  }

  try {
    const formData = new FormData();
    for (const file of fileList) {
      formData.append('files', file);
    }
    if (currentFolderId.value) {
      formData.append('folder_id', currentFolderId.value);
    }
    if (currentFolderName.value) {
      formData.append('foldername', currentFolderName.value);
    }

    const csrfToken = getCsrfToken();
    if (!csrfToken) {
      alert(__('Session expired. Refresh the page and try again.'));
      return;
    }

    const response = await fetch('/api/method/seminary.api.folder_upload.upload_folder', {
      method: 'POST',
      body: formData,
      headers: {
        'X-Frappe-CSRF-Token': csrfToken,
      },
      credentials: 'include',
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      console.error('Error uploading files:', error);
      alert(`Error: ${error.message || 'Failed to upload files.'}`);
      return;
    }

    console.log('Files uploaded successfully.');
    if (event?.target) {
      event.target.value = '';
    }
    await fetchFiles();
  } catch (error) {
    console.error('Error uploading files:', error);
    alert('An error occurred while uploading files.');
  } finally {
    isDragActive.value = false;
  }
};

const removeFile = async (fileUrl) => {
  const csrfToken = getCsrfToken();
  if (!csrfToken) {
    alert('Session expired. Refresh the page and try again.');
    return;
  }
  await fetch('/api/method/seminary.api.folder_upload.delete_file', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Frappe-CSRF-Token': csrfToken,
      },
      body: JSON.stringify({ file_url: fileUrl }),
      credentials: 'include',
    }).then((response) => response.json());

  await fetchFiles();
};

const onDragEnter = (event) => {
  event.preventDefault();
  event.stopPropagation();
  if (!currentFolderId.value && !currentFolderName.value) {
    return;
  }
  isDragActive.value = true;
};

const onDragOver = (event) => {
  if (!currentFolderId.value && !currentFolderName.value) {
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
  if (!currentFolderId.value && !currentFolderName.value) {
    alert('Please select a folder before uploading.');
    return;
  }
  const droppedFiles = event.dataTransfer?.files;
  if (droppedFiles?.length) {
    await uploadFiles(null, droppedFiles);
  }
  isDragActive.value = false;
};

const triggerFileSelect = () => {
  if (!currentFolderId.value && !currentFolderName.value) {
    alert('Please select a folder first.');
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
      folderName: folder.file_name,
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
  foldername.value = target.folderName || target.label;
  await fetchFiles({ folderId: target.id, folderLabel: target.folderName || target.label });
};

const createSubfolder = async () => {
  if (!newSubfolderName.value) {
    alert('Sub-folder name is required.');
    return;
  }

  if (!currentFolderId.value && !currentFolderName.value) {
    alert('Please select a folder first.');
    return;
  }

  try {
    const tool = new FolderTool({ data: {}, readOnly: false });
    await tool.createSubfolder({
      parentFolderId: currentFolderId.value,
      parentFolderName: currentFolderName.value,
      subfolderName: newSubfolderName.value,
    });

    newSubfolderName.value = '';
    await fetchFiles();
  } catch (error) {
    console.error('Error creating sub-folder:', error);
    alert(error.message || 'Failed to create sub-folder.');
  }
};

// Watch selectedFolder and update folder state
watch(selectedFolder, async (newFolder) => {
  if (newFolder) {
    try {
      const resource = createResource({
        url: 'frappe.client.get_value',
        makeParams() {
          return {
            doctype: 'Course Folder',
            fieldname: ['foldername', 'file_reference', 'parent_folder'],
            filters: {
              name: newFolder,
            },
          };
        },
      });
      const result = await resource.fetch();
      foldername.value = result?.foldername || '';
      currentFolderId.value = result?.file_reference || null;
      currentFolderName.value = result?.foldername || '';
      breadcrumbStack.value = [
        {
          id: currentFolderId.value,
          label: currentFolderName.value,
          folderName: foldername.value,
        },
      ];
      addFolder();
      await fetchFiles({
        folderId: currentFolderId.value,
        folderLabel: currentFolderName.value,
      });
    } catch (error) {
      console.error('Error fetching foldername:', error);
    }
  } else {
    foldername.value = '';
    currentFolderId.value = null;
    currentFolderName.value = '';
    breadcrumbStack.value = [];
    subfolders.value = [];
    files.value = [];
  }
});

let hasMounted = false;

onMounted(async () => {
  hasMounted = true;
  await fetchCourse();
  await fetchFolders();
  if (props.initialFolder) {
    await initializeFromFolder(props.initialFolder, { refreshFolders: false });
  }
});

watch(
  () => props.initialFolder,
  async (newValue, oldValue) => {
    if (!hasMounted) {
      return;
    }
    const trimmedValue = newValue?.trim();
    const previous = oldValue?.trim();
    if (!trimmedValue || trimmedValue === previous) {
      return;
    }
    await initializeFromFolder(trimmedValue);
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
