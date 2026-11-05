# Menu HR di Stock Ops PWA: Klaim Biaya (Expense Claim) & Kasbon (Employee Advance) — app HRMS.
#
# Alur STANDAR HRMS (tidak diubah):
#   Expense Claim   : karyawan menyimpan draft (approval_status Draft) → dibagikan ke Expense Approver →
#                     approver isi approval_status Approved / Rejected lalu submit → Finance membayar dari
#                     Desk (Payment Entry) → status Unpaid → Paid otomatis oleh HRMS.
#   Employee Advance: karyawan menyimpan draft → Expense Approver submit (= disetujui) → Finance bayar →
#                     status Paid / Claimed / Returned dihitung HRMS. Ditolak = draft di-discard + alasan.
# Approver = Employee.expense_approver (fallback standar HRMS: approver pertama di Department).
# Tidak ada fallback ke Leave Approver: bila kosong, karyawan diminta menghubungi HR.
import frappe
from frappe import _
from frappe.utils import flt, getdate, today

KINDS = {"claim": "Expense Claim", "advance": "Employee Advance"}
MENU_KEYS = {"claim": "expense_claim", "advance": "employee_advance"}
APP_URL = "/stock_ops#/hr/{kind}/{name}"
HR_ADMIN_ROLES = {"HR Manager", "HR User", "System Manager"}


def hrms_installed():
	return "hrms" in frappe.get_installed_apps() and frappe.db.exists("DocType", "Expense Claim")


def _dt(kind):
	if kind not in KINDS:
		frappe.throw(_("Jenis tidak dikenal: {0}").format(kind))
	if not hrms_installed():
		frappe.throw(_("Aplikasi HRMS belum terpasang di server ini."))
	return KINDS[kind]


def my_employee(user=None):
	user = user or frappe.session.user
	return frappe.db.get_value(
		"Employee",
		{"user_id": user, "status": "Active"},
		["name", "employee_name", "company", "department", "expense_approver"],
		as_dict=True,
	)


def approver_of(emp):
	"""Expense Approver karyawan (standar HRMS): Employee.expense_approver → approver pertama Department."""
	if not emp:
		return None
	if emp.expense_approver:
		return emp.expense_approver
	if emp.department:
		return frappe.db.get_value(
			"Department Approver",
			{"parent": emp.department, "parentfield": "expense_approvers", "parenttype": "Department"},
			"approver",
			order_by="idx asc",
		)
	return None


def _is_hr_admin():
	return bool(HR_ADMIN_ROLES & set(frappe.get_roles())) or frappe.session.user == "Administrator"


def _team_employees(user=None):
	"""Karyawan yang Expense Approver-nya user ini (langsung, atau lewat Department bila kosong)."""
	user = user or frappe.session.user
	direct = frappe.get_all("Employee", filters={"expense_approver": user, "status": "Active"}, pluck="name")
	depts = frappe.get_all(
		"Department Approver",
		filters={"approver": user, "parentfield": "expense_approvers", "parenttype": "Department"},
		pluck="parent",
	)
	via_dept = []
	if depts:
		via_dept = frappe.get_all(
			"Employee",
			filters={"department": ["in", depts], "status": "Active", "expense_approver": ["in", ["", None]]},
			pluck="name",
		)
	return list(dict.fromkeys(direct + via_dept))


def _todo_filters(kind, user=None):
	user = user or frappe.session.user
	if kind == "claim":
		return {"docstatus": 0, "approval_status": "Draft", "expense_approver": user}
	team = _team_employees(user)
	return {"docstatus": 0, "employee": ["in", team or ["__none__"]]}


def hr_caps():
	"""Kemampuan menu HR user login — ikut bootstrap (menu Beranda + tab daftar)."""
	if not hrms_installed():
		return {"enabled": False}
	user = frappe.session.user
	emp = my_employee(user)
	approver = approver_of(emp)
	out = {"enabled": True, "employee": emp.name if emp else None, "employee_name": emp.employee_name if emp else None}
	out["approver"] = approver
	out["approver_name"] = frappe.utils.get_fullname(approver) if approver else None
	out["can_approve"] = "Expense Approver" in frappe.get_roles() or _is_hr_admin()
	for kind, dt in KINDS.items():
		out[kind] = {
			"can_request": bool(emp) and bool(frappe.has_permission(dt, "create")),
			"todo": frappe.db.count(dt, _todo_filters(kind, user)) if out["can_approve"] else 0,
		}
	return out


