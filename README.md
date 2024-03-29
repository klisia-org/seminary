This project was originally a forked version of Frappe Education, but we unforked it as the workflow changed significantly.
Essentially, this is an ongoing development to make it appropriate for higher education, particularly seminaries.

This is an open-source and user-friendly School Management System designed to streamline the administrative and academic processes of educational institutions. It is a powerful module based on and integrated with the ERPNext software.

Seminary is dedicated to making education management more efficient and less time-consuming. The module offers a range of features that cater to the needs of educators and administrators, facilitating a more organized and effective learning environment.




## Table of Contents

- [Key Features](#key-features)
- [License](#license)

## Key Features

Here are some of the standout features of the Frappe Education module:

- **Student Admission**: Streamline the admission process for new students. 🎓
- **Program Enrollment**: Manage and keep track of student enrollments in various programs. Students can also enroll in different program tacks (emphasis). 📋
- **Course Enrollment**: Students can enroll in courses that are scheduled, according to their programs, pre-requisites, and academic terms.
- **Fee Categories**: Fees are associated with ERPNext Items, and students can be assigned to different Customer Groups and have specific price lists. Fees categories are also associated with Triggers (for now, these are hardcoded: Program Enrollment, Course Enrollment, New Academic Term, New Academic Year) and to payment terms templates (so you can create a fee that is triggered by one of these events and have a distinct invoice schedule).
- **Payers**: As a student is enrolled in a program, their customer is associated with all different fee categories for that program. However, the registrar may split (% only) each fee category among different payers. That way, a church/company may pay a percentage of some fess but not of others. 💰
- **Course Scheduling**: Efficiently schedule courses and manage course calendars. 🗓️
- **Attendance Management**: Track and manage student attendance records. ✔️



## License

GNU GPL V3. See [license.txt](https://github.com/frappe/agriculture/blob/develop/license.txt) for more information.
