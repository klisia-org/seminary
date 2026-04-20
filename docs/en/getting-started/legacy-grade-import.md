# Legacy Grade Import

SeminaryERP uses a single pipeline for both transfer credits from a partner institution and bulk backfill of grades from a legacy system. The model treats "our own pre-SeminaryERP history" as a self-referential Partner Seminary, so the same workflow that ingests a transfer student's transcript also onboards decades of historical data. 

The import is a staged, idempotent workflow:

**Partner Seminary → Course Equivalences → Transcript Import Batch (Draft → Dry-Run → Submit)**

Dry-run resolves every row against the equivalences and conversion policy without touching the student's record. Submit commits each row into the student's Program Enrollment and refreshes degree-audit totals. Re-submitting the same (student, source course code, source term) updates the existing transcript row in place — no duplicates.

## 1. One-time setup (Internal Legacy)

To import your own institution's historical data, create one self-referential **Partner Seminary** plus one **grade conversion policy**. Register only once, reuse forever.

1. **Create the Grade Conversion Policy "Identity (Internal)"**
    * Source Grading Scale = your internal scale
    * Target Grading Scale = your internal scale (same)
    * Conversion Method = `identity`
    * Submit it. Submitted policies can be referenced by Partner Seminary records; drafts cannot.
2. **Create the Partner Seminary record**
    * Name: e.g. `ESWA Legacy (pre-2026)`
    * `Is Internal Legacy`: checked (this flag is read-only after creation, prevents deletion, and hides the record from default list views)
    * `Counts in GPA`: checked (legacy grades ARE your institution's own grades — they should participate in GPA math)
    * `Credit Unit Ratio`: `1.0`
    * Default Grading Scale = your internal scale
    * Default Conversion Policy = `Identity (Internal)`
3. **Bulk-create Course Equivalences**
    * Open the Partner Seminary Course Equivalence list view.
    * Click **Create Legacy Integration** (System Manager only).
    * Pick the legacy Partner Seminary you just created.
    * One submitted `legacy_identity` equivalence is created per Course in your catalog, self-mapping the course to itself. Already-mapped courses are skipped — the action is idempotent.

After this, the legacy Partner Seminary is ready to receive transcript imports. Skip to step 3 for the actual import flow.

## 2. One-time setup (External Partner)

For a true external partner (a peer seminary transferring credits in):

1. Create (or reuse) the partner's **Grading Scale** if different from yours. Submit it.
2. Create the **Grade Conversion Policy** from the partner's scale to your internal scale:
    * Pick a `conversion_method`: `identity`, `linear_multiplier`, `linear_with_offset`, `interval_map`, or `manual_per_course`.
    * For `linear_*`, set the `multiplier` (and `offset` if applicable). E.g. Francophone 0–20 strong → Internal Percentage = ×5.
    * For `interval_map`, fill the symbol-by-symbol mapping table. The Source Symbol and Target Symbol dropdowns auto-populate from the respective scales — every source symbol must be mapped (target symbols without a source are allowed).
    * Submit.
3. Create the **Partner Seminary** record for the institution:
    * `Is Internal Legacy`: unchecked
    * `Counts in GPA`: usually unchecked (industry default — transferred credits count toward degree but not GPA)
    * `Credit Unit Ratio`: internal credit hours per 1 partner credit unit (e.g. `0.5` for ECTS → US semester hours at half weight)
    * `Minimum Transferable Grade`: grade code on your internal scale below which transfers are blocked at commit time (e.g. `C`)
    * Default Grading Scale / Default Conversion Policy = what you just created
4. Create **Partner Seminary Course Equivalences** one at a time from the partner course to your internal course:
    * Fill `source_course_code`, `source_course_name`, `source_credit_value`, and the target `internal_course`.
    * Optional per-course overrides: `credit_override` (to force a specific credit count), `conversion_policy_override` (for a course on a different scale than the partner's default — e.g. a music department on pass/fail).
    * Attach a `Supporting Document` (director approval, committee minutes, accreditor letter) for audit trail.
    * Submit. Only submitted equivalences are usable during import.

Course equivalences are submittable: to change one, cancel and amend — the old version is retained via `amended_from`, and existing transcript rows continue to reference the original.

## 3. Importing transcripts

Partner Transcript Import Batch drives both the manual single-student case and the CSV bulk case. Every batch carries:

- `Partner Seminary`: which partner's data this batch represents
- `Target Program`: the internal program the credits apply toward
- `Target Academic Term`: the internal term these rows are anchored to (typically the student's current term for external transfer, or a designated legacy term for backfill)

### Manual entry (one student)

1. Create a new **Partner Transcript Import Batch**.
2. Pick Partner Seminary, Target Program, Target Academic Term. Save. *(Autocompletes activate only after the first save.)*
3. In the Rows table, add one row per course:
    * `Student` (Link) OR `Student Email` — either identifies the student. If only email is provided, dry-run resolves it to the Student record via `Student.user`.
    * `Source Course Code` — dropdown populated from submitted equivalences for this partner. Selecting a code auto-fills `Source Course Name` and `Source Credit Value` from the equivalence.
    * `Source Term` — free-text (partner terms aren't tracked as Academic Term records here).
    * `Source Grade` — dropdown populated from the partner's default grading scale grade codes.
    * `External Reference` — optional source-system ID; takes precedence over the natural idempotency key.
4. **Save**, then click **Run Dry-Run**.
5. If dry-run is clean, the status advances to `Dry-Run Clean`. Click **Submit**.

### CSV bulk entry

1. Use Frappe's built-in **Data Import** tool (use the seach bar) --> Add Data Import
2. Document type: Partner Transcript Import Batch Import
   Import Type: Insert New records
   The only checkbox marked should be Don't send emails.
   **Save**
3. You can download a CSV template from the tool to upload your data. Note that you do not need to repeat the initial fields (parent seminary, target program, and target academic term)

    ```csv
    Partner Seminary,Target Program,Target Academic Term,Source Course Code (Rows),Source Grade (Rows),Source Term (Rows),Student email (Rows)
    T-LINK,Master of Divinity,2025-2026 (SP26),SFD-101,A,1S 24,modest@gmail.com
    ,,,THM-201,A,1S24,modest@gmail.com
    ```

4. Upon successful import, Open the Batch — all rows should be in the grid with `Student` blank and `Student Email` populated.
5. Click **Run Dry-Run**. Each row resolves:
    * Email → Student Link
    * Source course → Internal course via the equivalence
    * Source credit → Internal credit (via `credit_override`, the equivalence's `source_credit_value`, or the row's own value × `credit_unit_ratio`)
    * Source grade → Target grade via the conversion policy
6. Fix any warnings (see reference below), then Submit.

## 4. Dry-run warning reference

| Warning | Meaning | Fix |
|---|---|---|
| `unknown_student_email` | No Student record has a `user` field matching the email. | Correct the email in the row, or update the Student's User link. |
| `no_submitted_equivalence` | No submitted Course Equivalence for this partner + source code. | Create and submit the equivalence, or correct the source code. |
| `zero_credits` | The row's source credit is blank and the equivalence has no `source_credit_value` / `credit_override`. | Fill the row's `source_credit_value`, or edit the equivalence to carry a default. |
| `below_minimum_transferable` | The converted grade is below the partner's `Minimum Transferable Grade`. | Registrar judgment — either skip the row or add an `Override Note` to accept it. |
| `clamped_high` / `clamped_low` | The linear conversion produced a value outside the target scale; result was clamped. | Usually acceptable; informational. Review the policy multiplier if the clamp is frequent. |
| `no_mapping` | An `interval_map` conversion had no row for this source symbol, or the grade wasn't found on the target scale. | Amend the policy's map to cover the missing symbol. |
| `unparseable_source` | Linear conversion couldn't parse the source grade as a number. | Correct the source grade, or switch the policy to `interval_map` / `manual_per_course`. |

A row with a warning blocks Dry-Run Clean unless the registrar fills `Override Note` on that row. Commit is additionally guarded: every row must have a resolved `Student` before Submit succeeds.

## 5. Submit

On submit:

* Each row becomes a transferred `Program Enrollment Course` entry on the student's Program Enrollment for (Target Program, Target Academic Term). `Is Transfer` is checked; `Partner Seminary`, `Mapping Type`, `Course Equivalence`, `Conversion Policy Applied`, `Source Course Code`, `Source Term`, `Source Grade`, `External Reference` are all stamped for audit.
* The Program Enrollment's `Total Credits` is recalculated from the SUM of passing rows.
* Emphasis track credits are recalculated; auto-grant emphases are checked.
* The student-facing transcript view shows the transferred courses alongside internal ones. 

## 6. Re-running and amending

The batch is idempotent. Re-submitting a batch with the same rows updates existing transcript entries in place (matched on `partner_seminary + source_course_code + source_term`, or `external_reference` when present). To correct data:

* **Same-term correction** — Create a new batch with the corrected rows; the existing PEC rows update. Totals refresh.
* **Wrong term selected** — Cancel the original batch (supervised; blocked if transcript rows still exist), create a new batch with the correct `Target Academic Term`.
* **Policy correction** — Amend the Grade Conversion Policy (Frappe's built-in amendment creates `amended_from` lineage). Existing transcripts keep referencing the original policy ID; new imports use the amended version. This preserves historical reproducibility.

## Related

* [Initial Setup](initial-setup.md) — the full first-install sequence
* [Frappe Data Import](https://docs.frappe.io/framework/user/en/data-import)
