# Bible Lookup

SeminaryERP can pull **scripture text on demand** from
[api.bible](https://scripture.api.bible) so that instructors building
scripture-based quiz questions don't have to paste verses by hand. This is an
**optional integration**: leave it off and the rest of the system works exactly
as before; turn it on and questions can resolve a reference like *John 3:16* into
the actual verse text, in the right translation for each student's language.

## What it powers

The lookup feeds the **Scripture Matching** and **Scripture Memorization**
question types (see [Grading](../modules/grading.html#quiz)). When an instructor
enters a reference on one of these questions, the server fetches the verse text
and caches it on the question. The **API key never leaves the server** — the
frontend only ever asks the server to do the lookup, so your credentials stay
private.

References are typed the natural way and converted for you, including common
abbreviations and other languages — for example `Jn 3:16`, `John 3:16-17`,
`1 João 3:1`, or a whole chapter like `Sl 23`. (Cross-chapter ranges and
multi-passage references are not supported; split those into separate
references.)

## Configuring the connection

Open **Bible API Settings** (a single settings record) and fill in:

| Field | What it is |
| --- | --- |
| **Enabled** | Master switch for the integration. |
| **API Key** | Your personal key from api.bible (stored encrypted). |
| **Base URL** | The api.bible endpoint. The default is correct for almost everyone. |
| **Default Bible ID** | The translation to use when no language-specific one applies. |
| **Per-Language Bibles** | A table mapping a **Language** to the **Bible** to use for it. |

To get a key, register a free account at
[scripture.api.bible](https://scripture.api.bible), create an application, and
copy its key into **API Key**. Each translation on api.bible has its own **Bible
ID**; copy the ID of the version you want into **Default Bible ID**.

## Translations per language

A seminary that teaches in more than one language will want each student to see
scripture in their own. Add a row to **Per-Language Bibles** for each language,
choosing the api.bible **Bible ID** for that language's preferred translation.
When a lookup runs, the integration picks the Bible that matches the caller's
language and falls back to the **Default Bible ID** when there is no specific
mapping.

## Day-to-day

Once configured, there is nothing to maintain — instructors simply type
references on scripture questions and the text appears. If lookups stop working,
check that **Enabled** is on and that the **API Key** is still valid on your
api.bible account.

## Related

- [Grading](../modules/grading.html#quiz) — the scripture question types this
  powers.
- [Customization](customization.md) — other institution-level settings.
