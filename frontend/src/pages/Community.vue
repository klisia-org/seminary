<template>
	<div class="mx-auto flex h-full w-full max-w-5xl gap-4 px-4 py-6">
		<!-- Bible tree (left) -->
		<aside v-if="cohorts.length && bibleTree.data?.length"
			class="hidden w-56 shrink-0 flex-col overflow-y-auto md:flex">
			<div class="mb-2 flex items-center gap-1 text-sm font-semibold text-ink-gray-8">
				<BookOpen class="h-4 w-4" />{{ __('Scripture') }}
			</div>
			<div v-if="passageFilter" class="mb-2 flex items-center gap-1 rounded bg-surface-gray-2 px-2 py-1 text-xs text-ink-gray-7">
				<span class="truncate">{{ passageLabel }}</span>
				<button class="ml-auto" @click="clearPassage"><X class="h-3 w-3" /></button>
			</div>
			<ul class="flex flex-col gap-0.5 text-sm">
				<li v-for="b in bibleTree.data" :key="b.osis">
					<button class="flex w-full items-center gap-1 rounded px-1.5 py-1 hover:bg-surface-gray-2"
						@click="toggleBook(b)">
						<component :is="expandedBook === b.osis ? ChevronDown : ChevronRight" class="h-3 w-3 text-ink-gray-4" />
						<span class="truncate text-ink-gray-8">{{ b.name }}</span>
						<span class="ml-auto text-xs text-ink-gray-5">{{ b.count }}</span>
					</button>
					<ul v-if="expandedBook === b.osis" class="ml-3 flex flex-col gap-0.5">
						<li v-for="c in chapters" :key="c.chapter">
							<button class="flex w-full items-center gap-1 rounded px-1.5 py-0.5 hover:bg-surface-gray-2"
								@click="toggleChapter(b, c)">
								<component :is="expandedChapter === c.chapter ? ChevronDown : ChevronRight" class="h-3 w-3 text-ink-gray-4" />
								<span class="text-ink-gray-7">{{ b.name }} {{ c.chapter }}</span>
								<span class="ml-auto text-xs text-ink-gray-5">{{ c.count }}</span>
							</button>
							<ul v-if="expandedChapter === c.chapter" class="ml-4 flex flex-col gap-0.5">
								<li v-for="v in verses" :key="v.verse">
									<button class="flex w-full items-center rounded px-1.5 py-0.5 text-xs hover:bg-surface-gray-2"
										@click="selectVerse(b, c, v)">
										<span class="text-ink-gray-6">{{ b.name }} {{ c.chapter }}:{{ v.verse }}</span>
										<span class="ml-auto text-ink-gray-5">{{ v.count }}</span>
									</button>
								</li>
							</ul>
						</li>
					</ul>
				</li>
			</ul>
		</aside>

		<div class="flex min-w-0 flex-1 flex-col">
		<!-- header: title + cohort switcher -->
		<div class="mb-4 flex items-center justify-between gap-3">
			<div class="flex items-center gap-2">
				<MessagesSquare class="h-6 w-6 text-ink-gray-7" />
				<h1 class="text-xl font-semibold text-ink-gray-9">{{ __('Community') }}</h1>
			</div>
			<div class="flex items-center gap-2">
				<select v-if="cohorts.length" v-model="selectedCohort"
					class="rounded-md border border-outline-gray-2 bg-surface-white px-2 py-1.5 text-sm text-ink-gray-8">
					<option v-for="c in cohorts" :key="c.name" :value="c.name">{{ c.cohort_name }}</option>
				</select>
				<button v-if="cohorts.length > 1 && selectedCohort" :title="__('Save as default cohort')"
					class="text-ink-gray-5 hover:text-ink-gray-8" @click="setDefaultCohort">
					<Star class="h-4 w-4" />
				</button>
				<Button v-if="canModerate" variant="subtle" :title="__('Message leaders')" @click="openBroadcast">
					<template #prefix><Megaphone class="h-4 w-4" /></template>
				</Button>
				<Button v-if="selectedCohort" variant="subtle" :title="__('My cohort')" @click="openMembers">
					<template #prefix><UsersRound class="h-4 w-4" /></template>
				</Button>
				<Button v-if="canModerate" variant="subtle" :title="__('Moderation queue')" @click="openModeration">
					<template #prefix><Shield class="h-4 w-4" /></template>
				</Button>
				<Button v-if="selectedCohort" variant="solid" :label="__('New post')" @click="openCompose">
					<template #prefix><SquarePen class="h-4 w-4" /></template>
				</Button>
			</div>
		</div>

		<div v-if="!cohorts.length" class="mt-16 text-center text-ink-gray-5">
			{{ __('You are not part of any cohort yet.') }}
		</div>

		<template v-else>
			<!-- search -->
			<div class="mb-3 flex items-center gap-2 rounded-md border border-outline-gray-2 bg-surface-white px-2">
				<Search class="h-4 w-4 text-ink-gray-4" />
				<input v-model="searchQuery" type="text" :placeholder="__('Search posts, topics, passages…')"
					class="w-full bg-transparent py-1.5 text-sm text-ink-gray-8 focus:outline-none" />
				<button v-if="searchQuery" @click="searchQuery = ''"><X class="h-4 w-4 text-ink-gray-4" /></button>
			</div>
			<div v-if="searchActive" class="mb-3 flex items-center gap-2 text-xs text-ink-gray-5">
				<span v-if="searchRes.loading">{{ __('Searching…') }}</span>
				<span v-else>{{ __('{0} result(s)').format(posts.length) }}</span>
			</div>

			<!-- channel filter -->
			<div v-show="!searchActive" class="mb-4 flex flex-wrap gap-2">
				<button
					class="rounded-full border px-3 py-1 text-sm"
					:class="channelFilter === '' ? 'border-outline-gray-3 bg-surface-gray-3 text-ink-gray-9' : 'border-outline-gray-2 text-ink-gray-6'"
					@click="setChannel('')">{{ __('All') }}</button>
				<button v-for="ch in channels" :key="ch.name"
					class="rounded-full border px-3 py-1 text-sm"
					:class="channelFilter === ch.name ? 'border-outline-gray-3 bg-surface-gray-3 text-ink-gray-9' : 'border-outline-gray-2 text-ink-gray-6'"
					@click="setChannel(ch.name)">
					<span v-if="ch.icon" class="mr-1">{{ ch.icon }}</span>{{ ch.channel_name }}
					<span v-if="unread[ch.name]" class="ml-1 rounded-full bg-surface-gray-4 px-1.5 text-xs">{{ unread[ch.name] }}</span>
				</button>
			</div>

			<!-- visibility scope -->
			<div class="mb-3 flex items-center gap-2 text-sm text-ink-gray-6">
				<span>{{ __('Show') }}</span>
				<select v-model="scopeFilter" class="rounded-md border border-outline-gray-2 bg-surface-white px-2 py-1 text-sm text-ink-gray-8"
					@change="refresh">
					<option value="">{{ __('All') }}</option>
					<option value="cohort_only">{{ __('Cohort only') }}</option>
					<option value="portal_users">{{ __('Whole community') }}</option>
				</select>
				<label class="ml-2 flex items-center gap-1">
					<input type="checkbox" v-model="savedOnly" class="rounded" @change="refresh" />
					<Bookmark class="h-3.5 w-3.5" />{{ __('Saved') }}
				</label>
			</div>

			<!-- prayer: active vs answered -->
			<div v-if="isPrayerChannel" class="mb-3 flex gap-2 text-sm">
				<button class="rounded-md px-3 py-1"
					:class="prayerView === 'active' ? 'bg-surface-gray-3 text-ink-gray-9' : 'text-ink-gray-6'"
					@click="setPrayerView('active')">{{ __('Active') }}</button>
				<button class="rounded-md px-3 py-1"
					:class="prayerView === 'answered' ? 'bg-surface-gray-3 text-ink-gray-9' : 'text-ink-gray-6'"
					@click="setPrayerView('answered')">{{ __('Answered') }}</button>
			</div>

			<!-- feed -->
			<div class="flex flex-col gap-4">
				<div v-if="feed.loading" class="py-10 text-center text-ink-gray-5">{{ __('Loading…') }}</div>
				<div v-else-if="!posts.length" class="py-10 text-center text-ink-gray-5">{{ __('No posts yet. Be the first to share.') }}</div>

				<template v-for="(post, i) in posts" :key="post.name">
				<article class="rounded-lg border border-outline-gray-2 bg-surface-white p-4">
					<header class="mb-2 flex items-center justify-between">
						<div class="flex items-center gap-2 text-sm">
							<span class="font-medium text-ink-gray-9">{{ post.author_name || post.author }}</span>
							<span v-if="post.author_membership === 'outside'"
								class="rounded bg-surface-gray-2 px-1.5 py-0.5 text-xs text-ink-gray-6">{{ __('guest') }}</span>
							<component :is="visIcon(post.visibility)" class="h-3.5 w-3.5 text-ink-gray-5" />
							<span class="text-ink-gray-5">· {{ timeAgo(post.creation) }}</span>
						</div>
						<div class="flex items-center gap-2">
							<span v-if="post.new_comments" class="rounded-full bg-surface-red-5 px-1.5 py-0.5 text-xs text-ink-white">
								{{ post.new_comments }} {{ __('new') }}
							</span>
							<span v-if="post.prayer_answered" class="flex items-center gap-1 rounded bg-surface-gray-2 px-2 py-0.5 text-xs text-ink-gray-7">
								<Check class="h-3.5 w-3.5" />{{ __('Answered') }}
							</span>
							<span v-if="post.status === 'pinned'" class="flex items-center gap-1 text-xs text-ink-gray-5">
								<Pin class="h-3.5 w-3.5" />{{ __('Pinned') }}
							</span>
						</div>
					</header>

					<h2 v-if="post.title" class="mb-1 font-semibold text-ink-gray-9">{{ post.title }}</h2>
					<div class="prose-sm max-w-none text-ink-gray-8" v-html="post.content"></div>

					<!-- prayer testimony -->
					<div v-if="post.prayer_answered && post.prayer_answer_note"
						class="mt-2 rounded-md border-l-2 border-outline-gray-3 bg-surface-gray-1 p-2 text-sm text-ink-gray-7">
						<span class="font-medium">{{ __('Answered') }}<span v-if="post.prayer_answered_on"> · {{ post.prayer_answered_on }}</span>:</span>
						{{ post.prayer_answer_note }}
					</div>

					<!-- tags -->
					<div v-if="post.topics?.length || post.scripture?.length" class="mt-2 flex flex-wrap gap-1.5">
						<span v-for="t in post.topics" :key="'t' + t"
							class="rounded border border-outline-gray-2 px-2 py-0.5 text-xs text-ink-gray-6">#{{ t }}</span>
						<button v-for="s in post.scripture" :key="'s' + s.resolved_ref"
							class="flex items-center gap-1 rounded border border-outline-gray-2 px-2 py-0.5 text-xs text-ink-gray-7 hover:bg-surface-gray-2"
							@click="openPassage(s)">
							<BookOpen class="h-3 w-3" />{{ s.display }}
						</button>
					</div>

					<!-- sermon lab: video + timestamped comments -->
					<SermonLabPlayer v-if="post.channel_kind === 'video_timestamp' && post.video_url"
						:post-name="post.name" :video-url="post.video_url" :can-comment="true" />

					<!-- exegetical: passage reader + verse-anchored comments -->
					<ExegeticalReader v-else-if="post.channel_kind === 'bible_passage' && post.scripture?.length"
						:post-name="post.name" :scripture="post.scripture" :can-comment="true" />

					<!-- reactions -->
					<div class="mt-3 flex flex-wrap items-center gap-1.5">
						<button v-for="rt in reactionTypes" :key="rt.name"
							class="flex items-center gap-1 rounded-full border px-2 py-0.5 text-sm"
							:class="reactionMine(post, rt.name) ? 'border-outline-gray-4 bg-surface-gray-2' : 'border-outline-gray-2'"
							@click="react(post, rt.name)">
							<span>{{ rt.glyph }}</span>
							<span v-if="reactionCount(post, rt.name)" class="text-xs text-ink-gray-6">{{ reactionCount(post, rt.name) }}</span>
						</button>
						<button v-if="!['video_timestamp', 'bible_passage'].includes(post.channel_kind)"
							class="ml-2 flex items-center gap-1 text-sm text-ink-gray-6" @click="toggleThread(post)">
							<MessageCircle class="h-4 w-4" />{{ post.comment_count || 0 }}
						</button>
						<button v-if="post.channel_kind === 'prayer' && post.is_mine && !post.prayer_answered"
							class="ml-2 text-sm text-ink-gray-6 hover:text-ink-gray-9" @click="openAnswer(post)">
							{{ __('Mark answered') }}
						</button>
						<button v-if="post.channel_kind === 'prayer' && post.is_mine && post.prayer_answered"
							class="ml-2 text-sm text-ink-gray-6 hover:text-ink-gray-9" @click="reopen(post)">
							{{ __('Reopen') }}
						</button>
						<button class="ml-auto text-ink-gray-4 hover:text-ink-gray-7"
							:title="post.saved ? __('Unsave') : __('Save')" @click="toggleSave(post)">
							<component :is="post.saved ? BookmarkCheck : Bookmark" class="h-3.5 w-3.5"
								:class="post.saved ? 'text-ink-gray-8' : ''" />
						</button>
						<button class="text-ink-gray-4 hover:text-ink-gray-7" :title="__('Report')"
							@click="openReport('Cohort Post', post.name)">
							<Flag class="h-3.5 w-3.5" />
						</button>
						<template v-if="canModerate">
							<button class="text-ink-gray-5 hover:text-ink-gray-9"
								:title="post.status === 'pinned' ? __('Unpin') : __('Pin')"
								@click="moderatePost(post, post.status === 'pinned' ? 'published' : 'pinned')">
								<Pin class="h-3.5 w-3.5" />
							</button>
							<button class="text-ink-gray-5 hover:text-ink-red-5" :title="__('Block')"
								@click="moderatePost(post, 'blocked')">
								<Ban class="h-3.5 w-3.5" />
							</button>
						</template>
						<template v-if="post.is_mine">
							<button class="text-ink-gray-5 hover:text-ink-gray-9" :title="__('Edit')" @click="openEdit(post)">
								<Pencil class="h-3.5 w-3.5" />
							</button>
							<button class="text-ink-gray-5 hover:text-ink-red-5" :title="__('Delete')" @click="confirmDelete(post)">
								<Trash2 class="h-3.5 w-3.5" />
							</button>
						</template>
					</div>

					<!-- thread -->
					<div v-if="expandedPost === post.name" class="mt-3 border-t border-outline-gray-1 pt-3">
						<div v-if="thread.loading" class="text-sm text-ink-gray-5">{{ __('Loading…') }}</div>
						<div v-else class="flex flex-col gap-3">
							<div v-for="c in threadComments" :key="c.name"
								:style="{ marginLeft: Math.min(c.depth, 4) * 16 + 'px' }">
								<div class="text-sm">
									<span class="font-medium text-ink-gray-9">{{ c.author_name || c.author }}</span>
									<span v-if="c.is_private" class="ml-1 inline-flex items-center gap-0.5 rounded bg-surface-gray-2 px-1.5 text-xs text-ink-gray-6"><Lock class="h-3 w-3" />{{ __('private') }}</span>
									<span class="text-ink-gray-5">· {{ timeAgo(c.creation) }}</span>
								</div>
								<div class="prose-sm max-w-none text-ink-gray-8" v-html="c.content"></div>
								<button class="text-xs text-ink-gray-5" @click="replyTo = c">{{ __('Reply') }}</button>
							</div>

							<!-- reply box -->
							<div class="mt-2">
								<div v-if="replyTo" class="mb-1 flex items-center gap-2 text-xs text-ink-gray-5">
									{{ __('Replying to') }} {{ replyTo.author_name || replyTo.author }}
									<button @click="replyTo = null"><X class="h-3 w-3" /></button>
								</div>
								<div class="flex gap-2">
									<Input v-model="replyText" type="text" :placeholder="__('Write a reply…')" class="flex-1"
										@keyup.enter="submitReply(post)" />
									<Button variant="solid" :loading="addComment.loading" @click="submitReply(post)">
										<Send class="h-4 w-4" />
									</Button>
								</div>
									<label class="mt-1 flex items-center gap-1 text-xs text-ink-gray-5"><input type="checkbox" v-model="replyPrivate" class="rounded" /><Lock class="h-3 w-3" />{{ __('Private — only the author and leaders will see this') }}</label>
							</div>

							<!-- linked reflections -->
							<div v-if="thread.data?.post?.linked_posts?.length" class="mt-2">
								<div class="mb-1 text-xs font-medium text-ink-gray-6">{{ __('Linked reflections') }}</div>
								<ul class="flex flex-col gap-1">
									<li v-for="l in thread.data.post.linked_posts" :key="l.name" class="text-sm text-ink-gray-8">
										{{ l.title || l.name }}
										<span class="text-xs text-ink-gray-5">· {{ l.relation_type }}</span>
									</li>
								</ul>
							</div>
							<div v-if="post.is_mine" class="mt-2 flex items-center gap-2">
								<Input v-model="linkTarget" type="text" :placeholder="__('Link a post by ID (e.g. a journal)')" class="flex-1" />
								<Button :label="__('Link')" :loading="linkPost.loading" @click="submitLink(post)" />
							</div>

							<!-- related across channels -->
							<div v-if="related.data?.length" class="mt-2 rounded-md bg-surface-gray-1 p-2">
								<div class="mb-1 text-xs font-medium text-ink-gray-6">{{ __('Related across channels') }}</div>
								<ul class="flex flex-col gap-1">
									<li v-for="r in related.data" :key="r.name" class="flex items-center gap-2 text-sm text-ink-gray-8">
										<span class="truncate">{{ r.title || plain(r.content) }}</span>
										<span class="whitespace-nowrap text-xs text-ink-gray-5">· {{ r.channel_kind }}</span>
									</li>
								</ul>
							</div>
						</div>
					</div>
				</article>
				<div v-if="i === lastNewIndex && i < posts.length - 1"
					class="my-1 flex items-center gap-2 text-xs font-medium text-ink-red-4">
					<div class="h-px flex-1 bg-red-300/60"></div>{{ __('New') }}<div class="h-px flex-1 bg-red-300/60"></div>
				</div>
				</template>
			</div>
		</template>

		<!-- compose dialog -->
		<Dialog v-model="showCompose" :options="{ title: __('New post'), size: 'lg' }">
			<template #body-content>
				<div class="flex flex-col gap-3">
					<select v-model="draft.channel"
						class="rounded-md border border-outline-gray-2 bg-surface-white px-2 py-1.5 text-sm">
						<option value="" disabled>{{ __('Select a channel') }}</option>
						<option v-for="ch in channels" :key="ch.name" :value="ch.name">{{ ch.channel_name }}</option>
					</select>
					<Input v-model="draft.title" type="text" :placeholder="__('Title (optional)')" />
					<div v-if="composeChannelKind === 'video_timestamp'" class="flex items-center gap-2">
						<Video class="h-4 w-4 text-ink-gray-5" />
						<Input v-model="draft.video_url" type="text"
							:placeholder="__('YouTube link (required)')" class="flex-1" />
					</div>
					<div class="flex items-center gap-2">
						<label class="text-sm text-ink-gray-6">{{ __('Visibility') }}</label>
						<select v-model="draft.visibility"
							class="rounded-md border border-outline-gray-2 bg-surface-white px-2 py-1.5 text-sm">
							<option value="cohort_only">{{ __('Cohort only') }}</option>
							<option value="portal_users">{{ __('Whole community') }}</option>
							<option value="private">{{ __('Only me') }}</option>
						</select>
					</div>
					<Input v-model="draft.topics" type="text" :placeholder="__('Topics (comma-separated)')" />
					<Input v-model="draft.scripture" type="text"
						:placeholder="__('Scripture, e.g. Jn 3:16-18; Rom 8:28')" />
					<!-- content editor: :teleport="false" keeps its menu inline (inside
					     the Dialog) instead of teleporting to body over other fields -->
					<RichTextEditor :key="'compose-' + composeKey" :content="draft.content" :teleport="false"
						:placeholder="__('Share something…')" @change="(v) => (draft.content = v)" />
				</div>
			</template>
			<template #actions>
				<div class="flex justify-end gap-2">
					<Button :label="__('Cancel')" @click="showCompose = false" />
					<Button variant="solid" :label="__('Post')" :loading="createPost.loading" @click="submitPost" />
				</div>
			</template>
		</Dialog>

		<!-- mark answered dialog -->
		<Dialog v-model="showAnswer" :options="{ title: __('Mark prayer answered') }">
			<template #body-content>
				<textarea v-model="answerNote" rows="3"
					class="w-full rounded-md border border-outline-gray-2 bg-surface-white p-2 text-sm text-ink-gray-8"
					:placeholder="__('Share how it was answered (optional)')"></textarea>
			</template>
			<template #actions>
				<div class="flex justify-end gap-2">
					<Button :label="__('Cancel')" @click="showAnswer = false" />
					<Button variant="solid" :label="__('Mark answered')" :loading="markAnswered.loading" @click="confirmAnswer" />
				</div>
			</template>
		</Dialog>

		<!-- edit post dialog -->
		<Dialog v-model="showEdit" :options="{ title: __('Edit post'), size: 'lg' }">
			<template #body-content>
				<div class="flex flex-col gap-3">
					<Input v-model="editDraft.title" type="text" :placeholder="__('Title (optional)')" />
					<div v-if="editDraft.channel_kind === 'video_timestamp'" class="flex items-center gap-2">
						<Video class="h-4 w-4 text-ink-gray-5" />
						<Input v-model="editDraft.video_url" type="text" :placeholder="__('YouTube link')" class="flex-1" />
					</div>
					<div class="flex items-center gap-2">
						<label class="text-sm text-ink-gray-6">{{ __('Visibility') }}</label>
						<select v-model="editDraft.visibility"
							class="rounded-md border border-outline-gray-2 bg-surface-white px-2 py-1.5 text-sm">
							<option value="cohort_only">{{ __('Cohort only') }}</option>
							<option value="portal_users">{{ __('Whole community') }}</option>
							<option value="private">{{ __('Only me') }}</option>
						</select>
					</div>
					<Input v-model="editDraft.topics" type="text" :placeholder="__('Topics (comma-separated)')" />
					<Input v-model="editDraft.scripture" type="text"
						:placeholder="__('Scripture, e.g. Jn 3:16-18; Rom 8:28')" />
					<RichTextEditor :key="'edit-' + editKey" :content="editDraft.content" :teleport="false"
						:placeholder="__('Share something…')" @change="(v) => (editDraft.content = v)" />
				</div>
			</template>
			<template #actions>
				<div class="flex justify-end gap-2">
					<Button :label="__('Cancel')" @click="showEdit = false" />
					<Button variant="solid" :label="__('Save')" :loading="editPostRes.loading" @click="submitEdit" />
				</div>
			</template>
		</Dialog>

		<!-- message leaders (Inbox broadcast) -->
		<Dialog v-model="showBroadcast" :options="{ title: __('Message leaders') }">
			<template #body-content>
				<div class="flex flex-col gap-3">
					<Input v-model="broadcastSubject" type="text" :placeholder="__('Subject')" />
					<textarea v-model="broadcastMessage" rows="4"
						class="w-full rounded-md border border-outline-gray-2 bg-surface-white p-2 text-sm text-ink-gray-8"
						:placeholder="__('Message to the leaders you oversee…')"></textarea>
					<label class="flex items-center gap-1 text-sm text-ink-gray-6">
						<input type="checkbox" v-model="broadcastEmail" class="rounded" />{{ __('Also send by email') }}
					</label>
					<p class="text-xs text-ink-gray-4">{{ __('Goes to each leader’s Community inbox.') }}</p>
				</div>
			</template>
			<template #actions>
				<div class="flex justify-end gap-2">
					<Button :label="__('Cancel')" @click="showBroadcast = false" />
					<Button variant="solid" :label="__('Send')" :loading="broadcastRes.loading" @click="submitBroadcast" />
				</div>
			</template>
		</Dialog>

		<!-- split cohort (transfer members) -->
		<Dialog v-model="showSplit" :options="{ title: __('Split cohort'), size: '3xl' }">
			<template #body-content>
				<div class="flex flex-col gap-3">
					<Input v-model="splitName" type="text" :placeholder="__('New cohort name')" />
					<div class="grid grid-cols-2 gap-3">
						<div class="rounded-md border border-outline-gray-2 p-2">
							<div class="mb-1 text-xs font-medium text-ink-gray-6">{{ __('Stays in original') }}</div>
							<ul class="flex flex-col gap-1">
								<li v-for="m in splitOriginal" :key="m.person"
									class="flex items-center justify-between gap-2 rounded px-1 py-0.5 text-sm hover:bg-surface-gray-1">
									<span class="truncate text-ink-gray-8">{{ m.name }}</span>
									<button class="font-semibold text-ink-gray-5 hover:text-ink-gray-9" :title="__('Move to new cohort')"
										@click="moveToNew(m)">»</button>
								</li>
								<li v-if="!splitOriginal.length" class="text-xs text-ink-gray-4">{{ __('None') }}</li>
							</ul>
						</div>
						<div class="rounded-md border border-outline-gray-2 p-2">
							<div class="mb-1 text-xs font-medium text-ink-gray-6">{{ __('Moves to new cohort') }}</div>
							<ul class="flex flex-col gap-1">
								<li v-for="m in splitMoving" :key="m.person"
									class="flex items-center gap-2 rounded px-1 py-0.5 text-sm hover:bg-surface-gray-1">
									<button class="font-semibold text-ink-gray-5 hover:text-ink-gray-9" :title="__('Move back')"
										@click="moveToOriginal(m)">«</button>
									<span class="mr-auto truncate text-ink-gray-8">{{ m.name }}</span>
									<button class="rounded px-1.5 py-0.5 text-xs"
										:class="splitLeader === m.person ? 'bg-surface-gray-3 text-ink-gray-9' : 'text-ink-gray-5 hover:text-ink-gray-9'"
										@click="splitLeader = m.person">
										{{ splitLeader === m.person ? __('Leader ✓') : __('Make leader') }}
									</button>
								</li>
								<li v-if="!splitMoving.length" class="text-xs text-ink-gray-4">{{ __('Move members here with »') }}</li>
							</ul>
						</div>
					</div>
				</div>
			</template>
			<template #actions>
				<div class="flex justify-end gap-2">
					<Button :label="__('Cancel')" @click="showSplit = false" />
					<Button variant="solid" :label="__('Create split')" :loading="splitRes.loading" @click="submitSplit" />
				</div>
			</template>
		</Dialog>

		<!-- passage text popover -->
		<Dialog v-model="showPassage" :options="{ title: passageRes.data?.reference || __('Passage') }">
			<template #body-content>
				<div v-if="passageRes.loading" class="py-4 text-center text-sm text-ink-gray-5">{{ __('Loading…') }}</div>
				<p v-else class="whitespace-pre-line text-sm leading-relaxed text-ink-gray-8">
					{{ passageRes.data?.text || __('Passage text unavailable.') }}
				</p>
			</template>
		</Dialog>

		<!-- my cohort -->
		<Dialog v-model="showMembers" :options="{ title: __('My cohort'), size: 'xl' }">
			<template #body-content>
				<div class="flex flex-col gap-3">
					<div v-if="membersRes.data?.is_leader" class="flex flex-wrap items-center gap-2">
						<Input v-model="inviteEmail" type="text" :placeholder="__('Invite by email')" class="w-56"
							@keyup.enter="inviteMember" />
						<Button variant="solid" :label="__('Invite')" :loading="inviteRes.loading" @click="inviteMember" />
						<Button v-if="membersRes.data?.allow_split" :label="__('Split cohort')" @click="openSplit" />
					</div>
					<table class="w-full text-sm">
						<thead>
							<tr class="text-left text-xs text-ink-gray-5">
								<th class="py-1">{{ __('Member') }}</th>
								<th>{{ __('Role') }}</th>
								<th>{{ __('Last visit') }}</th>
								<th>{{ __('Last post') }}</th>
								<th></th>
							</tr>
						</thead>
						<tbody>
							<tr v-for="m in membersRes.data?.members || []" :key="m.person" class="border-t border-outline-gray-1">
								<td class="py-1.5">
									<div class="font-medium text-ink-gray-9">
										{{ m.name }}<span v-if="m.is_leader" class="ml-1 text-xs text-ink-gray-5">({{ __('leader') }})</span>
									</div>
									<a v-if="m.email" :href="'mailto:' + m.email" class="text-xs text-ink-blue-3 hover:underline">{{ m.email }}</a>
								</td>
								<td class="text-ink-gray-7">{{ m.role }}</td>
								<td class="text-ink-gray-6">{{ m.last_visited ? timeAgo(m.last_visited) : '—' }}</td>
								<td class="text-ink-gray-6">{{ m.last_post_on ? timeAgo(m.last_post_on) : '—' }}</td>
								<td class="text-right">
									<button v-if="membersRes.data?.is_leader && !m.is_leader"
										class="text-xs text-ink-gray-6 hover:text-ink-gray-9" @click="makeLeader(m)">
										{{ __('Make leader') }}
									</button>
								</td>
							</tr>
						</tbody>
					</table>
				</div>
			</template>
		</Dialog>

		<!-- report dialog -->
		<Dialog v-model="showReport" :options="{ title: __('Report content') }">
			<template #body-content>
				<div class="flex flex-col gap-3">
					<select v-model="reportReason"
						class="rounded-md border border-outline-gray-2 bg-surface-white px-2 py-1.5 text-sm">
						<option value="Inappropriate">{{ __('Inappropriate') }}</option>
						<option value="Off-topic">{{ __('Off-topic') }}</option>
						<option value="Harmful">{{ __('Harmful') }}</option>
						<option value="Spam">{{ __('Spam') }}</option>
						<option value="Other">{{ __('Other') }}</option>
					</select>
					<textarea v-model="reportDetail" rows="3"
						class="w-full rounded-md border border-outline-gray-2 bg-surface-white p-2 text-sm text-ink-gray-8"
						:placeholder="__('Anything the moderator should know (optional)')"></textarea>
				</div>
			</template>
			<template #actions>
				<div class="flex justify-end gap-2">
					<Button :label="__('Cancel')" @click="showReport = false" />
					<Button variant="solid" :label="__('Report')" :loading="flagContent.loading" @click="submitReport" />
				</div>
			</template>
		</Dialog>

		<!-- moderation queue -->
		<Dialog v-model="showModeration" :options="{ title: __('Moderation queue'), size: 'lg' }">
			<template #body-content>
				<div v-if="!flagsRes.data?.length" class="py-6 text-center text-sm text-ink-gray-5">
					{{ __('No open flags.') }}
				</div>
				<div v-else class="flex flex-col gap-3">
					<div v-for="f in flagsRes.data" :key="f.name" class="rounded-md border border-outline-gray-2 p-2">
						<div class="text-xs text-ink-gray-5">{{ f.target_doctype }} · {{ f.reason }}</div>
						<div class="my-1 text-sm text-ink-gray-8">{{ f.preview || '—' }}</div>
						<div v-if="f.detail" class="mb-1 text-xs italic text-ink-gray-5">{{ f.detail }}</div>
						<div class="flex gap-2">
							<Button variant="subtle" :label="__('Dismiss')" @click="resolveFlag(f.name, 'dismiss')" />
							<Button variant="solid" theme="red" :label="__('Block content')" @click="resolveFlag(f.name, 'block')" />
						</div>
					</div>
				</div>
			</template>
		</Dialog>
		</div>
	</div>
