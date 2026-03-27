$(document).ready(function() {
  console.log(frappe.session.user);
  if(frappe.user.has_role("POS User")&& window.location.pathname !== "/app/point-of-sale"){
  window.location.href = "/app/point-of-sale";
  }
});