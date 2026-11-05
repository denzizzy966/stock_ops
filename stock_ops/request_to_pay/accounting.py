# Request to Pay → Purchase Invoice → Payment Entry.
#
# RTP sendiri tidak membuat jurnal. Setelah Approved, orang yang berwenang (punya izin membuat
# Purchase Invoice — biasanya Finance / Tax) menekan "Buat Purchase Invoice": SATU PI draft per baris
# invoice RTP (vendor bisa berbeda per baris). Pembayaran memakai alur bawaan ERPNext
# (PI → Create → Payment). Begitu SEMUA PI dari satu RTP lunas, RTP otomatis menjadi "Paid";
# bila pembayaran dibatalkan, RTP kembali "Approved".
#
# Pajak dipotong (PPh 23 / PPh 21 / PPh 4(2)) dicatat sebagai baris pajak "Deduct" bernilai tetap
# (= nominal pajak di RTP) ke akun utang pajak dari Stock Ops Settings, sehingga
# grand total PI == "Total Dibayar" baris RTP.
import re

import frappe
from frappe import _
from frappe.utils import flt, getdate, today

DT = "Request to Pay"
PI = "Purchase Invoice"
# Toleransi pembulatan saat memeriksa "lunas".
EPS = 0.01


# ── field custom di Purchase Invoice (dipasang dari setup/rtp.py) ──
CUSTOM_FIELDS = {
	PI: [
		{
			"fieldname": "request_to_pay",
			"label": "Request to Pay",
			"fieldtype": "Link",
			"options": DT,
			"insert_after": "supplier",
			"read_only": 1,
			"no_copy": 1,
			"search_index": 1,
			"in_standard_filter": 1,
		},
		{
			"fieldname": "request_to_pay_invoice",
			"label": "Baris Invoice RTP",
			"fieldtype": "Data",
			"insert_after": "request_to_pay",
			"read_only": 1,
			"no_copy": 1,
			"hidden": 1,
		},
	]
}


def ensure_custom_fields():
	from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

	if frappe.db.exists("DocType", PI):
		create_custom_fields(CUSTOM_FIELDS, update=True)


# ── util ──
def _norm(s):
	"""Nama vendor → kunci pembanding: huruf kecil, tanpa PT/CV/Toko/UD & tanda baca."""
	s = re.sub(r"\b(pt|cv|toko|ud|tbk)\b\.?", "", (s or "").lower())
	return re.sub(r"[^a-z0-9]", "", s)


def _settings():
	return frappe.get_cached_doc("Stock Ops Settings")


def _pi_item():
	item = _settings().get("rtp_pi_item")
	if not item and frappe.db.exists("Item", "OTHNONE"):
		item = "OTHNONE"
	return item


def tax_account(company, tax_type):
	for row in _settings().get("rtp_tax_accounts") or []:
		if row.company == company and row.tax_type == tax_type:
			return row.account
	return None


def guess_tax_type(rate):
	"""Tebakan awal untuk data lama yang belum punya Jenis Pajak (bisa diganti di dialog)."""
	rate = flt(rate)
	if rate >= 10:
		return "PPh 4(2)"
	if rate in (2.5, 5, 6):
		return "PPh 21"
	return "PPh 23"


def _assert_can_bill(doc):
	if not frappe.has_permission(PI, "create"):
		frappe.throw(_("Anda tidak punya izin membuat Purchase Invoice."), frappe.PermissionError)
	doc.check_permission("read")
	if doc.docstatus != 1 or doc.workflow_state != "Approved":
		frappe.throw(_("Purchase Invoice hanya bisa dibuat dari pengajuan yang sudah Approved."))


def _open_pi(row):
	"""PI aktif (draft / submit) milik baris ini, atau None."""
	if not row.purchase_invoice:
		return None
	ds = frappe.db.get_value(PI, row.purchase_invoice, "docstatus")
	return row.purchase_invoice if ds in (0, 1) else None


