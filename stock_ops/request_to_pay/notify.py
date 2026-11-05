# Notifikasi Request to Pay per perubahan status.
#
# Kenapa tidak memakai DocType Notification bawaan: penerima "by role" di sana mengabaikan
# company — approver MET Thailand ikut menerima email pengajuan RMI Indonesia. Di sini penerima
# = user ber-role tahap itu YANG company-nya mencakup company dokumen (User Permission Company;
# tanpa User Permission = semua company).
import frappe
from frappe import _

# state → role yang harus bertindak
STAGE_ROLE = {
	"Pending Tax Review": "RTP Tax Reviewer",
	"Pending FAT Approval": "RTP FAT Approver",
	"Pending HOD Approval": "RTP HOD Approver",
	"Pending Global Approval": "RTP Global Approver",
	"Approved": "RTP Payment Processor",
}
APP_URL = "/stock_ops#/rtp/{name}"


def users_for(role, company, exclude=()):
	"""User aktif ber-`role` yang boleh melihat `company`."""
	users = set(
		frappe.get_all("Has Role", filters={"role": role, "parenttype": "User"}, pluck="parent")
	)
	out = []
	for u in sorted(users):
		if u in ("Administrator", "Guest") or u in exclude:
			continue
		if not frappe.db.get_value("User", u, "enabled"):
			continue
		cos = frappe.get_all("User Permission", filters={"user": u, "allow": "Company"}, pluck="for_value")
		if cos and company not in cos:
			continue
		out.append(u)
	return out


def _money(doc):
	return frappe.format_value(doc.total_payment, {"fieldtype": "Currency", "options": "currency"}, doc)


def _send(users, subject, body, doc):
	if not users:
		return
	from frappe.desk.doctype.notification_log.notification_log import enqueue_create_notification

	enqueue_create_notification(
		users,
		{
			"type": "Alert",
			"document_type": doc.doctype,
			"document_name": doc.name,
			"subject": subject,
			"email_content": body,
			"from_user": frappe.session.user,
		},
	)
	link = frappe.utils.get_url(APP_URL.format(name=doc.name))
	try:
		frappe.sendmail(
			recipients=users,
			subject=subject,
			message=f"<p>{frappe.utils.escape_html(body)}</p><p><a href=\"{link}\">{_('Buka pengajuan')}</a></p>",
			reference_doctype=doc.doctype,
			reference_name=doc.name,
		)
	except Exception:
		frappe.log_error(frappe.get_traceback(), "Request to Pay email")
	try:
		from stock_ops.push import send_to_user

		for u in users:
			send_to_user(u, subject, body, APP_URL.format(name=doc.name))
	except Exception:
		frappe.log_error(frappe.get_traceback(), "Request to Pay push")


def on_state_change(doc):
	state = doc.workflow_state
	summary = f"{doc.name} · {doc.requester_name or doc.requester} · {_money(doc)}"
	role = STAGE_ROLE.get(state)

	if role and state != "Approved":
		users = users_for(role, doc.company, exclude=(frappe.session.user,))
		urgent = _("URGENT · ") if doc.urgency == "Urgent" else ""
		_send(users, f"{urgent}{_('Persetujuan diperlukan')}: {doc.name}", f"{summary} — {_(state)}", doc)

	elif state == "Approved":
		payers = users_for("RTP Payment Processor", doc.company)
		_send(payers, f"{_('Siap dibayar')}: {doc.name}", f"{summary} — {_('jatuh tempo')} {doc.payment_date}", doc)
		_send(
			[u for u in users_for("RTP Finance", doc.company) if u not in payers],
			f"{_('Pengajuan disetujui')}: {doc.name}",
			summary,
			doc,
		)
		_assign(payers, doc)
		_send([doc.requester], f"{_('Pengajuan Anda disetujui')}: {doc.name}", summary, doc)

	elif state == "Rejected":
		note = doc.approval_note or "-"
		_send([doc.requester], f"{_('Pengajuan Anda ditolak')}: {doc.name}", f"{summary} — {_('Alasan')}: {note}", doc)

	elif state == "Paid":
		_close_assignments(doc)
		_send([doc.requester], f"{_('Pengajuan Anda sudah dibayar')}: {doc.name}", summary, doc)


def _assign(users, doc):
	"""ToDo "Payment List" untuk pemroses pembayaran (padanan task Jotform)."""
	if not users:
		return
	from frappe.desk.form.assign_to import add

	try:
		add(
			{
				"assign_to": users,
				"doctype": doc.doctype,
				"name": doc.name,
				"description": _("Bayar {0} sebelum {1}").format(_money(doc), doc.payment_date),
				"date": doc.payment_date,
				"priority": "High" if doc.urgency == "Urgent" else "Medium",
			},
			ignore_permissions=True,
		)
	except Exception:
		frappe.log_error(frappe.get_traceback(), "Request to Pay assign")


def _close_assignments(doc):
	for name in frappe.get_all(
		"ToDo",
		filters={"reference_type": doc.doctype, "reference_name": doc.name, "status": "Open"},
		pluck="name",
	):
		frappe.db.set_value("ToDo", name, "status", "Closed")