</template>

<script setup>
import { computed, inject, onMounted, onUnmounted, reactive, ref, watch } from 'vue'
import { Button, Dialog, Input, createResource } from 'frappe-ui'
import {
	MessagesSquare, SquarePen, MessageCircle, Send, Pin, X,
	Lock, Users, Globe, Mail, BookOpen, Check, Video, Flag, Shield, Ban, Pencil, Trash2,
	Bookmark, BookmarkCheck, UsersRound, ChevronRight, ChevronDown, Search, Star, Megaphone,
} from 'lucide-vue-next'
import { timeAgo, createToast } from '@/utils'
import RichTextEditor from '@/components/RichTextEditor.vue'
import SermonLabPlayer from '@/components/SermonLabPlayer.vue'
import ExegeticalReader from '@/components/ExegeticalReader.vue'

const socket = inject('$socket')

const selectedCohort = ref('')
const channelFilter = ref('')
const expandedPost = ref(null)
const replyTo = ref(null)
const replyText = ref('')
const showCompose = ref(false)
const composeKey = ref(0)
const draft = reactive({ channel: '', title: '', content: '', visibility: 'cohort_only', direct_recipient: '', topics: '', scripture: '', video_url: '' })
const prayerView = ref('active')
const scopeFilter = ref('')
const savedOnly = ref(false)
const searchQuery = ref('')
const showPassage = ref(false)
const showMembers = ref(false)
const inviteEmail = ref('')
const expandedBook = ref(null)
const expandedChapter = ref(null)
const passageFilter = ref(null)
const showSplit = ref(false)
const splitName = ref('')
const splitOriginal = ref([])
const splitMoving = ref([])
const splitLeader = ref(null)
const replyPrivate = ref(false)
const showBroadcast = ref(false)
const broadcastSubject = ref('')
const broadcastMessage = ref('')
const broadcastEmail = ref(false)
const showEdit = ref(false)
const editKey = ref(0)
const editDraft = reactive({ name: '', title: '', content: '', visibility: 'cohort_only', direct_recipient: '', topics: '', scripture: '', video_url: '', channel_kind: '' })
const showAnswer = ref(false)
const answerNote = ref('')
const answerPost = ref(null)
const linkTarget = ref('')

