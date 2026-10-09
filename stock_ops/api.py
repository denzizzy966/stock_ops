import json

import frappe
from frappe import _
from frappe.utils import cint

ALLOWED_DOCTYPES = ("Material Request", "Stock Entry", "Purchase Receipt", "Quotation")


def get_user_warehouses(user=None):
	"""Gudang milik user.

	Prioritas: gudang yang dipetakan di Employee (field stock_ops_warehouses) →
	lalu User Permission (allow=Warehouse). Kosong = tidak dibatasi (mis. Administrator).
	"""
	user = user or frappe.session.user
	whs = []

	emp = frappe.db.get_value("Employee", {"user_id": user}, "name")
	if emp:
		whs = [
			r.warehouse
			for r in frappe.get_all(
				"Stock Ops Employee Warehouse",
				filters={"parent": emp, "parentfield": "stock_ops_warehouses"},
				fields=["warehouse"],
			)
		]

	if not whs:
		whs = [
			p.for_value
			for p in frappe.get_all(
				"User Permission", filters={"user": user, "allow": "Warehouse"}, fields=["for_value"]
			)
		]

	return list(dict.fromkeys([w for w in whs if w]))


def get_user_companies(user=None):
	"""Perusahaan yang diizinkan untuk user via **User Permission** (allow=Company).
	Kosong = tidak dibatasi per-perusahaan. Dicek lebih dulu dari default Stock Ops Settings."""
	user = user or frappe.session.user
	return list(
		dict.fromkeys(
			[
				p.for_value
				for p in frappe.get_all(
					"User Permission", filters={"user": user, "allow": "Company"}, fields=["for_value"]
				)
				if p.for_value
			]
		)
	)


def get_user_employee(user=None):
	"""Employee yang tertaut ke user (via Employee.user_id). None bila tidak ada."""
	user = user or frappe.session.user
	meta = frappe.get_meta("Employee")
	# "grade" (dan sebagian field lain) berasal dari HRMS — pilih hanya yang ada agar tak 500 tanpa HRMS.
	fields = ["name", "employee_name", "company"] + [
		f for f in ("department", "designation", "branch", "grade") if meta.get_field(f)
	]
	return frappe.db.get_value("Employee", {"user_id": user}, fields, as_dict=True)


@frappe.whitelist()
def get_user_context():
	"""Konteks user untuk aplikasi: Employee, perusahaan, status read-only, dan
	daftar gudang/perusahaan yang boleh diakses. Dipakai untuk mengunci field
	Company dan memfilter picker gudang."""
	scope = _user_scope()
	return {
		"employee": scope["employee"] or None,
		"company": scope["company"],
		"company_read_only": scope["company_read_only"],
		"restricted": scope["restricted"],
		"allowed_warehouses": scope["user_whs"],
		"allowed_companies": scope["allowed_companies"],
		"default_source_warehouse": scope["default_source_warehouse"],
	}


def _warehouse_companies(whs):
	"""Perusahaan (distinct, urut stabil) dari sejumlah gudang."""
	if not whs:
		return []
	rows = frappe.get_all("Warehouse", filters={"name": ["in", whs]}, fields=["company"])
	return list(dict.fromkeys([r.company for r in rows if r.company]))


def _settings_default_company():
	try:
		s = frappe.get_cached_doc("Stock Ops Settings")
		return getattr(s, "default_company", None) or ""
	except Exception:
		return ""


def _user_scope(emp=None):
	"""Lingkup akses user login.

	- `user_whs` = get_user_warehouses() (dari Employee.stock_ops_warehouses ATAU
	  User Permission Warehouse). KOSONG = tidak dibatasi → lihat semua gudang &
	  semua perusahaan (untuk segelintir user/manajer yang dibuka penuh).
	- Bila dibatasi: gudang yang terlihat = `user_whs`; perusahaan = perusahaan
	  gudang tsb; Company dikunci (read-only) bila lingkupnya satu perusahaan.
	"""
	if emp is None:
		emp = get_user_employee()
	# Prioritas: User Permission (Warehouse & Company). Bila kosong → default Stock Ops Settings.
	user_whs = get_user_warehouses()
	up_companies = get_user_companies()
	restricted = bool(user_whs) or bool(up_companies)

	# Perusahaan yang diizinkan: User Permission Company diutamakan; jika tidak ada tapi
	# gudang dibatasi, pakai perusahaan gudang tsb; selain itu tak dibatasi.
	if up_companies:
		allowed_companies = up_companies
	elif user_whs:
		allowed_companies = _warehouse_companies(user_whs)
	else:
		allowed_companies = []

	# Perusahaan default: Employee (bila dalam lingkup) → lingkup pertama → Settings → pertama.
	if emp and emp.get("company") and (not allowed_companies or emp["company"] in allowed_companies):
		company = emp["company"]
	elif allowed_companies:
		company = allowed_companies[0]
	else:
		company = _settings_default_company() or frappe.defaults.get_user_default("Company")
		if not company:
			first = frappe.get_all("Company", pluck="name", limit_page_length=1)
			company = first[0] if first else None

	if restricted and allowed_companies and company not in allowed_companies:
		company = allowed_companies[0]

	# Kunci Company hanya bila lingkup tepat satu perusahaan.
	company_read_only = bool(restricted and len(allowed_companies) == 1 and company)

	# Gudang sumber default — pakai Settings; bila gudang dibatasi & tak valid, gudang pertama user.
	src = _default_source_warehouse()
	if user_whs and (not src or src not in user_whs):
		src = user_whs[0]

	return {
		"employee": emp,
		"user_whs": user_whs,
		"up_companies": up_companies,
		"restricted": restricted,
		"allowed_companies": allowed_companies,
		"company": company,
		"company_read_only": company_read_only,
		"default_source_warehouse": src,
	}


def _collect_warehouses(data):
	"""Kumpulkan semua nilai gudang dari sebuah payload dokumen (top-level + item)."""
	keys = ("from_warehouse", "to_warehouse", "s_warehouse", "t_warehouse", "set_warehouse", "warehouse")
	whs = set()
	for k in keys:
		v = data.get(k)
		if v:
			whs.add(v)
	for it in (data.get("items") or []):
		for k in ("warehouse", "s_warehouse", "t_warehouse"):
			v = it.get(k)
			if v:
				whs.add(v)
	return whs


def _assert_warehouses_allowed(whs):
	"""Tolak bila ada gudang di luar lingkup user (saat user dibatasi). Aman bila tak dibatasi.
	Lingkup gudang (User Permission Warehouse / Employee) diutamakan; bila tak ada tapi user
	dibatasi per-perusahaan (User Permission Company), tolak gudang di luar perusahaan itu."""
	allowed = get_user_warehouses()
	if allowed:
		bad = sorted(w for w in whs if w and w not in allowed)
		if bad:
			frappe.throw(_("Anda tidak punya akses ke gudang: {0}").format(", ".join(bad)))
		return
	up_companies = get_user_companies()
	if up_companies:
		wanted = [w for w in whs if w]
		co = {r.name: r.company for r in frappe.get_all("Warehouse", filters={"name": ["in", wanted]}, fields=["name", "company"])} if wanted else {}
		bad = sorted(w for w in wanted if co.get(w) not in up_companies)
		if bad:
			frappe.throw(_("Anda tidak punya akses ke gudang: {0}").format(", ".join(bad)))


def _default_source_warehouse():
	try:
		s = frappe.get_cached_doc("Stock Ops Settings")
		return getattr(s, "default_source_warehouse", None) or ""
	except Exception:
		return ""


# Role yang boleh mengelola persetujuan MR (selain approver yang ditunjuk).
APPROVAL_ADMIN_ROLES = {"Stock Ops Manager", "Purchase Manager", "System Manager"}


def _is_manager():
	roles = set(frappe.get_roles(frappe.session.user))
	return frappe.session.user == "Administrator" or any(
		r in roles for r in ("System Manager", "Stock Manager", "Stock Ops Manager")
	)


def _allowed_companies():
	"""Perusahaan dalam lingkup user: User Permission Company, lalu perusahaan gudang user.
	Kosong = tidak dibatasi (sama dengan aturan `_user_scope`)."""
	up = get_user_companies()
	if up:
		return up
	whs = get_user_warehouses()
	return _warehouse_companies(whs) if whs else []


