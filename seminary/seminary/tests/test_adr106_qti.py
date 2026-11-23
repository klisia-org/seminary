"""decisions/106: options without a limit, and QTI import into quizzes and exams."""

import io
import json
import zipfile

import frappe
from frappe.tests import IntegrationTestCase

from seminary.seminary import qti
from seminary.seminary.doctype.question.question import save_question
from seminary.seminary.doctype.quiz.quiz import check_choice_answers, check_input_answers, choice_is_correct
from seminary.seminary.utils import get_question_details

CANVAS = """<?xml version="1.0" encoding="UTF-8"?>
<questestinterop xmlns="http://www.imsglobal.org/xsd/ims_qtiasiv1p2">
  <assessment ident="a1" title="Week 1">
    <section ident="root_section">
      <item ident="i1" title="Gospels">
        <itemmetadata><qtimetadata>
          <qtimetadatafield><fieldlabel>question_type</fieldlabel><fieldentry>multiple_choice_question</fieldentry></qtimetadatafield>
          <qtimetadatafield><fieldlabel>points_possible</fieldlabel><fieldentry>2.0</fieldentry></qtimetadatafield>
        </qtimetadata></itemmetadata>
        <presentation>
          <material><mattext texttype="text/html">&lt;p&gt;Which is a Gospel? &lt;img src="$IMS-CC-FILEBASE$/Quiz%20Files/map.png"&gt;&lt;/p&gt;</mattext></material>
          <response_lid ident="response1" rcardinality="Single">
            <render_choice>
              <response_label ident="o1"><material><mattext texttype="text/plain">Acts</mattext></material></response_label>
              <response_label ident="o2"><material><mattext texttype="text/plain">Romans</mattext></material></response_label>
              <response_label ident="o3"><material><mattext texttype="text/plain">Hebrews</mattext></material></response_label>
              <response_label ident="o4"><material><mattext texttype="text/plain">James</mattext></material></response_label>
              <response_label ident="o5"><material><mattext texttype="text/plain">Jude</mattext></material></response_label>
              <response_label ident="o6"><material><mattext texttype="text/plain">Mark</mattext></material></response_label>
            </render_choice>
          </response_lid>
        </presentation>
        <resprocessing>
          <outcomes><decvar maxvalue="100" minvalue="0" varname="SCORE" vartype="Decimal"/></outcomes>
          <respcondition continue="No">
            <conditionvar><varequal respident="response1">o6</varequal></conditionvar>
            <setvar action="Set" varname="SCORE">100</setvar>
          </respcondition>
        </resprocessing>
      </item>
      <item ident="i2" title="Paul">
        <itemmetadata><qtimetadata>
          <qtimetadatafield><fieldlabel>question_type</fieldlabel><fieldentry>multiple_answers_question</fieldentry></qtimetadatafield>
        </qtimetadata></itemmetadata>
        <presentation>
          <material><mattext texttype="text/html">&lt;p&gt;Letters by Paul&lt;/p&gt;</mattext></material>
          <response_lid ident="response1" rcardinality="Multiple">
            <render_choice>
              <response_label ident="a"><material><mattext>Romans</mattext></material></response_label>
              <response_label ident="b"><material><mattext>Galatians</mattext></material></response_label>
              <response_label ident="c"><material><mattext>Jude</mattext></material></response_label>
            </render_choice>
          </response_lid>
        </presentation>
        <resprocessing>
          <respcondition continue="No">
            <conditionvar><and>
              <varequal respident="response1">a</varequal>
              <varequal respident="response1">b</varequal>
              <not><varequal respident="response1">c</varequal></not>
            </and></conditionvar>
            <setvar action="Set" varname="SCORE">100</setvar>
          </respcondition>
        </resprocessing>
      </item>
      <item ident="i3" title="Capital">
        <itemmetadata><qtimetadata>
          <qtimetadatafield><fieldlabel>question_type</fieldlabel><fieldentry>short_answer_question</fieldentry></qtimetadatafield>
        </qtimetadata></itemmetadata>
        <presentation>
          <material><mattext texttype="text/html">&lt;p&gt;Where was the temple?&lt;/p&gt;</mattext></material>
          <response_str ident="response1" rcardinality="Single"><render_fib><response_label ident="answer1" rshuffle="No"/></render_fib></response_str>
        </presentation>
        <resprocessing>
          <respcondition continue="No">
            <conditionvar>
              <varequal respident="response1">Jerusalem</varequal>
              <varequal respident="response1">Zion</varequal>
            </conditionvar>
            <setvar action="Set" varname="SCORE">100</setvar>
          </respcondition>
        </resprocessing>
      </item>
      <item ident="i4" title="Reflect">
        <itemmetadata><qtimetadata>
          <qtimetadatafield><fieldlabel>question_type</fieldlabel><fieldentry>essay_question</fieldentry></qtimetadatafield>
          <qtimetadatafield><fieldlabel>points_possible</fieldlabel><fieldentry>10</fieldentry></qtimetadatafield>
        </qtimetadata></itemmetadata>
        <presentation>
          <material><mattext texttype="text/html">&lt;p&gt;Describe grace.&lt;/p&gt;</mattext></material>
          <response_str ident="response1" rcardinality="Single"><render_fib><response_label ident="answer1"/></render_fib></response_str>
        </presentation>
        <resprocessing><respcondition continue="No"><conditionvar><other/></conditionvar></respcondition></resprocessing>
      </item>
      <item ident="i5" title="Pairs">
        <itemmetadata><qtimetadata>
          <qtimetadatafield><fieldlabel>question_type</fieldlabel><fieldentry>matching_question</fieldentry></qtimetadatafield>
        </qtimetadata></itemmetadata>
        <presentation><material><mattext>Match</mattext></material></presentation>
      </item>
    </section>
  </assessment>
</questestinterop>
"""

