import { h, createApp } from 'vue';
import FolderPlugin from '@/components/FolderPlugin.vue';
import FolderBlock from '@/components/FolderBlock.vue';
import { FolderOpen } from 'lucide-vue-next';
import translationPlugin from '../translation'
import router from '@/router'

const getCsrfToken = () => {
  if (typeof window === 'undefined') {
    return null
  }
  return (
    window.csrf_token ||
    window.frappe?.csrf_token ||
    document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') ||
    null
  )
}

const FOLDER_SCOPES = ['Course', 'Instructor', 'Section', 'School']

/**
 * EditorJS block for an embedded Course Folder.
 *
 * Block data is `{ folder_ref, folder }`: `folder_ref` is the Course Folder
 * docname and is what the API resolves; `folder` is only the display label.
 * A block that carries `folder` alone predates the docname reference and is
 * shown as needing re-linking rather than resolved by name (p006 §2.2a).
 */
export class FolderTool {
  constructor({ data, api, readOnly }) {
    this.data = data;
    this.readOnly = readOnly
    this.api = api;
    this.wrapper = undefined;
    this.vueApp = null;
  }

  static get toolbox() {
    const app = createApp({
      render: () =>
        h(FolderOpen, { size: 18, strokeWidth: 1.5, color: 'black' }),
    });

    const div = document.createElement('div');
    app.mount(div);

    return {
      title: 'Folder',
      icon: div.innerHTML,
    };
  }
	static get isReadOnlySupported() {
		return true
	}

  render() {
    this.wrapper = document.createElement('div')
    if (this.data && (this.data.folder_ref || this.data.folder)) {
      this.renderFolder({ folderRef: this.data.folder_ref, folder: this.data.folder })
    } else {
      this.renderFolderModal()
    }
    return this.wrapper
  }

  destroyApp() {
    if (this.vueApp) {
      this.vueApp.unmount()
      this.vueApp = null
    }
    if (this.wrapper) {
      this.wrapper.innerHTML = ''
    }
  }

  renderFolder({ folderRef = null, folder = null } = {}) {
    if (this.readOnly) {
      this.destroyApp()
      this.vueApp = createApp(FolderBlock, {
        folderRef: folderRef || null,
        folder: folder || '',
      })
      this.vueApp.use(translationPlugin)
      this.vueApp.use(router)
      this.vueApp.mount(this.wrapper)
      return
    }
    this.renderFolderModal({ folderRef, folder })
  }

  renderFolderModal({ folderRef = null, folder = null } = {}) {
    if (this.readOnly) {
      return
    }
    this.destroyApp()
    this.vueApp = createApp(FolderPlugin, {
      initialFolderRef: folderRef || null,
      initialFolder: folder || null,
      onAddition: (selected) => {
        if (!this.data) {
          this.data = {}
        }
        // Accept both the `{ folder_ref, folder }` shape and a bare docname.
        if (selected && typeof selected === 'object') {
          this.data.folder_ref = selected.folder_ref || null
          this.data.folder = selected.folder || ''
        } else {
          this.data.folder_ref = selected || null
        }
      },
    })
    this.vueApp.use(translationPlugin)
    this.vueApp.use(router)
    this.vueApp.mount(this.wrapper)
  }

    save(blockContent) {
      return {
        folder_ref: this.data?.folder_ref || null,
        folder: this.data?.folder || '',
      }
    }

    destroy() {
      this.destroyApp()
    }

    /**
     * Create a Course Folder through the resource API.
     *
     * `course` is required for every scope except School; Instructor scope
     * needs `instructor`, Section scope needs `courseSchedule`.
     */
    async createCourseFolder({ course, folderName, scope = 'Course', instructor = null, courseSchedule = null }) {
      const trimmedFolderName = folderName?.trim()
      if (!trimmedFolderName) {
        throw new Error('Folder name is required to create a course folder')
      }
      if (!FOLDER_SCOPES.includes(scope)) {
        throw new Error(`Unknown folder scope: ${scope}`)
      }
      if (scope !== 'School' && !course) {
        throw new Error('Course is required to create a course folder')
      }
      if (scope === 'Instructor' && !instructor) {
        throw new Error('Instructor is required for an Instructor folder')
      }
      if (scope === 'Section' && !courseSchedule) {
        throw new Error('Section is required for a Section folder')
      }

      const csrfToken = getCsrfToken()
      if (!csrfToken) {
        throw new Error('CSRF token not found. Please refresh the page and try again.')
      }

      const body = {
        foldername: trimmedFolderName,
        scope,
      }
      if (scope !== 'School') {
        body.course = course
      }
      if (scope === 'Instructor') {
        body.instructor = instructor
      }
      if (scope === 'Section') {
        body.course_schedule = courseSchedule
      }

      let responseData
      const response = await fetch('/api/resource/Course Folder', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Accept: 'application/json',
          'X-Frappe-CSRF-Token': csrfToken,
        },
        credentials: 'include',
        body: JSON.stringify(body),
      })
      try {
        responseData = await response.json()
      } catch (error) {
        responseData = null
      }

      if (!response.ok) {
        const serverMessage = responseData?.message || responseData?.exc || response.statusText
        throw new Error(serverMessage || 'Failed to create course folder')
      }

      const data = responseData?.data || responseData
      if (!this.data) {
        this.data = {}
      }
      this.data.folder_ref = data?.name || null
      this.data.folder = data?.foldername || trimmedFolderName
      return data
    }

    async createSubfolder({ parentFolderId, subfolderName, courseSchedule = null }) {
      const trimmedSubfolderName = subfolderName?.trim()
      if (!trimmedSubfolderName) {
        throw new Error('Sub-folder name is required')
      }

      if (!parentFolderId) {
        throw new Error('Parent folder information is required to create a sub-folder')
      }

      const csrfToken = getCsrfToken()
      if (!csrfToken) {
        throw new Error('CSRF token not found. Please refresh the page and try again.')
      }

      const body = {
        parent_folder_id: parentFolderId,
        subfoldername: trimmedSubfolderName,
      }
      if (courseSchedule) {
        body.course_schedule = courseSchedule
      }

      let responseData
      const response = await fetch('/api/method/seminary.api.folder_upload.create_subfolder', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Accept: 'application/json',
          'X-Frappe-CSRF-Token': csrfToken,
        },
        credentials: 'include',
        body: JSON.stringify(body),
      })

      try {
        responseData = await response.json()
      } catch (error) {
        responseData = null
      }

      if (!response.ok) {
        const serverMessage = responseData?.message || responseData?.exc || response.statusText
        throw new Error(serverMessage || 'Failed to create sub-folder')
      }

      return responseData?.message || responseData?.data || responseData
    }
  }
