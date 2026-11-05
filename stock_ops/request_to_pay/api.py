# API Request to Pay untuk PWA Stock Ops (online-only; bukan antrean offline seperti dokumen stok).
#
# Penegakan akses berlapis:
#   1. Izin DocType (role RTP; RTP Requester hanya dokumen miliknya — if_owner).
#   2. Lingkup company user (User Permission Company → _assert_company_allowed / _company_filter).
#   3. Workflow: transisi hanya untuk role tahap itu (+ kondisi, + larangan self-approval di Global).
import html
import json

import frappe
from frappe import _
from frappe.utils import cint

DT = "Request to Pay"
RTP_ROLES = (
	"RTP Requester",
	"RTP Tax Reviewer",
	"RTP FAT Approver",
	"RTP HOD Approver",
	"RTP Global Approver",
	"RTP Payment Processor",
	"RTP Finance",
)
# state → role yang bertindak di state itu (antrean "Perlu Tindakan")
STATE_ROLE = {
	"Pending Tax Review": "RTP Tax Reviewer",
	"Pending FAT Approval": "RTP FAT Approver",
	"Pending HOD Approval": "RTP HOD Approver",
	"Pending Global Approval": "RTP Global Approver",
	"Approved": "RTP Payment Processor",
}
LIST_FIELDS = [
	"name",
	"company",
	"requester",
	"requester_name",
	"department",
	"business_unit",
	"payment_purpose",
	"urgency",
	"payment_date",
	"currency",
	"total_payment",
	"workflow_state",
	"docstatus",
	"creation",
	"modified",
]
INVOICE_FIELDS = (
	"supplier",
	"vendor_name",
	"invoice_no",
	"invoice_file",
	"amount",
	"tax_withheld",
	"tax_type",
	"tax_id",
	"tax_rate",
	"notes",
)
HEADER_FIELDS = (
	"company",
	"employee",
	"department",
	"position",
	"business_unit",
	"payment_purpose",
	"purpose_detail",
	"urgency",
	"payment_date",
)


def _scope():
	from stock_ops.api import _allowed_companies

	return _allowed_companies()


def _assert_company(company):
	from stock_ops.api import _assert_company_allowed

	_assert_company_allowed(company)


def _my_roles():
	roles = set(frappe.get_roles())
	if "System Manager" in roles or frappe.session.user == "Administrator":
		return set(RTP_ROLES)
	return roles & set(RTP_ROLES)


def _act_states(roles=None):
	roles = _my_roles() if roles is None else roles
	return [s for s, r in STATE_ROLE.items() if r in roles]


def rtp_caps():
	"""Kemampuan Request to Pay user login (dipakai PWA untuk menampilkan menu & tab)."""
	if not frappe.db.exists("DocType", DT):
		return {"enabled": False}
	roles = _my_roles()
	states = _act_states(roles)
	todo = 0
	if states:
		filters = {"workflow_state": ["in", states]}
		scope = _scope()
		if scope:
			filters["company"] = ["in", scope]
		todo = frappe.db.count(DT, filters)
	return {
		"enabled": bool(roles),
		"roles": sorted(roles),
		"can_request": "RTP Requester" in roles,
		"act_states": states,
		"can_view_all": bool(roles - {"RTP Requester"}),
		"todo": todo,
	}


@frappe.whitelist()
def get_rtp_setup(company=None):
	"""Pilihan form: company dalam lingkup, departemen & unit bisnis per company, tujuan pembayaran,
	serta isian awal dari data Employee / pengajuan terakhir user."""
	scope = _scope()
	co_filters = {"name": ["in", scope]} if scope else {}
	companies = frappe.get_all("Company", filters=co_filters, fields=["name", "abbr", "default_currency"], order_by="name")
	names = [c.name for c in companies]
	user = frappe.session.user

	last = frappe.get_all(
		DT,
		filters={"requester": user},
		fields=["company", "department", "position", "business_unit", "employee"],
		order_by="creation desc",
		limit=1,
	)
	last = last[0] if last else {}
	emp = frappe.db.get_value(
		"Employee", {"user_id": user, "status": "Active"}, ["name", "company", "department", "designation"], as_dict=True
	)
	if not company or company not in names:
		company = (last.get("company") if last.get("company") in names else None) or (
			emp.company if emp and emp.company in names else None
		) or (names[0] if len(names) == 1 else None)

	cc_filters = {"company": company, "is_group": 0}
	if frappe.get_meta("Cost Center").has_field("disabled"):
		cc_filters["disabled"] = 0
	defaults = {}
	if company:
		src = last if last.get("company") == company else {}
		defaults = {
			"department": src.get("department") or (emp.department if emp and emp.company == company else None),
			"position": src.get("position") or (emp.designation if emp else None),
			"business_unit": src.get("business_unit"),
			"employee": emp.name if emp and emp.company == company else None,
		}
	return {
		"companies": companies,
		"company": company,
		"departments": frappe.get_all(
			"Department", filters={"company": company, "is_group": 0}, pluck="name", order_by="name"
		)
		if company
		else [],
		"business_units": frappe.get_all("Cost Center", filters=cc_filters, fields=["name", "cost_center_name"], order_by="name")
		if company
		else [],
		"purposes": frappe.get_all(
			"Request to Pay Purpose", filters={"disabled": 0}, fields=["name", "is_other"], order_by="creation asc"
		),
		"suppliers": frappe.get_all(
			"Supplier", filters={"disabled": 0}, fields=["name", "supplier_name", "tax_id"], order_by="supplier_name", limit=2000
		),
		"defaults": defaults,
		"caps": rtp_caps(),
	}


