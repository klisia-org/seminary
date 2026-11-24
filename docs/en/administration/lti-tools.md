# External Tools (LTI)

SeminaryERP can open outside tools inside a course: publisher textbooks, Bible and language software, video platforms, plagiarism checkers. It uses **LTI 1.3** with the three **LTI Advantage** services:

* **Content selection** (Deep Linking): instructors choose material inside the tool, and each choice becomes a lesson.
* **Class list** (Names and Roles): the tool can read who is in the section and their roles.
* **Grades** (Assignment and Grade Services): the tool can send scores back.

Students open the tool from a lesson and arrive signed in as themselves. They don't need a separate account or password.

## Registering a tool

A tool is registered once for the whole site, by a System Manager or Seminary Manager, under **LTI Tool**.

### By URL

If the tool supports LTI Dynamic Registration, its administrator gives you a registration URL. On the **LTI Tool** list, choose **Register by URL** and paste it. The tool opens in a new window and registers itself. When it is done, the new tool appears in the list.

### By hand

Create an **LTI Tool** and fill in what the tool's administrator gives you:

| Field | What it is |
| --- | --- |
| **Login URL** | Where a launch starts (the tool's OpenID Connect login initiation URL). |
| **Launch URL** | Where a launch lands when a lesson does not name its own URL. |
| **Content selection URL** | Where instructors choose content in the tool. Leave it empty if the tool has none. |
| **Redirect URLs** | One per line. Leave this empty to use the launch and content selection URLs. |
| **Key-set URL** or **Public key** | The tool's public keys. |

When you save, the form shows the **Client ID** and **Deployment ID** this site issued, and this site's endpoints: issuer, authorization URL, token URL, key-set URL and content selection return URL. Send these to the tool's administrator.

### Services and privacy

* **Content selection**, **Class list** and **Grades** switch each service on or off for this tool.
* **Send name** and **Send email** are **off** by default. With them off, the tool knows each person only by an identifier that means nothing outside your site, and a different identifier for every tool. Turn them on only for a tool that needs them, and that your school has agreed may receive students' names or emails.
* **Open in** chooses a new window (the default) or embedded in the lesson. Many tools refuse to be embedded. A student can always open an embedded tool in a new window instead.

## Adding a tool to a course

Instructors who can edit a course have two ways to add a tool:

* **Add from tool**, under a chapter in the course outline. It opens the tool's catalogue in a new window, and each item you choose becomes a lesson at the end of the chapter. When you return to the course, the outline shows them.
* **External tool**, in the lesson editor. Pick the tool, and optionally a launch URL and custom parameters the tool's documentation asks for.

Anything else in the lesson, such as instructions or readings, is shown above the button that opens the tool. The chapter's release dates and prerequisites apply to the tool too.

Students, and teaching staff on the section, can open the tool. Mentors and observers see the lesson but cannot open the tool.

## Grades

Every score a tool sends is kept on the lesson, under **LTI Score**. A score is written to the gradebook only when the lesson is linked to an assessment criterion. Instructors set that link under **Grade passback**, below the tool on the lesson page.

* Only final scores are written. A score the tool is still grading is kept but not written.
* A grade you enter by hand replaces the tool's score, and later scores from the tool never overwrite it.
* When content selection creates a graded item, the lesson gets its own assessment criterion with a weight of 0%. Set its weight before the section can be saved.
* In competency-based sections and sections graded with descriptions, the gradebook holds a level rather than a percentage, so scores stay on the lesson.

## Moving courses

When you import a Common Cartridge or a Moodle backup, LTI links become LTI lessons if a tool on the same host is already registered here. Register the tool first, then import. Links with no matching tool are listed in the import report, with the host to register. Exporting a Common Cartridge writes LTI lessons as LTI links. See [Moving Courses from Another LMS](../getting-started/course-migration).

## Signing keys

The site signs every launch with its own key, published at `/lti/jwks`. A System Manager can rotate the key. The old key stays published for a day, so launches already under way still work.