# ── saran supplier & akun ──
def _suggest_supplier(row, company, suppliers):
	"""(supplier, sumber, kandidat_mirip). Sumber: baris / riwayat / nama."""
	if row.supplier:
		return row.supplier, "row", []
	key = _norm(row.vendor_name)
	if not key:
		return None, None, []
	# Pilihan Finance sebelumnya untuk nama vendor yang sama (RTP lain) = "mapping" yang dipelajari.
	prev = frappe.db.sql(
		"""select i.vendor_name, i.supplier from `tabRequest to Pay Invoice` i
		join `tabRequest to Pay` r on r.name = i.parent
		where r.company = %s and ifnull(i.supplier, '') != '' and i.parenttype = %s
		order by r.modified desc limit 500""",
		(company, DT),
		as_dict=True,
	)
	for p in prev:
		if _norm(p.vendor_name) == key:
			return p.supplier, "history", []
	exact = [s.name for s in suppliers if _norm(s.supplier_name) == key or _norm(s.name) == key]
	if exact:
		return exact[0], "name", []
	similar = [
		s.name
		for s in suppliers
		if len(key) >= 4 and (key in _norm(s.supplier_name) or (len(_norm(s.supplier_name)) >= 4 and _norm(s.supplier_name) in key))
	]
	return None, None, similar[:5]


def _suggest_account(supplier, company):
	if not supplier:
		return None
	acc = frappe.db.sql(
		"""select pii.expense_account from `tabPurchase Invoice Item` pii
		join `tabPurchase Invoice` pi on pi.name = pii.parent
		where pi.supplier = %s and pi.company = %s and pi.docstatus = 1
		order by pi.posting_date desc, pi.creation desc limit 1""",
		(supplier, company),
	)
	if acc:
		return acc[0][0]
	prev = frappe.db.sql(
		"""select i.expense_account from `tabRequest to Pay Invoice` i
		join `tabRequest to Pay` r on r.name = i.parent
		where i.supplier = %s and r.company = %s and ifnull(i.expense_account, '') != ''
		order by r.modified desc limit 1""",
		(supplier, company),
	)
	return prev[0][0] if prev else None


@frappe.whitelist()
def suggest_expense_account(supplier, company):
	if not frappe.has_permission(PI, "create"):
		return None
	return _suggest_account(supplier, company)


@frappe.whitelist()
def get_billing_dialog(name):
	"""Data dialog "Buat Purchase Invoice": baris yang belum punya PI + saran supplier/akun."""
	doc = frappe.get_doc(DT, name)
	_assert_can_bill(doc)
	suppliers = frappe.get_all("Supplier", filters={"disabled": 0}, fields=["name", "supplier_name"])
	rows = []
	for row in doc.invoices:
		if _open_pi(row):
			continue
		sup, src, similar = _suggest_supplier(row, doc.company, suppliers)
		tax_type = (row.tax_type or guess_tax_type(row.tax_rate)) if row.tax_withheld else None
		rows.append(
			{
				"row": row.name,
				"idx": row.idx,
				"vendor_name": row.vendor_name,
				"invoice_no": row.invoice_no,
				"tax_id": row.tax_id,
				"amount": row.amount,
				"tax_withheld": row.tax_withheld,
				"tax_rate": row.tax_rate,
				"tax_amount": row.tax_amount,
				"net_amount": row.net_amount,
				"tax_type": tax_type,
				"supplier": sup,
				"supplier_source": src,
				"similar": similar,
				"expense_account": row.expense_account or _suggest_account(sup, doc.company),
			}
		)
	missing_tax = sorted(
		{r["tax_type"] for r in rows if r["tax_withheld"] and not tax_account(doc.company, r["tax_type"])}
	)
	return {
		"company": doc.company,
		"currency": doc.currency,
		"item": _pi_item(),
		"can_create_supplier": bool(frappe.has_permission("Supplier", "create")),
		"rows": rows,
		"missing_tax_accounts": missing_tax,
	}