def _assert_company_allowed(company):
	"""Tolak akses ke dokumen/data perusahaan di luar lingkup user (bila dibatasi)."""
	allowed = _allowed_companies()
	if allowed and company not in allowed:
		frappe.throw(_("Anda tidak punya akses ke perusahaan: {0}").format(company), frappe.PermissionError)


def _company_filter(company=None):
	"""Nilai filter `company` untuk endpoint BACA, dijepit ke lingkup user.

	Perusahaan yang diminta dipakai bila dalam lingkup (atau user tak dibatasi). Bila di luar
	lingkup (mis. default perangkat basi di HP bersama) → jatuh ke seluruh lingkup user, bukan
	error, agar layar tetap jalan tanpa membocorkan data perusahaan lain.
	None = tanpa filter (user tak dibatasi & tak meminta perusahaan)."""
	allowed = _allowed_companies()
	if not allowed:
		return company or None
	if company in allowed:
		return company
	return ["in", allowed]


def _resolve_warehouses(warehouse=None, company=None):
	"""Gudang yang boleh DIBACA user. Gudang eksplisit di luar lingkup → ditolak;
	perusahaan dijepit ke lingkup user (lihat `_company_filter`)."""
	user_whs = get_user_warehouses()
	restricted = bool(user_whs) or bool(get_user_companies())
	if warehouse:
		_assert_warehouses_allowed([warehouse])
		return [warehouse], restricted
	if user_whs:
		return user_whs, True
	wfilter = {"disabled": 0, "is_group": 0}
	co = _company_filter(company)
	if co:
		wfilter["company"] = co
	return frappe.get_all("Warehouse", filters=wfilter, pluck="name"), restricted


@frappe.whitelist()
def resolve_item(code):
	"""Cari item_code dari sebuah kode (item_code, barcode, atau sebagian nama)."""
	code = (code or "").strip()
	if not code:
		return None
	if frappe.db.exists("Item", code):
		return code
	bc = frappe.db.get_value("Item Barcode", {"barcode": code}, "parent")
	if bc:
		return bc
	hit = frappe.get_all("Item", filters={"item_name": ["like", f"%{code}%"]}, pluck="name", limit_page_length=1)
	return hit[0] if hit else None


@frappe.whitelist()
def get_item_detail(item_code, company=None):
	"""Detail item: info, stok per gudang user, & mutasi terakhir."""
	item = frappe.db.get_value(
		"Item", item_code, ["name as item_code", "item_name", "stock_uom", "image", "item_group", "description"], as_dict=True
	)
	if not item:
		frappe.throw(_("Item tidak ditemukan: {0}").format(item_code))

	whs, restricted = _resolve_warehouses(None, company)
	barcodes = frappe.get_all("Item Barcode", filters={"parent": item_code}, pluck="barcode")
	bins = frappe.get_all(
		"Bin",
		filters={"item_code": item_code, "warehouse": ["in", whs or [""]]},
		fields=["warehouse", "actual_qty", "reserved_qty", "projected_qty"],
		order_by="warehouse",
	)
	total = sum(b["actual_qty"] for b in bins)
	moves = frappe.get_all(
		"Stock Ledger Entry",
		filters=[["item_code", "=", item_code], ["warehouse", "in", whs or [""]], ["is_cancelled", "=", 0]],
		fields=["posting_date", "posting_time", "warehouse", "actual_qty", "qty_after_transaction", "voucher_type", "voucher_no"],
		order_by="posting_date desc, posting_time desc, creation desc",
		limit_page_length=20,
	)
	return {
		"item": item,
		"barcodes": barcodes,
		"stock": bins,
		"total": total,
		"uom": item["stock_uom"],
		"movements": moves,
		"warehouses": whs,
		"restricted": restricted,
	}


@frappe.whitelist()
def list_open_purchase_orders(company=None, supplier=None, search=None, limit=50):
	"""Purchase Order yang masih bisa diterima (belum 100% diterima) — untuk Penerimaan Barang."""
	filters = {
		"docstatus": 1,
		"status": ["not in", ["Closed", "Completed", "Cancelled", "On Hold"]],
		"per_received": ["<", 100],
	}
	co = _company_filter(company)
	if co:
		filters["company"] = co
	if supplier:
		filters["supplier"] = supplier
	if search:
		filters["name"] = ["like", "%" + search + "%"]
	return frappe.get_all(
		"Purchase Order",
		filters=filters,
		fields=["name", "supplier", "supplier_name", "transaction_date", "status", "company", "per_received", "grand_total", "currency"],
		order_by="transaction_date desc, modified desc",
		limit_page_length=int(limit),
	)


@frappe.whitelist()
def get_purchase_order_items(purchase_order):
	"""Item PO yang belum diterima penuh → untuk auto-isi form Penerimaan Barang.

	Tiap baris membawa purchase_order + purchase_order_item (po_detail) agar Purchase
	Receipt ter-link ke PO; ERPNext memvalidasi qty terima terhadap qty pesan.
	"""
	po = frappe.get_doc("Purchase Order", purchase_order)
	_assert_company_allowed(po.company)
	out = []
	for it in po.items:
		remaining = (it.qty or 0) - (it.received_qty or 0)
		if remaining <= 0:
			continue
		out.append({
			"item_code": it.item_code,
			"item_name": it.item_name,
			"uom": it.uom or it.stock_uom,
			"qty": remaining,
			"rate": it.rate,
			"warehouse": it.warehouse,
			"is_fixed_asset": int(frappe.db.get_value("Item", it.item_code, "is_fixed_asset") or 0),
			"purchase_order": po.name,
			"purchase_order_item": it.name,
		})
	return {
		"name": po.name,
		"supplier": po.supplier,
		"supplier_name": po.supplier_name,
		"company": po.company,
		"set_warehouse": po.get("set_warehouse"),
		"items": out,
	}


@frappe.whitelist()
def list_returnable_receipts(company=None, supplier=None, search=None, limit=50):
	"""Purchase Receipt yang sudah disubmit & bisa diretur (bukan dokumen retur)."""
	filters = {"docstatus": 1, "is_return": 0}
	co = _company_filter(company)
	if co:
		filters["company"] = co
	if supplier:
		filters["supplier"] = supplier
	if search:
		filters["name"] = ["like", "%" + search + "%"]
	return frappe.get_all(
		"Purchase Receipt",
		filters=filters,
		fields=["name", "supplier", "supplier_name", "posting_date", "company", "per_returned", "grand_total", "currency"],
		order_by="posting_date desc, modified desc",
		limit_page_length=int(limit),
	)


@frappe.whitelist()
def get_receipt_items_for_return(purchase_receipt):
	"""Item Purchase Receipt untuk diretur beserta **sisa qty yang masih bisa diretur**.

	Sisa dihitung lewat `make_return_doc` (mengurangi qty yang sudah diretur pada
	dokumen retur sebelumnya) — lebih andal daripada field `per_returned` yang bisa basi.
	"""
	from erpnext.controllers.sales_and_purchase_return import make_return_doc

	pr = frappe.get_doc("Purchase Receipt", purchase_receipt)
	_assert_company_allowed(pr.company)
	remaining = {}
	try:
		ret = make_return_doc("Purchase Receipt", purchase_receipt)
		for it in ret.items:
			# make_return_doc memberi qty negatif = sisa yang masih bisa diretur
			remaining[it.purchase_receipt_item] = abs(it.qty or 0)
	except Exception:
		remaining = {}

	out = []
	for it in pr.items:
		max_qty = remaining.get(it.name, it.qty) if remaining else it.qty
		out.append({
			"item_code": it.item_code,
			"item_name": it.item_name,
			"uom": it.uom,
			"qty": it.qty,  # qty diterima asli
			"returnable_qty": max_qty,  # sisa yang masih bisa diretur
			"warehouse": it.warehouse,
			"purchase_receipt_item": it.name,
		})
	return {"name": pr.name, "supplier": pr.supplier, "supplier_name": pr.supplier_name, "company": pr.company, "items": out}


