<!-- RichTextEditor.vue — Full Tiptap editor, fully lazy-loaded -->
<!-- Uses Teleport when in deeply nested DOM, renders inline when inside a Dialog -->
<template>
    <div>
        <!-- Before activation: clickable placeholder -->
        <div v-if="!active" @click="activate" ref="anchorEl"
            class="border rounded-md py-2 px-2 min-h-[7rem] text-sm text-ink-gray-4 cursor-text prose-sm">
            {{ placeholder || __('Click to write...') }}
        </div>

        <!-- Inline mode (inside Dialogs — already teleported to body by Dialog) -->
        <div v-else-if="!useTeleport" class="border rounded-md">
            <component v-if="menuComponent && editor" :is="menuComponent"
                class="w-full overflow-x-auto rounded-t-md border-b border-outline-gray-modals"
                :buttons="true"
            />
            <component v-if="editorContentComponent && editor" :is="editorContentComponent"
                :editor="editor"
                class="prose-sm py-2 px-2 min-h-[7rem]"
            />
        </div>

        <!-- Teleport mode (deeply nested pages like DiscussionActivity) -->
        <template v-else>
            <div ref="anchorEl" :style="{ minHeight: editorHeight + 'px' }" class="min-h-[7rem]"></div>
            <Teleport to="body">
                <div ref="editorWrapperEl"
                    class="border rounded-md bg-surface-white shadow-lg"
                    :style="editorStyle">
                    <component v-if="menuComponent && editor" :is="menuComponent"
                        class="w-full overflow-x-auto rounded-t-md border-b border-outline-gray-modals"
                        :buttons="true"
                    />
                    <component v-if="editorContentComponent && editor" :is="editorContentComponent"
                        :editor="editor"
                        class="prose-sm py-2 px-2 min-h-[7rem]"
                    />
                </div>
            </Teleport>
        </template>
    </div>
</template>

<script setup>
import { ref, watch, provide, onMounted, onBeforeUnmount, nextTick, computed, shallowRef } from 'vue'

const props = defineProps({
    content: { type: String, default: '' },
    placeholder: { type: String, default: '' },
    id: { type: String, default: '' },
    editable: { type: Boolean, default: true },
    teleport: { type: Boolean, default: true },
})

const emit = defineEmits(['change'])

const editor = ref(null)
const active = ref(false)
const anchorEl = ref(null)
const editorWrapperEl = ref(null)
const anchorRect = ref({ top: 0, left: 0, width: 0 })
const editorHeight = ref(112)
const menuComponent = shallowRef(null)
const editorContentComponent = shallowRef(null)
const useTeleport = computed(() => props.teleport)
let debounceTimer = null
let settingContent = false

provide('editor', editor)

const editorStyle = computed(() => ({
    position: 'absolute',
    top: `${anchorRect.value.top + window.scrollY}px`,
    left: `${anchorRect.value.left}px`,
    width: `${anchorRect.value.width}px`,
    zIndex: 9999,
}))

function updatePosition() {
    if (!anchorEl.value) return
    const rect = anchorEl.value.getBoundingClientRect()
    anchorRect.value = { top: rect.top, left: rect.left, width: rect.width }
}

function updateEditorHeight() {
    if (editorWrapperEl.value) {
        editorHeight.value = editorWrapperEl.value.offsetHeight
    }
}

async function activate() {
    active.value = true
    await nextTick()
    if (useTeleport.value) updatePosition()

    const [{ Editor, EditorContent }, { TextEditorFixedMenu }, { getTextEditorExtensions }] = await Promise.all([
        import('@tiptap/vue-3'),
        import('frappe-ui'),
        import('@/utils/textEditorFull'),
    ])

    menuComponent.value = TextEditorFixedMenu
    editorContentComponent.value = EditorContent

    editor.value = new Editor({
        content: props.content || '',
        editable: props.editable,
        extensions: getTextEditorExtensions({
            placeholder: props.placeholder,
        }),
        onUpdate: ({ editor: e }) => {
            if (settingContent) return
            clearTimeout(debounceTimer)
            debounceTimer = setTimeout(() => {
                emit('change', e.getHTML())
            }, 500)
            if (useTeleport.value) nextTick(updateEditorHeight)
        },
    })

    await nextTick()
    if (useTeleport.value) updateEditorHeight()
    editor.value?.commands.focus()
}

function destroyEditor() {
    clearTimeout(debounceTimer)
    if (editor.value) {
        editor.value.destroy()
        editor.value = null
    }
    active.value = false
}

function clear() {
    if (editor.value) {
        settingContent = true
        editor.value.commands.clearContent()
        settingContent = false
    }
}

onMounted(() => {
    if (useTeleport.value) {
        window.addEventListener('scroll', updatePosition, true)
        window.addEventListener('resize', updatePosition)
    }
})

onBeforeUnmount(() => {
    if (useTeleport.value) {
        window.removeEventListener('scroll', updatePosition, true)
        window.removeEventListener('resize', updatePosition)
    }
    destroyEditor()
})

watch(() => props.id, () => {
    if (!editor.value) return
    destroyEditor()
})

watch(() => props.content, (newContent) => {
    if (!editor.value) return
    const current = editor.value.getHTML()
    if (newContent !== current) {
        settingContent = true
        editor.value.commands.setContent(newContent || '')
        settingContent = false
    }
})

defineExpose({ clear })
</script>
