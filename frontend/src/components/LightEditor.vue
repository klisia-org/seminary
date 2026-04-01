<!-- LightEditor.vue — Lightweight editor using contenteditable (no Tiptap/ProseMirror) -->
<template>
    <div>
        <!-- Read-only: just render HTML -->
        <div v-if="!editable" v-html="content" class="prose-sm py-2 px-2 min-h-[7rem]"></div>
        <!-- Lazy placeholder until user clicks -->
        <div v-else-if="lazy && !activated" @click="activate"
            class="border rounded-md py-2 px-2 min-h-[7rem] text-sm text-ink-gray-4 cursor-text">
            {{ placeholder || __('Click to write...') }}
        </div>
        <!-- Active editor -->
        <div v-else class="border rounded-md">
            <div class="flex gap-1 p-1 border-b bg-surface-gray-2 rounded-t-md flex-wrap">
                <button @mousedown.prevent="exec('bold')" :class="btnClass" title="Bold"><strong>B</strong></button>
                <button @mousedown.prevent="exec('italic')" :class="btnClass" title="Italic"><em>I</em></button>
                <button @mousedown.prevent="exec('insertUnorderedList')" :class="btnClass" title="Bullet List">
                    <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="8" y1="6" x2="21" y2="6"/><line x1="8" y1="12" x2="21" y2="12"/><line x1="8" y1="18" x2="21" y2="18"/><circle cx="4" cy="6" r="1" fill="currentColor"/><circle cx="4" cy="12" r="1" fill="currentColor"/><circle cx="4" cy="18" r="1" fill="currentColor"/></svg>
                </button>
                <button @mousedown.prevent="exec('insertOrderedList')" :class="btnClass" title="Numbered List">
                    <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="10" y1="6" x2="21" y2="6"/><line x1="10" y1="12" x2="21" y2="12"/><line x1="10" y1="18" x2="21" y2="18"/><text x="2" y="8" font-size="8" fill="currentColor" stroke="none">1</text><text x="2" y="14" font-size="8" fill="currentColor" stroke="none">2</text><text x="2" y="20" font-size="8" fill="currentColor" stroke="none">3</text></svg>
                </button>
                <button @mousedown.prevent="exec('formatBlock', '<blockquote>')" :class="btnClass" title="Blockquote">
                    <svg class="w-4 h-4" viewBox="0 0 24 24" fill="currentColor"><path d="M4.583 17.321C3.553 16.227 3 15 3 13.011c0-3.5 2.457-6.637 6.03-8.188l.893 1.378c-3.335 1.804-3.987 4.145-4.247 5.621.537-.278 1.24-.375 1.929-.311 1.804.167 3.226 1.648 3.226 3.489a3.5 3.5 0 01-3.5 3.5c-1.073 0-2.099-.49-2.748-1.179zm10 0C13.553 16.227 13 15 13 13.011c0-3.5 2.457-6.637 6.03-8.188l.893 1.378c-3.335 1.804-3.987 4.145-4.247 5.621.537-.278 1.24-.375 1.929-.311 1.804.167 3.226 1.648 3.226 3.489a3.5 3.5 0 01-3.5 3.5c-1.073 0-2.099-.49-2.748-1.179z"/></svg>
                </button>
                <button @mousedown.prevent="insertLink" :class="btnClass" title="Link">
                    <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M10 13a5 5 0 007.54.54l3-3a5 5 0 00-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 00-7.54-.54l-3 3a5 5 0 007.07 7.07l1.71-1.71"/></svg>
                </button>
            </div>
            <div
                ref="editorEl"
                contenteditable="true"
                class="light-editor-content prose-sm py-2 px-2 min-h-[7rem] outline-none text-left"
                :data-placeholder="placeholder"
                @input="onInput"
            ></div>
        </div>
    </div>
</template>

<script setup>
import { ref, watch, onMounted, onBeforeUnmount, nextTick } from 'vue'

const props = defineProps({
    content: { type: String, default: '' },
    placeholder: { type: String, default: '' },
    id: { type: String, default: '' },
    editable: { type: Boolean, default: true },
    lazy: { type: Boolean, default: false },
})

const emit = defineEmits(['change'])

const editorEl = ref(null)
const activated = ref(!props.lazy)
let debounceTimer = null
let settingContent = false

const btnClass = 'px-2 py-1 rounded text-xs hover:bg-surface-gray-3 flex items-center justify-center'

function exec(command, value = null) {
    document.execCommand(command, false, value)
    editorEl.value?.focus()
    emitChange()
}

function insertLink() {
    const url = prompt('URL')
    if (url) {
        document.execCommand('createLink', false, url)
        editorEl.value?.focus()
        emitChange()
    }
}

function onInput() {
    if (settingContent) return
    clearTimeout(debounceTimer)
    debounceTimer = setTimeout(() => {
        emit('change', editorEl.value?.innerHTML || '')
    }, 500)
}

function emitChange() {
    clearTimeout(debounceTimer)
    debounceTimer = setTimeout(() => {
        emit('change', editorEl.value?.innerHTML || '')
    }, 500)
}

function setContent(html) {
    if (!editorEl.value) return
    settingContent = true
    editorEl.value.innerHTML = html || ''
    settingContent = false
}

function clear() {
    setContent('')
    emit('change', '')
}

function activate() {
    activated.value = true
    nextTick(() => {
        if (editorEl.value) {
            setContent(props.content)
            editorEl.value.focus()
        }
    })
}

onMounted(() => {
    if (props.editable && !props.lazy) {
        nextTick(() => {
            if (editorEl.value) {
                setContent(props.content)
            }
        })
    }
})

watch(() => props.id, () => {
    if (!props.editable) return
    if (props.lazy && !activated.value) return
    nextTick(() => setContent(props.content))
})

watch(() => props.content, (newContent) => {
    if (!editorEl.value || settingContent) return
    if (newContent !== editorEl.value.innerHTML) {
        setContent(newContent)
    }
})

onBeforeUnmount(() => {
    clearTimeout(debounceTimer)
    if (editorEl.value) {
        editorEl.value.blur()
        editorEl.value.innerHTML = ''
    }
})

defineExpose({ clear })
</script>

<style scoped>
.light-editor-content:empty::before {
    content: attr(data-placeholder);
    color: var(--ink-gray-4, #9ca3af);
    pointer-events: none;
}
.light-editor-content :deep(blockquote) {
    border-left: 3px solid #d1d5db;
    padding-left: 0.75rem;
    margin: 0.5rem 0;
}
</style>
