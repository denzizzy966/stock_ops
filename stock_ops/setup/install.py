import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.permissions import add_permission, update_permission_property

# Custom field untuk idempotensi sync dari Stock Ops PWA.
# Diisi UUID (localId) yang dibuat di klien; dipakai untuk mencegah duplikasi saat retry.
LOCALID_FIELD = {
	"fieldname": "external_localid",
	"label": "External Local ID",
	"fieldtype": "Data",
	"unique": 1,
	"no_copy": 1,
	"hidden": 1,
	"read_only": 1,
	"print_hide": 1,
	"insert_after": "amended_from",
	"description": "Client-generated UUID dari Stock Ops PWA (idempotensi sync offline).",
}

GEO_FIELD = {
	"fieldname": "stock_ops_geolocation",
	"label": "Geolocation (Stock Ops)",
	"fieldtype": "Data",
	"read_only": 1,
	"no_copy": 1,
	"print_hide": 1,
	"insert_after": "external_localid",
	"description": "Koordinat 'lat,lng' saat transaksi dibuat dari Stock Ops PWA.",
}

APPROVER_FIELD = {
	"fieldname": "stock_ops_approver",
	"label": "Approver (Stock Ops)",
	"fieldtype": "Link",
	"options": "User",
	"read_only": 1,
	"no_copy": 1,
	"print_hide": 1,
	"insert_after": "stock_ops_geolocation",
	"description": "Line manager (leave approver) yang menyetujui permintaan pembelian.",
}

APPROVAL_NOTE_FIELD = {
	"fieldname": "stock_ops_approval_note",
	"label": "Approval Note (Stock Ops)",
	"fieldtype": "Small Text",
	"read_only": 1,
	"no_copy": 1,
	"print_hide": 1,
	"insert_after": "stock_ops_approver",
	"description": "Catatan persetujuan/penolakan dari aplikasi Stock Ops.",
}

# Material Request TIDAK punya field remarks bawaan → tambahkan agar catatan/remark dari
# aplikasi tersimpan. (Stock Entry & Purchase Receipt sudah punya `remarks` bawaan.)
MR_REMARKS_FIELD = {
	"fieldname": "remarks",
	"label": "Remarks",
	"fieldtype": "Small Text",
	"no_copy": 1,
	"insert_after": "stock_ops_approval_note",
	"description": "Catatan/keterangan dari aplikasi Stock Ops.",
}

# Quotation (penawaran penjualan) TIDAK punya field remarks bawaan → tambahkan untuk
# menyimpan catatan dari aplikasi. (Diverifikasi: quotation.json tidak punya `remarks`.)
QTN_REMARKS_FIELD = {
	"fieldname": "remarks",
	"label": "Remarks",
	"fieldtype": "Small Text",
	"no_copy": 1,
	"insert_after": "external_localid",
	"description": "Catatan/keterangan dari aplikasi Stock Ops (Quotation).",
}

# Tujuan Stock Out (Material Issue) — dipetakan ke cost center di Stock Ops Settings.
PURPOSE_FIELD = {
	"fieldname": "stock_ops_purpose",
	"label": "Tujuan (Stock Ops)",
	"fieldtype": "Data",
	"no_copy": 1,
	"in_standard_filter": 1,
	"insert_after": "stock_ops_geolocation",
	"description": "Tujuan barang keluar dari aplikasi Stock Ops; menentukan cost center (Stock Ops Settings).",
}

CUSTOM_FIELDS = {
	"Material Request": [dict(LOCALID_FIELD), dict(GEO_FIELD), dict(APPROVER_FIELD), dict(APPROVAL_NOTE_FIELD), dict(MR_REMARKS_FIELD)],
	"Stock Entry": [dict(LOCALID_FIELD), dict(GEO_FIELD), dict(PURPOSE_FIELD)],
	"Stock Reconciliation": [dict(LOCALID_FIELD)],
	"Purchase Receipt": [dict(LOCALID_FIELD), dict(GEO_FIELD)],
	# Quotation: hanya perlu idempotensi + catatan (tanpa gudang/geo).
	"Quotation": [dict(LOCALID_FIELD), dict(QTN_REMARKS_FIELD)],
	# Pengaitan gudang per employee (dipakai Stock Ops untuk membatasi stok/pergerakan)
	"Employee": [
		{
			"fieldname": "stock_ops_warehouses",
			"label": "Stock Ops Warehouses",
			"fieldtype": "Table MultiSelect",
			"options": "Stock Ops Employee Warehouse",
			"insert_after": "department",
			"description": "Gudang yang dikelola karyawan ini di aplikasi Stock Ops.",
		}
	],
}