@frappe.whitelist()
def create_purchase_return(purchase_receipt, items=None, external_localid=None, remarks=None):
	"""Buat dokumen **retur barang** (Purchase Receipt is_return=1) atas sebuah Purchase
	Receipt: qty negatif & return_against terisi (stok berkurang saat di-submit).

	`items` opsional = [{item_code, qty}] untuk retur sebagian; kosong = retur penuh.
	Idempoten via external_localid. Mengembalikan draft (submit lewat submit_transaction).
	"""
	if isinstance(items, str):
		items = json.loads(items)
	if external_localid:
		existing = frappe.db.get_value("Purchase Receipt", {"external_localid": external_localid}, "name")
		if existing:
			return {"name": existing, "duplicate": True}

	from erpnext.controllers.sales_and_purchase_return import make_return_doc

	_assert_company_allowed(frappe.db.get_value("Purchase Receipt", purchase_receipt, "company"))
	ret = make_return_doc("Purchase Receipt", purchase_receipt)
	_assert_warehouses_allowed(_collect_warehouses(ret.as_dict()))

	# Retur sebagian: sesuaikan qty per item (negatif) & buang item yang tak diretur.
	if items:
		want = {}
		for i in items:
			code = i.get("item_code")
			qty = abs(float(i.get("qty") or 0))
			if code and qty:
				want[code] = qty
		kept = []
		for it in ret.items:
			if it.item_code in want:
				it.qty = -want[it.item_code]
				it.received_qty = it.qty
				it.rejected_qty = 0
				kept.append(it)
		if kept:
			ret.set("items", kept)

	if external_localid:
		ret.external_localid = external_localid
	if remarks:
		ret.remarks = remarks
	ret.insert()
	frappe.db.commit()
	return {"name": ret.name, "duplicate": False}


@frappe.whitelist()
def get_opname_sheet(warehouse, company=None):
	"""Lembar opname: stok sistem saat ini di sebuah gudang (untuk dihitung fisik)."""
	whs, restricted = _resolve_warehouses(None, company)
	if restricted and warehouse not in whs:
		frappe.throw(_("Anda tidak punya akses ke gudang {0}").format(warehouse))

	bins = frappe.get_all(
		"Bin",
		filters={"warehouse": warehouse},
		fields=["item_code", "actual_qty", "valuation_rate", "stock_uom"],
		order_by="item_code",
		limit_page_length=0,
	)
	if bins:
		codes = list({b["item_code"] for b in bins})
		names = {i["name"]: i["item_name"] for i in frappe.get_all("Item", filters={"name": ["in", codes]}, fields=["name", "item_name"])}
		for b in bins:
			b["item_name"] = names.get(b["item_code"], b["item_code"])
	return {"warehouse": warehouse, "items": bins}


@frappe.whitelist()
def create_opname(warehouse, items, company=None, external_localid=None):
	"""Buat Stock Reconciliation (draft) dari hasil hitung fisik. Idempoten via external_localid."""
	if isinstance(items, str):
		items = json.loads(items)
	if not items:
		frappe.throw(_("Tidak ada item untuk direkonsiliasi"))

	_assert_warehouses_allowed({warehouse})

	if external_localid:
		existing = frappe.db.get_value("Stock Reconciliation", {"external_localid": external_localid}, "name")
		if existing:
			return {"name": existing, "duplicate": True}

	doc = frappe.get_doc(
		{
			"doctype": "Stock Reconciliation",
			"purpose": "Stock Reconciliation",
			"company": company,
			"external_localid": external_localid,
			"items": [
				{
					"item_code": i["item_code"],
					"warehouse": warehouse,
					"qty": i["qty"],
					"valuation_rate": i.get("valuation_rate") or 0,
					"allow_zero_valuation_rate": 1,
				}
				for i in items
			],
		}
	)
	doc.insert()
	frappe.db.commit()
	return {"name": doc.name, "duplicate": False, "count": len(items)}


@frappe.whitelist()
def bulk_purchase_request(items, company=None, external_localid=None):
	"""Buat satu Material Request (Purchase) dari beberapa item terpilih (stok menipis).

	items = [{item_code, qty, uom, warehouse}]. Idempoten via external_localid.
	"""
	if isinstance(items, str):
		items = json.loads(items)
	items = [i for i in items if i.get("item_code") and float(i.get("qty") or 0) > 0]
	if not items:
		frappe.throw(_("Tidak ada item untuk diminta"))

	_assert_warehouses_allowed({i.get("warehouse") for i in items if i.get("warehouse")})

	if external_localid:
		existing = frappe.db.get_value("Material Request", {"external_localid": external_localid}, "name")
		if existing:
			return {"name": existing, "duplicate": True}

	today = frappe.utils.nowdate()
	doc = frappe.get_doc(
		{
			"doctype": "Material Request",
			"material_request_type": "Purchase",
			"company": company,
			"transaction_date": today,
			"schedule_date": today,
			"external_localid": external_localid,
			"items": [
				{
					"item_code": i["item_code"],
					"qty": i["qty"],
					"uom": i.get("uom"),
					"schedule_date": today,
					"warehouse": i.get("warehouse"),
				}
				for i in items
			],
		}
	)
	doc.insert()
	frappe.db.commit()
	return {"name": doc.name, "duplicate": False, "count": len(items)}


@frappe.whitelist()
def get_low_stock(company=None, threshold=10):
	"""Item dengan stok menipis di gudang user.

	Batas = reorder level item-per-gudang (Item Reorder) bila ada, jika tidak pakai `threshold`.
	"""
	whs, restricted = _resolve_warehouses(None, company)
	threshold = float(threshold or 0)

	reorders = {}
	for r in frappe.get_all(
		"Item Reorder",
		filters={"warehouse": ["in", whs or [""]]},
		fields=["parent", "warehouse", "warehouse_reorder_level", "warehouse_reorder_qty"],
	):
		reorders[(r.parent, r.warehouse)] = (r.warehouse_reorder_level or 0, r.warehouse_reorder_qty or 0)

	bins = frappe.get_all(
		"Bin",
		filters={"warehouse": ["in", whs or [""]]},
		fields=["item_code", "warehouse", "actual_qty", "projected_qty", "stock_uom"],
		limit_page_length=0,
	)
	low = []
	for b in bins:
		lvl, rqty = reorders.get((b["item_code"], b["warehouse"]), (0, 0))
		limit = lvl if lvl > 0 else threshold
		if limit > 0 and b["actual_qty"] <= limit:
			b["reorder_level"] = lvl
			b["reorder_qty"] = rqty
			b["limit"] = limit
			low.append(b)

	if low:
		codes = list({b["item_code"] for b in low})
		names = {i["name"]: i["item_name"] for i in frappe.get_all("Item", filters={"name": ["in", codes]}, fields=["name", "item_name"])}
		for b in low:
			b["item_name"] = names.get(b["item_code"], b["item_code"])
	low.sort(key=lambda b: (b["actual_qty"] - b["limit"]))
	return {"warehouses": whs, "restricted": restricted, "threshold": threshold, "items": low}


@frappe.whitelist()
def get_stock_ledger(item_code=None, warehouse=None, direction=None, from_date=None, to_date=None, limit=100, company=None):
	"""Pergerakan stok (Stock Ledger Entry) untuk gudang user, dengan filter."""
	whs, restricted = _resolve_warehouses(warehouse, company)
	conds = [["warehouse", "in", whs or [""]], ["is_cancelled", "=", 0]]
	if item_code:
		conds.append(["item_code", "=", item_code])
	if from_date:
		conds.append(["posting_date", ">=", from_date])
	if to_date:
		conds.append(["posting_date", "<=", to_date])
	if direction == "in":
		conds.append(["actual_qty", ">", 0])
	elif direction == "out":
		conds.append(["actual_qty", "<", 0])

	sle = frappe.get_all(
		"Stock Ledger Entry",
		filters=conds,
		fields=[
			"name", "posting_date", "posting_time", "item_code", "warehouse",
			"actual_qty", "qty_after_transaction", "voucher_type", "voucher_no",
		],
		order_by="posting_date desc, posting_time desc, creation desc",
		limit_page_length=int(limit),
	)
	if sle:
		codes = list({s["item_code"] for s in sle})
		meta = {
			i["name"]: i
			for i in frappe.get_all("Item", filters={"name": ["in", codes]}, fields=["name", "item_name", "stock_uom"])
		}
		for s in sle:
			m = meta.get(s["item_code"], {})
			s["item_name"] = m.get("item_name", s["item_code"])
			s["stock_uom"] = m.get("stock_uom", "")
	return {"warehouses": whs, "restricted": restricted, "entries": sle}