// --- resources ---
const cohortsRes = createResource({
	url: 'seminary.seminary.discipleship.feed_api.my_cohorts_list',
	auto: true,
	onSuccess(data) {
		if (data?.length && !selectedCohort.value) {
			const saved = localStorage.getItem('community:defaultCohort')
			selectedCohort.value = saved && data.some((c) => c.name === saved) ? saved : data[0].name
		}
	},
})
function setDefaultCohort() {
	if (!selectedCohort.value) return
	localStorage.setItem('community:defaultCohort', selectedCohort.value)
	createToast({ title: __('Default cohort saved.'), icon: 'check' })
}
const channelsRes = createResource({
	url: 'seminary.seminary.discipleship.feed_api.list_channels',
	auto: true,
})
const reactionTypesRes = createResource({
	url: 'seminary.seminary.discipleship.feed_api.list_reaction_types',
	auto: true,
})
const feed = createResource({
	url: 'seminary.seminary.discipleship.feed_api.list_feed',
	makeParams: () => ({
		cohort: selectedCohort.value,
		channel: channelFilter.value || null,
		visibility: scopeFilter.value || null,
		saved_only: savedOnly.value ? 1 : 0,
		answered: isPrayerChannel.value ? (prayerView.value === 'answered' ? 1 : 0) : null,
	}),
})
const unreadRes = createResource({
	url: 'seminary.seminary.discipleship.feed_api.unread_counts',
	makeParams: () => ({ cohort: selectedCohort.value }),
})
const thread = createResource({
	url: 'seminary.seminary.discipleship.feed_api.get_thread',
	makeParams: () => ({ post: expandedPost.value }),
})
const related = createResource({
	url: 'seminary.seminary.discipleship.feed_api.related_posts',
	makeParams: () => ({ post: expandedPost.value }),
})
const createPost = createResource({ url: 'seminary.seminary.discipleship.feed_api.create_post' })
const addComment = createResource({ url: 'seminary.seminary.discipleship.feed_api.add_comment' })
const toggleReaction = createResource({ url: 'seminary.seminary.discipleship.feed_api.toggle_reaction' })
const markSeen = createResource({ url: 'seminary.seminary.discipleship.feed_api.mark_seen' })
const markAnswered = createResource({ url: 'seminary.seminary.discipleship.feed_api.mark_prayer_answered' })
const reopenPrayer = createResource({ url: 'seminary.seminary.discipleship.feed_api.reopen_prayer' })
const linkPost = createResource({ url: 'seminary.seminary.discipleship.feed_api.link_post' })
const canModerateRes = createResource({ url: 'seminary.seminary.discipleship.moderation.can_moderate', auto: true })
const flagsRes = createResource({ url: 'seminary.seminary.discipleship.moderation.list_flags' })
const flagContent = createResource({ url: 'seminary.seminary.discipleship.moderation.flag_content' })
const resolveFlagRes = createResource({ url: 'seminary.seminary.discipleship.moderation.resolve_flag' })
const setPostStatusRes = createResource({ url: 'seminary.seminary.discipleship.moderation.set_post_status' })
const editPostRes = createResource({ url: 'seminary.seminary.discipleship.feed_api.edit_post' })
const deletePostRes = createResource({ url: 'seminary.seminary.discipleship.feed_api.delete_post' })
const toggleSaveRes = createResource({ url: 'seminary.seminary.discipleship.feed_api.toggle_save' })
const passageRes = createResource({ url: 'seminary.seminary.integrations.bible.passage_text' })
const membersRes = createResource({ url: 'seminary.seminary.discipleship.api.cohort_members' })
const inviteRes = createResource({ url: 'seminary.seminary.discipleship.api.invite_member' })
const reassignRes = createResource({ url: 'seminary.seminary.discipleship.api.reassign_leader' })
const splitRes = createResource({ url: 'seminary.seminary.discipleship.api.split_cohort' })
const bibleTree = createResource({ url: 'seminary.seminary.discipleship.scripture.scripture_books' })
const chaptersRes = createResource({ url: 'seminary.seminary.discipleship.scripture.scripture_chapters' })
const versesRes = createResource({ url: 'seminary.seminary.discipleship.scripture.scripture_verses' })
const passagePostsRes = createResource({ url: 'seminary.seminary.discipleship.scripture.posts_in_range' })
const searchRes = createResource({ url: 'seminary.seminary.discipleship.feed_api.search_posts' })
const broadcastRes = createResource({ url: 'seminary.seminary.discipleship.api.broadcast_to_leaders' })

