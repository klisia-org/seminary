# Moving Courses from Another LMS

You can bring a course over from Canvas, Moodle, Blackboard, Brightspace or Schoology in one upload. The course arrives as ordinary chapters, lessons, quizzes, assignments and discussions, and you can edit all of them. Programs and courses from Populi come in as spreadsheets instead (see [From Populi](#from-populi)).

## What you need

* A **Common Cartridge** (`.imscc`) exported from Canvas, Blackboard, Brightspace, Schoology or Moodle, **or**
* a **Moodle backup** (`.mbz`) from Moodle 5.0, 5.1, 5.2 or 5.3. Backups from other Moodle releases are refused. If your Moodle is older, upgrade it first or export a Common Cartridge instead.
* A **Course Schedule** (a section) for the course, in **Draft** or **Open for Enrollment**, with no chapters and no grades yet. You need the Program Chair, Seminary Manager or Registrar role.

In Canvas, export from **Settings → Export Course Content → Course**. In Moodle, make a course backup *without users*, then download the `.mbz` file.

## Importing

1. Open the Course Schedule.
2. Choose **Actions → Import Course from Another LMS**.
3. Upload the `.imscc` or `.mbz` file.

When the import finishes, a report lists what was created and every item that could not be imported, with the reason. The same summary is added to the section's comments.

## What comes across

| From the other LMS | Becomes |
| --- | --- |
| Modules (Canvas) or sections (Moodle) | Chapters |
| Pages, Moodle books and labels | Lessons, with headings, paragraphs, lists, tables, images and embedded videos |
| Files and links | Lessons that show the file or link |
| Files no page uses | The course folder **Imported files** |
| Quizzes | Quizzes: multiple choice, multiple answer, true/false, short answer and fill-in-the-blank questions |
| Essay questions in a quiz | An exam beside the quiz, named after it |
| Assignments | Assignments, with the Canvas rubric when there is one |
| Discussions and Moodle forums | Discussions, with the prompt but no posts |

Every graded quiz, exam and assignment gets a row under **Assessment Criteria** with a weight of 0%.

## What you rebuild by hand

These things never come across. Plan time for them before the term starts.

* **Weights and categories.** Set each assessment's weight. Until the weights add up to 100%, the section cannot be saved.
* **Due dates, release dates and prerequisites.**
* **Groups.**
* **External tools (LTI)**, such as publisher content or video platforms.
* **SCORM packages.** Add them as SCORM chapters again.
* **H5P content**, and Moodle workshops, lessons, glossaries, choices and wikis.
* **Question types seminary does not have:** matching, numeric, several drop-downs or blanks, ordering, hot spot, file upload, and Moodle random questions.
* **Rubrics from anywhere except Canvas.** Canvas rubrics are mapped onto your default rubric scale. Check each one.
* **Student work and grades.** These belong to the student's record, not the course. To bring past grades, see [Legacy Grade Import](./legacy-grade-import).
* **The Moodle announcements forum.** It is left out on purpose.

## Taking a course out

**Actions → Export Common Cartridge** downloads the section as a Common Cartridge 1.3, which Canvas, Moodle, Blackboard and Brightspace can import. Quizzes are written as QTI 1.2, and their questions are also written as QTI 2.1 items. Rubrics, weights, release rules, oral activities, SCORM chapters and competencies are not carried, and the section's comments list anything else that was left out.

To copy a course to another SeminaryERP site, use **Export Course Pack** instead, which carries everything.

## From Populi

Populi holds programs and courses, not course content, so there is no file to upload. Bring them in with **Data Import**:

1. Export your programs and your course catalog from Populi as spreadsheets.
2. Download the templates: [programs](/assets/seminary/migration/populi-programs.csv) and [courses](/assets/seminary/migration/populi-courses.csv).
3. Copy the Populi columns into the template: the program name and abbreviation; the course name, course number (into **Course Code**) and credits. Every course needs a **Default Grading Scale**: use the name of one of your grading scales.
4. In SeminaryERP, open **Data Import**, choose **Program** or **Course**, and upload the filled template. Import programs before courses.

Past enrollments and grades come in through [Legacy Grade Import](./legacy-grade-import).
