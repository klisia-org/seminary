// The block palette beside the lesson editors. `tool` is the editorjs tool name from
// getEditorTools(); the / menu inside an editor still lists every tool.
import {
	BookOpenCheck,
	CircleHelp,
	Code,
	Code2,
	Folder,
	Heading,
	List,
	MessagesSquare,
	Mic,
	Pencil,
	Table,
	Type,
	Upload,
	Video,
} from 'lucide-vue-next'

// editorjs's `defaultBlock`: the tool used for a plain new block, and the only one a
// palette drop replaces when it lands on an empty line.
export const DEFAULT_BLOCK = 'markdown'

export const blockGroups = () => [
	{
		key: 'text',
		label: __('Text'),
		text: 'text-ink-gray-5',
		icon: 'bg-surface-gray-2 text-ink-gray-7',
		blocks: [
			{ tool: 'markdown', label: __('Text'), icon: Type },
			{ tool: 'header', label: __('Heading'), icon: Heading },
			{ tool: 'list', label: __('List'), icon: List },
			{ tool: 'table', label: __('Table'), icon: Table },
			{ tool: 'codeBox', label: __('Code'), icon: Code },
		],
	},
	{
		key: 'media',
		label: __('Media'),
		text: 'text-ink-blue-3',
		icon: 'bg-surface-blue-1 text-ink-blue-3',
		blocks: [
			{ tool: 'upload', label: __('Upload'), hint: __('Video, audio, PDF or image file'), icon: Upload },
			{ tool: 'iframe', label: __('Embed'), hint: __('A link to a video or web page'), icon: Code2 },
			{ tool: 'recordVideo', label: __('Record video'), icon: Video },
			{ tool: 'folder', label: __('Folder'), icon: Folder },
		],
	},
	{
		key: 'assessment',
		activity: true,
		label: __('Assessment'),
		text: 'text-ink-amber-3',
		icon: 'bg-surface-amber-1 text-ink-amber-3',
		blocks: [
			{ tool: 'quiz', label: __('Quiz'), icon: CircleHelp },
			{ tool: 'exam', label: __('Exam'), icon: BookOpenCheck },
			{ tool: 'assignment', label: __('Assignment'), icon: Pencil },
		],
	},
	{
		key: 'engagement',
		activity: true,
		label: __('Engagement'),
		text: 'text-ink-green-3',
		icon: 'bg-surface-green-1 text-ink-green-3',
		blocks: [
			{ tool: 'discussionActivity', label: __('Discussion'), icon: MessagesSquare },
			{ tool: 'oralActivity', label: __('Oral activity'), icon: Mic },
		],
	},
]

// Content without one section's activities: what a library lesson may hold (decisions/122).
export const contentBlockGroups = () => blockGroups().filter((g) => !g.activity)
