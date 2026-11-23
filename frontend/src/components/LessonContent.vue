<template>
	<div v-if="youtube">
		<iframe class="youtube-video" :src="getYouTubeVideoSource(youtube.split('/').pop())" :title="__('Lesson video')" width="100%" height="400"
			frameborder="0" allowfullscreen></iframe>
	</div>
	<div v-for="block in content?.split('\n\n')">
		<div v-if="block.includes('{{ YouTubeVideo')">
			<iframe class="youtube-video" :src="getYouTubeVideoSource(block)" :title="__('Video')" width="100%" height="400" frameborder="0"
				allowfullscreen></iframe>
		</div>

		<div v-else-if="block.includes('{{ Video')">
			<video controls width="100%" controlsList="nodownload" oncontextmenu="return false;">
				<source :src="getId(block)" type="video/mp4" />
				<!-- The lesson's caption files (102 §6); native controls offer them. -->
				<track v-for="track in captions || []" :key="track.file" kind="captions"
					:srclang="track.language" :label="track.label" :src="track.file" />
			</video>
		</div>
		<div v-else-if="block.includes('{{ PDF')">
			<iframe :src="getPDFSource(block)" :title="__('PDF document')" width="100%" height="700px" frameborder="0" allowfullscreen></iframe>
		</div>
		<div v-else-if="block.includes('{{ Audio')">
			<!-- eslint-disable-next-line vuejs-accessibility/media-has-caption -- audio-only: what it needs is a transcript in the lesson text, and an audio element shows no caption track -->
			<audio width="100%" controls controlsList="nodownload">
				<source :src="getId(block)" type="audio/mp3" />
			</audio>
		</div>
		<div v-else-if="block.includes('{{ Embed')">
			<iframe width="100%" height="400" :src="getId(block)" :title="__('Embedded content')" frameborder="0" allowfullscreen>
			</iframe>
		</div>
		<SafeHtml v-else :html="markdown.render(block)" />
	</div>
	<div v-if="quizId">
		<Quiz :quiz="quizId" />
	</div>
	<div v-if="exam">
		<Exam :exam="exam" />
	</div>
	<div v-if="discussionID">
		<DiscussionActivity :discussionID="discussionID" :courseName="props.courseName" />
	</div>
	<div v-if="folder">
		<Folder :folder="folder" />
	</div>
</template>
<script setup>
import Quiz from '@/components/QuizBlock.vue'
import Exam from '@/components/ExamBlock.vue'
import DiscussionActivity from '@/components/DiscussionActivityBlock.vue'
import Folder from '@/components/FolderBlock.vue'

import MarkdownIt from 'markdown-it'

// `html: false` (p008 F5). This renders `Course Lesson.body` / `instructor_notes`
// in every enrolled student's session, and markdown-it's own normaliser is not a
// security boundary -- with `html: true` any raw tag in a lesson body reached the
// DOM verbatim. The output still goes through <SafeHtml>; the two are belt and
// braces, not alternatives. `linkify` is unaffected and stays on.
const markdown = new MarkdownIt({
	html: false,
	linkify: true,
})

const props = defineProps({
	courseName: {
		type: String,
		required: true,
	},
	content: {
		type: String,
		required: true,
	},
	youtube: {
		type: String,
		required: false,
	},
	quizId: {
		type: String,
		required: false,
	},
	exam: {
		type: String,
		required: false,
	},
	discussionID: {
		type: String,
		required: false,
	},
	folder: {
		type: String,
		required: false,
	},
	// [{ language, label, file }] for the lesson's videos (102 §6).
	captions: {
		type: Array,
		required: false,
	},

})


const getYouTubeVideoSource = (block) => {
	if (block.includes('{{')) {
		block = getId(block)
	}
	return `https://www.youtube.com/embed/${block}`
}

const getPDFSource = (block) => {
	return `${getId(block)}#toolbar=0`
}

const getId = (block) => {
	return block.match(/\(["']([^"']+?)["']\)/)[1]
}
</script>