# ── setup form ──
@frappe.whitelist()
def get_hr_setup(kind):
	dt = _dt(kind)
	emp = my_employee()
	if not emp:
		frappe.throw(_("Akun Anda belum terhubung ke data Karyawan (Employee). Hubungi HR."))
	approver = approver_of(emp)
	currency = frappe.get_cached_value("Company", emp.company, "default_currency")
	out = {
		"doctype": dt,
		"employee": emp,
		"approver": approver,
		"approver_name": frappe.utils.get_fullname(approver) if approver else None,
		"currency": currency,
	}
	if kind == "claim":
		types = frappe.get_all("Expense Claim Type", pluck="name", order_by="name")
		with_acc = set(
			frappe.get_all(
				"Expense Claim Account", filters={"company": emp.company, "parenttype": "Expense Claim Type"}, pluck="parent"
			)
		)
		out["expense_types"] = [{"name": t, "has_account": t in with_acc} for t in types]
		out["advances"] = _open_advances(emp.name)
	return out


def _open_advances(employee):
	"""Kasbon yang sudah dibayar & masih ada sisa untuk dipotongkan ke klaim."""
	rows = frappe.get_all(
		"Employee Advance",
		filters={"employee": employee, "docstatus": 1, "status": ["in", ["Paid", "Partly Claimed and Returned"]]},
		fields=["name", "posting_date", "purpose", "paid_amount", "claimed_amount", "return_amount", "currency"],
		order_by="posting_date asc, creation asc",  # FIFO: kasbon terlama dipotong dulu
	)
	out = []
	for r in rows:
		r["unclaimed"] = flt(r.paid_amount) - flt(r.claimed_amount) - flt(r.return_amount)
		if r["unclaimed"] > 0:
			out.append(r)
	return out


# ── daftar & detail ──
@frappe.whitelist()
def list_hr(kind, scope="mine", txt=None, start=0, limit=20):
	dt = _dt(kind)
	start, limit = int(start or 0), min(int(limit or 20), 50)
	if scope == "todo":
		filters = _todo_filters(kind)
	else:
		emp = my_employee()
		filters = {"employee": emp.name if emp else "__none__"}
	or_filters = None
	if txt:
		like = f"%{txt}%"
		or_filters = {"name": ["like", like], "employee_name": ["like", like]}
		or_filters["remark" if kind == "claim" else "purpose"] = ["like", like]
	amount = "total_claimed_amount" if kind == "claim" else "advance_amount"
	fields = ["name", "employee", "employee_name", "posting_date", "status", "docstatus", "currency", f"{amount} as amount"]
	if kind == "claim":
		fields += ["approval_status", "grand_total", "remark as title"]
	else:
		fields += ["purpose as title", "paid_amount", "claimed_amount"]
	rows = frappe.get_all(
		dt,
		filters=filters,
		or_filters=or_filters,
		fields=fields,
		order_by="modified desc",
		start=start,
		limit_page_length=limit + 1,
		ignore_permissions=scope == "todo",  # baris "todo" sudah dibatasi ke tim approver ini
	)
	return {
		"items": rows[:limit],
		"has_more": len(rows) > limit,
		"todo": frappe.db.count(dt, _todo_filters(kind)) if hr_caps().get("can_approve") else 0,
	}


def _load(kind, name):
	dt = _dt(kind)
	doc = frappe.get_doc(dt, name)
	user = frappe.session.user
	emp = my_employee(user)
	mine = emp and doc.employee == emp.name
	is_approver = user == _approver_user(kind, doc)
	if not (mine or is_approver or _is_hr_admin() or frappe.has_permission(dt, "read", doc)):
		frappe.throw(_("Anda tidak berhak membuka dokumen ini."), frappe.PermissionError)
	return doc, bool(mine), bool(is_approver)


def _approver_user(kind, doc):
	if kind == "claim":
		return doc.expense_approver
	emp = frappe.db.get_value("Employee", doc.employee, ["name", "department", "expense_approver"], as_dict=True)
	return approver_of(emp)


def _actions(kind, doc, mine, is_approver):
	acts = []
	if doc.docstatus != 0:
		return acts
	pending = kind == "advance" or doc.approval_status == "Draft"
	if pending and (is_approver or _is_hr_admin()) and not mine:
		acts += ["Approve", "Reject"]
	if mine and pending:
		acts.append("Discard")
	return acts


