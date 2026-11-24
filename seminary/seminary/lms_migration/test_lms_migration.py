"""Course migration from another LMS (decisions/108).

The fixtures are built here, in the shapes Canvas's Common Cartridge exporter
and Moodle's backup writer produce (element names checked against their source,
2026-11-23). They are synthetic: real exports should be added as fixtures when a
school sends one."""

import html
import io
import json
import tarfile
import zipfile

import frappe
from frappe.tests.utils import FrappeTestCase

from seminary.seminary.course_pack.editorjs import scan_content_refs
from seminary.seminary.course_pack.test_course_pack import _any_academic_term, _ensure

from . import html_blocks
from .export_cc import build_cartridge_bytes
from .importer import import_into

PNG = (
	b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4"
	b"\x89\x00\x00\x00\rIDATx\x9cc\xf8\xcf\xc0\xf0\x1f\x00\x05\x00\x01\xff\x89\x99=\x1d\x00\x00\x00\x00IEND"
	b"\xaeB`\x82"
)
CANVAS = "http://canvas.instructure.com/xsd/cccv1p0"
PUBLISHER = "https://publisher.lti-test.example"


class TestHtmlBlocks(FrappeTestCase):
	def test_blocks(self):
		blocks, missing = html_blocks.to_blocks(
			"<h1>Title</h1><p>Some <b>bold</b> <span>text</span> <a href='javascript:x'>bad</a>"
			"<a href='https://e.org'>ok</a></p><ul><li>one<ul><li>inner</li></ul></li></ul>"
			"<p><img src='pic.png' alt='A pic'></p><table><tr><th>h</th></tr><tr><td>c</td></tr></table>"
			"<script>alert(1)</script><p><img src='gone.png'></p><iframe src='https://www.youtube.com/embed/x'></iframe>",
			lambda src: "/private/files/p.png" if src == "pic.png" else None,
		)
		types = [b["type"] for b in blocks]
		self.assertEqual(types, ["header", "paragraph", "list", "image", "table", "iframe"])
		para = blocks[1]["data"]["text"]
		self.assertIn("<b>bold</b>", para)
		self.assertNotIn("javascript", para)
		self.assertIn('href="https://e.org"', para)
		self.assertEqual(blocks[2]["data"]["items"][0]["items"][0]["content"], "inner")
		self.assertEqual(blocks[3]["data"]["url"], "/private/files/p.png")
		self.assertTrue(blocks[4]["data"]["withHeadings"])
		self.assertEqual(missing, ["gone.png"])
		self.assertNotIn("alert", json.dumps(blocks))