@frappe.whitelist()
def get_stock_balance(warehouse=None, company=None):
	"""Saldo stok (dari Bin) untuk gudang user. Dikelompokkan per gudang."""
	whs, restricted = _resolve_warehouses(warehouse, company)

	bins = frappe.get_all(
		"Bin",
		filters={"warehouse": ["in", whs or [""]], "actual_qty": ["!=", 0]},
		fields=["item_code", "warehouse", "actual_qty", "reserved_qty", "projected_qty", "stock_uom", "valuation_rate"],
		order_by="warehouse asc, item_code asc",
		limit_page_length=0,
	)
	if bins:
		codes = list({b["item_code"] for b in bins})
		names = {
			i["name"]: i["item_name"]
			for i in frappe.get_all("Item", filters={"name": ["in", codes]}, fields=["name", "item_name"])
		}
		for b in bins:
			b["item_name"] = names.get(b["item_code"], b["item_code"])

	return {"warehouses": whs, "restricted": restricted, "balance": bins}


# Peta key menu (dipakai aplikasi) -> fieldname checkbox di Stock Ops Settings.
MENU_FIELDS = {
	"stock_balance": "show_stock_balance",
	"movement": "show_movement",
	"documents": "show_documents",
	"notifications": "show_notifications",
	"scan": "show_scan",
	"transfer": "show_transfer",
	"low_stock": "show_low_stock",
	"opname": "show_opname",
	"mr": "show_mr",
	"pr": "show_pr",
	"se_in": "show_se_in",
	"se_out": "show_se_out",
	"se_transfer": "show_se_transfer",
	"grn": "show_purchase_receipt",
}


def _menu_settings(settings=None):
	"""Flag tampil/sembunyi tiap menu, dengan override per-role.

	- Default per menu = field global `show_*` (True bila belum migrate/diset).
	- Bila sebuah menu punya baris override untuk salah satu role user, nilai
	  role dipakai (OR antar role: tampil bila ada role yang mengizinkan).
	"""
	s = settings
	if s is None:
		try:
			s = frappe.get_cached_doc("Stock Ops Settings")
		except Exception:
			s = None

	# Pakai nilai yang BENAR-BENAR tersimpan (tabSingles). Field yang belum pernah
	# diset (mis. menu baru ditambah lewat migrate ke doc lama) TIDAK muncul di sini,
	# sehingga default-nya "tampil" (True) — bukan 0/hidden akibat Check di-load jadi 0.
	try:
		stored = frappe.db.get_singles_dict("Stock Ops Settings") or {}
	except Exception:
		stored = {}

	base = {}
	for key, field in MENU_FIELDS.items():
		if field in stored:
			base[key] = bool(int(stored[field] or 0))
		else:
			base[key] = True  # belum diset → tampil secara default

	# Kumpulkan override yang berlaku untuk role user
	roles = set(frappe.get_roles(frappe.session.user))
	applicable = {}  # menu -> list[bool]
	for row in (getattr(s, "menu_overrides", None) or []):
		if row.role in roles and row.menu in MENU_FIELDS:
			applicable.setdefault(row.menu, []).append(bool(row.visible))

	out = {}
	for key in MENU_FIELDS:
		out[key] = any(applicable[key]) if key in applicable else base[key]
	return out


def _user_caps():
	"""Kemampuan user (untuk UI sembunyikan aksi yang tak diizinkan).

	Penegakan tetap di server (API patuh izin standar); ini hanya supaya tombol
	cancel/hapus tak ditampilkan ke Stock Ops User biasa.
	"""
	is_manager = _is_manager()
	can_cancel = is_manager or any(
		frappe.has_permission(dt, ptype="cancel") for dt in ("Material Request", "Stock Entry")
	)
	return {"is_manager": is_manager, "can_cancel": bool(can_cancel), "is_system_manager": _is_system_manager()}


def _app_settings():
	try:
		s = frappe.get_cached_doc("Stock Ops Settings")
	except Exception:
		s = None
	default_lang = (getattr(s, "default_language", None) or "id") if s else "id"
	apk_url = (getattr(s, "flutter_apk_url", None) or "") if s else ""
	return {
		"menu": _menu_settings(s),
		"default_lang": default_lang,
		"flutter_apk_url": apk_url,
		"default_source_warehouse": (getattr(s, "default_source_warehouse", None) or "") if s else "",
		"caps": _user_caps(),
	}


@frappe.whitelist()
def get_app_settings():
	"""Menu flags + bahasa default (untuk refresh tanpa bootstrap penuh)."""
	return _app_settings()


@frappe.whitelist()
def get_notifications(limit=20):
	"""Notifikasi in-app (Notification Log) untuk user login — dipoll aplikasi (tanpa Firebase)."""
	user = frappe.session.user
	items = frappe.get_all(
		"Notification Log",
		filters={"for_user": user},
		fields=["name", "subject", "type", "document_type", "document_name", "read", "creation", "from_user"],
		order_by="creation desc",
		limit_page_length=int(limit),
	)
	unread = frappe.db.count("Notification Log", {"for_user": user, "read": 0})
	return {"items": items, "unread": unread}


@frappe.whitelist()
def mark_notifications_read(name=None):
	"""Tandai satu (name) atau semua notifikasi user sebagai sudah dibaca."""
	user = frappe.session.user
	if name:
		if frappe.db.get_value("Notification Log", name, "for_user") == user:
			frappe.db.set_value("Notification Log", name, "read", 1)
	else:
		frappe.db.sql("UPDATE `tabNotification Log` SET `read`=1 WHERE for_user=%s AND `read`=0", user)
	frappe.db.commit()
	return {"ok": True}


def has_app_permission():
	"""Siapa yang melihat tile Stock Ops di App Switcher desk.
	Dibatasi ke manajer; Stock Ops User biasa cukup pakai PWA (/stock_ops)."""
	if frappe.session.user == "Administrator":
		return True
	roles = set(frappe.get_roles())
	return any(r in roles for r in ("System Manager", "Stock Manager", "Stock Ops Manager"))