QTI21_CHOICE = """<?xml version="1.0" encoding="UTF-8"?>
<assessmentItem xmlns="http://www.imsglobal.org/xsd/imsqti_v2p1" identifier="q1" title="Exodus">
  <responseDeclaration identifier="RESPONSE" cardinality="single" baseType="identifier">
    <correctResponse><value>B</value></correctResponse>
  </responseDeclaration>
  <outcomeDeclaration identifier="SCORE" cardinality="single" baseType="float" normalMaximum="3"/>
  <itemBody>
    <p>Who led Israel out of Egypt?</p>
    <choiceInteraction responseIdentifier="RESPONSE" shuffle="false" maxChoices="1">
      <simpleChoice identifier="A">Aaron</simpleChoice>
      <simpleChoice identifier="B">Moses</simpleChoice>
      <simpleChoice identifier="C">Joshua</simpleChoice>
    </choiceInteraction>
  </itemBody>
</assessmentItem>
"""

QTI21_BLANK = """<?xml version="1.0" encoding="UTF-8"?>
<assessmentItem xmlns="http://www.imsglobal.org/xsd/imsqti_v2p1" identifier="q2" title="Blank">
  <responseDeclaration identifier="RESPONSE" cardinality="single" baseType="string">
    <correctResponse><value>Bethlehem</value></correctResponse>
  </responseDeclaration>
  <itemBody><p>Jesus was born in <textEntryInteraction responseIdentifier="RESPONSE"/> of Judea.</p></itemBody>
</assessmentItem>
"""

PNG = (
	b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4"
	b"\x89\x00\x00\x00\rIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
)


def _zip(files):
	buf = io.BytesIO()
	with zipfile.ZipFile(buf, "w") as z:
		for name, content in files.items():
			z.writestr(name, content)
	return buf.getvalue()


