# Notifikasi Request to Pay per perubahan status.
#
# Kenapa tidak memakai DocType Notification bawaan: penerima "by role" di sana mengabaikan
# company — approver MET Thailand ikut menerima email pengajuan RMI Indonesia. Di sini penerima
# = user ber-role tahap itu YANG company-nya mencakup company dokumen (User Permission Company;
# tanpa User Permission = semua company).
import frappe
from frappe import _
from frappe.utils import flt

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


STATE_LABEL = {
	"Pending Tax Review": "Menunggu tinjauan pajak",
	"Pending FAT Approval": "Menunggu persetujuan FAT",
	"Pending HOD Approval": "Menunggu persetujuan HOD",
	"Pending Global Approval": "Menunggu persetujuan Global",
	"Approved": "Disetujui",
	"Rejected": "Ditolak",
	"Paid": "Sudah dibayar",
}
STATE_TONE = {"Approved": "success", "Rejected": "danger", "Paid": "paid"}

# audiens → (judul, intro). {requester} sudah di-escape.
EMAIL_COPY = {
	"approver": ("Persetujuan Anda diperlukan", "<b>{requester}</b> mengajukan pembayaran dan sedang menunggu tinjauan Anda."),
	"payer": ("Siap dibayar", "Pengajuan dari <b>{requester}</b> sudah <b>disetujui</b>. Buat Purchase Invoice lalu Payment Entry sebelum jatuh tempo."),
	"finance": ("Pengajuan disetujui", "Pengajuan pembayaran dari <b>{requester}</b> sudah <b>disetujui</b>."),
	"req_approved": ("Pengajuan Anda disetujui", "Pengajuan pembayaran Anda sudah <b>disetujui</b> dan diteruskan ke Finance untuk dibayar."),
	"req_rejected": ("Pengajuan Anda ditolak", "Pengajuan pembayaran Anda <b>ditolak</b>. Lihat alasannya di bawah, perbaiki lalu ajukan ulang bila perlu."),
	"req_paid": ("Pengajuan Anda sudah dibayar", "Pembayaran untuk pengajuan Anda sudah <b>dilakukan</b>."),
}


def email_html(doc, audience):
	"""Email HTML (layout bersama stock_ops.email_ui) untuk satu audiens."""
	from stock_ops.email_ui import _items_cap, date, e, money, render

	title, intro = EMAIL_COPY[audience]
	state = doc.workflow_state
	requester = doc.requester_name or doc.requester
	purpose = " — ".join(x for x in (doc.payment_purpose, doc.purpose_detail) if x)
	rows = [
		(
			r.vendor_name or r.supplier or "-",
			" · ".join(x for x in (r.invoice_no and _("Invoice {0}").format(r.invoice_no), r.tax_type) if x),
			money(r.net_amount or r.amount, doc),
		)
		for r in doc.invoices or []
	]
	rows, more = _items_cap(rows)
	sub = ""
	if flt(doc.total_tax):
		sub = _("Nilai invoice {0} · pajak dipotong {1}").format(money(doc.total_amount, doc), money(doc.total_tax, doc))
	fields = [
		(_("Pemohon"), " · ".join(x for x in (requester, doc.department) if x)),
		(_("Jatuh tempo"), date(doc.payment_date), True),
		(_("Tujuan pembayaran"), purpose),
		(_("Business unit"), doc.business_unit),
		(_("Urgensi"), doc.urgency, doc.urgency == "Urgent"),
	]
	if state == "Paid":
		fields += [(_("Dibayar tanggal"), date(doc.paid_on), True), (_("Referensi pembayaran"), doc.payment_reference, True)]
	return render(
		kicker=_("Request to Pay"),
		title=_(title),
		intro=_(intro).format(requester=e(requester)),
		status=_(STATE_LABEL.get(state, state)),
		tone=STATE_TONE.get(state, "warn"),
		doc_name=doc.name,
		company=doc.company,
		urgent=doc.urgency == "Urgent" and state not in ("Rejected", "Paid"),
		amount=money(doc.total_payment, doc),
		amount_label=_("Total dibayarkan"),
		amount_sub=sub,
		fields=fields,
		note=doc.approval_note if state == "Rejected" else "",
		note_label=_("Alasan penolakan"),
		items=rows,
		items_more=more,
		items_title=_("Invoice / vendor"),
		cta_url=frappe.utils.get_url(APP_URL.format(name=doc.name)),
		cta_label=_("Tinjau pengajuan") if audience == "approver" else _("Buka pengajuan"),
		secondary_url=frappe.utils.get_url_to_form(doc.doctype, doc.name) if audience in ("payer", "finance") else "",
		preheader=f"{_(STATE_LABEL.get(state, state))} · {money(doc.total_payment, doc)} · {_('jatuh tempo')} {date(doc.payment_date)}",
	)


def _send(users, subject, body, doc, audience):
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
	try:
		frappe.sendmail(
			recipients=users,
			subject=subject,
			message=email_html(doc, audience),
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
		_send(
			users,
			f"{urgent}[{_('Perlu persetujuan')}] {doc.name} · {_money(doc)}",
			f"{summary} — {_(state)}",
			doc,
			"approver",
		)

	elif state == "Approved":
		payers = users_for("RTP Payment Processor", doc.company)
		_send(
			payers,
			f"[{_('Siap dibayar')}] {doc.name} · {_money(doc)} · {_('jatuh tempo')} {frappe.utils.formatdate(doc.payment_date)}",
			f"{summary} — {_('jatuh tempo')} {doc.payment_date}",
			doc,
			"payer",
		)
		_send(
			[u for u in users_for("RTP Finance", doc.company) if u not in payers],
			f"[{_('Disetujui')}] {doc.name} · {_money(doc)}",
			summary,
			doc,
			"finance",
		)
		_assign(payers, doc)
		_send([doc.requester], f"[{_('Disetujui')}] {_('Pengajuan Anda')} {doc.name}", summary, doc, "req_approved")

	elif state == "Rejected":
		note = doc.approval_note or "-"
		_send(
			[doc.requester],
			f"[{_('Ditolak')}] {_('Pengajuan Anda')} {doc.name}",
			f"{summary} — {_('Alasan')}: {note}",
			doc,
			"req_rejected",
		)

	elif state == "Paid":
		_close_assignments(doc)
		_send([doc.requester], f"[{_('Sudah dibayar')}] {_('Pengajuan Anda')} {doc.name}", summary, doc, "req_paid")


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
