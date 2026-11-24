/**
 * Full Tiptap editor extensions matching frappe-ui's TextEditor.
 *
 * This file is loaded dynamically (via import()) to avoid blocking
 * page load with heavy frappe-ui extension imports.
 *
 * Requires vite.config.js `resolve.alias` entries for all prosemirror-* and
 * @tiptap/* packages to prevent duplicate module instances.
 */
import StarterKit from '@tiptap/starter-kit'
import Placeholder from '@tiptap/extension-placeholder'
import TextAlign from '@tiptap/extension-text-align'
import Table from '@tiptap/extension-table'
import TableCell from '@tiptap/extension-table-cell'
import TableHeader from '@tiptap/extension-table-header'
import TableRow from '@tiptap/extension-table-row'
import Typography from '@tiptap/extension-typography'
import TextStyle from '@tiptap/extension-text-style'
import TaskItem from '@tiptap/extension-task-item'
import TaskList from '@tiptap/extension-task-list'

// frappe-ui custom extensions (imported via relative path since package.json
// exports don't expose internal paths)
import { ImageExtension } from '../../node_modules/frappe-ui/src/components/TextEditor/extensions/image'
import ImageViewerExtension from '../../node_modules/frappe-ui/src/components/TextEditor/image-viewer-extension'
import { ImageGroup } from '../../node_modules/frappe-ui/src/components/TextEditor/extensions/image-group/image-group-extension'
import { RichEmbed, RichVideo } from './richEditorNodes.js'
import LinkExtension from '../../node_modules/frappe-ui/src/components/TextEditor/link-extension'
import { Heading } from '../../node_modules/frappe-ui/src/components/TextEditor/extensions/heading/heading'
import { ExtendedCode, ExtendedCodeBlock } from '../../node_modules/frappe-ui/src/components/TextEditor/extensions/code-block'
import NamedColorExtension from '../../node_modules/frappe-ui/src/components/TextEditor/extensions/color'
import NamedHighlightExtension from '../../node_modules/frappe-ui/src/components/TextEditor/extensions/highlight'
import EmojiExtension from '../../node_modules/frappe-ui/src/components/TextEditor/extensions/emoji/emoji-extension'
import SlashCommands from '../../node_modules/frappe-ui/src/components/TextEditor/extensions/slash-commands/slash-commands-extension'
import { ContentPasteExtension } from '../../node_modules/frappe-ui/src/components/TextEditor/extensions/content-paste-extension'
import { uploadForEditor } from './editorUpload.js'

// Through object storage where the site has it, with progress (editorUpload.js).
function defaultUploadFunction(file, options) {
	return uploadForEditor(file, options)
}

/**
 * The editable area's classes, as frappe-ui's TextEditor gives them. Without them the
 * editable area is as tall as its text, and the browser outlines just that: a one-line
 * box inside the larger frame. `minHeight` makes it fill the frame; the frame shows the
 * focus instead (`focus-within:` on the wrapper).
 */
export function editorClass(minHeight = 'min-h-[7rem]') {
	return [
		'prose prose-sm max-w-none focus:outline-none',
		'prose-table:table-fixed prose-td:p-2 prose-th:p-2 prose-td:border prose-th:border',
		'prose-td:border-outline-gray-2 prose-th:border-outline-gray-2 prose-th:bg-surface-gray-2',
		minHeight,
	].join(' ')
}

export function getTextEditorExtensions({ placeholder = '', uploadFunction } = {}) {
	const upload = uploadFunction || defaultUploadFunction
	return [
		StarterKit.configure({
			code: false,
			codeBlock: false,
			heading: false,
		}),
		Heading,
		Table.configure({ resizable: true }),
		TableRow,
		TableHeader,
		TableCell,
		TaskList,
		TaskItem.configure({ nested: true }),
		Typography,
		TextAlign.configure({ types: ['heading', 'paragraph'] }),
		TextStyle,
		NamedColorExtension,
		NamedHighlightExtension,
		ExtendedCode,
		ExtendedCodeBlock,
		ImageExtension.configure({ uploadFunction: upload }),
		ImageGroup.configure({ uploadFunction: upload }),
		ImageViewerExtension,
		// Saved as markup the sanitisers keep (decision 109 §1, §5).
		RichVideo.configure({ uploadFunction: upload }),
		RichEmbed,
		LinkExtension.configure({ openOnClick: false }),
		Placeholder.configure({ placeholder: () => placeholder }),
		EmojiExtension,
		SlashCommands,
		ContentPasteExtension.configure({
			enabled: true,
			uploadFunction: upload,
		}),
	]
}