@frappe.whitelist()
def get_bootstrap():
	"""Master data untuk Stock Ops PWA dalam satu panggilan (untuk cache offline)."""
	user = frappe.session.user

	scope = _user_scope()

	companies = frappe.get_all("Company", fields=["name", "default_currency", "abbr"], order_by="name")
	warehouses = frappe.get_all(
		"Warehouse",
		filters={"disabled": 0},
		fields=["name", "warehouse_name", "company", "is_group"],
		order_by="name",
		limit_page_length=0,
	)
	# hanya warehouse non-group yang bisa dipakai transaksi
	warehouses = [w for w in warehouses if not w.get("is_group")]

	# Batasi daftar gudang & perusahaan sesuai lingkup user (Employee.stock_ops_warehouses
	# / User Permission). User tanpa batasan tetap melihat semua.
	if scope["restricted"]:
		if scope["allowed_companies"]:
			allowed_co = set(scope["allowed_companies"])
			companies = [c for c in companies if c["name"] in allowed_co]
		if scope["user_whs"]:
			# dibatasi per-gudang (User Permission Warehouse / Employee)
			allowed_wh = set(scope["user_whs"])
			warehouses = [w for w in warehouses if w["name"] in allowed_wh]
		elif scope["allowed_companies"]:
			# dibatasi per-perusahaan saja → tampilkan gudang perusahaan tsb
			allowed_co = set(scope["allowed_companies"])
			warehouses = [w for w in warehouses if w.get("company") in allowed_co]

	items = frappe.get_all(
		"Item",
		filters={"disabled": 0},
		or_filters=[{"is_stock_item": 1}, {"is_fixed_asset": 1}],
		fields=["name as item_code", "item_name", "stock_uom", "image", "item_group", "is_fixed_asset"],
		order_by="item_name",
		limit_page_length=0,
	)
	# barcode (opsional) — siapkan map untuk scan nanti
	barcodes = frappe.get_all("Item Barcode", fields=["parent", "barcode"], limit_page_length=0)
	bc_map = {}
	for b in barcodes:
		bc_map.setdefault(b.parent, b.barcode)
	for it in items:
		it["barcode"] = bc_map.get(it["item_code"], "")

	# UOM yang diizinkan per item (stock_uom factor 1 + konversi tambahan) → untuk ubah UOM di form.
	uom_rows = frappe.get_all(
		"UOM Conversion Detail", fields=["parent", "uom", "conversion_factor"], limit_page_length=0
	)
	uom_map = {}
	for r in uom_rows:
		uom_map.setdefault(r["parent"], []).append({"uom": r["uom"], "conversion_factor": r["conversion_factor"]})
	for it in items:
		su = it["stock_uom"]
		opts = [{"uom": su, "conversion_factor": 1.0}]
		for u in uom_map.get(it["item_code"], []):
			if u["uom"] != su:
				opts.append(u)
		it["uoms"] = opts

	uoms = [u.name for u in frappe.get_all("UOM", filters={"enabled": 1}, fields=["name"], order_by="name", limit_page_length=0)]
	# Supplier bisa tak terbaca oleh role terbatas (mis. Stock User) → jangan gagalkan bootstrap.
	try:
		suppliers = frappe.get_all("Supplier", fields=["name as supplier", "supplier_name"], order_by="supplier_name", limit_page_length=0)
	except frappe.PermissionError:
		suppliers = []

	# Customer (untuk Quotation/penawaran penjualan) — role tanpa akses jual → daftar kosong.
	try:
		customers = frappe.get_all("Customer", fields=["name", "customer_name"], order_by="customer_name", limit_page_length=0)
	except frappe.PermissionError:
		customers = []

	# Lokasi aset (untuk penerimaan barang yang berupa fixed asset). Modul/akses bisa tak ada.
	try:
		locations = frappe.get_all("Location", filters={"is_group": 0}, pluck="name", order_by="name", limit_page_length=0)
	except Exception:
		locations = []

	company = scope["company"] or (companies[0]["name"] if companies else None)
	_app = _app_settings()

	# Konteks persetujuan: apakah user seorang approver (leave approver) + jumlah antrean.
	is_emp_approver = (
		bool(frappe.db.exists("Employee", {"leave_approver": user})) if frappe.db.exists("DocType", "Employee") else False
	)
	pending_approvals = 0
	if frappe.get_meta("Material Request").get_field("workflow_state"):
		pending_approvals = frappe.db.count(
			"Material Request", {"stock_ops_approver": user, "workflow_state": "Pending Approval"}
		)

	# Akses Desk: hanya System User (punya /app) + izin baca per-doctype. Dipakai PWA
	# untuk menampilkan tautan "Buka di Desk" HANYA bila user memang bisa membukanya.
	desk_can_access = frappe.db.get_value("User", user, "user_type") == "System User"
	desk_perms = (
		{dt: bool(frappe.has_permission(dt, "read")) for dt in ("Material Request", "Stock Entry", "Purchase Receipt")}
		if desk_can_access
		else {}
	)

	# Menu Quotation (permintaan barang penjualan) hanya untuk user yang boleh buat Quotation.
	can_quotation = bool(frappe.has_permission("Quotation", "create")) if frappe.db.exists("DocType", "Quotation") else False

	return {
		"user": {"name": user, "full_name": frappe.utils.get_fullname(user)},
		"employee": scope["employee"] or None,
		"companies": companies,
		"warehouses": warehouses,
		"items": items,
		"uoms": uoms,
		"suppliers": suppliers,
		"customers": customers,
		"locations": locations,
		"defaults": {
			"company": company,
			"company_read_only": scope["company_read_only"],
			"source_warehouse": scope["default_source_warehouse"],
		},
		"restricted": scope["restricted"],
		"user_warehouses": scope["user_whs"],
		"menu": _app["menu"],
		"default_lang": _app["default_lang"],
		"flutter_apk_url": _app["flutter_apk_url"],
		"caps": _app["caps"],
		"is_approver": bool(is_emp_approver or pending_approvals or _is_system_manager()),
		"issue_purposes": [p for p in _issue_purposes() if not scope["allowed_companies"] or p["company"] in scope["allowed_companies"]],
		"issue_purpose_required": bool(frappe.db.get_single_value("Stock Ops Settings", "issue_purpose_required")),
		"pending_approvals": pending_approvals,
		"desk": {"can_access": bool(desk_can_access), "perms": desk_perms},
		"can_quotation": can_quotation,
		"server_time": frappe.utils.now(),
	}


@frappe.whitelist()
def create_transaction(data):
	"""Buat Material Request / Stock Entry sebagai draft, idempoten via external_localid.

	`data` = dict/JSON berisi field dokumen (termasuk `doctype`, `external_localid`, `items`).
	Mengembalikan {name, duplicate}.
	"""
	if isinstance(data, str):
		data = json.loads(data)

	doctype = data.get("doctype")
	if doctype not in ALLOWED_DOCTYPES:
		frappe.throw(_("Doctype tidak diizinkan: {0}").format(doctype))

	_assert_warehouses_allowed(_collect_warehouses(data))

	localid = data.get("external_localid")
	if localid:
		existing = frappe.db.get_value(doctype, {"external_localid": localid}, "name")
		if existing:
			return {"name": existing, "duplicate": True}

	if doctype == "Purchase Receipt" and any(i.get("purchase_order") for i in data.get("items") or []):
		doc = _purchase_receipt_from_po(data)
	else:
		doc = frappe.get_doc(data)
	_apply_issue_cost_center(doc)
	doc.insert()  # tetap draft (docstatus = 0)
	frappe.db.commit()
	return {"name": doc.name, "duplicate": False}


def _purchase_receipt_from_po(data):
	"""Bangun Purchase Receipt dari PO lewat mapper ERPNext (sama dengan Desk "Create > Purchase
	Receipt") agar currency, kurs, price list, rate, diskon, pajak & supplier IKUT PO.

	Membangun dari nol membuat ERPNext mengisi ulang currency/price list dari supplier/default
	(mis. Standard Buying) → error "Currency must be equal to …" / "Rate must be same as Purchase
	Order" bila Maintain Same Rate aktif. Dari aplikasi hanya qty, gudang & data tolak yang dipakai.
	"""
	from erpnext.buying.doctype.purchase_order.purchase_order import make_purchase_receipt
	from frappe.utils import flt

	lines = data.get("items") or []
	pos = list(dict.fromkeys(i["purchase_order"] for i in lines if i.get("purchase_order")))
	if len(pos) > 1:
		frappe.throw(_("Satu penerimaan hanya boleh dari satu Purchase Order."))
	po_company = frappe.db.get_value("Purchase Order", pos[0], "company")
	_assert_company_allowed(po_company)
	if data.get("company") and data["company"] != po_company:
		frappe.throw(_("Perusahaan penerimaan harus sama dengan Purchase Order ({0}).").format(po_company))

	pr = make_purchase_receipt(pos[0])
	by_po_item = {i.get("purchase_order_item"): i for i in lines if i.get("purchase_order_item")}
	kept = []
	for row in pr.items:
		line = by_po_item.get(row.purchase_order_item)
		if not line:
			continue  # baris PO yang tidak diterima kali ini
		# Rate PO berlaku per UOM PO; bila user mengganti UOM di aplikasi, konversikan qty ke UOM PO.
		factor = 1.0
		if line.get("uom") and line["uom"] != row.uom:
			factor = flt(line.get("conversion_factor") or 1) / flt(row.conversion_factor or 1)
		accepted = flt(line.get("qty")) * factor
		rejected = flt(line.get("rejected_qty")) * factor
		row.qty = accepted
		row.rejected_qty = rejected
		row.received_qty = accepted + rejected
		if line.get("warehouse"):
			row.warehouse = line["warehouse"]
		row.rejected_warehouse = line.get("rejected_warehouse") if rejected else None
		if line.get("asset_location"):
			row.asset_location = line["asset_location"]
		if line.get("allow_zero_valuation_rate"):
			row.allow_zero_valuation_rate = 1
		kept.append(row)
	pr.set("items", kept)
	# Item tambahan (tanpa link PO) tetap ikut, dengan harga dari aplikasi.
	for line in lines:
		if not line.get("purchase_order"):
			pr.append("items", line)
	if not pr.items:
		frappe.throw(_("Tidak ada item Purchase Order yang diterima."))

	for f in ("posting_date", "set_warehouse", "external_localid", "stock_ops_geolocation", "remarks", "stock_ops_purpose"):
		if data.get(f):
			pr.set(f, data[f])
	return pr


