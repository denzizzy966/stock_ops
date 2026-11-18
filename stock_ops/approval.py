import frappe
from frappe import _


def get_approver_or_none(user=None):
	"""Line manager (leave approver) untuk user, atau None. Tidak melempar error.

	Peta: User → Employee(user_id) → leave_approver. Aman bila HR (hrms) tidak
	terpasang (DocType Employee tak ada) → mengembalikan None.
	"""
	user = user or frappe.session.user
	if not frappe.db.exists("DocType", "Employee"):
		return None
	approver = frappe.db.get_value("Employee", {"user_id": user}, "leave_approver")
	return approver or None


def mr_approval_required():
	"""MR Purchase wajib disetujui atasan? False bila "Lewati persetujuan atasan" dicentang di
	Stock Ops Settings. Aman sebelum migrate (field belum ada) → tetap wajib."""
	try:
		return not frappe.db.get_single_value("Stock Ops Settings", "mr_skip_approval")
	except Exception:
		return True


def resolve_approver(user=None):
	"""Line manager (leave approver) untuk user. Memblokir bila tak ditemukan.

	Dipakai saat mengajukan Material Request (Purchase) untuk persetujuan.
	"""
	approver = get_approver_or_none(user)
	if not approver:
		frappe.throw(
			_("Setel Leave Approver Anda di Employee dulu untuk mengajukan permintaan pembelian."),
			title=_("Approver belum diatur"),
		)
	return approver