# ── pembuatan PI ──
def _new_supplier(row, tax_type):
	name = (row.vendor_name or "").strip()
	if not name:
		frappe.throw(_("Baris {0}: nama vendor kosong.").format(row.idx))
	existing = frappe.db.get_value("Supplier", {"supplier_name": name}, "name")
	if existing:
		return existing
	group = frappe.db.get_single_value("Buying Settings", "supplier_group") or frappe.db.get_value(
		"Supplier Group", {"is_group": 0}, "name"
	)
	sup = frappe.get_doc(
		{
			"doctype": "Supplier",
			"supplier_name": name,
			"supplier_group": group,
			"supplier_type": "Individual" if tax_type == "PPh 21" else "Company",
			"tax_id": (row.tax_id or "").strip() or None,
		}
	)
	sup.insert()
	return sup.name


def _build_pi(doc, row, supplier, expense_account, tax_type, item):
	purpose = doc.purpose_detail if doc.purpose_requires_detail and doc.purpose_detail else doc.payment_purpose
	desc = " — ".join(x for x in ((row.vendor_name or "").strip(), (purpose or "").strip(), (row.notes or "").strip()) if x)
	desc = f"{desc} ({doc.name})"
	due = doc.payment_date if doc.payment_date and getdate(doc.payment_date) >= getdate(today()) else today()
	pi = frappe.new_doc(PI)
	pi.update(
		{
			"company": doc.company,
			"supplier": supplier,
			"posting_date": today(),
			"due_date": due,
			"bill_no": (row.invoice_no or "").strip() or None,
			"currency": doc.currency,
			"ignore_pricing_rule": 1,
			"request_to_pay": doc.name,
			"request_to_pay_invoice": row.name,
			"remarks": _("Dari pengajuan {0} · invoice {1}").format(doc.name, row.invoice_no or "-"),
		}
	)
	pi.append(
		"items",
		{
			"item_code": item,
			"qty": 1,
			"rate": flt(row.amount),
			"description": desc,
			"expense_account": expense_account,
			"cost_center": doc.business_unit or None,
		},
	)
	if row.tax_withheld and flt(row.tax_amount):
		acc = tax_account(doc.company, tax_type)
		if not acc:
			frappe.throw(
				_("Akun {0} untuk {1} belum diatur di Stock Ops Settings → Akun Pajak Dipotong.").format(tax_type, doc.company)
			)
		pi.append(
			"taxes",
			{
				"category": "Total",
				"add_deduct_tax": "Deduct",
				"charge_type": "Actual",
				"account_head": acc,
				"tax_amount": flt(row.tax_amount),
				"cost_center": doc.business_unit or None,
				"description": f"{tax_type} {flt(row.tax_rate):g}% — {row.vendor_name}"
				+ (f" ({row.tax_id})" if row.tax_id else ""),
			},
		)
	pi.set_missing_values()
	pi.insert()
	return pi


def _attach_invoice_file(row, pi_name):
	if not row.invoice_file:
		return
	src = frappe.db.get_value("File", {"file_url": row.invoice_file}, ["file_name", "is_private"], as_dict=True)
	if not src:
		return
	frappe.get_doc(
		{
			"doctype": "File",
			"file_url": row.invoice_file,
			"file_name": src.file_name,
			"is_private": src.is_private,
			"attached_to_doctype": PI,
			"attached_to_name": pi_name,
		}
	).insert(ignore_permissions=True)