def _quiz():
	quiz = frappe.new_doc("Quiz")
	quiz.title = f"QTI-{frappe.generate_hash(length=8)}"
	quiz.standalone = 1
	quiz.passing_percentage = 50
	quiz.insert(ignore_permissions=True, ignore_mandatory=True)
	return quiz


def _exam():
	exam = frappe.new_doc("Exam Activity")
	exam.title = f"QTI-{frappe.generate_hash(length=8)}"
	exam.flags.ignore_mandatory = True
	exam.insert(ignore_permissions=True, ignore_mandatory=True)
	return exam


def _choice(n, correct):
	q = frappe.new_doc("Question")
	q.question = f"QL-{frappe.generate_hash(length=8)}"
	q.type = "Choices"
	for i in range(1, n + 1):
		q.append("choices", {"option": f"opt {i}", "is_correct": 1 if i in correct else 0})
	q.insert(ignore_permissions=True)
	return q


class TestADR106Options(IntegrationTestCase):
	def test_more_than_four_options_grade(self):
		q = _choice(7, {7})
		self.assertEqual(choice_is_correct(q.name, ["opt 7"]), 1)
		self.assertEqual(choice_is_correct(q.name, ["opt 1"]), 0)
		self.assertEqual(check_choice_answers(q.name, ["opt 1"]), [0, 0, 0, 0, 0, 0, 2])

	def test_more_than_four_accepted_answers(self):
		q = frappe.new_doc("Question")
		q.question = f"QA-{frappe.generate_hash(length=8)}"
		q.type = "User Input"
		for a in ("one", "two", "three", "four", "fifth answer"):
			q.append("accepted_answers", {"answer": a})
		q.insert(ignore_permissions=True)
		self.assertEqual(check_input_answers(q.name, "fifth answer"), 1)

	def test_blank_rows_are_dropped_and_two_options_needed(self):
		q = _choice(2, {1})
		q.append("choices", {"option": "  "})
		q.save()
		self.assertEqual(len(q.choices), 2)
		q.choices = q.choices[:1]
		with self.assertRaises(frappe.ValidationError):
			q.save()

	def test_save_question_replaces_the_rows(self):
		q = _choice(2, {1})
		save_question(
			q.name,
			json.dumps(
				{
					"question": "Edited",
					"choices": [
						{"option": "a", "is_correct": 0},
						{"option": "b", "is_correct": 1, "explanation": "why"},
						{"option": "c", "is_correct": 1},
						{"option": "d"},
						{"option": "e"},
					],
				}
			),
		)
		q.reload()
		self.assertEqual([c.option for c in q.choices], ["a", "b", "c", "d", "e"])
		self.assertEqual(q.multiple, 1)
		self.assertEqual(q.choices[1].explanation, "why")

	def test_payload_lists_options_without_the_key(self):
		q = _choice(5, {5})
		d = get_question_details(q.name)  # as Administrator, a grader
		self.assertEqual([o["option"] for o in d["options"]], [f"opt {i}" for i in range(1, 6)])
		self.assertTrue(all("is_correct" not in o for o in d["options"]))

	def test_patch_moves_the_old_slots(self):
		if "option_1" not in frappe.db.get_table_columns("Question"):
			self.skipTest("this site never had the old columns")
		from seminary.seminary.patches import adr106_question_rows

		q = frappe.new_doc("Question")
		q.question = f"QP-{frappe.generate_hash(length=8)}"
		q.type = "Reading Report"
		q.pages_total = 1
		q.insert(ignore_permissions=True)
		frappe.db.sql(
			"""update `tabQuestion` set type='Choices', option_1='Yes', is_correct_1=1, explanation_1='e',
			option_2=' No ', option_3='', possibility_1='p' where name=%s""",
			q.name,
		)
		adr106_question_rows.execute()
		adr106_question_rows.execute()  # a second run adds nothing
		q.reload()
		self.assertEqual(
			[(c.option, c.is_correct, c.explanation) for c in q.choices], [("Yes", 1, "e"), (" No ", 0, None)]
		)
		self.assertEqual([a.answer for a in q.accepted_answers], ["p"])


