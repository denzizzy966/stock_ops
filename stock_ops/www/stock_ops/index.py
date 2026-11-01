import frappe

no_cache = 1


def get_context(context):
	# Tamu tidak dialihkan ke /login desk: PWA menampilkan layar login sendiri (bermerek, bisa dipasang).
	context.csrf_token = frappe.sessions.get_csrf_token() if frappe.session.user != "Guest" else ""
	context.stockops_user = frappe.session.user
	frappe.db.commit()  # nosemgrep
	return context