// --- derived ---
const cohorts = computed(() => cohortsRes.data || [])
const channels = computed(() => channelsRes.data || [])
const selectedChannelKind = computed(() => channels.value.find((c) => c.name === channelFilter.value)?.channel_kind || null)
const isPrayerChannel = computed(() => selectedChannelKind.value === 'prayer')
const composeChannelKind = computed(() => channels.value.find((c) => c.name === draft.channel)?.channel_kind || null)
const reactionTypes = computed(() => reactionTypesRes.data || [])
const searchActive = computed(() => searchQuery.value.trim().length >= 2)
const posts = computed(() => {
	if (searchActive.value) return searchRes.data || []
	return passageFilter.value ? (passagePostsRes.data || []) : (feed.data || [])
})
const chapters = computed(() => chaptersRes.data || [])
const verses = computed(() => versesRes.data || [])
const passageLabel = computed(() => passageFilter.value?.label || '')
const lastNewIndex = computed(() => {
	let idx = -1
	posts.value.forEach((p, i) => { if (p.is_new) idx = i })
	return idx
})
const unread = computed(() => unreadRes.data || {})
const threadComments = computed(() => buildThread(thread.data?.comments || []))

function buildThread(comments) {
	// order = as returned (creation asc); compute depth from parent chain
	const byName = {}
	comments.forEach((c) => (byName[c.name] = c))
	const depthOf = (c) => {
		let d = 0, cur = c
		while (cur.parent_comment && byName[cur.parent_comment]) { d++; cur = byName[cur.parent_comment] }
		return d
	}
	// depth-first order so replies sit under their parent
	const children = {}
	comments.forEach((c) => {
		const key = c.parent_comment || '__root'
		;(children[key] = children[key] || []).push(c)
	})
	const out = []
	const walk = (key) => (children[key] || []).forEach((c) => {
		out.push({ ...c, depth: depthOf(c) })
		walk(c.name)
	})
	walk('__root')
	return out
}