class TestADR106QTI(IntegrationTestCase):
	def test_canvas_package_into_a_quiz(self):
		quiz = _quiz()
		package = qti.Package(
			_zip(
				{
					"g1/g1.xml": CANVAS,
					"web_resources/Quiz Files/map.png": PNG,
					"imsmanifest.xml": "<manifest/>",
				}
			),
			"export.zip",
		)
		report = qti.import_into(quiz, package)
		self.assertEqual(report["created"], 3)
		self.assertEqual(
			{(s["title"], s["reason"]) for s in report["skipped"]},
			{("Reflect", "essay; import it into an exam"), ("Pairs", "matching")},
		)
		quiz.reload()
		self.assertEqual([r.points for r in quiz.questions], [2, 1, 1])
		six = frappe.get_doc("Question", quiz.questions[0].question)
		self.assertEqual(len(six.choices), 6)
		self.assertEqual([c.option for c in six.choices if c.is_correct], ["Mark"])
		self.assertIn("/private/files/", six.question)
		self.assertTrue(
			frappe.db.exists(
				"File", {"attached_to_doctype": "Quiz", "attached_to_name": quiz.name, "is_private": 1}
			)
		)
		paul = frappe.get_doc("Question", quiz.questions[1].question)
		self.assertEqual([c.option for c in paul.choices if c.is_correct], ["Romans", "Galatians"])
		self.assertEqual(paul.multiple, 1)
		short = frappe.get_doc("Question", quiz.questions[2].question)
		self.assertEqual(short.type, "User Input")
		self.assertEqual(sorted(a.answer for a in short.accepted_answers), ["Jerusalem", "Zion"])

	def test_essays_go_into_an_exam(self):
		exam = _exam()
		report = qti.import_into(exam, qti.Package(CANVAS.encode(), "quiz.xml"))
		self.assertEqual(report["created"], 1)
		exam.reload()
		self.assertEqual(exam.questions[0].points, 10)
		self.assertIn(
			"Describe grace", frappe.db.get_value("Open Question", exam.questions[0].question, "question")
		)

	def test_qti21_items(self):
		quiz = _quiz()
		report = qti.import_into(
			quiz, qti.Package(_zip({"q1.xml": QTI21_CHOICE, "q2.xml": QTI21_BLANK}), "p.zip")
		)
		self.assertEqual(report["created"], 2)
		quiz.reload()
		moses = frappe.get_doc("Question", quiz.questions[0].question)
		self.assertEqual([c.option for c in moses.choices if c.is_correct], ["Moses"])
		self.assertEqual(quiz.questions[0].points, 3)
		blank = frappe.get_doc("Question", quiz.questions[1].question)
		self.assertIn("born in _____ of Judea", blank.question)
		self.assertEqual([a.answer for a in blank.accepted_answers], ["Bethlehem"])

	def test_entity_expansion_is_refused(self):
		bomb = '<?xml version="1.0"?><!DOCTYPE x [<!ENTITY a "aaaa">]><questestinterop>&a;</questestinterop>'
		with self.assertRaises(frappe.ValidationError):
			qti.parse(qti.Package(bomb.encode(), "x.xml"))

	def test_only_the_uploader_may_import_a_file(self):
		quiz = _quiz()
		f = frappe.get_doc(
			{"doctype": "File", "file_name": "q.xml", "content": QTI21_CHOICE.encode(), "is_private": 1}
		)
		f.insert(ignore_permissions=True)
		frappe.db.set_value("File", f.name, "owner", "Guest")
		with self.assertRaises(frappe.PermissionError):
			qti.import_questions("Quiz", quiz.name, f.file_url)
		with self.assertRaises(frappe.ValidationError):
			qti.import_questions("User", "Administrator", f.file_url)
