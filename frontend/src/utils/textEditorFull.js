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
import VideoExtension from '../../node_modules/frappe-ui/src/components/TextEditor/video-extension'
import { IframeExtension } from '../../node_modules/frappe-ui/src/components/TextEditor/extensions/iframe'
import LinkExtension from '../../node_modules/frappe-ui/src/components/TextEditor/link-extension'
import { Heading } from '../../node_modules/frappe-ui/src/components/TextEditor/extensions/heading/heading'
import { ExtendedCode, ExtendedCodeBlock } from '../../node_modules/frappe-ui/src/components/TextEditor/extensions/code-block'
import NamedColorExtension from '../../node_modules/frappe-ui/src/components/TextEditor/extensions/color'
import NamedHighlightExtension from '../../node_modules/frappe-ui/src/components/TextEditor/extensions/highlight'
import EmojiExtension from '../../node_modules/frappe-ui/src/components/TextEditor/extensions/emoji/emoji-extension'
import SlashCommands from '../../node_modules/frappe-ui/src/components/TextEditor/extensions/slash-commands/slash-commands-extension'
import { ContentPasteExtension } from '../../node_modules/frappe-ui/src/components/TextEditor/extensions/content-paste-extension'
import { useFileUpload } from '../../node_modules/frappe-ui/src/utils/useFileUpload'

function defaultUploadFunction(file) {
	let fileUpload = useFileUpload()
	return fileUpload.upload(file, {})
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
		VideoExtension.configure({ uploadFunction: upload }),
		IframeExtension,
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