def after_install():
	setup_custom_fields()
	setup_roles_and_permissions()
	setup_approval_workflow()
	from stock_ops.push import ensure_vapid_keys

	ensure_vapid_keys()


def after_migrate():
	"""Self-heal saat tiap `bench migrate`: pastikan custom field + role aplikasi ada.

	Aman dijalankan berulang (idempoten). Custom field DocType (mis. Employee →
	stock_ops_warehouses) ikut dipastikan agar install lama yang hanya `migrate`
	tetap memperoleh field baru tanpa perlu reinstall.
	"""
	setup_custom_fields()
	setup_roles_and_permissions()
	setup_approval_workflow()


def setup_custom_fields():
	create_custom_fields(CUSTOM_FIELDS, ignore_validate=True)
	frappe.db.commit()


# ============================================================
# Role & Permission
# ============================================================
#
# Aplikasi TIDAK punya lapisan izin sendiri: semua aksi tulis (buat/submit/
# cancel) memakai izin standar ERPNext pada doctype-nya. Maka kita siapkan
# dua role khusus saat install, dipetakan ke Material Request / Stock Entry /
# Stock Reconciliation:
#
#   - "Stock Ops User"    : operasional lapangan — buat/ubah/submit dokumen.
#                           TIDAK bisa cancel/hapus. PWA-only (tanpa akses Desk).
#   - "Stock Ops Manager" : semua di atas + cancel/hapus/amend + edit Pengaturan.
#                           Punya akses Desk (lihat Workspace Stock Ops).
#
# Catatan: menambah izin lewat Custom DocPerm membuat ERPNext memakai Custom
# DocPerm sebagai SATU-SATUNYA sumber izin untuk doctype tsb. `add_permission`
# memanggil `setup_custom_perms` lebih dulu (menyalin izin standar utuh), jadi
# izin role bawaan (Stock User/Stock Manager, dll) TETAP terjaga.

ROLE_USER = "Stock Ops User"
ROLE_MANAGER = "Stock Ops Manager"

# Doctype transaksi yang dioperasikan aplikasi (submittable).
# Quotation = permintaan barang penjualan (ops), nanti ditarik sales → Sales Invoice.
TXN_DOCTYPES = ("Material Request", "Stock Entry", "Stock Reconciliation", "Purchase Receipt", "Quotation")

# Master data yang cukup dibaca (read-only) oleh aplikasi.
READ_DOCTYPES = (
	"Item",
	"Item Barcode",
	"Item Reorder",
	"Bin",
	"Warehouse",
	"UOM",
	"Company",
	"Supplier",
	"Customer",
	"Stock Ledger Entry",
)

_USER_PERMS = {"read": 1, "write": 1, "create": 1, "submit": 1, "print": 1, "email": 1, "report": 1, "export": 1}
_MANAGER_PERMS = {**_USER_PERMS, "cancel": 1, "delete": 1, "amend": 1}


def setup_roles_and_permissions():
	_ensure_role(ROLE_USER, desk_access=0)
	_ensure_role(ROLE_MANAGER, desk_access=1)

	for dt in TXN_DOCTYPES:
		_grant(dt, ROLE_USER, _USER_PERMS)
		_grant(dt, ROLE_MANAGER, _MANAGER_PERMS)

	for dt in READ_DOCTYPES:
		_grant(dt, ROLE_USER, {"read": 1})
		_grant(dt, ROLE_MANAGER, {"read": 1})

	# Pengaturan aplikasi: manajer Stock Ops boleh baca + ubah.
	# (Stock Manager bawaan sudah punya akses lewat doctype JSON.)
	_grant("Stock Ops Settings", ROLE_MANAGER, {"read": 1, "write": 1})

	frappe.db.commit()


def _ensure_role(role_name, desk_access=0):
	if not frappe.db.exists("Role", role_name):
		frappe.get_doc(
			{"doctype": "Role", "role_name": role_name, "desk_access": desk_access}
		).insert(ignore_permissions=True)
	elif frappe.db.get_value("Role", role_name, "desk_access") != desk_access:
		frappe.db.set_value("Role", role_name, "desk_access", desk_access)


