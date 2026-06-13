// Copyright (c) 2024, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

// frappe.ui.form.on("Course Enrollment Individual", {
// 	refresh(frm) {

// 	},
// });
function load_courses_for_program(frm) {
    if (!frm.doc.program_ce) return;
    frappe.call({
        method: "seminary.seminary.api.courses_for_student",
        args: { program_ce: frm.doc.program_ce },
        callback: function (response) {
            frm.courses = response.message || [];
            frm.refresh_field("coursesc_ce");
        },
    });
}

// ADR 050: double-booking is allowed on purpose (warn, not block). Resolves
// true to proceed with the save, false to abort. ESC / dialog close = abort.
function confirm_schedule_conflict(clashes) {
    const lines = clashes
        .map(
            (c) =>
                `${frappe.utils.escape_html(c.title || c.course_schedule)} — ${c.meetdate} (${c.from_time}–${c.to_time})`
        )
        .join("<br>");
    return new Promise((resolve) => {
        const d = new frappe.ui.Dialog({
            title: __("Schedule conflict"),
            primary_action_label: __("Proceed Anyway"),
            primary_action() {
                resolve(true);
                d.hide();
            },
            secondary_action_label: __("Cancel"),
            secondary_action() {
                resolve(false);
                d.hide();
            },
        });
        d.$body.html(
            `<div class="text-muted" style="padding:8px 0;">${__(
                "This section overlaps the student's enrollment(s):"
            )}<br><br>${lines}<br><br>${__(
                "Enroll anyway? The registrar can later cancel one of the two enrollments."
            )}</div>`
        );
        // ESC / X without choosing a button counts as Cancel (no-op if already resolved).
        d.onhide = () => resolve(false);
        d.show();
    });
}

frappe.ui.form.on("Course Enrollment Individual", {
    onload(frm) {


        frappe.db.get_single_value('Seminary Settings', 'allow_audit')
            .then(value => {
                if (value === 1) {
                    frm.toggle_display('audit', true);
                } else {
                    frm.toggle_display('audit', false);
                }
            })
            .catch(error => {
                console.log('Error occurred while fetching Seminary Settings:', error);
            });
        frappe.db.get_list('Program Enrollment', {
            fields: ['name'],
            filters: {
                docstatus: 1
            }
        }).then(result => {
            const programEnrollments = result.map(item => item.name);
            frm.set_query('program_ce', () => {
                return {
                    filters: {
                        name: ['in', programEnrollments]
                    }
                };
            });
        }).catch(error => {
            console.log('Error occurred while fetching Program Enrollment:', error);
        });

    },
    refresh(frm) {
        frm.set_query("coursesc_ce", () => {
            const NO_MATCH = { filters: { course: ["in", ["__none__"]], workflow_state: "Open for Enrollment" } };
            let q;
            if (!frm.doc.program_ce) {
                q = NO_MATCH;
            } else if (frm.doc.no_prereq === 1 || frm.doc.audit === 1) {
                q = { filters: { workflow_state: "Open for Enrollment" } };
            } else if (frm.courses && frm.courses.length) {
                q = { filters: { course: ["in", frm.courses], workflow_state: "Open for Enrollment" } };
            } else {
                q = NO_MATCH;
            }
            console.log("coursesc_ce set_query →", q.filters);
            return q;
        });

        // Existing record: program is already set but field event never fired.
        if (frm.doc.program_ce && !frm.courses) {
            load_courses_for_program(frm);
        }
        if (!frm.doc.cei_si) {

            frm.add_custom_button("Create Sales Invoice(s)", function() {
                frm.call('get_inv_data_ce')
                    .then(r => {
                        frm.set_value("cei_si", 1);
                        frm.save();
                        frm.refresh();
                    })
                    .catch(e => {
                        frappe.msgprint("Error creating Sales Invoice(s)!");
                    });
            }).css({"color":"white", "background": "#0d3049", "font-weight": "700", "border-radius": "5px", "padding": "5px 10px", "margin-right": "10px"});};

        if (frm.doc.docstatus === 1 && !frm.doc.withdrawn && !frm.doc.withdrawal_request) {
            frm.add_custom_button(__("Request Withdrawal"), function() {
                frappe.model.with_doctype("Withdrawal Request", function() {
                    const wr = frappe.model.get_new_doc("Withdrawal Request");
                    wr.program_enrollment = frm.doc.program_ce;
                    wr.student = frm.doc.student_ce;
                    wr.course_enrollment_individual = frm.doc.name;
                    wr.withdrawal_scope = "Single Course";
                    frappe.set_route("Form", "Withdrawal Request", wr.name);
                });
            }).css({"color":"white", "background": "#0d3049", "font-weight": "700", "border-radius": "5px", "padding": "5px 10px", "margin-right": "10px"});
        }

    },
    validate(frm) {
        // ADR 050: warn (don't block) on a student schedule double-booking.
        // Async gate — the returned promise is awaited; cancelling sets
        // frappe.validated = false to abort the save.
        if (frm.doc.audit || !frm.doc.student_ce || !frm.doc.coursesc_ce) return;
        return frappe
            .call({
                method: "seminary.seminary.api.check_schedule_conflicts",
                args: {
                    student: frm.doc.student_ce,
                    course_schedule: frm.doc.coursesc_ce,
                    exclude_cei: frm.doc.name,
                },
            })
            .then((r) => {
                const clashes = (r && r.message) || [];
                if (!clashes.length) return;
                return confirm_schedule_conflict(clashes).then((proceed) => {
                    if (!proceed) frappe.validated = false;
                });
            })
            .catch(() => {
                // Never block the save on a failed conflict check.
            });
    },
    program_ce(frm) {
        // Clear stale course selection when program changes
        frm.set_value("coursesc_ce", "");
        frm.courses = null;

        if (frm.doc.program_ce) {
            load_courses_for_program(frm);
        }
    },




    student_ce(frm) {
        frm.set_query("program_ce", function() {
            return {
                filters: {
                    student: frm.doc.student_ce
                }
            };
        });
    },
    coursesc_ce(frm) {

        frm.call('get_credits')
                .then(r => {
                        r.message = Number(r.message);
                        frm.set_value('credits', r.message);


                    });

    },


    on_submit(frm) {
        frm.call('get_credits2')
        .then(r => {
            if (r.message) {
                frm.credits = r.message;
                console.log("Credits: ", r.message);
            }
        }
    );

    }
});