# Jenis dokumen yang memakai Tujuan → cost center (nilai kolom "Berlaku untuk").
PURPOSE_APPLIES = {"SE_OUT": "Stock Out", "GRN": "Penerimaan Barang"}


def _issue_purposes(company=None, applies=None):
	"""Daftar Tujuan → cost center (Stock Ops Settings › Tujuan → Cost Center).

	Perusahaan tiap tujuan = perusahaan cost center-nya, sehingga satu nama tujuan boleh
	dipetakan ke cost center berbeda per perusahaan. `applies_to` = "Semua" / "Stock Out" /
	"Penerimaan Barang". `company` & `applies` = saring (opsional)."""
	if not frappe.db.exists("DocType", "Stock Ops Issue Purpose"):
		return []
	has_applies = bool(frappe.get_meta("Stock Ops Issue Purpose").get_field("applies_to"))
	rows = frappe.get_all(
		"Stock Ops Issue Purpose",
		filters={"parent": "Stock Ops Settings", "parenttype": "Stock Ops Settings"},
		fields=["purpose", "cost_center"] + (["applies_to"] if has_applies else []),
		order_by="idx asc",
	)
	ccs = [r.cost_center for r in rows if r.cost_center]
	cc_company = (
		{c.name: c.company for c in frappe.get_all("Cost Center", filters={"name": ["in", ccs]}, fields=["name", "company"])}
		if ccs
		else {}
	)
	out = [
		{
			"purpose": r.purpose,
			"cost_center": r.cost_center,
			"company": cc_company.get(r.cost_center),
			"applies_to": r.get("applies_to") or "Semua",
		}
		for r in rows
		if r.purpose and r.cost_center
	]
	if company:
		out = [p for p in out if p["company"] == company]
	if applies:
		out = [p for p in out if p["applies_to"] in ("Semua", applies)]
	return out


def _apply_issue_cost_center(doc):
	"""Tujuan → satu cost center seragam untuk semua baris, pada:
	- Stock Out (Stock Entry · Material Issue) → tujuan "Stock Out"/"Semua"; bila tanpa tujuan
	  dipakai Default Cost Center (bila milik perusahaan dokumen).
	- Penerimaan Barang (Purchase Receipt, bukan retur) → tujuan "Penerimaan Barang"/"Semua".
	Tujuan wajib bila diatur & ada tujuan untuk perusahaan + jenis dokumen tsb. Bila tak ada cost
	center terpilih, ERPNext mengisi dari Item/Company/PO seperti biasa.
	"""
	if doc.doctype == "Stock Entry" and doc.get("stock_entry_type") == "Material Issue":
		applies, label = "Stock Out", _("Stock Out")
	elif doc.doctype == "Purchase Receipt" and not doc.get("is_return"):
		applies, label = "Penerimaan Barang", _("Penerimaan Barang")
	else:
		return
	purpose = (doc.get("stock_ops_purpose") or "").strip()
	purposes = _issue_purposes(doc.company, applies)
	cc = None
	if purpose:
		match = next((p for p in purposes if p["purpose"] == purpose), None)
		if not match:
			frappe.throw(_("Tujuan \"{0}\" tidak terdaftar untuk {1} perusahaan {2}.").format(purpose, label, doc.company))
		doc.stock_ops_purpose = purpose
		cc = match["cost_center"]
	elif purposes and frappe.db.get_single_value("Stock Ops Settings", "issue_purpose_required"):
		frappe.throw(_("Tujuan wajib diisi untuk {0}.").format(label))
	elif applies == "Stock Out":
		cc = frappe.db.get_single_value("Stock Ops Settings", "default_cost_center")
		if cc and frappe.db.get_value("Cost Center", cc, "company") != doc.company:
			cc = None
	if cc:
		for row in doc.get("items") or []:
			row.cost_center = cc


@frappe.whitelist()
def create_quotation(customer, items, company=None, external_localid=None, remarks=None):
	"""Buat Quotation (permintaan barang penjualan) draft dari Stock Ops. Idempoten via external_localid.

	`customer` = nama Customer yang sudah ada, ATAU nama bebas (dibuatkan Lead baru untuk calon pelanggan).
	`items`    = list [{item_code, qty, uom}]. Harga (rate) sengaja 0 — diisi tim sales nanti di Desk,
	             lalu Quotation ditarik menjadi Sales Order → Sales Invoice.
	"""
	if isinstance(items, str):
		items = json.loads(items)
	customer = (customer or "").strip()
	if not customer:
		frappe.throw(_("Customer wajib diisi."))
	items = [i for i in (items or []) if i.get("item_code") and (i.get("qty") or 0) > 0]
	if not items:
		frappe.throw(_("Minimal 1 item dengan qty > 0."))

	if external_localid:
		existing = frappe.db.get_value("Quotation", {"external_localid": external_localid}, "name")
		if existing:
			return {"name": existing, "duplicate": True}

	# Tentukan party: Customer yang ada → quotation_to=Customer; selain itu buat/pakai Lead.
	if frappe.db.exists("Customer", customer):
		quotation_to, party_name = "Customer", customer
	elif frappe.db.exists("Lead", {"lead_name": customer}):
		quotation_to, party_name = "Lead", frappe.db.get_value("Lead", {"lead_name": customer}, "name")
	else:
		lead = frappe.get_doc({"doctype": "Lead", "lead_name": customer, "company_name": customer})
		lead.insert(ignore_permissions=True)
		quotation_to, party_name = "Lead", lead.name

	doc = frappe.new_doc("Quotation")
	doc.quotation_to = quotation_to
	doc.party_name = party_name
	if company:
		doc.company = company
	doc.transaction_date = frappe.utils.nowdate()
	if external_localid:
		doc.external_localid = external_localid
	if remarks:
		doc.remarks = remarks
	for it in items:
		row = {"item_code": it.get("item_code"), "qty": it.get("qty") or 0, "rate": 0}
		if it.get("uom"):
			row["uom"] = it.get("uom")
		doc.append("items", row)
	doc.insert()  # draft (docstatus 0)

	# Paksa harga 0: ERPNext otomatis mengisi rate dari Selling Price List saat insert.
	# Sesuai kebutuhan ops ("harga diisi tim sales nanti di Desk"), nolkan rate + total pada
	# draft ini. Saat sales membuka & mengisi harga, ERPNext menghitung ulang seperti biasa.
	_ITEM_ZERO = (
		"rate", "amount", "base_rate", "base_amount", "net_rate", "net_amount",
		"base_net_rate", "base_net_amount", "price_list_rate", "base_price_list_rate", "discount_amount",
	)
	for row in doc.items:
		frappe.db.set_value("Quotation Item", row.name, {f: 0 for f in _ITEM_ZERO}, update_modified=False)
	_PARENT_ZERO = (
		"total", "base_total", "net_total", "base_net_total", "grand_total", "base_grand_total",
		"rounded_total", "base_rounded_total", "total_taxes_and_charges", "base_total_taxes_and_charges",
	)
	frappe.db.set_value("Quotation", doc.name, {f: 0 for f in _PARENT_ZERO}, update_modified=False)
	frappe.db.commit()
	return {"name": doc.name, "duplicate": False}