def _grant(doctype, role, ptypes):
	"""Pastikan Custom DocPerm (doctype, role, permlevel 0) ada lalu set tiap ptype.

	`add_permission` memanggil `setup_custom_perms` di balik layar (menyalin izin
	standar utuh ke Custom DocPerm) sebelum menambah role baru, jadi izin role
	bawaan tetap terjaga. Kita panggil eksplisit juga sebagai jaring pengaman.
	"""
	if not frappe.db.exists("DocType", doctype):
		return
	try:
		from frappe.permissions import setup_custom_perms

		setup_custom_perms(doctype)
	except Exception:
		pass
	if not frappe.db.exists("Custom DocPerm", {"parent": doctype, "role": role, "permlevel": 0}):
		add_permission(doctype, role, 0)
	for ptype, value in ptypes.items():
		update_permission_property(doctype, role, 0, ptype, value, validate=False)


# ============================================================
# Approval Workflow (Material Request — Purchase)
# ============================================================
#
# Workflow ERPNext mengikat SELURUH Material Request. Tipe Purchase digerbang
# persetujuan line manager (leave approver); tipe lain (Transfer, dst.) langsung
# submit lewat transition "Submit" berkondisi. Dibuat idempoten saat install/migrate.

WORKFLOW_NAME = "Stock Ops MR Approval"

_WF_STATES = [
	# (state, docstatus, allow_edit, style)
	("Draft", "0", ROLE_USER, ""),
	("Pending Approval", "0", ROLE_MANAGER, "Warning"),
	("Approved", "1", ROLE_MANAGER, "Success"),
	("Rejected", "0", ROLE_USER, "Danger"),
]

_WF_ACTIONS = ["Submit for Approval", "Submit", "Approve", "Reject", "Reopen"]

_WF_TRANSITIONS = [
	# (from_state, action, next_state, allowed_role, condition)
	("Draft", "Submit for Approval", "Pending Approval", ROLE_USER, "doc.material_request_type == 'Purchase'"),
	("Draft", "Submit", "Approved", ROLE_USER, "doc.material_request_type != 'Purchase'"),
	# Approve/Reject: role kasar = Stock Ops User (PWA, tanpa Desk) supaya line manager cukup
	# jadi user PWA; gerbang sebenarnya = kondisi stock_ops_approver == user yang login.
	("Pending Approval", "Approve", "Approved", ROLE_USER, "doc.stock_ops_approver == frappe.session.user"),
	("Pending Approval", "Reject", "Rejected", ROLE_USER, "doc.stock_ops_approver == frappe.session.user"),
	("Rejected", "Reopen", "Draft", ROLE_USER, ""),
]


def setup_approval_workflow():
	"""Buat/perbaiki Workflow persetujuan MR Purchase + notifikasi (idempoten).

	Hanya aktif bila role 'Purchase Manager' ada (erpnext buying terpasang) dan
	DocType Material Request ada.
	"""
	if not frappe.db.exists("DocType", "Material Request"):
		return
	if not frappe.db.exists("Role", "Purchase Manager"):
		return

	for state, _ds, _ae, style in _WF_STATES:
		if not frappe.db.exists("Workflow State", state):
			frappe.get_doc(
				{"doctype": "Workflow State", "workflow_state_name": state, "style": style or ""}
			).insert(ignore_permissions=True)
	for action in _WF_ACTIONS:
		if not frappe.db.exists("Workflow Action Master", action):
			frappe.get_doc(
				{"doctype": "Workflow Action Master", "workflow_action_name": action}
			).insert(ignore_permissions=True)

	if frappe.db.exists("Workflow", WORKFLOW_NAME):
		wf = frappe.get_doc("Workflow", WORKFLOW_NAME)
		wf.set("states", [])
		wf.set("transitions", [])
	else:
		wf = frappe.new_doc("Workflow")
		wf.workflow_name = WORKFLOW_NAME

	wf.document_type = "Material Request"
	wf.is_active = 1
	wf.override_status = 0
	wf.workflow_state_field = "workflow_state"
	wf.send_email_alert = 0

	for state, docstatus, allow_edit, _style in _WF_STATES:
		wf.append("states", {"state": state, "doc_status": docstatus, "allow_edit": allow_edit})
	for from_state, action, next_state, allowed, condition in _WF_TRANSITIONS:
		row = wf.append(
			"transitions",
			{
				"state": from_state,
				"action": action,
				"next_state": next_state,
				"allowed": allowed,
				"allow_self_approval": 1,
			},
		)
		if condition:
			row.condition = condition

	wf.save(ignore_permissions=True)
	_ensure_notifications()
	frappe.db.commit()


