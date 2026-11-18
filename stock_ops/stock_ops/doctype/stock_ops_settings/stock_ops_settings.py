# Copyright (c) 2026, RMI and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


STOCK_OPS_ROLES = ("Stock Ops User", "Stock Ops Manager")

# Jenis "Berlaku untuk" (Default per User) yang memakai Tujuan → jenis di tabel Tujuan.
PURPOSE_KINDS = {"Semua": ("Stock Out", "Penerimaan Barang"), "Stock Out": ("Stock Out",), "Penerimaan Barang": ("Penerimaan Barang",)}


def _companies_changed(doc, table):
	before = doc.get_doc_before_save()
	key = lambda d: sorted(r.company for r in (d.get(table) or []) if r.company)
	return before is None or key(before) != key(doc)


class StockOpsSettings(Document):
	def validate(self):
		self.validate_issue_purposes()
		self.validate_user_defaults()

	def on_update(self):
		# "Lewati persetujuan atasan" (MR Purchase) diubah → susun ulang transisi Workflow MR saat itu juga.
		if self.has_value_changed("mr_skip_approval"):
			from stock_ops.setup.install import setup_approval_workflow

			setup_approval_workflow(commit=False)
		# Daftar company FAT diubah → pengajuan yang belum ditinjau Pajak ikut cabang yang baru.
		if _companies_changed(self, "rtp_fat_companies"):
			from stock_ops.request_to_pay.doctype.request_to_pay.request_to_pay import refresh_routing_flags

			refresh_routing_flags({r.company for r in (self.get("rtp_fat_companies") or []) if r.company})

	def validate_issue_purposes(self):
		"""Tujuan: cost center harus non-grup & tiap tujuan unik per perusahaan + jenis dokumen
		("Semua" bertabrakan dengan jenis apa pun bernama sama)."""
		seen = set()
		for row in self.get("issue_purposes") or []:
			row.purpose = (row.purpose or "").strip()
			cc = frappe.db.get_value("Cost Center", row.cost_center, ["company", "is_group"], as_dict=True)
			if not cc:
				continue
			if cc.is_group:
				frappe.throw(_("Baris {0}: Cost Center {1} adalah grup — pilih cost center non-grup.").format(row.idx, row.cost_center))
			applies = row.get("applies_to") or "Semua"
			kinds = ("Stock Out", "Penerimaan Barang") if applies == "Semua" else (applies,)
			for kind in kinds:
				key = (row.purpose.lower(), cc.company, kind)
				if key in seen:
					frappe.throw(_("Baris {0}: Tujuan \"{1}\" sudah ada untuk {2} perusahaan {3}.").format(row.idx, row.purpose, kind, cc.company))
				seen.add(key)

	def validate_user_defaults(self):
		"""Default per User: satu baris per (user, jenis); company/gudang/tujuan harus konsisten dan
		di dalam lingkup akses user (Employee / User Permission) — default bukan jalan pintas akses."""
		from stock_ops.api import _warehouse_companies, get_user_companies, get_user_warehouses

		purposes = {}  # (purpose_lower, company) -> set(kind)
		for p in self.get("issue_purposes") or []:
			co = frappe.db.get_value("Cost Center", p.cost_center, "company")
			kinds = PURPOSE_KINDS["Semua"] if (p.get("applies_to") or "Semua") == "Semua" else (p.applies_to,)
			purposes.setdefault(((p.purpose or "").strip().lower(), co), set()).update(kinds)

		seen = set()
		for row in self.get("user_defaults") or []:
			label = _("Baris {0} ({1})").format(row.idx, row.user)
			key = (row.user, row.applies_to or "Semua")
			if key in seen:
				frappe.throw(_("{0}: user sudah punya baris \"{1}\".").format(label, key[1]))
			seen.add(key)

			whs = [w for w in (row.source_warehouse, row.target_warehouse) if w]
			wh_info = {w.name: w for w in frappe.get_all("Warehouse", filters={"name": ["in", whs]}, fields=["name", "company", "is_group"])} if whs else {}
			for w in whs:
				if wh_info[w].is_group:
					frappe.throw(_("{0}: gudang {1} adalah grup — pilih gudang non-grup.").format(label, w))
			wh_cos = list(dict.fromkeys(wh_info[w].company for w in whs))
			if not row.company and len(wh_cos) == 1:
				row.company = wh_cos[0]
			if row.company and any(c != row.company for c in wh_cos):
				frappe.throw(_("{0}: gudang harus milik perusahaan {1}.").format(label, row.company))
			if len(wh_cos) > 1:
				frappe.throw(_("{0}: gudang sumber & tujuan beda perusahaan.").format(label))
			if row.applies_to == "Transfer" and row.source_warehouse and row.source_warehouse == row.target_warehouse:
				frappe.throw(_("{0}: gudang sumber dan tujuan transfer tidak boleh sama.").format(label))

			# Lingkup akses user (aturan sama dengan api._user_scope).
			user_whs = get_user_warehouses(row.user)
			bad = [w for w in whs if user_whs and w not in user_whs]
			if bad:
				frappe.throw(_("{0}: user tidak punya akses ke gudang {1}.").format(label, ", ".join(bad)))
			allowed_cos = get_user_companies(row.user) or (_warehouse_companies(user_whs) if user_whs else [])
			if row.company and allowed_cos and row.company not in allowed_cos:
				frappe.throw(_("{0}: user tidak punya akses ke perusahaan {1}.").format(label, row.company))

			row.purpose = (row.purpose or "").strip()
			if row.purpose:
				kinds = PURPOSE_KINDS.get(row.applies_to or "Semua")
				if not kinds:
					frappe.throw(_("{0}: Tujuan hanya dipakai untuk Semua / Stock Out / Penerimaan Barang.").format(label))
				if not row.company:
					frappe.throw(_("{0}: isi Company/gudang agar Tujuan bisa dicocokkan.").format(label))
				if not purposes.get((row.purpose.lower(), row.company), set()) & set(kinds):
					frappe.throw(_("{0}: Tujuan \"{1}\" tidak ada di tabel Tujuan → Cost Center untuk {2}.").format(label, row.purpose, row.company))


@frappe.whitelist()
def get_stock_ops_users():
	"""User aktif ber-role Stock Ops User / Manager (Has Role) + usulan default dari Employee
	dan lingkup gudangnya — untuk tombol "Get Users" di Stock Ops Settings."""
	frappe.has_permission("Stock Ops Settings", "write", throw=True)
	from stock_ops.api import get_user_warehouses

	users = frappe.get_all(
		"Has Role",
		filters={"role": ["in", STOCK_OPS_ROLES], "parenttype": "User", "parent": ["not in", ("Administrator", "Guest")]},
		pluck="parent",
		distinct=True,
	)
	enabled = frappe.get_all("User", filters={"name": ["in", users or [""]], "enabled": 1}, fields=["name", "full_name"], order_by="full_name asc")
	out = []
	for u in enabled:
		company = frappe.db.get_value("Employee", {"user_id": u.name, "status": "Active"}, "company") or frappe.db.get_value(
			"Employee", {"user_id": u.name}, "company"
		)
		whs = get_user_warehouses(u.name)
		if company:
			whs = [w for w in whs if frappe.db.get_value("Warehouse", w, "company") == company]
		elif whs:
			company = frappe.db.get_value("Warehouse", whs[0], "company")
		out.append({"user": u.name, "full_name": u.full_name, "company": company or "", "source_warehouse": whs[0] if whs else ""})
	return out