@frappe.whitelist()
def submit_transaction(doctype, name):
	"""Finalkan dokumen — aksi terpisah, online.

	Bila doctype punya Workflow aktif (mis. Material Request), TIDAK memanggil
	doc.submit() langsung; melainkan menerapkan transition maju sesuai Workflow
	(seperti Desk). Untuk MR Purchase → 'Submit for Approval' (tetap draft, menunggu
	persetujuan); tipe lain → 'Submit' (docstatus 1). Doctype tanpa workflow → submit biasa.
	"""
	if doctype not in ALLOWED_DOCTYPES:
		frappe.throw(_("Doctype tidak diizinkan: {0}").format(doctype))
	doc = frappe.get_doc(doctype, name)

	from frappe.model.workflow import apply_workflow, get_transitions, get_workflow_name

	if get_workflow_name(doctype):
		# MR Purchase wajib punya approver (leave approver) sebelum diajukan — blokir bila kosong.
		# PENTING: apply_workflow() melakukan load_from_db() sehingga perubahan in-memory hilang;
		# maka approver DITULIS ke DB (db_set) dulu agar terbawa saat workflow di-apply + saat
		# Notification "Pending Approval" mengevaluasi penerima (field stock_ops_approver).
		if doctype == "Material Request" and getattr(doc, "material_request_type", None) == "Purchase":
			from stock_ops.approval import resolve_approver

			doc.db_set("stock_ops_approver", resolve_approver(doc.owner))
		transitions = get_transitions(doc)
		if not transitions:
			frappe.throw(_("Tidak ada aksi workflow yang tersedia untuk dokumen ini."))
		apply_workflow(doc, transitions[0].get("action"))
	else:
		doc.submit()

	frappe.db.commit()
	doc.reload()
	return {"name": doc.name, "docstatus": doc.docstatus, "workflow_state": getattr(doc, "workflow_state", None)}


@frappe.whitelist()
def cancel_transaction(doctype, name):
	"""Batalkan dokumen submitted (docstatus 2)."""
	if doctype not in ALLOWED_DOCTYPES:
		frappe.throw(_("Doctype tidak diizinkan: {0}").format(doctype))
	doc = frappe.get_doc(doctype, name)
	doc.cancel()
	frappe.db.commit()
	return {"name": doc.name, "docstatus": doc.docstatus}


@frappe.whitelist()
def get_workflow_transitions(doctype, name):
	"""Aksi workflow yang tersedia untuk user saat ini pada dokumen (seperti Desk)."""
	from frappe.model.workflow import get_transitions

	doc = frappe.get_doc(doctype, name)
	return get_transitions(doc)


@frappe.whitelist()
def apply_workflow_action(doctype, name, action, note=None):
	"""Terapkan aksi workflow (Approve/Reject/dll). Server memverifikasi approver."""
	from frappe.model.workflow import apply_workflow

	doc = frappe.get_doc(doctype, name)
	user = frappe.session.user
	# Approver yang ditunjuk hanya memutuskan (Approve/Reject); Reopen adalah hak pemohon.
	is_approver = getattr(doc, "stock_ops_approver", None) == user and action in ("Approve", "Reject")
	# Pemohon boleh membuka kembali permintaannya sendiri yang ditolak (Rejected → Draft)
	# untuk diperbaiki & diajukan ulang — transition "Reopen" memang diizinkan untuk Stock Ops User.
	is_owner_reopen = (
		action == "Reopen" and doc.owner == user and getattr(doc, "workflow_state", None) == "Rejected"
	)
	is_admin = bool(APPROVAL_ADMIN_ROLES & set(frappe.get_roles()))
	if not (is_approver or is_owner_reopen or is_admin):
		frappe.throw(_("Anda tidak berwenang mengubah status dokumen ini."), frappe.PermissionError)
	if is_admin and not (is_approver or is_owner_reopen):
		_assert_company_allowed(doc.company)
	# Catatan hanya dari approver/admin — Reopen pemohon tak boleh menimpa alasan penolakan.
	if note and not is_owner_reopen:
		doc.stock_ops_approval_note = note
		doc.save(ignore_permissions=True)
		doc.reload()
	apply_workflow(doc, action)
	frappe.db.commit()
	doc.reload()
	return {"name": doc.name, "workflow_state": getattr(doc, "workflow_state", None), "docstatus": doc.docstatus}


@frappe.whitelist()
def get_server_doc(doctype, name):
	"""Detail dokumen server untuk ditampilkan DI aplikasi (Daftar > Server), tanpa membuka Desk.

	Lingkup sama dengan list_recent: perusahaan dalam lingkup user; staf (dibatasi, bukan manajer)
	hanya dokumen miliknya atau yang ia setujui."""
	if doctype not in ALLOWED_DOCTYPES:
		frappe.throw(_("Doctype tidak diizinkan: {0}").format(doctype))
	doc = frappe.get_doc(doctype, name)
	_assert_company_allowed(doc.company)
	user = frappe.session.user
	if _allowed_companies() and not _is_manager() and user not in (doc.owner, doc.get("stock_ops_approver")):
		frappe.throw(_("Anda tidak berwenang melihat dokumen ini."), frappe.PermissionError)

	items = doc.get("items") or []
	first = items[0] if items else frappe._dict()
	if doctype == "Stock Entry":
		src = doc.get("from_warehouse") or first.get("s_warehouse")
		tgt = doc.get("to_warehouse") or first.get("t_warehouse")
	elif doctype == "Material Request":
		src = doc.get("set_from_warehouse") or first.get("from_warehouse")
		tgt = doc.get("set_warehouse") or first.get("warehouse")
	else:
		src, tgt = None, doc.get("set_warehouse") or first.get("warehouse")
	state = doc.get("workflow_state")
	return {
		"doctype": doctype,
		"name": doc.name,
		"docstatus": doc.docstatus,
		"workflow_state": state,
		"approval_note": doc.get("stock_ops_approval_note") if state == "Rejected" else None,
		"company": doc.company,
		"date": str(doc.get("posting_date") or doc.get("transaction_date") or ""),
		"subtype": doc.get("stock_entry_type") or doc.get("material_request_type"),
		"is_return": cint(doc.get("is_return")),
		"source_warehouse": src,
		"target_warehouse": tgt,
		"supplier": doc.get("supplier"),
		"customer": doc.get("party_name"),
		"purpose": doc.get("stock_ops_purpose"),
		"remarks": doc.get("remarks"),
		"owner": doc.owner,
		"approver": doc.get("stock_ops_approver"),
		"items": [
			{
				"item_code": i.item_code,
				"item_name": i.get("item_name"),
				"qty": i.get("qty"),
				"uom": i.get("uom") or i.get("stock_uom"),
				"rejected_qty": i.get("rejected_qty"),
			}
			for i in items
		],
	}


@frappe.whitelist()
def get_doc_state(doctype, name):
	"""Status terkini dokumen dari server (untuk refresh tampilan lokal): docstatus + workflow_state."""
	if doctype not in ALLOWED_DOCTYPES:
		frappe.throw(_("Doctype tidak diizinkan: {0}").format(doctype))
	meta = frappe.get_meta(doctype)
	fields = ["docstatus", "company"]
	for f in ("workflow_state", "stock_ops_approval_note"):
		if meta.get_field(f):
			fields.append(f)
	row = frappe.db.get_value(doctype, name, fields, as_dict=True) or {}
	if row:
		_assert_company_allowed(row.get("company"))
	state = row.get("workflow_state")
	return {
		"docstatus": row.get("docstatus"),
		"workflow_state": state,
		# Alasan penolakan — ditampilkan ke pemohon agar tahu apa yang harus diperbaiki.
		"approval_note": row.get("stock_ops_approval_note") if state == "Rejected" else None,
	}


@frappe.whitelist()
def get_approval_detail(name):
	"""Detail Material Request untuk ditinjau approver sebelum menyetujui."""
	doc = frappe.get_doc("Material Request", name)
	user = frappe.session.user
	if user not in (doc.owner, getattr(doc, "stock_ops_approver", None)):
		if not APPROVAL_ADMIN_ROLES & set(frappe.get_roles()):
			frappe.throw(_("Anda tidak berwenang melihat dokumen ini."), frappe.PermissionError)
		_assert_company_allowed(doc.company)
	return {
		"name": doc.name,
		"owner": doc.owner,
		"material_request_type": doc.material_request_type,
		"company": doc.company,
		"transaction_date": str(doc.transaction_date or ""),
		"schedule_date": str(getattr(doc, "schedule_date", "") or ""),
		"workflow_state": getattr(doc, "workflow_state", None),
		"stock_ops_approver": getattr(doc, "stock_ops_approver", None),
		"items": [
			{
				"item_code": i.item_code,
				"item_name": i.item_name,
				"qty": i.qty,
				"uom": i.uom,
				"warehouse": i.warehouse,
				"rate": i.rate,
			}
			for i in doc.items
		],
	}