# (name, subject, event, value_changed, condition, channel, recipient, message)
_NOTIFICATIONS = [
	{
		"name": "Stock Ops MR Pending (Email)",
		"subject": "Persetujuan diperlukan: {{ doc.name }}",
		"event": "Value Change",
		"value_changed": "workflow_state",
		"condition": "doc.workflow_state == 'Pending Approval' and doc.material_request_type == 'Purchase'",
		"channel": "Email",
		"recipient": {"receiver_by_document_field": "stock_ops_approver"},
		"message": "Permintaan pembelian {{ doc.name }} oleh {{ doc.owner }} menunggu persetujuan Anda.",
	},
	{
		"name": "Stock Ops MR Pending (System)",
		"subject": "Persetujuan diperlukan: {{ doc.name }}",
		"event": "Value Change",
		"value_changed": "workflow_state",
		"condition": "doc.workflow_state == 'Pending Approval' and doc.material_request_type == 'Purchase'",
		"channel": "System Notification",
		"recipient": {"receiver_by_document_field": "stock_ops_approver"},
		"message": "Permintaan pembelian {{ doc.name }} menunggu persetujuan Anda.",
	},
	{
		"name": "Stock Ops MR Approved PM (Email)",
		"subject": "Permintaan pembelian disetujui: {{ doc.name }}",
		"event": "Submit",
		"value_changed": None,
		"condition": "doc.material_request_type == 'Purchase'",
		"channel": "Email",
		"recipient": {"receiver_by_role": "Purchase Manager"},
		"message": "Permintaan pembelian {{ doc.name }} telah disetujui dan siap diproses.",
	},
	{
		"name": "Stock Ops MR Approved PM (System)",
		"subject": "Permintaan pembelian disetujui: {{ doc.name }}",
		"event": "Submit",
		"value_changed": None,
		"condition": "doc.material_request_type == 'Purchase'",
		"channel": "System Notification",
		"recipient": {"receiver_by_role": "Purchase Manager"},
		"message": "Permintaan pembelian {{ doc.name }} telah disetujui.",
	},
	{
		"name": "Stock Ops MR Outcome Requester (System)",
		"subject": "Status permintaan {{ doc.name }}: {{ doc.workflow_state }}",
		"event": "Value Change",
		"value_changed": "workflow_state",
		"condition": "doc.workflow_state in ('Approved','Rejected') and doc.material_request_type == 'Purchase'",
		"channel": "System Notification",
		"recipient": {"receiver_by_document_field": "owner"},
		"message": "Permintaan {{ doc.name }} Anda: {{ doc.workflow_state }}. {{ doc.stock_ops_approval_note or '' }}",
	},
	{
		"name": "Stock Ops MR Rejected Requester (Email)",
		"subject": "Permintaan {{ doc.name }} ditolak",
		"event": "Value Change",
		"value_changed": "workflow_state",
		"condition": "doc.workflow_state == 'Rejected' and doc.material_request_type == 'Purchase'",
		"channel": "Email",
		"recipient": {"receiver_by_document_field": "owner"},
		"message": "Permintaan pembelian {{ doc.name }} ditolak. Alasan: {{ doc.stock_ops_approval_note or '-' }}",
	},
]


def _ensure_notifications():
	"""Buat/perbaiki Notification persetujuan (Email + System) — idempoten by name."""
	if not frappe.db.exists("DocType", "Notification"):
		return
	for cfg in _NOTIFICATIONS:
		if frappe.db.exists("Notification", cfg["name"]):
			doc = frappe.get_doc("Notification", cfg["name"])
		else:
			doc = frappe.new_doc("Notification")
			doc.name = cfg["name"]
		doc.subject = cfg["subject"]
		doc.document_type = "Material Request"
		doc.event = cfg["event"]
		doc.value_changed = cfg["value_changed"]
		doc.condition = cfg["condition"]
		doc.channel = cfg["channel"]
		doc.enabled = 1
		doc.is_standard = 0
		doc.message = cfg["message"]
		doc.set("recipients", [])
		doc.append("recipients", cfg["recipient"])
		doc.flags.ignore_permissions = True
		doc.save(ignore_permissions=True)