function reactionFor(post, rtName) {
	return (post.reactions || []).find((r) => r.reaction_type === rtName)
}
function reactionCount(post, rtName) { return reactionFor(post, rtName)?.count || 0 }
function reactionMine(post, rtName) { return !!reactionFor(post, rtName)?.mine }

const visIconMap = { cohort_only: Users, portal_users: Globe, private: Lock, direct: Mail }
function visIcon(v) { return visIconMap[v] || Users }

// --- actions ---
function refresh() {
	if (!selectedCohort.value) return
	feed.fetch()
	unreadRes.fetch()
}
function setChannel(name) {
	channelFilter.value = name // watch → refresh; feed onSuccess marks seen
}
function openEdit(post) {
	Object.assign(editDraft, {
		name: post.name,
		title: post.title || '',
		content: post.content || '',
		visibility: post.visibility,
		direct_recipient: post.direct_recipient || '',
		topics: (post.topics || []).join(', '),
		scripture: (post.scripture || []).map((s) => s.display).join('\n'),
		video_url: post.video_url || '',
		channel_kind: post.channel_kind || '',
	})
	editKey.value++
	showEdit.value = true
}
function submitEdit() {
	editPostRes
		.submit({
			post: editDraft.name,
			title: editDraft.title || null,
			content: editDraft.content,
			visibility: editDraft.visibility,
			direct_recipient: editDraft.visibility === 'direct' ? editDraft.direct_recipient : null,
			topics: editDraft.topics.split(',').map((t) => t.trim()).filter(Boolean),
			scripture: editDraft.scripture.split('\n').map((s) => s.trim()).filter(Boolean),
			video_url: editDraft.channel_kind === 'video_timestamp' ? editDraft.video_url : null,
		})
		.then(() => { showEdit.value = false; refresh() })
		.catch((e) => createToast({ title: e.messages?.[0] || __('Could not save.'), icon: 'alert-circle', iconClasses: 'text-red-500' }))
}
function confirmDelete(post) {
	if (window.confirm(__('Delete this post? This cannot be undone.'))) {
		deletePostRes.submit({ post: post.name }).then(() => {
			if (expandedPost.value === post.name) expandedPost.value = null
			refresh()
		})
	}
}
function toggleThread(post) {
	if (expandedPost.value === post.name) { expandedPost.value = null; return }
	expandedPost.value = post.name
	replyTo.value = null
	thread.fetch()
	related.fetch()
}
function plain(html) {
	return (html || '').replace(/<[^>]+>/g, '').slice(0, 60)
}
function setPrayerView(v) {
	prayerView.value = v
	refresh()
}
function openAnswer(post) {
	answerPost.value = post.name
	answerNote.value = ''
	showAnswer.value = true
}
function confirmAnswer() {
	markAnswered.submit({ post: answerPost.value, note: answerNote.value || null }).then(() => {
		showAnswer.value = false
		refresh()
		if (expandedPost.value) thread.fetch()
	})
}
function reopen(post) {
	reopenPrayer.submit({ post: post.name }).then(() => { refresh(); if (expandedPost.value) thread.fetch() })
}
function submitLink(post) {
	if (!linkTarget.value.trim()) return
	linkPost
		.submit({ post: post.name, linked_post: linkTarget.value.trim(), relation_type: 'reflection' })
		.then(() => { linkTarget.value = ''; thread.fetch() })
		.catch((e) => createToast({ title: e.messages?.[0] || __('Could not link.'), icon: 'alert-circle', iconClasses: 'text-red-500' }))
}