@frappe.whitelist()
def make_purchase_invoices(name, rows):
	"""Buat PI draft untuk baris RTP terpilih.

	rows: [{row, supplier | new_supplier: 1, expense_account, tax_type}] — hasil dialog.
	Baris yang sudah punya PI aktif dilewati (aman bila tombol ditekan dua kali)."""
	rows = frappe.parse_json(rows) or []
	doc = frappe.get_doc(DT, name)
	_assert_can_bill(doc)
	item = _pi_item()
	if not item:
		frappe.throw(_("Atur \"Item Purchase Invoice\" di Stock Ops Settings (mis. OTHNONE)."))
	by_name = {r.name: r for r in doc.invoices}
	# Tahap 1: periksa SEMUA baris dulu — gagal di baris ke-3 tidak boleh meninggalkan PI baris 1.
	plan = []
	for sel in rows:
		row = by_name.get(sel.get("row"))
		if not row:
			frappe.throw(_("Baris invoice tidak ditemukan: {0}").format(sel.get("row")))
		if _open_pi(row):
			continue
		tax_type = (sel.get("tax_type") or row.tax_type or "").strip() if row.tax_withheld else None
		if row.tax_withheld:
			if tax_type not in ("PPh 23", "PPh 21", "PPh 4(2)"):
				frappe.throw(_("Baris {0}: pilih jenis pajak.").format(row.idx))
			if flt(row.tax_amount) and not tax_account(doc.company, tax_type):
				frappe.throw(
					_("Akun {0} untuk {1} belum diatur di Stock Ops Settings → Akun Pajak Dipotong.").format(tax_type, doc.company)
				)
		supplier = (sel.get("supplier") or "").strip()
		new_supplier = not supplier and sel.get("new_supplier")
		if new_supplier and not frappe.has_permission("Supplier", "create"):
			frappe.throw(
				_("Baris {0}: Anda tidak punya izin membuat Supplier baru. Pilih supplier yang ada, atau minta Purchase Manager membuatnya.").format(row.idx),
				frappe.PermissionError,
			)
		if not supplier and not new_supplier:
			frappe.throw(_("Baris {0} ({1}): pilih Supplier.").format(row.idx, row.vendor_name))
		if supplier and not frappe.db.exists("Supplier", supplier):
			frappe.throw(_("Supplier tidak ditemukan: {0}").format(supplier))
		account = (sel.get("expense_account") or "").strip()
		acc = frappe.db.get_value("Account", account, ["company", "is_group"], as_dict=True) if account else None
		if not acc or acc.company != doc.company or acc.is_group:
			frappe.throw(_("Baris {0}: pilih akun biaya milik {1}.").format(row.idx, doc.company))
		plan.append((row, supplier, new_supplier, account, tax_type))

	# Tahap 2: buat.
	made = []
	for row, supplier, new_supplier, account, tax_type in plan:
		if new_supplier:
			supplier = _new_supplier(row, tax_type)
		pi = _build_pi(doc, row, supplier, account, tax_type, item)
		_attach_invoice_file(row, pi.name)
		# Simpan kembali ke baris RTP: supplier jadi "mapping" untuk pengajuan berikutnya.
		frappe.db.set_value(
			"Request to Pay Invoice",
			row.name,
			{"purchase_invoice": pi.name, "supplier": supplier, "expense_account": account, "tax_type": tax_type},
			update_modified=False,
		)
		made.append({"row": row.name, "idx": row.idx, "purchase_invoice": pi.name, "grand_total": pi.grand_total})
	if made:
		doc.add_comment(
			"Info", _("Purchase Invoice dibuat: {0}").format(", ".join(m["purchase_invoice"] for m in made))
		)
	return {"created": made}


# ── status kembali ke RTP (dipanggil doc_events) ──
def billing_status(doc):
	"""Ringkasan PI per baris: dipakai sinkron status, form Desk, dan PWA."""
	out = []
	for row in doc.invoices:
		pi = None
		if row.purchase_invoice:
			pi = frappe.db.get_value(
				PI, row.purchase_invoice, ["name", "docstatus", "status", "grand_total", "outstanding_amount"], as_dict=True
			)
		out.append({"row": row.name, "idx": row.idx, "pi": pi})
	return out


