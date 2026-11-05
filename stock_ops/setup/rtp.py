# Setup Request to Pay — role, Workflow persetujuan berjenjang, tujuan pembayaran awal.
# Idempoten: dipanggil dari after_install / after_migrate (setup/install.py).
import frappe

ROLES = [
	# (role, desk_access) — semua bisa memakai PWA Stock Ops; Finance & admin juga lewat Desk.
	("RTP Requester", 0),
	("RTP Tax Reviewer", 0),
	("RTP FAT Approver", 0),
	("RTP HOD Approver", 0),
	("RTP Global Approver", 0),
	("RTP Payment Processor", 1),
	("RTP Finance", 1),
]

WORKFLOW_NAME = "Request to Pay Approval"

_STATES = [
	# (state, docstatus, allow_edit, style)
	("Draft", "0", "RTP Requester", ""),
	("Pending Tax Review", "0", "RTP Tax Reviewer", "Warning"),
	("Pending FAT Approval", "0", "RTP FAT Approver", "Warning"),
	("Pending HOD Approval", "0", "RTP HOD Approver", "Warning"),
	("Pending Global Approval", "0", "RTP Global Approver", "Warning"),
	("Approved", "1", "RTP Payment Processor", "Success"),
	("Paid", "1", "RTP Payment Processor", "Primary"),
	("Rejected", "0", "RTP Requester", "Danger"),
]

_ACTIONS = ["Submit", "Approve", "Reject", "Mark as Paid", "Reopen"]

_TRANSITIONS = [
	# (from, action, to, role, condition, allow_self_approval)
	("Draft", "Submit", "Pending Tax Review", "RTP Requester", "", 1),
	("Pending Tax Review", "Approve", "Pending FAT Approval", "RTP Tax Reviewer", "", 1),
	("Pending Tax Review", "Reject", "Rejected", "RTP Tax Reviewer", "", 1),
	# Satu aksi "Approve" dengan dua tujuan — kondisi memilih cabang (lihat needs_hod_approval).
	("Pending FAT Approval", "Approve", "Pending Global Approval", "RTP FAT Approver", "not doc.requires_hod", 1),
	("Pending FAT Approval", "Approve", "Pending HOD Approval", "RTP FAT Approver", "doc.requires_hod", 1),
	("Pending FAT Approval", "Reject", "Rejected", "RTP FAT Approver", "", 1),
	("Pending HOD Approval", "Approve", "Pending Global Approval", "RTP HOD Approver", "", 1),
	("Pending HOD Approval", "Reject", "Rejected", "RTP HOD Approver", "", 1),
	# Gerbang uang terakhir: pengaju tidak boleh menyetujui pengajuannya sendiri.
	("Pending Global Approval", "Approve", "Approved", "RTP Global Approver", "", 0),
	("Pending Global Approval", "Reject", "Rejected", "RTP Global Approver", "", 1),
	("Approved", "Mark as Paid", "Paid", "RTP Payment Processor", "", 1),
	("Rejected", "Reopen", "Draft", "RTP Requester", "", 1),
]

# Kategori dari form Jotform. "Others / Lainnya" wajib diberi keterangan.
_PURPOSES = [
	("Payment For Services / Pembayaran Jasa", 0),
	("Purchase Of Goods / Pembelian Barang", 0),
	("Tax / Pajak", 0),
	("Electricity / Listrik", 0),
	("Utilities / Utilitas", 0),
	("Food and Beverage / Makanan atau Minuman", 0),
	("Fuel / Bahan Bakar", 0),
	("Others / Lainnya", 1),
]


def setup_request_to_pay():
	if not frappe.db.exists("DocType", "Request to Pay"):
		return
	for role, desk in ROLES:
		if not frappe.db.exists("Role", role):
			frappe.get_doc({"doctype": "Role", "role_name": role, "desk_access": desk}).insert(ignore_permissions=True)
	_setup_workflow()
	for name, is_other in _PURPOSES:
		if not frappe.db.exists("Request to Pay Purpose", name):
			frappe.get_doc(
				{"doctype": "Request to Pay Purpose", "purpose_name": name, "is_other": is_other}
			).insert(ignore_permissions=True)
	_grant_masters()
	_init_setting_defaults()
	from stock_ops.request_to_pay.accounting import ensure_custom_fields

	ensure_custom_fields()
	frappe.db.commit()


# Field baru di Single "Stock Ops Settings" belum punya baris di tabSingles setelah migrate.
# Saat admin menyimpan Settings, field itu ikut tersimpan 0 (Check kosong) — menu Request to Pay
# hilang & "Urgent Lewati HOD" mati diam-diam. Maka tulis nilai default-nya sekali, bila belum ada.
_SETTING_DEFAULTS = {
	"show_request_to_pay": 1,
	"rtp_hod_skip_urgent": 1,
	# Menu HR (Klaim Biaya / Kasbon) — hanya tampil bila HRMS terpasang & user terhubung ke Employee.
	"show_expense_claim": 1,
	"show_employee_advance": 1,
}


def _init_setting_defaults():
	if not frappe.db.exists("DocType", "Stock Ops Settings"):
		return
	stored = frappe.db.get_singles_dict("Stock Ops Settings") or {}
	for field, value in _SETTING_DEFAULTS.items():
		if field not in stored:
			frappe.db.set_single_value("Stock Ops Settings", field, value)


def _setup_workflow():
	for state, _ds, _ae, style in _STATES:
		if not frappe.db.exists("Workflow State", state):
			frappe.get_doc({"doctype": "Workflow State", "workflow_state_name": state, "style": style}).insert(
				ignore_permissions=True
			)
	for action in _ACTIONS:
		if not frappe.db.exists("Workflow Action Master", action):
			frappe.get_doc({"doctype": "Workflow Action Master", "workflow_action_name": action}).insert(
				ignore_permissions=True
			)

	if frappe.db.exists("Workflow", WORKFLOW_NAME):
		wf = frappe.get_doc("Workflow", WORKFLOW_NAME)
		wf.set("states", [])
		wf.set("transitions", [])
	else:
		wf = frappe.new_doc("Workflow")
		wf.workflow_name = WORKFLOW_NAME
	wf.document_type = "Request to Pay"
	wf.is_active = 1
	wf.override_status = 0
	wf.workflow_state_field = "workflow_state"
	# Email Workflow Action bawaan mengabaikan company → notifikasi ditangani notify.py.
	wf.send_email_alert = 0
	for state, docstatus, allow_edit, _style in _STATES:
		wf.append("states", {"state": state, "doc_status": docstatus, "allow_edit": allow_edit})
	for frm, action, to, role, cond, self_ok in _TRANSITIONS:
		wf.append(
			"transitions",
			{
				"state": frm,
				"action": action,
				"next_state": to,
				"allowed": role,
				"condition": cond or None,
				"allow_self_approval": self_ok,
			},
		)
	wf.save(ignore_permissions=True)


def _grant_masters():
	"""Role RTP perlu membaca master yang dipilih di form (company, departemen, cost center, ...)."""
	from stock_ops.setup.install import _grant

	for dt in ("Company", "Department", "Cost Center", "Supplier", "Currency"):
		for role, _desk in ROLES:
			_grant(dt, role, {"read": 1})