// --- moderation ---
const canModerate = computed(() => !!canModerateRes.data)
const showReport = ref(false)
const reportTarget = ref(null)
const reportReason = ref('Inappropriate')
const reportDetail = ref('')
const showModeration = ref(false)

function openReport(doctype, name) {
	reportTarget.value = { doctype, name }
	reportReason.value = 'Inappropriate'
	reportDetail.value = ''
	showReport.value = true
}
function submitReport() {
	flagContent
		.submit({
			target_doctype: reportTarget.value.doctype,
			target_name: reportTarget.value.name,
			reason: reportReason.value,
			detail: reportDetail.value || null,
		})
		.then(() => { showReport.value = false; createToast({ title: __('Reported. Thank you.'), icon: 'check' }) })
		.catch((e) => createToast({ title: e.messages?.[0] || __('Could not report.'), icon: 'alert-circle', iconClasses: 'text-red-500' }))
}
function openModeration() {
	showModeration.value = true
	flagsRes.fetch()
}
function resolveFlag(flag, action) {
	resolveFlagRes.submit({ flag, action }).then(() => { flagsRes.fetch(); refresh() })
}
function moderatePost(post, status) {
	setPostStatusRes.submit({ post: post.name, status }).then(() => refresh())
}

// --- save ---
function toggleSave(post) {
	toggleSaveRes.submit({ post: post.name }).then((r) => { post.saved = r.saved })
}

