import { ref } from 'vue'
import { DEFAULT_BLOCK } from '@/utils/blockPalette'

// Drag from the palette. A custom type keeps these drags apart from editorjs's own
// block dragging and from files dropped into the editor.
const BLOCK_MIME = 'application/x-seminary-block'

/**
 * Palette tiles into an editorjs editor: click to add at the end, or drag to a spot.
 * `editor` is a ref to the EditorJS instance, `holder` the id of its element, and
 * `onAdded` runs after each block lands.
 */
export function useBlockDrop(editor, holder, { onAdded } = {}) {
	const dropZone = ref(null)
	const draggingTool = ref(null)
	const dropIndicatorTop = ref(null)
	let dropIndex = null

	/**
	 * Add a block at `index` (default: the end). An empty text line at the spot -- the
	 * free line left for the caret, or a blank new lesson -- is replaced rather than
	 * left stranded above the new block.
	 */
	const addBlock = async (tool, index = null) => {
		const api = editor.value
		if (!api) return
		await api.isReady
		const count = api.blocks.getBlocksCount()
		let at = index === null ? count : Math.max(0, Math.min(index, count))
		const isFreeLine = (i) => {
			const block = i >= 0 && i < count ? api.blocks.getBlockByIndex(i) : null
			return Boolean(block && block.name === DEFAULT_BLOCK && block.isEmpty)
		}
		let replace = false
		if (isFreeLine(at)) {
			replace = true
		} else if (isFreeLine(at - 1)) {
			at -= 1
			replace = true
		}
		api.blocks.insert(tool, {}, {}, at, true, replace)
		onAdded?.(tool)
	}

	const onTileDragStart = (event, tool) => {
		event.dataTransfer.setData(BLOCK_MIME, tool)
		event.dataTransfer.effectAllowed = 'copy'
		draggingTool.value = tool
	}

	const onTileDragEnd = () => {
		draggingTool.value = null
		dropIndicatorTop.value = null
		dropIndex = null
	}

	const isBlockDrag = (event) => Array.from(event.dataTransfer?.types || []).includes(BLOCK_MIME)

	const onDragOver = (event) => {
		if (!isBlockDrag(event) || !dropZone.value) return
		event.preventDefault()
		event.stopPropagation()
		event.dataTransfer.dropEffect = 'copy'

		// The drop lands before the first block whose middle is below the pointer.
		const blocks = Array.from(dropZone.value.querySelectorAll(`#${holder} .ce-block`))
		const zoneTop = dropZone.value.getBoundingClientRect().top
		let index = blocks.length
		for (let i = 0; i < blocks.length; i++) {
			const rect = blocks[i].getBoundingClientRect()
			if (event.clientY < rect.top + rect.height / 2) {
				index = i
				break
			}
		}
		dropIndex = index
		if (!blocks.length) {
			dropIndicatorTop.value = 12
		} else if (index < blocks.length) {
			dropIndicatorTop.value = blocks[index].getBoundingClientRect().top - zoneTop
		} else {
			dropIndicatorTop.value = blocks[blocks.length - 1].getBoundingClientRect().bottom - zoneTop
		}
	}

	const onDragLeave = (event) => {
		if (dropZone.value && !dropZone.value.contains(event.relatedTarget)) {
			dropIndicatorTop.value = null
		}
	}

	const onDrop = (event) => {
		if (!isBlockDrag(event)) return
		event.preventDefault()
		event.stopPropagation()
		const tool = event.dataTransfer.getData(BLOCK_MIME)
		const index = dropIndex ?? editor.value?.blocks.getBlocksCount() ?? 0
		onTileDragEnd()
		if (tool) addBlock(tool, index)
	}

	return { dropZone, draggingTool, dropIndicatorTop, addBlock, onTileDragStart, onTileDragEnd, onDragOver, onDragLeave, onDrop }
}