@frappe.whitelist()
def list_pending_approvals(limit=50, all=0):
	"""Material Request yang menunggu persetujuan user saat ini.

	`all=1` (khusus System Manager): SEMUA permintaan yang menunggu persetujuan dalam lingkup
	perusahaannya — untuk memantau & mengganti approver yang salah/sudah resign."""
	if not frappe.get_meta("Material Request").get_field("workflow_state"):
		return []
	filters = {"workflow_state": "Pending Approval"}
	if frappe.utils.cint(all):
		_assert_system_manager()
		co = _company_filter()
		if co:
			filters["company"] = co
	else:
		filters["stock_ops_approver"] = frappe.session.user
	rows = frappe.get_all(
		"Material Request",
		filters=filters,
		fields=["name", "transaction_date", "material_request_type", "owner", "company", "workflow_state", "stock_ops_approver"],
		order_by="transaction_date desc, modified desc",
		limit_page_length=int(limit),
	)
	for r in rows:
		r["item_count"] = frappe.db.count("Material Request Item", {"parent": r["name"]})
	return rows


def _is_system_manager():
	return frappe.session.user == "Administrator" or "System Manager" in frappe.get_roles()


def _assert_system_manager():
	if not _is_system_manager():
		frappe.throw(_("Hanya System Manager yang dapat melakukan ini."), frappe.PermissionError)


@frappe.whitelist()
def change_approver(name, approver, reason=None):
	"""System Manager mengganti approver Permintaan Pembelian yang sedang Menunggu Persetujuan
	(mis. approver di Employee salah, atau approver sudah resign). Approver baru langsung
	menerima notifikasi "Persetujuan diperlukan" (email + lonceng) & bisa menyetujui."""
	_assert_system_manager()
	doc = frappe.get_doc("Material Request", name)
	_assert_company_allowed(doc.company)
	if doc.material_request_type != "Purchase" or doc.get("workflow_state") != "Pending Approval":
		frappe.throw(_("Approver hanya bisa diganti saat permintaan pembelian Menunggu Persetujuan."))
	approver = (approver or "").strip()
	if approver in ("", "Guest") or not frappe.db.get_value("User", approver, "enabled"):
		frappe.throw(_("User approver tidak ditemukan atau nonaktif: {0}").format(approver))
	if approver == doc.owner:
		frappe.throw(_("Approver tidak boleh pemohon sendiri."))
	old = doc.get("stock_ops_approver")
	if approver == old:
		return {"name": doc.name, "stock_ops_approver": approver, "changed": False}

	doc.db_set("stock_ops_approver", approver)
	msg = _("Approver diganti dari {0} ke {1} oleh {2}.").format(old or "-", approver, frappe.session.user)
	if reason:
		msg += " " + _("Alasan: {0}").format(reason)
	doc.add_comment("Info", msg)
	# Notifikasi "Pending" hanya terpicu saat workflow_state berubah → kirim ulang template yang
	# sama secara eksplisit ke approver baru.
	for n in ("Stock Ops MR Pending (Email)", "Stock Ops MR Pending (System)"):
		if frappe.db.get_value("Notification", n, "enabled"):
			try:
				frappe.get_doc("Notification", n).send(doc)
			except Exception:
				frappe.log_error(frappe.get_traceback(), "Stock Ops change_approver notify")
	frappe.db.commit()
	return {"name": doc.name, "stock_ops_approver": approver, "changed": True}


@frappe.whitelist()
def search_users(txt=None, limit=20):
	"""Cari user aktif (calon approver) — khusus System Manager."""
	_assert_system_manager()
	txt = (txt or "").strip()
	or_filters = [["name", "like", f"%{txt}%"], ["full_name", "like", f"%{txt}%"]] if txt else None
	return frappe.get_all(
		"User",
		filters={"enabled": 1, "name": ["not in", ["Guest", "Administrator"]]},
		or_filters=or_filters,
		fields=["name", "full_name"],
		order_by="full_name asc",
		limit_page_length=int(limit),
	)


@frappe.whitelist()
def list_recent(company=None, limit=20):
	"""Dokumen terbaru dari server (MR + Stock Entry) — untuk tab 'Server' di Daftar."""
	limit = int(limit)
	out = []
	base = {}
	co = _company_filter(company)
	if co:
		base["company"] = co
	# User dibatasi (staf) hanya melihat dokumen miliknya; manajer melihat seluruh lingkupnya.
	if _allowed_companies() and not _is_manager():
		base["owner"] = frappe.session.user
	mr_filters = dict(base)
	se_filters = dict(base)

	mr_fields = ["name", "material_request_type as subtype", "transaction_date as date", "status", "docstatus", "modified"]
	if frappe.get_meta("Material Request").get_field("workflow_state"):
		mr_fields.append("workflow_state")
	for d in frappe.get_all(
		"Material Request",
		filters=mr_filters,
		fields=mr_fields,
		order_by="modified desc",
		limit_page_length=limit,
	):
		out.append({"doctype": "Material Request", **d})

	for d in frappe.get_all(
		"Stock Entry",
		filters=se_filters,
		fields=["name", "stock_entry_type as subtype", "posting_date as date", "docstatus", "modified"],
		order_by="modified desc",
		limit_page_length=limit,
	):
		out.append({"doctype": "Stock Entry", "status": None, **d})

	for d in frappe.get_all(
		"Purchase Receipt",
		filters=dict(base),
		fields=["name", "supplier as subtype", "is_return", "posting_date as date", "status", "docstatus", "modified"],
		order_by="modified desc",
		limit_page_length=limit,
	):
		out.append({"doctype": "Purchase Receipt", **d})

	out.sort(key=lambda x: x.get("modified") or "", reverse=True)
	for d in out:
		d.pop("modified", None)
	return out[:limit]


@frappe.whitelist()
def report_counts(company=None):
	"""Ringkasan jumlah dokumen bulan berjalan, per subtipe."""
	from frappe.utils import get_first_day, nowdate

	start = str(get_first_day(nowdate()))
	mr_cond = {"transaction_date": [">=", start]}
	se_cond = {"posting_date": [">=", start]}
	co = _company_filter(company)
	if co:
		mr_cond["company"] = co
		se_cond["company"] = co

	res = {"period": start, "mr": {}, "se": {}}
	for tp in ("Material Transfer", "Purchase"):
		c = frappe.db.count("Material Request", {**mr_cond, "material_request_type": tp})
		if c:
			res["mr"][tp] = c
	for tp in ("Material Receipt", "Material Issue", "Material Transfer"):
		c = frappe.db.count("Stock Entry", {**se_cond, "stock_entry_type": tp})
		if c:
			res["se"][tp] = c
	return res


@frappe.whitelist()
def get_or_create_token():
	"""Setelah login (sesi via /api/method/login), kembalikan api_key + api_secret BARU.

	Dipakai app mobile (Capacitor): login user/password sekali, lalu pakai token auth
	untuk semua request berikutnya (tanpa cookie/CSRF) → ramah lintas-origin.
	"""
	user = frappe.session.user
	if user == "Guest":
		frappe.throw(frappe._("Harus login"), frappe.AuthenticationError)

	# Set langsung pada user yang sedang login (bukan generate_keys yang butuh System Manager).
	doc = frappe.get_doc("User", user)
	if not doc.api_key:
		doc.api_key = frappe.generate_hash(length=15)
	secret = frappe.generate_hash(length=15)
	doc.api_secret = secret
	doc.save(ignore_permissions=True)
	frappe.db.commit()
	return {
		"api_key": doc.api_key,
		"api_secret": secret,
		"user": user,
		"full_name": frappe.utils.get_fullname(user),
	}