@frappe.whitelist()
def get_hr(kind, name):
	doc, mine, is_approver = _load(kind, name)
	data = doc.as_dict(no_default_fields=False)
	appr = _approver_user(kind, doc)
	data["approver"] = appr
	data["approver_name"] = frappe.utils.get_fullname(appr) if appr else None
	files = frappe.get_all(
		"File",
		filters={"attached_to_doctype": doc.doctype, "attached_to_name": doc.name},
		fields=["name", "file_name", "file_url", "is_private"],
		order_by="creation asc",
	)
	history = frappe.get_all(
		"Comment",
		filters={"reference_doctype": doc.doctype, "reference_name": doc.name, "comment_type": ["in", ["Comment", "Info"]]},
		fields=["comment_type", "content", "owner", "creation"],
		order_by="creation asc",
	)
	import html

	for h in history:
		h["owner_name"] = frappe.utils.get_fullname(h.owner)
		h["content"] = html.unescape(frappe.utils.strip_html(h.content or "")).strip()
	return {
		"doc": data,
		"files": files,
		"history": history,
		"mine": mine,
		"can_edit": mine and doc.docstatus == 0 and (kind == "advance" or doc.approval_status == "Draft"),
		"actions": _actions(kind, doc, mine, is_approver),
	}


# ── simpan (karyawan) ──
@frappe.whitelist(methods=["POST"])
def save_hr(kind, data):
	dt = _dt(kind)
	data = frappe.parse_json(data) or {}
	emp = my_employee()
	if not emp:
		frappe.throw(_("Akun Anda belum terhubung ke data Karyawan (Employee). Hubungi HR."))
	approver = approver_of(emp)
	if not approver:
		frappe.throw(_("Expense Approver Anda belum diisi. Hubungi HR untuk mengisinya di data Karyawan."))
	if approver == frappe.session.user:
		frappe.throw(_("Expense Approver Anda adalah diri sendiri. Hubungi HR untuk menggantinya."))

	if data.get("name"):
		doc = frappe.get_doc(dt, data["name"])
		if doc.employee != emp.name or doc.docstatus != 0 or (kind == "claim" and doc.approval_status != "Draft"):
			frappe.throw(_("Dokumen ini tidak bisa diubah lagi."))
		is_new = False
	else:
		doc = frappe.new_doc(dt)
		doc.employee = emp.name
		doc.company = emp.company
		doc.posting_date = today()
		is_new = True
	doc.currency = frappe.get_cached_value("Company", emp.company, "default_currency")
	if doc.meta.has_field("exchange_rate"):
		doc.exchange_rate = 1

	if kind == "claim":
		_fill_claim(doc, data, emp, approver)
	else:
		_fill_advance(doc, data)
	doc.save()
	if kind == "advance":
		# HRMS membagikan Expense Claim ke approver (share_doc_with_approver), tapi tidak Employee Advance.
		# Tanpa share, approver yang dibatasi User Permission Employee-nya sendiri tak bisa membuka/submit.
		frappe.share.add_docshare(
			dt, doc.name, approver, read=1, write=1, submit=1, flags={"ignore_share_permission": True}
		)
	if is_new:
		_notify(
			[approver],
			"[{0}] {1} {2} · {3}".format(_("Perlu persetujuan"), _label(kind), doc.name, emp.employee_name),
			_summary(kind, doc),
			kind,
			doc,
			"new",
		)
	return {"name": doc.name, "status": doc.status}