// --- passage popover (Bible badge click) ---
function openPassage(ref) {
	passageRes.data = null
	showPassage.value = true
	passageRes.submit({ resolved_ref: ref.resolved_ref }).catch(() => {})
}

// --- my cohort ---
function openMembers() {
	showMembers.value = true
	membersRes.fetch({ cohort: selectedCohort.value })
}
function inviteMember() {
	if (!inviteEmail.value.trim()) return
	inviteRes
		.submit({ cohort: selectedCohort.value, email: inviteEmail.value.trim() })
		.then(() => { inviteEmail.value = ''; membersRes.fetch({ cohort: selectedCohort.value }); createToast({ title: __('Invitation sent.'), icon: 'check' }) })
		.catch((e) => createToast({ title: e.messages?.[0] || __('Could not invite.'), icon: 'alert-circle', iconClasses: 'text-red-500' }))
}
function makeLeader(m) {
	if (!window.confirm(__('Make this person the cohort leader?'))) return
	reassignRes.submit({ cohort: selectedCohort.value, new_leader: m.person }).then(() => membersRes.fetch({ cohort: selectedCohort.value }))
}
function openSplit() {
	showMembers.value = false
	splitName.value = ''
	splitMoving.value = []
	splitLeader.value = null
	// everyone except the current leader can be moved to the new cohort
	splitOriginal.value = (membersRes.data?.members || []).filter((m) => !m.is_leader)
	showSplit.value = true
}
function moveToNew(m) {
	splitOriginal.value = splitOriginal.value.filter((x) => x.person !== m.person)
	splitMoving.value = [...splitMoving.value, m]
}
function moveToOriginal(m) {
	splitMoving.value = splitMoving.value.filter((x) => x.person !== m.person)
	splitOriginal.value = [...splitOriginal.value, m]
	if (splitLeader.value === m.person) splitLeader.value = null
}
function submitSplit() {
	if (!splitName.value.trim())
		return createToast({ title: __('Name the new cohort.'), icon: 'alert-circle', iconClasses: 'text-red-500' })
	if (!splitMoving.value.length)
		return createToast({ title: __('Move at least one member.'), icon: 'alert-circle', iconClasses: 'text-red-500' })
	if (!splitLeader.value)
		return createToast({ title: __('Choose a leader for the new cohort.'), icon: 'alert-circle', iconClasses: 'text-red-500' })
	splitRes
		.submit({
			cohort: selectedCohort.value,
			new_cohort_name: splitName.value.trim(),
			member_ids: JSON.stringify(splitMoving.value.map((m) => m.membership)),
			new_leader: splitLeader.value,
		})
		.then(() => { showSplit.value = false; cohortsRes.reload(); refresh(); createToast({ title: __('New cohort created.'), icon: 'check' }) })
		.catch((e) => createToast({ title: e.messages?.[0] || __('Could not split.'), icon: 'alert-circle', iconClasses: 'text-red-500' }))
}