@frappe.whitelist()
def list_rtp(scope="mine", company=None, state=None, txt=None, start=0, limit=20):
	"""Daftar pengajuan. scope: mine (milik saya) · todo (menunggu tindakan saya) · all (semua yang boleh saya lihat)."""
	from stock_ops.api import _company_filter

	filters = {}
	co = _company_filter(company)
	if co:
		filters["company"] = co
	if scope == "mine":
		filters["requester"] = frappe.session.user
	elif scope == "todo":
		states = _act_states()
		if not states:
			return {"items": [], "has_more": False, "todo": 0}
		filters["workflow_state"] = ["in", states] if not state or state not in states else state
	elif scope != "all":
		frappe.throw(_("Scope tidak dikenal: {0}").format(scope))
	if state and scope != "todo":
		filters["workflow_state"] = state
	or_filters = None
	if txt:
		like = f"%{txt.strip()}%"
		or_filters = [["name", "like", like], ["requester_name", "like", like], ["payment_purpose", "like", like]]
	limit = min(cint(limit) or 20, 100)
	rows = frappe.get_list(
		DT,
		filters=filters,
		or_filters=or_filters,
		fields=LIST_FIELDS,
		order_by="creation desc",
		limit_start=cint(start),
		limit_page_length=limit + 1,
	)
	for r in rows:
		r["invoice_count"] = frappe.db.count("Request to Pay Invoice", {"parent": r.name, "parenttype": DT})
		r["vendors"] = ", ".join(
			dict.fromkeys(
				frappe.get_all(
					"Request to Pay Invoice", filters={"parent": r.name, "parenttype": DT}, pluck="vendor_name", order_by="idx"
				)
			)
		)
	return {"items": rows[:limit], "has_more": len(rows) > limit, "todo": rtp_caps().get("todo", 0)}


def _load(name, ptype="read"):
	doc = frappe.get_doc(DT, name)
	doc.check_permission(ptype)
	_assert_company(doc.company)
	return doc


@frappe.whitelist()
def get_rtp(name):
	"""Detail pengajuan + aksi Workflow yang boleh dijalankan user + riwayat persetujuan."""
	from frappe.model.workflow import get_transitions

	doc = _load(name)
	try:
		actions = [t.action for t in get_transitions(doc)]
	except Exception:
		actions = []
	history = frappe.get_all(
		"Comment",
		filters={"reference_doctype": DT, "reference_name": name, "comment_type": ["in", ["Workflow", "Comment", "Info"]]},
		fields=["comment_type", "content", "owner", "creation"],
		order_by="creation asc",
	)
	for h in history:
		h["owner_name"] = frappe.utils.get_fullname(h.owner)
		# Comment disimpan ter-escape/HTML ("&amp;", "<p>") → kirim teks polos; PWA menampilkannya sebagai teks.
		h["content"] = html.unescape(frappe.utils.strip_html(h.content or "")).strip()
	data = doc.as_dict(no_default_fields=False)
	data["invoices"] = [
		{k: row.get(k) for k in (*INVOICE_FIELDS, "name", "idx", "tax_amount", "net_amount", "purchase_invoice")}
		for row in doc.invoices
	]
	# Status Purchase Invoice per baris (dibuat Finance di Desk) — ditampilkan apa adanya di aplikasi.
	from stock_ops.request_to_pay.accounting import billing_status

	pis = {s["row"]: s["pi"] for s in billing_status(doc) if s["pi"]}
	for inv in data["invoices"]:
		pi = pis.get(inv["name"])
		inv["pi_status"] = pi.status if pi else None
		inv["pi_outstanding"] = pi.outstanding_amount if pi else None
	if pis:
		# "Mark as Paid" manual tidak berlaku lagi — Paid mengikuti pelunasan PI.
		actions = [a for a in actions if a != "Mark as Paid"]
	return {
		"doc": data,
		"actions": list(dict.fromkeys(actions)),
		"can_edit": _can_edit(doc),
		"history": history,
	}


