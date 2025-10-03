import frappe
import os
import socket
from urllib.parse import urlparse
from typing import Optional

DEV_SERVER_ENV_KEY = "SEMINARY_DEV_SERVER_URL"
DEFAULT_DEV_SERVER_URL = os.environ.get(DEV_SERVER_ENV_KEY, "http://localhost:8080")


def get_context(context):
	"""Get context for seminary frontend page."""
	if frappe.session.user == "Guest":
		frappe.local.flags.redirect_location = "/login?redirect-to=/seminary/"
		raise frappe.Redirect

	context.no_cache = 1
	context.boot = frappe._dict(get_boot_data())
	context.title = "Seminary ERP"
	context.history_base = "/seminary/"

	if _is_dev_request():
		dev_server_url = _get_dev_server_url().rstrip("/")
		if not _is_dev_server_running(dev_server_url):
			frappe.throw(
				f"Vite dev server is not reachable at {dev_server_url}. "
				"Run `yarn dev` in apps/seminary/frontend to start it."
			)
		context.template = "templates/pages/seminary_dev.html"
		context.dev_server_url = dev_server_url
	else:
		context.dev_server_url = None

	return context


def get_boot_data():
	"""Shared boot data for Seminary frontend."""
	boot = {}

	user = frappe.get_doc("User", frappe.session.user)
	boot["user"] = {
		"name": user.name,
		"email": user.email,
		"full_name": user.full_name,
		"user_image": user.user_image,
		"username": user.username,
	}

	boot["csrf_token"] = frappe.session.data.csrf_token
	boot["sitename"] = frappe.local.site
	boot["sysdefaults"] = frappe.defaults.get_defaults()
	boot["session"] = {
		"user": frappe.session.user,
		"sid": frappe.session.sid,
	}

	return boot


def _is_dev_request() -> bool:
	flag = frappe.form_dict.get("dev")
	return isinstance(flag, str) and flag.lower() in {"1", "true", "yes"}


def _get_dev_server_url() -> str:
	return os.environ.get(DEV_SERVER_ENV_KEY, DEFAULT_DEV_SERVER_URL)


def _is_dev_server_running(dev_server_url: str) -> bool:
	parsed = urlparse(dev_server_url)
	if not parsed.hostname:
		return False

	port = parsed.port or (443 if parsed.scheme == "https" else 80)
	sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
	sock.settimeout(1)
	try:
		return sock.connect_ex((parsed.hostname, port)) == 0
	finally:
		sock.close()
