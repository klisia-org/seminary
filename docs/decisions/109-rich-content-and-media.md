# 109 — Rich content and media

**Date:** 2026-11-23
**Status:** Accepted 2026-11-23; implemented 2026-11-23
**Delivers:** LMS-CRS-04 (Yes)
**Related:** 040 (upload limits), 102 (accessibility: captions, content check), p008 (HTML policy)

## Context

Lessons and the rich-text editors already cover most of what this row asks for, but four things
fall short:

- The rich-text editor's "/Embed" makes an `<iframe>`, and both the save sanitiser and the display
  sanitiser remove it. The embed is lost without a warning.
- The upload picker offers any audio or video file, then refuses all but mp4, mov, mp3 and three
  image types, saying only images and video are allowed. An m4a recording can't be added.
- Lessons keep a change history, but only Desk shows it, as raw block data.
- No text is marked right to left, so a Hebrew passage in an English lesson is laid out wrongly.

A video in rich text can't keep captions either: the save sanitiser removes `<track>`. The content
check still warns about it, but the instructor has no way to fix it.

## Decision

1. **Rich-text embeds are saved as a link, and built into a frame when shown.** The editor saves an
   embed as `<figure data-embed="URL"><a href="URL">title</a></figure>`, which both sanitisers keep.
   On save the server drops `data-embed` from any URL that `safe_embed_url` refuses. When the page
   is shown, `SafeHtml` builds the iframe itself from a URL that passes `safeEmbedUrl`, the check
   the lesson iframe block uses. The frame gets the link's text as its title, and the same sandbox
   as that block. Where frames aren't built (email, PDF, feeds) the link remains. The insert dialog
   asks for a title. Nothing needs migrating, because earlier embeds never got saved.
2. **One list of media types.** The picker and the upload block share one list of the types that
   browsers play:
   - video: mp4, m4v, webm, mov and ogv;
   - audio: mp3, m4a, aac, wav, ogg, oga, opus and flac.

   mkv and avi are dropped, because browsers don't reliably play them. The picker offers only the
   types on the list, plus images and PDF. Only images are shown as images. Any other file already
   in a lesson, mkv and avi included, shows as a download link with its name.
3. **Lesson history in the lesson editor.** A History panel lists the saved versions of the
   lesson's content and instructor notes, with who saved each one and when. It reads Frappe's
   Version rows. A version opens read-only, and *Restore* loads it into the editor. Saving the
   restore makes it a new version, so a restore can itself be undone. Anyone who can edit the
   lesson can use History.
4. **Text direction follows the text.** Paragraphs, headings, list items, quotes and table cells
   get `dir="auto"`:
   - in lesson blocks, while editing and when shown;
   - in the rich-text editor, which saves the attribute with the HTML.

   A Hebrew line then reads right to left inside English content, and the other way round. Turning
   the whole interface right to left for an RTL language is not part of this decision.
5. **Rich-text videos take captions the way lesson videos do.** Each caption is a language and a
   WebVTT file (102 §6). In rich text they belong to the video itself, because rich text has no
   lesson to hold a Captions table:
   - the editor's video gets a *Captions* button, which uploads a file per language;
   - the saved `<video>` lists the captions in a `data-captions` attribute, which the sanitisers
     keep;
   - `SafeHtml` turns each caption into a `<track>`, but only for a file on this site.

   The content check counts a video as captioned when it lists at least one caption.

## Consequences

Embeds in rich text work, and are checked in the same way as lesson embeds. A file type outside the
list, mkv and avi included, must be converted before it is uploaded. A video in rich text can now
pass the caption check. A restore adds a version and never deletes one.
Content that mixes directions can still need a manual fix when a line starts in the other
script.

## As built

- `content_safety.clean_rich` checks `data-embed` with `safe_embed_url`. `utils/embed.js` builds
  the frames and caption tracks after `sanitize()` has cleaned rich text, and adds `dir="auto"` to
  text saved before the editor did.
- frappe-ui's TextEditor has its iframe and video nodes replaced by `utils/richEditorNodes.js`. Its
  embed dialog is patched in `overrides/frappe-ui/InsertIframe.vue`. The node replacement is
  opt-in in `frappe-ui-overrides.js` (`richMedia: true`), because another portal using the overrides
  shows HTML its own way. Text direction comes with the embed node, the one node every editor has.
- `utils/mediaTypes.js` holds the list. The upload block, its picker, the content check and the
  lesson icon use it.
- `CaptionsEditor.vue` is shared by the lesson's Captions section and the rich-text video.
- `lesson_history.py` lists editing sessions, not single saves, because the editor autosaves.
  Saves by one person less than 15 minutes apart are one session, up to 30 minutes long.
- The editor autosaved a version every 10 seconds, even with no edit: EditorJS stamps a new
  `time` on each save, and the caret's empty last line was saved too. One demo lesson had 1,096
  versions from one day. The editor now saves neither, so an unchanged lesson writes no version.
- First browser pass, in the Announcement dialog:
  - The / menu showed but couldn't be clicked. frappe-ui attaches it to `<body>`, where a modal
    dialog turns clicks off. `overrides/frappe-ui/createSuggestionExtension.js` attaches it inside
    the open dialog, for mentions and emoji too, in every portal.
  - The editable area was one line tall inside its frame. The editors now give it
    `editorClass()`, and the frame shows the focus.
  - A video upload showed nothing until it finished. A video is now a placeholder with its
    progress until it is in. Editor uploads go through `utils/editorUpload.js` (object storage
    where the site has it), which checks the size first.