def _fill_claim(doc, data, emp, approver):
	rows = data.get("expenses") or []
	if not rows:
		frappe.throw(_("Tambahkan minimal satu baris biaya."))
	doc.expense_approver = approver
	doc.department = emp.department
	doc.remark = (data.get("remark") or "").strip() or None
	# Default company — sama dengan form HRMS (get_company_cost_center_and_expense_account):
	# tanpa payable account & cost center, approver gagal submit ("Cost Center is required").
	co = frappe.get_cached_value("Company", emp.company, ["cost_center", "default_expense_claim_payable_account"], as_dict=True)
	doc.payable_account = doc.payable_account or co.default_expense_claim_payable_account
	doc.cost_center = doc.cost_center or co.cost_center
	doc.set("expenses", [])
	for i, r in enumerate(rows, 1):
		amount = flt(r.get("amount"))
		if amount <= 0:
			frappe.throw(_("Baris {0}: nominal harus lebih dari 0.").format(i))
		if not r.get("expense_type"):
			frappe.throw(_("Baris {0}: pilih jenis biaya.").format(i))
		d = r.get("expense_date") or today()
		if getdate(d) > getdate(today()):
			frappe.throw(_("Baris {0}: tanggal biaya tidak boleh di masa depan.").format(i))
		doc.append(
			"expenses",
			{
				"expense_date": d,
				"expense_type": r["expense_type"],
				"description": (r.get("description") or "").strip() or r["expense_type"],
				"amount": amount,
				"sanctioned_amount": amount,
				"cost_center": doc.cost_center,
			},
		)
	# Potong dari kasbon yang masih bersisa (standar HRMS: tabel advances, alokasi berurutan).
	doc.set("advances", [])
	if data.get("use_advances"):
		left = sum(flt(r.amount) for r in doc.expenses)
		for adv in _open_advances(emp.name):
			if left <= 0:
				break
			alloc = min(left, adv["unclaimed"])
			doc.append(
				"advances",
				{
					"employee_advance": adv["name"],
					"posting_date": adv["posting_date"],
					"advance_paid": adv["paid_amount"],
					"unclaimed_amount": adv["unclaimed"],
					"allocated_amount": alloc,
					"advance_account": frappe.db.get_value("Employee Advance", adv["name"], "advance_account"),
				},
			)
			left -= alloc


def _fill_advance(doc, data):
	amount = flt(data.get("advance_amount"))
	if amount <= 0:
		frappe.throw(_("Nominal kasbon harus lebih dari 0."))
	purpose = (data.get("purpose") or "").strip()
	if not purpose:
		frappe.throw(_("Tuliskan keperluan kasbon."))
	doc.advance_amount = amount
	doc.purpose = purpose


# ── aksi approver / karyawan ──
@frappe.whitelist(methods=["POST"])
def hr_action(kind, name, action, note=None):
	doc, mine, is_approver = _load(kind, name)
	note = (note or "").strip()
	allowed = _actions(kind, doc, mine, is_approver)
	if action not in allowed:
		frappe.throw(_("Aksi {0} tidak tersedia untuk dokumen ini.").format(action), frappe.PermissionError)
	if action == "Reject" and not note:
		frappe.throw(_("Tuliskan alasan penolakan."))
	if action in ("Approve", "Reject") and not frappe.has_permission(doc.doctype, "submit", doc):
		frappe.throw(
			_("Anda belum punya role Expense Approver untuk menyetujui. Hubungi HR / admin."), frappe.PermissionError
		)
	employee_user = frappe.db.get_value("Employee", doc.employee, "user_id")

	if kind == "claim" and action in ("Approve", "Reject"):
		doc.approval_status = "Approved" if action == "Approve" else "Rejected"
		for r in doc.expenses:
			if action == "Approve" and not flt(r.sanctioned_amount):
				r.sanctioned_amount = r.amount
		doc.submit()
	elif kind == "advance" and action == "Approve":
		doc.submit()
	else:  # Reject kasbon / Discard oleh karyawan → draft dibuang (status Cancelled), tidak dihapus
		doc.discard()
	if note:
		doc.add_comment("Comment", f"{_(action)}: {note}")
	doc.reload()

	if action in ("Approve", "Reject") and employee_user:
		tag = _("Disetujui") if action == "Approve" else _("Ditolak")
		body = _summary(kind, doc) + (f" — {_('Alasan')}: {note}" if action == "Reject" else "")
		_notify(
			[employee_user],
			"[{0}] {1} {2} {3}".format(tag, _label(kind), _("Anda"), doc.name),
			body,
			kind,
			doc,
			"approved" if action == "Approve" else "rejected",
			note,
		)
	return {"name": doc.name, "status": doc.status, "docstatus": doc.docstatus}


@frappe.whitelist()
def get_hr_file(kind, name, file_url):
	doc, _mine, _appr = _load(kind, name)
	f = frappe.get_doc("File", {"file_url": file_url, "attached_to_doctype": doc.doctype, "attached_to_name": doc.name})
	frappe.local.response.filename = f.file_name
	with open(f.get_full_path(), "rb") as fh:
		frappe.local.response.filecontent = fh.read()
	frappe.local.response.type = "download"