class MigrationCase(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.term = _any_academic_term()
		cls.scale = _ensure(
			"Grading Scale",
			{"grading_scale_name": "MIG Test Scale", "grscale_type": "Points", "maxnumgrade": 100},
			child={"intervals": [{"grade_code": "A", "threshold": 0, "grade_pass": "Pass"}]},  # nosec B105 - a grade label
		)
		cls.course = _ensure(
			"Course",
			{"course_name": "MIG Test Course", "coursecode": "MIG101", "default_grading_scale": cls.scale},
		)
		if not frappe.db.exists("Rubric Scale", "MIG Scale"):
			frappe.get_doc(
				{
					"doctype": "Rubric Scale",
					"scale_name": "MIG Scale",
					"enabled": 1,
					"levels": [
						{"label": "Exemplary", "percent": 100, "meets_expectations": 1},
						{"label": "Developing", "percent": 50},
						{"label": "Beginning", "percent": 0},
					],
				}
			).insert(ignore_permissions=True)

	def new_cs(self):
		dates = frappe.db.get_value(
			"Academic Term", self.term, ["term_start_date", "term_end_date"], as_dict=True
		)
		cs = frappe.get_doc(
			{
				"doctype": "Course Schedule",
				"course": self.course,
				"academic_term": self.term,
				"section": frappe.generate_hash(length=6),
				"gradesc_cs": self.scale,
				"modality": "Virtual",
				"c_datestart": dates.term_start_date or frappe.utils.nowdate(),
				"c_dateend": dates.term_end_date or frappe.utils.nowdate(),
			}
		)
		cs.insert(ignore_permissions=True, ignore_mandatory=True)
		frappe.db.set_value("Course Schedule", cs.name, "workflow_state", "Draft")
		return cs.name

	def lessons(self, cs):
		out = []
		for ch in frappe.get_all(
			"Course Schedule Chapter Reference", {"parent": cs}, pluck="chapter", order_by="idx asc"
		):
			title = frappe.db.get_value("Course Schedule Chapter", ch, "chapter_title")
			for lesson in frappe.get_all(
				"Course Schedule Lesson Reference", {"parent": ch}, pluck="lesson", order_by="idx asc"
			):
				out.append((title, frappe.get_doc("Course Lesson", lesson)))
		return out


# --- a Canvas cartridge --------------------------------------------------------------------


def _qti_item(ident, qtype, text, choices=None, correct=None, points=1, essay=False):
	meta = (
		"<itemmetadata><qtimetadata>"
		f"<qtimetadatafield><fieldlabel>question_type</fieldlabel><fieldentry>{qtype}</fieldentry></qtimetadatafield>"
		f"<qtimetadatafield><fieldlabel>points_possible</fieldlabel><fieldentry>{points}</fieldentry></qtimetadatafield>"
		"</qtimetadata></itemmetadata>"
	)
	material = f'<material><mattext texttype="text/html">{html.escape(text)}</mattext></material>'
	if essay:
		resp = '<response_str ident="response1" rcardinality="Single"><render_fib/></response_str>'
		return f'<item ident="{ident}" title="{ident}">{meta}<presentation>{material}{resp}</presentation></item>'
	labels = "".join(
		f'<response_label ident="{i}"><material><mattext texttype="text/plain">{c}</mattext></material></response_label>'
		for i, c in choices
	)
	return (
		f'<item ident="{ident}" title="{ident}">{meta}<presentation>{material}'
		f'<response_lid ident="response1" rcardinality="Single"><render_choice>{labels}</render_choice></response_lid>'
		'</presentation><resprocessing><respcondition continue="No"><conditionvar>'
		f'<varequal respident="response1">{correct}</varequal></conditionvar>'
		'<setvar varname="SCORE" action="Set">100</setvar></respcondition></resprocessing></item>'
	)


def canvas_cartridge():
	f = {}
	f["course_settings/course_settings.xml"] = (
		f'<course xmlns="{CANVAS}" identifier="c1"><title>Old Testament Survey</title>'
		"<course_code>OT501</course_code></course>"
	)
	f["course_settings/rubrics.xml"] = (
		f'<rubrics xmlns="{CANVAS}"><rubric identifier="rub1"><title>Essay rubric</title><criteria>'
		"<criterion><criterion_id>c1</criterion_id><points>10</points><description>Argument</description>"
		"<long_description>Clear thesis</long_description><ratings>"
		"<rating><description>Full marks</description><points>10</points></rating>"
		"<rating><description>Half</description><points>5</points></rating>"
		"<rating><description>None</description><points>0</points></rating></ratings></criterion>"
		"<criterion><criterion_id>c2</criterion_id><points>5</points><description>Sources</description>"
		"<ratings><rating><description>Good</description><points>5</points></rating></ratings></criterion>"
		"</criteria></rubric></rubrics>"
	)
	f["wiki_content/welcome.html"] = (
		"<html><head><title>Welcome</title></head><body><h2>Welcome</h2>"
		'<p>Read <a href="$WIKI_REFERENCE$/pages/syllabus">the syllabus</a>.</p>'
		'<p><img src="$IMS-CC-FILEBASE$/images/map%20one.png" alt="Map"></p></body></html>'
	)
	f["wiki_content/orphan.html"] = "<html><body><p>Not in any module.</p></body></html>"
	f["web_resources/images/map one.png"] = PNG
	f["web_resources/handouts/unused.pdf"] = b"%PDF-1.4 unused"
	f["web_resources/handouts/notes.txt"] = b"Reading notes"
	f["wl1.xml"] = (
		'<webLink xmlns="http://www.imsglobal.org/xsd/imsccv1p1/imswl_v1p1"><title>Bible Gateway</title>'
		'<url href="https://www.biblegateway.com/"/></webLink>'
	)
	f["q1/assessment_qti.xml"] = "<questestinterop><assessment ident='q1' title='Quiz 1'/></questestinterop>"
	f["q1/assessment_meta.xml"] = (
		f'<quiz xmlns="{CANVAS}" identifier="q1"><title>Quiz 1</title><shuffle_answers>true</shuffle_answers>'
		"<scoring_policy>keep_latest</scoring_policy><quiz_type>assignment</quiz_type>"
		"<time_limit>30</time_limit><allowed_attempts>2</allowed_attempts></quiz>"
	)
	f["non_cc_assessments/q1.xml.qti"] = (
		'<questestinterop xmlns="http://www.imsglobal.org/xsd/ims_qtiasiv1p2">'
		'<assessment ident="q1" title="Quiz 1"><section ident="root_section">'
		+ _qti_item(
			"i1",
			"multiple_choice_question",
			"<p>First book?</p>",
			[("a", "Genesis"), ("b", "Exodus")],
			"a",
			2,
		)
		+ _qti_item("i2", "essay_question", "<p>Discuss the covenant.</p>", essay=True, points=5)
		+ _qti_item("i3", "matching_question", "<p>Match</p>", [("a", "x"), ("b", "y")], "a")
		+ "</section></assessment></questestinterop>"
	)
	f["a1/essay.html"] = "<html><body><p>Write <i>two</i> pages.</p></body></html>"
	f["a1/assignment_settings.xml"] = (
		f'<assignment xmlns="{CANVAS}" identifier="a1"><title>Essay</title><points_possible>15</points_possible>'
		"<grading_type>points</grading_type><submission_types>online_upload</submission_types>"
		"<rubric_identifierref>rub1</rubric_identifierref></assignment>"
	)
	f["d1.xml"] = (
		'<topic xmlns="http://www.imsglobal.org/xsd/imsccv1p1/imsdt_v1p1"><title>Introductions</title>'
		'<text texttype="text/html">&lt;p&gt;Say hello.&lt;/p&gt;</text></topic>'
	)
	f["d1meta.xml"] = (
		f'<topicMeta xmlns="{CANVAS}" identifier="d1meta"><title>Introductions</title><type>topic</type>'
		"<assignment identifier='x'><points_possible>5</points_possible></assignment></topicMeta>"
	)
	f["n1.xml"] = (
		'<topic xmlns="http://www.imsglobal.org/xsd/imsccv1p1/imsdt_v1p1"><title>Welcome notice</title>'
		'<text texttype="text/html">hi</text></topic>'
	)
	f["n1meta.xml"] = f'<topicMeta xmlns="{CANVAS}" identifier="n1meta"><type>announcement</type></topicMeta>'
	resources = [
		'<resource identifier="r_welcome" type="webcontent" href="wiki_content/welcome.html"><file href="wiki_content/welcome.html"/></resource>',
		'<resource identifier="r_orphan" type="webcontent" href="wiki_content/orphan.html"><file href="wiki_content/orphan.html"/></resource>',
		'<resource identifier="r_map" type="webcontent" href="web_resources/images/map one.png"><file href="web_resources/images/map one.png"/></resource>',
		'<resource identifier="r_wl" type="imswl_xmlv1p1"><file href="wl1.xml"/></resource>',
		'<resource identifier="q1" type="imsqti_xmlv1p2/imscc_xmlv1p1/assessment"><file href="q1/assessment_qti.xml"/><dependency identifierref="canvas_q1"/></resource>',
		'<resource identifier="canvas_q1" type="associatedcontent/imscc_xmlv1p1/learning-application-resource" href="q1/assessment_meta.xml"><file href="q1/assessment_meta.xml"/><file href="non_cc_assessments/q1.xml.qti"/></resource>',
		'<resource identifier="a1" type="associatedcontent/imscc_xmlv1p1/learning-application-resource" href="a1/essay.html"><file href="a1/essay.html"/><file href="a1/assignment_settings.xml"/></resource>',
		'<resource identifier="d1" type="imsdt_xmlv1p1"><file href="d1.xml"/><dependency identifierref="d1meta"/></resource>',
		'<resource identifier="d1meta" type="associatedcontent/imscc_xmlv1p1/learning-application-resource" href="d1meta.xml"><file href="d1meta.xml"/></resource>',
		'<resource identifier="n1" type="imsdt_xmlv1p1"><file href="n1.xml"/><dependency identifierref="n1meta"/></resource>',
		'<resource identifier="n1meta" type="associatedcontent/imscc_xmlv1p1/learning-application-resource" href="n1meta.xml"><file href="n1meta.xml"/></resource>',
		'<resource identifier="lti1" type="imsbasiclti_xmlv1p0"><file href="lti1.xml"/></resource>',
	]
	items = (
		'<item identifier="m1"><title>Week 1</title>'
		'<item identifier="h1"><title>Readings</title></item>'
		'<item identifier="i1" identifierref="r_welcome"><title>Welcome</title></item>'
		'<item identifier="i2" identifierref="r_wl"><title>Bible Gateway</title></item>'
		'<item identifier="i3" identifierref="q1"><title>Quiz 1</title></item>'
		"</item>"
		'<item identifier="m2"><title>Week 2</title>'
		'<item identifier="i4" identifierref="a1"><title>Essay</title></item>'
		'<item identifier="i5" identifierref="d1"><title>Introductions</title></item>'
		'<item identifier="i6" identifierref="lti1"><title>Publisher tool</title></item>'
		"</item>"
	)
	f["lti1.xml"] = (
		'<cartridge_basiclti_link xmlns="http://www.imsglobal.org/xsd/imslticc_v1p0" '
		'xmlns:blti="http://www.imsglobal.org/xsd/imsbasiclti_v1p0" xmlns:lticm="http://www.imsglobal.org/xsd/imslticm_v1p0">'
		"<blti:title>Publisher tool</blti:title><blti:description>Chapter readings</blti:description>"
		'<blti:custom><lticm:property name="isbn">978-0</lticm:property></blti:custom>'
		f"<blti:launch_url>{PUBLISHER}/launch</blti:launch_url></cartridge_basiclti_link>"
	)
	f["imsmanifest.xml"] = (
		'<?xml version="1.0"?><manifest identifier="cc" xmlns="http://www.imsglobal.org/xsd/imsccv1p1/imscp_v1p1">'
		"<metadata><schema>IMS Common Cartridge</schema><schemaversion>1.1.0</schemaversion></metadata>"
		'<organizations><organization identifier="org_1" structure="rooted-hierarchy">'
		f'<item identifier="LearningModules">{items}</item></organization></organizations>'
		f"<resources>{''.join(resources)}</resources></manifest>"
	)
	buf = io.BytesIO()
	with zipfile.ZipFile(buf, "w") as zf:
		for name, content in f.items():
			zf.writestr(name, content)
	return buf.getvalue()


class TestCommonCartridgeImport(MigrationCase):
	def test_canvas_cartridge(self):
		cs = self.new_cs()
		report = import_into(cs, canvas_cartridge())
		skipped = {s["title"]: s["reason"] for s in report["skipped"]}
		lessons = self.lessons(cs)
		titles = [(ch, lesson.lesson_title) for ch, lesson in lessons]

		self.assertEqual(report["source"], "Common Cartridge")
		self.assertIn(("Week 1", "Welcome"), titles)
		self.assertIn(("Week 1", "Bible Gateway"), titles)
		self.assertIn(("Week 2", "Essay"), titles)
		self.assertIn(("Not in a module", "orphan.html"), titles)

		# the page's image is a new private File, and the wiki link is inert
		welcome = next(lesson for _ch, lesson in lessons if lesson.lesson_title == "Welcome")
		blocks = json.loads(welcome.content)["blocks"]
		image = next(b for b in blocks if b["type"] == "image")
		self.assertTrue(frappe.db.exists("File", {"file_url": image["data"]["url"], "is_private": 1}))
		self.assertNotIn("WIKI_REFERENCE", welcome.content)

		# quiz: the choice question in a quiz, the essay in an exam beside it, matching skipped
		quiz_lesson = next(lesson for _ch, lesson in lessons if lesson.lesson_title == "Quiz 1")
		quiz = scan_content_refs(quiz_lesson.content)[0][1]
		qdoc = frappe.get_doc("Quiz", quiz)
		self.assertEqual(len(qdoc.questions), 1)
		self.assertEqual(qdoc.questions[0].points, 2)
		self.assertEqual(qdoc.max_attempts, 2)
		self.assertEqual(qdoc.duration, 1800)
		self.assertEqual(qdoc.grading_basis, "Latest Attempt")
		self.assertTrue(skipped.get("Quiz 1: i3") == "matching")
		exams = [
			ref
			for _c, lesson in lessons
			for ref in scan_content_refs(lesson.content)
			if ref[0] == "Exam Activity"
		]
		self.assertEqual(len(exams), 1)

		# assignment with its Canvas rubric mapped onto a rubric scale
		essay = next(lesson for _ch, lesson in lessons if lesson.lesson_title == "Essay")
		assignment = scan_content_refs(essay.content)[0][1]
		rubric = frappe.db.get_value("Assignment Activity", assignment, "rubric")
		self.assertTrue(rubric)
		rdoc = frappe.get_doc("Rubric", rubric)
		self.assertEqual([c.title for c in rdoc.criteria], ["Argument", "Sources"])
		self.assertEqual(round(rdoc.criteria[0].weight), 67)
		self.assertEqual(frappe.db.get_value("Assignment Activity", assignment, "type"), "Document")

		# graded discussion; the announcement is reported, not imported, and so is
		# the LTI link while no tool on its host is registered (108 §4, by 110)
		self.assertEqual(
			skipped.get("Publisher tool"),
			"external tool (LTI): register a tool for publisher.lti-test.example, then import again",
		)
		self.assertTrue(any("announcement" in r for r in skipped.values()))

		# every graded activity has an assessment row with no weight
		rows = frappe.get_all(
			"Scheduled Course Assess Criteria",
			{"parent": cs},
			["quiz", "exam", "assignment", "discussion", "weight_scac"],
		)
		self.assertEqual(len(rows), 4)
		self.assertTrue(all(not r.weight_scac for r in rows))
		self.assertEqual(
			frappe.db.get_value("Course Lesson", essay.name, "assessment_criteria_assignment"),
			frappe.db.get_value("Scheduled Course Assess Criteria", {"parent": cs, "assignment": assignment}),
		)

		# the file no page used went to the course folder
		folder = frappe.db.get_value(
			"Course Folder", {"course": self.course, "foldername": ["like", "Imported files%"]}
		)
		self.assertTrue(folder)
		self.assertTrue(
			frappe.db.exists(
				"File",
				{
					"attached_to_doctype": "Course Folder",
					"attached_to_name": folder,
					"file_name": "notes.txt",
				},
			)
		)
		self.assertEqual(skipped.get("unused.pdf"), "damaged PDF")

	def test_refuses_section_with_chapters(self):
		cs = self.new_cs()
		import_into(cs, canvas_cartridge())
		with self.assertRaises(frappe.ValidationError):
			import_into(cs, canvas_cartridge())

	def test_refuses_other_files(self):
		buf = io.BytesIO()
		with zipfile.ZipFile(buf, "w") as zf:
			zf.writestr("readme.txt", "hello")
		with self.assertRaises(frappe.ValidationError):
			import_into(self.new_cs(), buf.getvalue())


# --- a Moodle backup -----------------------------------------------------------------------


def moodle_backup(release="5.3.1+ (Build: 20261124)", lti=False):
	f = {}
	activities = [
		("12", "34", "page", "Course outline"),
		("13", "34", "book", "Handbook"),
		("14", "35", "url", "Bible Gateway"),
		("15", "35", "forum", "Announcements"),
		("16", "35", "forum", "Week 1 discussion"),
		("17", "35", "assign", "Reflection paper"),
		("18", "35", "quiz", "Week 1 quiz"),
		("19", "35", "workshop", "Peer review"),
		("20", "35", "subsection", "Extra"),
		("21", "36", "label", "Optional reading"),
	]
	if lti:
		activities.append(("22", "36", "lti", "Publisher tool"))
	acts = "".join(
		f"<activity><moduleid>{m}</moduleid><sectionid>{s}</sectionid><modulename>{n}</modulename>"
		f"<title>{t}</title><directory>activities/{n}_{m}</directory></activity>"
		for m, s, n, t in activities
	)
	secs = "".join(
		f"<section><sectionid>{s}</sectionid><title>x</title><directory>sections/section_{s}</directory></section>"
		for s in ("34", "35", "36")
	)
	f["moodle_backup.xml"] = (
		"<moodle_backup><information><name>backup.mbz</name><moodle_version>2027042000</moodle_version>"
		f"<moodle_release>{release}</moodle_release><original_course_fullname>Church History I</original_course_fullname>"
		"<original_course_shortname>CH501</original_course_shortname>"
		f"<contents><activities>{acts}</activities><sections>{secs}</sections></contents></information></moodle_backup>"
	)
	f["sections/section_34/section.xml"] = (
		'<section id="34"><number>0</number><name/><summary>&lt;p&gt;Welcome to the course.&lt;/p&gt;</summary>'
		"<sequence>12,13</sequence><visible>1</visible><component/><itemid/></section>"
	)
	f["sections/section_35/section.xml"] = (
		'<section id="35"><number>1</number><name>Week 1</name><summary></summary>'
		"<sequence>14,15,16,17,18,19,20</sequence><visible>1</visible><component/><itemid/></section>"
	)
	f["sections/section_36/section.xml"] = (
		f'<section id="36"><number>2</number><name/><summary></summary><sequence>{"21,22" if lti else "21"}</sequence>'
		"<visible>1</visible><component>mod_subsection</component><itemid>7</itemid></section>"
	)

	def act(mid, name, ctx, body):
		f[f"activities/{name}_{mid}/{name}.xml"] = (
			f'<activity id="1" moduleid="{mid}" modulename="{name}" contextid="{ctx}">{body}</activity>'
		)
		f[f"activities/{name}_{mid}/module.xml"] = (
			f'<module id="{mid}"><modulename>{name}</modulename></module>'
		)

	act(
		"12",
		"page",
		"100",
		'<page id="1"><name>Course outline</name><intro/><content>&lt;h3&gt;Outline&lt;/h3&gt;&lt;p&gt;&lt;img '
		'src="@@PLUGINFILE@@/chart.png" alt="Chart"&gt;&lt;/p&gt;</content></page>',
	)
	act(
		"13",
		"book",
		"101",
		'<book id="1"><name>Handbook</name><chapters>'
		'<chapter id="2"><pagenum>2</pagenum><subchapter>0</subchapter><title>Policies</title><content>&lt;p&gt;Be kind.&lt;/p&gt;</content><hidden>0</hidden></chapter>'
		'<chapter id="1"><pagenum>1</pagenum><subchapter>0</subchapter><title>Start</title><content>&lt;p&gt;Hello.&lt;/p&gt;</content><hidden>0</hidden></chapter>'
		"</chapters></book>",
	)
	act(
		"14",
		"url",
		"102",
		'<url id="1"><name>Bible Gateway</name><intro/><externalurl>https://www.biblegateway.com/</externalurl></url>',
	)
	act("15", "forum", "103", '<forum id="1"><type>news</type><name>Announcements</name><intro/></forum>')
	act(
		"16",
		"forum",
		"104",
		'<forum id="2"><type>general</type><name>Week 1 discussion</name><intro>&lt;p&gt;Discuss.&lt;/p&gt;</intro>'
		"<assessed>1</assessed></forum>",
	)
	act(
		"17",
		"assign",
		"105",
		'<assign id="1"><name>Reflection paper</name><intro>&lt;p&gt;Reflect.&lt;/p&gt;</intro><grade>100</grade>'
		"<plugin_configs><plugin_config id='1'><plugin>onlinetext</plugin><subtype>assignsubmission</subtype>"
		"<name>enabled</name><value>1</value></plugin_config></plugin_configs></assign>",
	)
	slots = "".join(
		f"<question_instance id='{n}'><slot>{n}</slot><page>1</page><maxmark>{mark}</maxmark>"
		f"<question_reference id='{n}'><component>mod_quiz</component><questionarea>slot</questionarea>"
		f"<questionbankentryid>{entry}</questionbankentryid><version/></question_reference></question_instance>"
		for n, entry, mark in (
			(1, 50, "2.0000000"),
			(2, 51, "1.0000000"),
			(3, 52, "4.0000000"),
			(4, 53, "1.0000000"),
		)
	)
	slots += (
		"<question_instance id='5'><slot>5</slot><maxmark>1</maxmark><question_set_reference id='5'>"
		"<filtercondition>{}</filtercondition></question_set_reference></question_instance>"
	)
	act(
		"18",
		"quiz",
		"106",
		'<quiz id="1"><name>Week 1 quiz</name><intro/><timelimit>1200</timelimit><attempts_number>3</attempts_number>'
		"<grademethod>1</grademethod><grade>10</grade>"
		f"<question_instances>{slots}</question_instances>"
		"<sections><section id='1'><firstslot>1</firstslot><shufflequestions>1</shufflequestions></section></sections></quiz>",
	)
	act("19", "workshop", "107", '<workshop id="1"><name>Peer review</name></workshop>')
	act("20", "subsection", "108", '<subsection id="7"><name>Extra</name></subsection>')
	act(
		"21",
		"label",
		"109",
		'<label id="1"><name>Optional reading</name><intro>&lt;p&gt;Read more.&lt;/p&gt;</intro></label>',
	)

	if lti:
		act(
			"22",
			"lti",
			"110",
			'<lti id="1"><name>Publisher tool</name><intro>&lt;p&gt;Read chapter 2.&lt;/p&gt;</intro>'
			f"<typeid>0</typeid><toolurl>{PUBLISHER}/launch/moodle</toolurl>"
			"<instructorcustomparameters>isbn=978-0\nunit=2</instructorcustomparameters></lti>",
		)

	def question(qid, qtype, text, answers="", extra=""):
		return (
			f"<question id='{qid}'><parent>0</parent><name>Q{qid}</name><questiontext>{text}</questiontext>"
			f"<defaultmark>1.0000000</defaultmark><qtype>{qtype}</qtype>"
			f"<plugin_qtype_{qtype}_question><answers>{answers}</answers>{extra}</plugin_qtype_{qtype}_question></question>"
		)

	def answer(aid, text, fraction):
		return f"<answer id='{aid}'><answertext>{text}</answertext><fraction>{fraction}</fraction></answer>"

	def entry(eid, q):
		return (
			f"<question_bank_entry id='{eid}'><question_version><question_versions id='{eid}'><version>1</version>"
			f"<status>ready</status><questions>{q}</questions></question_versions></question_version></question_bank_entry>"
		)

	f["questions.xml"] = (
		"<question_categories><question_category id='1'><contextid>200</contextid><contextlevel>70</contextlevel>"
		"<question_bank_entries>"
		+ entry(
			50,
			question(
				60,
				"multichoice",
				"&lt;p&gt;Who wrote Confessions? &lt;img src=&quot;@@PLUGINFILE@@/aug.png&quot;&gt;&lt;/p&gt;",
				answer(1, "Augustine", "1.0000000") + answer(2, "Origen", "0.0000000"),
				"<multichoice id='1'><single>1</single></multichoice>",
			),
		)
		+ entry(
			51,
			question(
				61,
				"truefalse",
				"Nicaea was in 325.",
				answer(3, "True", "1.0000000") + answer(4, "False", "0.0000000"),
			),
		)
		+ entry(52, question(62, "essay", "&lt;p&gt;Explain the filioque.&lt;/p&gt;", "", "<essay id='1'/>"))
		+ entry(53, question(63, "match", "Match the councils.", ""))
		+ "</question_bank_entries></question_category></question_categories>"
	)
	files = [
		("aa11", "100", "mod_page", "content", "0", "chart.png", "image/png", PNG),
		("bb22", "200", "question", "questiontext", "60", "aug.png", "image/png", PNG + b"\x00"),
	]
	f["files.xml"] = (
		"<files>"
		+ "".join(
			f"<file id='{i}'><contenthash>{h}</contenthash><contextid>{c}</contextid><component>{comp}</component>"
			f"<filearea>{area}</filearea><itemid>{item}</itemid><filepath>/</filepath><filename>{name}</filename>"
			f"<mimetype>{mime}</mimetype><sortorder>0</sortorder></file>"
			for i, (h, c, comp, area, item, name, mime, _b) in enumerate(files, start=1)
		)
		+ "</files>"
	)
	blobs = {f"files/{h[:2]}/{h}": b for h, *_rest, b in files}

	buf = io.BytesIO()
	with tarfile.open(fileobj=buf, mode="w:gz") as tf:
		for name, content in list(f.items()) + list(blobs.items()):
			data = content.encode() if isinstance(content, str) else content
			info = tarfile.TarInfo(name)
			info.size = len(data)
			tf.addfile(info, io.BytesIO(data))
	return buf.getvalue()


class TestMoodleImport(MigrationCase):
	def test_moodle_backup(self):
		cs = self.new_cs()
		report = import_into(cs, moodle_backup())
		skipped = {s["title"]: s["reason"] for s in report["skipped"]}
		lessons = self.lessons(cs)
		titles = [(ch, lesson.lesson_title) for ch, lesson in lessons]

		self.assertEqual(report["source"], "Moodle")
		self.assertEqual(
			titles,
			[
				("General", "General"),
				("General", "Course outline"),
				("General", "Handbook: Start"),
				("General", "Handbook: Policies"),
				("Week 1", "Bible Gateway"),
				("Week 1", "Week 1 discussion"),
				("Week 1", "Reflection paper"),
				("Week 1", "Week 1 quiz"),
				("Week 1", "Week 1 quiz (written)"),
				("Week 1", "Optional reading"),
			],
		)
		self.assertEqual(skipped.get("Announcements"), "announcements forum, left out on purpose")
		self.assertEqual(skipped.get("Peer review"), "workshop")
		self.assertTrue(any(r == "matching" for r in skipped.values()))
		self.assertTrue(any(r == "random question from a category" for r in skipped.values()))

		outline = next(lesson for _c, lesson in lessons if lesson.lesson_title == "Course outline")
		image = next(b for b in json.loads(outline.content)["blocks"] if b["type"] == "image")
		self.assertTrue(frappe.db.exists("File", {"file_url": image["data"]["url"]}))

		quiz_lesson = next(lesson for _c, lesson in lessons if lesson.lesson_title == "Week 1 quiz")
		quiz = frappe.get_doc("Quiz", scan_content_refs(quiz_lesson.content)[0][1])
		self.assertEqual([r.points for r in quiz.questions], [2, 1])
		self.assertEqual(quiz.duration, 1200)
		self.assertEqual(quiz.max_attempts, 3)
		self.assertTrue(quiz.shuffle_questions)
		first = frappe.get_doc("Question", quiz.questions[0].question)
		self.assertIn("/private/files/", first.question)
		self.assertEqual([c.option for c in first.choices if c.is_correct], ["Augustine"])

		paper = next(lesson for _c, lesson in lessons if lesson.lesson_title == "Reflection paper")
		assignment = scan_content_refs(paper.content)[0][1]
		self.assertEqual(frappe.db.get_value("Assignment Activity", assignment, "type"), "Text")
		self.assertEqual(len(frappe.get_all("Scheduled Course Assess Criteria", {"parent": cs})), 4)

	def test_release_branch(self):
		from .moodle import release_branch

		self.assertEqual(release_branch("5.3.1+ (Build: 20261124)"), "5.3")
		self.assertEqual(release_branch("5.3 (Build: 20261005)"), "5.3")
		self.assertEqual(release_branch("5.30"), "5.30")
		self.assertEqual(release_branch("6.0dev (Build: 20261124)"), "6.0")

	def test_accepts_5_0_to_5_3(self):
		for release in ("5.0.12 (Build: 20261112)", "5.1.9+ (Build: 20261124)", "5.2.5+ (Build: 20261124)"):
			report = import_into(self.new_cs(), moodle_backup(release))
			self.assertEqual(report["source"], "Moodle")

	def test_refuses_other_releases(self):
		for release in ("4.5.8 (Build: 20261110)", "6.0dev (Build: 20261124)"):
			with self.assertRaises(frappe.ValidationError) as ctx:
				import_into(self.new_cs(), moodle_backup(release))
			self.assertIn(release.split(" (")[0], str(ctx.exception))


# --- exporting a Common Cartridge ----------------------------------------------------------


class TestCommonCartridgeExport(MigrationCase):
	def test_round_trip(self):
		source = self.new_cs()
		import_into(source, canvas_cartridge())
		_name, content, _left_out = build_cartridge_bytes(source)
		with zipfile.ZipFile(io.BytesIO(content)) as zf:
			names = zf.namelist()
			manifest = zf.read("imsmanifest.xml").decode()
		self.assertIn("imsmanifest.xml", names)
		self.assertIn("1.3.0", manifest)
		self.assertIn("assignment_xmlv1p0", manifest)
		self.assertIn("imsqti_item_xmlv2p1", manifest)
		self.assertTrue(any(n.startswith("web_resources/") for n in names))

		target = self.new_cs()
		report = import_into(target, content)
		before = sorted(lesson.lesson_title for _c, lesson in self.lessons(source))
		after = sorted(lesson.lesson_title for _c, lesson in self.lessons(target))
		self.assertEqual(before, after)
		self.assertEqual(report["questions"], 2)
		self.assertEqual(report["skipped"], [])


# --- LTI links (decisions/108 §4, amended by 110) -------------------------------------------


class TestLtiLinks(MigrationCase):
	def setUp(self):
		from cryptography.hazmat.primitives import serialization
		from cryptography.hazmat.primitives.asymmetric import rsa

		pem = (
			rsa.generate_private_key(public_exponent=65537, key_size=2048)
			.public_key()
			.public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
			.decode()
		)
		self.tool = frappe.get_doc(
			{
				"doctype": "LTI Tool",
				"tool_name": f"MIG publisher {frappe.generate_hash(length=6)}",
				"oidc_login_url": f"{PUBLISHER}/login",
				"target_link_url": f"{PUBLISHER}/launch",
				"public_key": pem,
			}
		).insert(ignore_permissions=True)
		self.addCleanup(
			lambda: frappe.delete_doc("LTI Tool", self.tool.name, force=True, ignore_permissions=True)
		)

	def _lti_lessons(self, cs):
		return [lesson for _c, lesson in self.lessons(cs) if lesson.lti_tool]

	def test_a_cartridge_link_becomes_an_lti_lesson(self):
		cs = self.new_cs()
		report = import_into(cs, canvas_cartridge())
		self.assertNotIn("Publisher tool", {s["title"] for s in report["skipped"]})
		(lesson,) = self._lti_lessons(cs)
		self.assertEqual(lesson.lesson_title, "Publisher tool")
		self.assertEqual(lesson.lti_tool, self.tool.name)
		self.assertEqual(lesson.lti_url, f"{PUBLISHER}/launch")
		self.assertEqual(lesson.lti_custom, "isbn=978-0")
		self.assertTrue(lesson.lti_resource_link_id)
		self.assertFalse(lesson.lti_assessment_criteria)
		self.assertIn("Chapter readings", lesson.content)

	def test_a_moodle_external_tool_becomes_an_lti_lesson(self):
		cs = self.new_cs()
		import_into(cs, moodle_backup(lti=True))
		(lesson,) = self._lti_lessons(cs)
		self.assertEqual(lesson.lti_url, f"{PUBLISHER}/launch/moodle")
		self.assertEqual(lesson.lti_custom, "isbn=978-0\nunit=2")

	def test_export_writes_lti_links_and_they_come_back(self):
		source = self.new_cs()
		import_into(source, canvas_cartridge())
		_name, content, _left_out = build_cartridge_bytes(source)
		with zipfile.ZipFile(io.BytesIO(content)) as zf:
			manifest = zf.read("imsmanifest.xml").decode()
			links = [zf.read(n).decode() for n in zf.namelist() if n.startswith("lti/")]
		self.assertIn("imsbasiclti_xmlv1p0", manifest)
		self.assertEqual(len(links), 1)
		self.assertIn(f"{PUBLISHER}/launch", links[0])
		self.assertIn('name="isbn"', links[0])

		target = self.new_cs()
		import_into(target, content)
		(lesson,) = self._lti_lessons(target)
		self.assertEqual((lesson.lti_tool, lesson.lti_custom), (self.tool.name, "isbn=978-0"))
