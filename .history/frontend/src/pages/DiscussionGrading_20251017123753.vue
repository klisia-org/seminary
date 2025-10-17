<template>
  <div class="discussion-grading">
    <div class="original-posts">
      <h2>{{ __('Original Post(s) by') }} {{ studentName }}</h2>
      <div v-for="post in originalPosts" :key="post.name" class="post">
        <div class="post-content" v-html="post.original_post"></div>
        <div class="post-meta text-sm text-ink-gray-5">
          {{ formatDate(post.creation) }}
        </div>
        <a
          v-if="post.original_attachment"
          :href="post.original_attachment"
          target="_blank"
          class="text-blue-500 underline"
        >
          {{ __('View Attachment') }}
        </a>
      </div>
    </div>

    <div class="replies">
      <h2>{{ __('Replies by') }} {{ studentName }}</h2>
      <div v-for="reply in studentReplies" :key="reply.creation" class="reply">
        <div class="reply-meta text-sm text-ink-gray-5">
          {{ __('Reply to:') }} {{ reply.parent_post }}
        </div>
        <div class="reply-content" v-html="reply.reply"></div>
        <div class="reply-meta text-sm text-ink-gray-5">
          {{ formatDate(reply.reply_dt) }}
        </div>
        <a
          v-if="reply.reply_attach"
          :href="reply.reply_attach"
          target="_blank"
          class="text-blue-500 underline"
        >
          {{ __('View Attachment') }}
        </a>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue';
import { createResource } from 'frappe-ui';
import dayjsModule from 'dayjs';
import relativeTime from 'dayjs/plugin/relativeTime';

const dayjs = typeof dayjsModule === 'function' ? dayjsModule : dayjsModule.default;
dayjs.extend(relativeTime);

const studentName = ref('');
const originalPosts = ref([]);
const studentReplies = ref([]);

const formatDate = (dateString) => {
  if (dateString && dateString.includes('.')) {
    return dayjs(dateString.split('.')[0]).fromNow();
  }
  return dayjs(dateString).fromNow();
};

const fetchStudentData = createResource({
  url: 'seminary.seminary.api.get_student_discussion_data',
  makeParams() {
    return {
      student_name: studentName.value,
      discussion_id: 'DISCUSSION_ID', // Replace with actual discussion ID
    };
  },
  auto: false,
  onSuccess(data) {
    originalPosts.value = data.original_posts || [];
    studentReplies.value = data.replies || [];
  },
});

onMounted(() => {
  studentName.value = 'STUDENT_NAME'; // Replace with actual student name
  fetchStudentData.reload();
});
</script>

<style scoped>
.discussion-grading {
  padding: 1rem;
}

.original-posts,
.replies {
  margin-bottom: 2rem;
}

.post,
.reply {
  border: 1px solid #e5e7eb;
  border-radius: 0.5rem;
  padding: 1rem;
  margin-bottom: 1rem;
}

.post-meta,
.reply-meta {
  color: #6b7280;
}
</style>