// --- bible tree ---
function fetchTree() {
	expandedBook.value = null
	expandedChapter.value = null
	if (selectedCohort.value) bibleTree.fetch({ cohort: selectedCohort.value })
}
function toggleBook(b) {
	if (expandedBook.value === b.osis) { expandedBook.value = null; return }
	expandedBook.value = b.osis
	expandedChapter.value = null
	chaptersRes.fetch({ cohort: selectedCohort.value, book: b.osis })
	setPassage(b.name, b.start_ord, b.end_ord)
}
function toggleChapter(b, c) {
	if (expandedChapter.value === c.chapter) { expandedChapter.value = null; return }
	expandedChapter.value = c.chapter
	versesRes.fetch({ cohort: selectedCohort.value, book: b.osis, chapter: c.chapter })
	setPassage(`${b.name} ${c.chapter}`, c.start_ord, c.end_ord)
}
function selectVerse(b, c, v) {
	setPassage(`${b.name} ${c.chapter}:${v.verse}`, v.start_ord, v.end_ord)
}
function setPassage(label, start, end) {
	passageFilter.value = { label, start, end }
	passagePostsRes.fetch({ cohort: selectedCohort.value, start_ord: start, end_ord: end })
}
function clearPassage() {
	passageFilter.value = null
	expandedBook.value = null
	expandedChapter.value = null
}
function react(post, rtName) {
	toggleReaction.submit({ reaction_type: rtName, post: post.name }).then(() => {
		feed.fetch()
		if (expandedPost.value) thread.fetch()
	})
}
function submitReply(post) {
	if (!replyText.value.trim()) return
	addComment
		.submit({
			post: post.name,
			content: replyText.value,
			parent_comment: replyTo.value?.name || null,
			is_private: replyPrivate.value ? 1 : 0,
		})
		.then(() => { replyText.value = ''; replyTo.value = null; replyPrivate.value = false; thread.fetch(); feed.fetch() })
}
function openBroadcast() {
	broadcastSubject.value = ''
	broadcastMessage.value = ''
	broadcastEmail.value = false
	showBroadcast.value = true
}
function submitBroadcast() {
	if (!broadcastSubject.value.trim() || !broadcastMessage.value.trim())
		return createToast({ title: __('Subject and message are required.'), icon: 'alert-circle', iconClasses: 'text-red-500' })
	broadcastRes
		.submit({ subject: broadcastSubject.value, message: broadcastMessage.value, email: broadcastEmail.value ? 1 : 0 })
		.then((r) => { showBroadcast.value = false; createToast({ title: __('Sent to {0} leader(s).').format(r.sent), icon: 'check' }) })
		.catch((e) => createToast({ title: e.messages?.[0] || __('Could not send.'), icon: 'alert-circle', iconClasses: 'text-red-500' }))
}
function openCompose() {
	Object.assign(draft, { channel: channelFilter.value || (channels.value[0]?.name || ''), title: '', content: '', visibility: 'cohort_only', direct_recipient: '', topics: '', scripture: '', video_url: '' })
	composeKey.value++ // force the editor to remount with empty content
	showCompose.value = true
}
function submitPost() {
	if (!draft.channel || !draft.content?.trim()) {
		createToast({ title: __('A channel and some content are required.'), icon: 'alert-circle', iconClasses: 'text-red-500' })
		return
	}
	if (composeChannelKind.value === 'video_timestamp' && !draft.video_url?.trim()) {
		createToast({ title: __('Sermon Lab posts need a YouTube link.'), icon: 'alert-circle', iconClasses: 'text-red-500' })
		return
	}
	createPost
		.submit({
			cohort: selectedCohort.value,
			channel: draft.channel,
			title: draft.title || null,
			content: draft.content,
			visibility: draft.visibility,
			direct_recipient: draft.visibility === 'direct' ? draft.direct_recipient : null,
			topics: draft.topics.split(',').map((t) => t.trim()).filter(Boolean),
			scripture: draft.scripture.split('\n').map((s) => s.trim()).filter(Boolean),
			video_url: draft.video_url || null,
		})
		.then(() => { showCompose.value = false; refresh() })
		.catch((e) => createToast({ title: e.messages?.[0] || __('Could not post.'), icon: 'alert-circle', iconClasses: 'text-red-500' }))
}

// --- reactive refetch + realtime ---
watch([selectedCohort, channelFilter], () => { expandedPost.value = null; refresh() })

// debounced search: cohort-scoped, only fires at 2+ chars
let searchTimer = null
watch(searchQuery, (q) => {
	clearTimeout(searchTimer)
	const term = (q || '').trim()
	if (term.length < 2) { searchRes.data = []; return }
	if (passageFilter.value) clearPassage()
	searchTimer = setTimeout(
		() => searchRes.submit({ cohort: selectedCohort.value, query: term }),
		300,
	)
})
watch(selectedCohort, () => { searchQuery.value = '' })

// Mark-on-LEAVE (not on load): the "New" divider baseline stays frozen while you
// read a channel, and only advances when you leave it, switch cohort, or close
// the page — so posts that arrived since your last visit stay flagged new.
function markLeaving(cohort, channel) {
	if (!cohort) return
	markSeen.submit({ cohort, channel: channel || null }).then(() => unreadRes.fetch())
}
// Leaving a specific channel marks just that one seen (its divider resets next
// time). Leaving the cohort or the page marks everything seen — a clean "since
// your last visit" baseline. The "All" view never mass-marks mid-session, so
// its divider survives channel hops.
watch(channelFilter, (nv, ov) => { if (ov) markLeaving(selectedCohort.value, ov) })
watch(selectedCohort, (nv, ov) => { if (ov) markLeaving(ov, null); passageFilter.value = null; fetchTree() })

function onFeedUpdate(data) {
	if (data?.cohort === selectedCohort.value) refresh()
}
onMounted(() => socket && socket.on('cohort_feed_update', onFeedUpdate))
onUnmounted(() => {
	socket && socket.off('cohort_feed_update', onFeedUpdate)
	markLeaving(selectedCohort.value, null)
})
</script>