def _can_edit(doc):
	"""Draft: pengaju. State pending: role tahap itu (mis. Tax Reviewer memperbaiki tarif pajak)."""
	if doc.docstatus != 0:
		return False
	state = doc.workflow_state or "Draft"
	if state == "Draft":
		return doc.requester == frappe.session.user or "System Manager" in frappe.get_roles()
	role = STATE_ROLE.get(state)
	return bool(role and role in _my_roles())


@frappe.whitelist()
def save_rtp(data, submit=0):
	"""Buat / ubah pengajuan. `data` = header + `invoices` (list). File invoice diunggah terpisah
	(upload_file → doctype Request to Pay) lalu URL-nya dikirim di `invoice_file`.
	submit=1 → langsung ajukan (aksi Workflow "Submit")."""
	data = json.loads(data) if isinstance(data, str) else (data or {})
	name = data.get("name")
	if name:
		doc = _load(name, "write")
		if not _can_edit(doc):
			frappe.throw(_("Pengajuan {0} tidak bisa diubah pada status {1}.").format(name, _(doc.workflow_state)))
	else:
		if "RTP Requester" not in _my_roles():
			frappe.throw(_("Anda tidak punya role RTP Requester."), frappe.PermissionError)
		doc = frappe.new_doc(DT)
		doc.requester = frappe.session.user

	for k in HEADER_FIELDS:
		if k in data:
			doc.set(k, data.get(k) or None)
	_assert_company(doc.company)

	if "invoices" in data:
		existing = {r.name: r for r in doc.invoices}
		rows = []
		for inv in data.get("invoices") or []:
			row = existing.get(inv.get("name")) if inv.get("name") else None
			vals = {k: inv.get(k) for k in INVOICE_FIELDS if k in inv}
			vals["tax_withheld"] = cint(vals.get("tax_withheld"))
			if vals.get("invoice_file"):
				_check_file(vals["invoice_file"], doc)
			if row:
				row.update(vals)
				rows.append(row)
			else:
				rows.append(vals)
		doc.set("invoices", [])
		for r in rows:
			doc.append("invoices", r if isinstance(r, dict) else r.as_dict())

	doc.save()
	if cint(submit) and (doc.workflow_state or "Draft") == "Draft":
		from frappe.model.workflow import apply_workflow

		doc = apply_workflow(doc, "Submit")
	return {"name": doc.name, "workflow_state": doc.workflow_state, "invoices": [r.name for r in doc.invoices]}


def _check_file(url, doc):
	"""File invoice harus lampiran dokumen ini (atau unggahan user ini yang belum terlampir)."""
	f = frappe.db.get_value("File", {"file_url": url}, ["name", "attached_to_doctype", "attached_to_name", "owner"], as_dict=True)
	if not f:
		frappe.throw(_("File invoice tidak ditemukan: {0}").format(url))
	if f.attached_to_doctype == DT and f.attached_to_name == doc.name:
		return
	if not f.attached_to_doctype and f.owner == frappe.session.user:
		return
	frappe.throw(_("File invoice bukan milik pengajuan ini: {0}").format(url), frappe.PermissionError)


@frappe.whitelist()
def apply_rtp_action(name, action, note=None, payment_reference=None):
	"""Jalankan aksi Workflow (Submit / Approve / Reject / Mark as Paid / Reopen).
	Reject wajib alasan — dikirim ke pengaju."""
	from frappe.model.workflow import apply_workflow

	doc = _load(name)
	note = (note or "").strip()
	if action == "Reject" and not note:
		frappe.throw(_("Tuliskan alasan penolakan."))
	# apply_workflow memuat ulang dokumen dari DB → tulis catatan ke DB lebih dulu.
	if note or action in ("Approve", "Reject"):
		doc.db_set("approval_note", note or None, update_modified=False)
	if action == "Mark as Paid" and payment_reference:
		doc.db_set("payment_reference", payment_reference.strip(), update_modified=False)
	doc = apply_workflow(doc, action)
	if note:
		doc.add_comment("Comment", f"{_(action)}: {note}")
	return {"name": doc.name, "workflow_state": doc.workflow_state, "docstatus": doc.docstatus}


@frappe.whitelist()
def get_rtp_file(name, file_url):
	"""Isi file invoice (untuk pratinjau di aplikasi; APK tak bisa memakai URL /private langsung)."""
	doc = _load(name)
	if file_url not in {r.invoice_file for r in doc.invoices}:
		frappe.throw(_("File tidak terkait pengajuan ini."), frappe.PermissionError)
	f = frappe.get_doc("File", {"file_url": file_url})
	frappe.local.response.filename = f.file_name
	with open(f.get_full_path(), "rb") as fh:
		frappe.local.response.filecontent = fh.read()
	frappe.local.response.type = "download"
