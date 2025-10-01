<template>
  <div class="flex flex-col gap-4 rounded-lg border-2 border-gray-200 p-4 mb-4">
    <div class="flex flex-col gap-1">
      <h4 class="text-lg font-semibold text-ink-gray-9">{{ currentFolderName || folderName }}</h4>
      <div class="text-sm text-ink-gray-6 flex flex-wrap items-center gap-1" v-if="breadcrumbStack.length">
        <template v-for="(crumb, index) in breadcrumbStack" :key="crumb.id || `${crumb.label}-${index}`">
          <button
            type="button"
            class="rounded px-1.5 py-0.5 transition hover:bg-ink-gray-2 hover:text-ink-gray-9"
            :class="index === breadcrumbStack.length - 1 ? 'font-medium text-ink-gray-8 cursor-default' : 'text-ink-gray-7'"
            @click="index === breadcrumbStack.length - 1 ? null : navigateToBreadcrumb(index)"
          >
            {{ crumb.label }}
          </button>
          <span v-if="index < breadcrumbStack.length - 1">/</span>
        </template>
      </div>
    </div>

    <div v-if="errorMessage" class="rounded border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
      {{ errorMessage }}
    </div>
    <div v-else-if="isLoading" class="text-sm text-ink-gray-6">
      {{ __('Loading folder contents…') }}
    </div>
    <template v-else>
      <section class="space-y-2">
        <h5 class="text-sm font-semibold text-ink-gray-9">{{ __('Sub-folders') }}</h5>
        <div v-if="!subfolders.length" class="text-sm text-ink-gray-5">
          {{ __('No sub-folders in this location.') }}
        </div>
        <ul v-else class="space-y-2">
          <li
            v-for="folder in subfolders"
            :key="folder.name"
            class="flex items-center justify-between rounded border border-outline-gray-2 px-3 py-2 transition hover:border-outline-gray-3"
          >
            <button
              type="button"
              class="text-left text-sm font-medium text-blue-600 hover:underline"
              @click="openSubfolder(folder)"
            >
              {{ folder.file_name }}
            </button>
            <span class="text-xs text-ink-gray-5">{{ __('Folder') }}</span>
          </li>
        </ul>
      </section>

      <section class="space-y-2">
        <h5 class="text-sm font-semibold text-ink-gray-9">{{ __('Files') }}</h5>
        <div v-if="!files.length" class="text-sm text-ink-gray-5">
          {{ __('No files available in this folder.') }}
        </div>
        <ul v-else class="space-y-2">
          <li
            v-for="file in files"
            :key="file.file_url || file.name"
            class="flex items-center gap-3 rounded border border-outline-gray-2 px-3 py-2 transition hover:border-outline-gray-3"
          >
            <a :href="file.file_url" download class="flex-1 truncate text-sm text-blue-600 hover:underline">
              {{ file.file_name }}
            </a>
            <span class="text-xs text-ink-gray-5">{{ humanFileSize(file.file_size) }}</span>
          </li>
        </ul>
      </section>
    </template>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { createResource } from 'frappe-ui'

const props = defineProps({
  folder: {
    type: [Object, String],
    required: true,
  },
})

const folderName = computed(() => {
  if (typeof props.folder === 'string') {
    return props.folder
  }
  if (props.folder && typeof props.folder === 'object') {
    return props.folder.folder || props.folder.foldername || ''
  }
  return ''
})

const isLoading = ref(false)
const errorMessage = ref('')
const files = ref([])
const subfolders = ref([])
const currentFolderId = ref(null)
const currentFolderName = ref('')
const breadcrumbStack = ref([])
let hasMounted = false

const humanFileSize = (value) => {
  if (!value && value !== 0) {
    return ''
  }
  const size = Number(value)
  if (Number.isNaN(size)) {
    return ''
  }
  if (size >= 1048576) {
    return `${(size / 1048576).toFixed(2)} MB`
  }
  if (size >= 1024) {
    return `${(size / 1024).toFixed(2)} KB`
  }
  return `${size} B`
}

const buildParams = ({ folderId = null, folderLabel = null }) => {
  const params = {}
  if (folderId) {
    params.folder_id = folderId
  }
  const labelCandidate = folderLabel ?? folderName.value
  if (!folderId && labelCandidate) {
    params.foldername = labelCandidate
  }
  return params
}

const loadFolder = async ({ folderId = null, folderLabel = null } = {}) => {
  const params = buildParams({ folderId, folderLabel })
  if (!params.folder_id && !params.foldername) {
    return null
  }
  isLoading.value = true
  errorMessage.value = ''

  try {
    const resource = createResource({
      url: 'seminary.api.folder_upload.get_files_in_folder',
      params,
      auto: true,
    })
    const result = await resource.fetch()
    const entries = result?.entries || []
    subfolders.value = entries.filter((entry) => entry.is_folder)
    files.value = entries.filter((entry) => !entry.is_folder)
    currentFolderId.value = result?.folder_id || folderId || null
    currentFolderName.value = result?.folder_name || folderLabel || folderName.value || ''
    return {
      id: currentFolderId.value,
      label: currentFolderName.value,
    }
  } catch (error) {
    console.error('Error fetching folder contents:', error)
    errorMessage.value = error?.message || __('Unable to load folder contents.')
    subfolders.value = []
    files.value = []
    return null
  } finally {
    isLoading.value = false
  }
}

const openRootFolder = async () => {
  const root = await loadFolder({ folderLabel: folderName.value })
  if (root) {
    breadcrumbStack.value = [root]
  }
}

const openSubfolder = async (folder) => {
  if (!folder?.name) {
    return
  }
  const crumb = await loadFolder({ folderId: folder.name, folderLabel: folder.file_name })
  if (crumb) {
    breadcrumbStack.value = [...breadcrumbStack.value, crumb]
  }
}

const navigateToBreadcrumb = async (index) => {
  if (index < 0 || index >= breadcrumbStack.value.length) {
    return
  }
  const target = breadcrumbStack.value[index]
  const crumb = await loadFolder({ folderId: target.id, folderLabel: target.label })
  if (crumb) {
    breadcrumbStack.value = [...breadcrumbStack.value.slice(0, index), crumb]
  }
}

onMounted(async () => {
  hasMounted = true
  await openRootFolder()
})

watch(
  () => folderName.value,
  async (newValue, oldValue) => {
    if (!hasMounted) {
      return
    }
    const trimmed = (newValue || '').trim()
    const previous = (oldValue || '').trim()
    if (!trimmed || trimmed === previous) {
      return
    }
    await openRootFolder()
  },
)
</script>