# ── notifikasi (in-app + push + email singkat) ──
def _label(kind):
	return _("Klaim biaya") if kind == "claim" else _("Kasbon")


def _summary(kind, doc):
	amount = doc.total_claimed_amount if kind == "claim" else doc.advance_amount
	money = frappe.format_value(amount, {"fieldtype": "Currency", "options": "currency"}, doc)
	what = (doc.remark or "") if kind == "claim" else (doc.purpose or "")
	return " · ".join(x for x in (doc.name, doc.employee_name, money, what[:80]) if x)


HR_EMAIL = {
	# event: (tone, status, judul, intro)
	"new": ("warn", "Menunggu persetujuan", "Persetujuan Anda diperlukan",
		"<b>{employee}</b> mengajukan {what} dan menunggu keputusan Anda sebagai Expense Approver."),
	"approved": ("success", "Disetujui · menunggu pembayaran", "{What} Anda disetujui",
		"{What} Anda sudah <b>disetujui</b>. Pembayaran akan diproses oleh Finance."),
	"rejected": ("danger", "Ditolak", "{What} Anda ditolak",
		"{What} Anda <b>ditolak</b>. Lihat alasannya di bawah."),
}


def email_html(kind, doc, event, note=""):
	from stock_ops.email_ui import _items_cap, date, e, money, render

	tone, status, title, intro = HR_EMAIL[event]
	what = _label(kind)
	fmt = {"employee": e(doc.employee_name), "what": e(what.lower()), "What": e(what)}
	approver = _approver_user(kind, doc) if event == "new" else None
	fields = [
		(_("Karyawan"), " · ".join(x for x in (doc.employee_name, doc.get("department")) if x)),
		(_("Tanggal pengajuan"), date(doc.posting_date)),
	]
	rows, more = [], 0
	if kind == "claim":
		amount = doc.total_claimed_amount
		fields += [
			(_("Dipotong kasbon"), money(doc.total_advance_amount, doc) if flt(doc.total_advance_amount) else ""),
			(_("Catatan"), doc.remark),
		]
		rows, more = _items_cap(
			[
				(r.expense_type, " · ".join(x for x in (date(r.expense_date), r.description if r.description != r.expense_type else "") if x), money(r.amount, doc))
				for r in doc.expenses or []
			]
		)
	else:
		amount = doc.advance_amount
		fields += [(_("Keperluan"), doc.purpose, True)]
	if approver:
		fields.append((_("Expense Approver"), frappe.utils.get_fullname(approver)))
	return render(
		kicker=what,
		title=_(title).format(**fmt),
		intro=_(intro).format(**fmt),
		status=_(status),
		tone=tone,
		doc_name=doc.name,
		company=doc.company,
		amount=money(amount, doc),
		amount_label=_("Total klaim") if kind == "claim" else _("Nominal kasbon"),
		fields=fields,
		note=note if event == "rejected" else "",
		note_label=_("Alasan penolakan"),
		items=rows,
		items_more=more,
		items_title=_("Rincian biaya"),
		cta_url=frappe.utils.get_url(APP_URL.format(kind=kind, name=doc.name)),
		cta_label=_("Setujui / Tolak di Stock Ops") if event == "new" else _("Lihat pengajuan"),
		preheader=f"{_(status)} · {doc.name} · {money(amount, doc)}",
	)


def _notify(users, subject, body, kind, doc, event="new", note=""):
	users = [u for u in users if u and u not in ("Guest",)]
	if not users:
		return
	from frappe.desk.doctype.notification_log.notification_log import enqueue_create_notification

	url = APP_URL.format(kind=kind, name=doc.name)
	try:
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
	except Exception:
		frappe.log_error(frappe.get_traceback(), "Stock Ops HR notify")
	try:
		frappe.sendmail(
			recipients=users,
			subject=subject,
			message=email_html(kind, doc, event, note),
			reference_doctype=doc.doctype,
			reference_name=doc.name,
		)
	except Exception:
		frappe.log_error(frappe.get_traceback(), "Stock Ops HR email")
	try:
		from stock_ops.push import send_to_user

		for u in users:
			send_to_user(u, subject, body, url)
	except Exception:
		frappe.log_error(frappe.get_traceback(), "Stock Ops HR push")
