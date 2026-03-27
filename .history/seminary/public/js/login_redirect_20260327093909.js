$(document).ready(function() {
  console.log(frappe.session.user);
  if(frappe.user.has_role("Student")&& window.location.pathname !== "/seminary/courses"){
  window.location.href = "/seminary";
  }
});