def _payment_refs(pi_names):
	if not pi_names:
		return []
	pe = frappe.get_all(
		"Payment Entry Reference",
		filters={"reference_doctype": PI, "reference_name": ["in", pi_names], "docstatus": 1},
		pluck="parent",
		order_by="creation asc",
	)
	je = frappe.get_all(
		"Journal Entry Account",
		filters={"reference_type": PI, "reference_name": ["in", pi_names], "docstatus": 1},
		pluck="parent",
		order_by="creation asc",
	)
	return list(dict.fromkeys(pe + je))


def sync_rtp(name, pi_cancelled=False):
	"""Approved ↔ Paid mengikuti pelunasan semua PI pengajuan ini.
	pi_cancelled: salah satu PI-nya baru dibatalkan → pasti belum lunas."""
	doc = frappe.get_doc(DT, name)
	if doc.docstatus != 1 or doc.workflow_state not in ("Approved", "Paid"):
		return
	status = billing_status(doc)
	billed = [s for s in status if s["pi"]]
	if not billed and not pi_cancelled:
		return  # belum ada PI → status hanya lewat "Mark as Paid" manual
	paid = not pi_cancelled and len(billed) == len(status) and all(s["pi"].docstatus == 1 and flt(s["pi"].outstanding_amount) <= EPS for s in billed)
	pis = [s["pi"].name for s in billed]
	if paid and doc.workflow_state == "Approved":
		refs = _payment_refs(pis)
		_set_state(doc, "Paid", paid_on=today(), payment_reference=", ".join(refs)[:140] or None)
		doc.add_comment("Info", _("Lunas via {0}").format(", ".join(refs) or ", ".join(pis)))
	elif not paid and doc.workflow_state == "Paid":
		_set_state(doc, "Approved", paid_on=None, payment_reference=None)
		doc.add_comment("Info", _("Pembayaran dibatalkan — kembali ke Approved."))


def _set_state(doc, state, **values):
	# Perubahan oleh sistem (bukan aksi Workflow user) → tulis langsung, lalu kirim notifikasi yang sama.
	doc.db_set({"workflow_state": state, **values})
	if state == "Paid":
		from stock_ops.request_to_pay.notify import on_state_change

		on_state_change(doc)


def _safe_sync(rtp_names, **kw):
	"""Jangan gagalkan pembayaran karena sinkron RTP: catat error & beri peringatan."""
	for name in rtp_names:
		try:
			sync_rtp(name, **kw)
		except Exception:
			frappe.log_error(frappe.get_traceback(), f"Request to Pay sync {name}")
			frappe.msgprint(
				_("Status pengajuan {0} belum ter-update otomatis; cek Error Log.").format(name), indicator="orange", alert=True
			)


def _rtps_of(pi_names):
	pi_names = [p for p in pi_names if p]
	if not pi_names:
		return []
	return list(
		set(frappe.get_all(PI, filters={"name": ["in", pi_names], "request_to_pay": ["is", "set"]}, pluck="request_to_pay"))
	)


def on_payment_entry(doc, method=None):
	_safe_sync(_rtps_of([r.reference_name for r in doc.references if r.reference_doctype == PI]))


def on_journal_entry(doc, method=None):
	_safe_sync(_rtps_of([a.reference_name for a in doc.accounts if a.reference_type == PI]))


def on_purchase_invoice_submit(doc, method=None):
	# PI "Is Paid" (dibayar tunai saat dibuat) lunas tanpa Payment Entry.
	if doc.get("request_to_pay"):
		_safe_sync([doc.request_to_pay])


def on_purchase_invoice_cancel(doc, method=None):
	"""PI dibatalkan / dihapus → lepas tautan di baris RTP supaya bisa dibuat ulang."""
	if not doc.get("request_to_pay"):
		return
	for row in frappe.get_all(
		"Request to Pay Invoice", filters={"parent": doc.request_to_pay, "purchase_invoice": doc.name}, pluck="name"
	):
		frappe.db.set_value("Request to Pay Invoice", row, "purchase_invoice", None, update_modified=False)
	if doc.docstatus == 2:
		_safe_sync([doc.request_to_pay], pi_cancelled=True)
