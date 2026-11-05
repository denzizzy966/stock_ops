# Request to Pay — pengajuan pembayaran vendor (pengganti form Jotform "REQUEST TO PAY").
#
# Dokumen ini HANYA menampung pengajuan + persetujuannya; tidak membuat jurnal sendiri.
# Setelah Approved, Finance membuat Purchase Invoice dari sini (request_to_pay/accounting.py);
# pelunasan PI (Payment Entry) mengubah status menjadi Paid secara otomatis.
# Alur persetujuan memakai Workflow "Request to Pay Approval" (dibuat di setup/rtp.py):
#   Draft → Pending Tax Review → Pending FAT Approval → (Pending HOD Approval) → Pending Global Approval
#         → Approved (docstatus 1) → Paid
# Multi-company: company wajib; department & unit bisnis (Cost Center) harus milik company yang sama;
# mata uang mengikuti default company (IDR / THB).
import frappe
from frappe import _
from frappe.model.document import Document
from frappe.model.naming import make_autoname
from frappe.utils import flt, getdate, today

# State yang mengirim notifikasi / penugasan — dipakai stock_ops.request_to_pay.notify.
EDITABLE_STATES = ("Draft", "Rejected", "", None)


class RequesttoPay(Document):
	def autoname(self):
		# Penomoran per company: RTP-RMI-2026-00001 / RTP-MET-2026-00001.
		abbr = frappe.get_cached_value("Company", self.company, "abbr") or "X"
		self.name = make_autoname(f"RTP-{abbr}-.YYYY.-.#####", doc=self)

	def validate(self):
		if not self.requester:
			self.requester = frappe.session.user
		self.currency = frappe.get_cached_value("Company", self.company, "default_currency")
		self._validate_company_links()
		self._validate_invoices()
		self.calculate_totals()
		self.requires_hod = 1 if needs_hod_approval(self) else 0
		# Judul list = vendor yang dibayar (pengaju & total sudah punya kolom sendiri).
		vendors = list(dict.fromkeys((r.vendor_name or "").strip() for r in self.invoices if r.vendor_name))
		self.title = (vendors[0] + (f" +{len(vendors) - 1}" if len(vendors) > 1 else "")) if vendors else self.payment_purpose

	def _validate_company_links(self):
		dept_co = frappe.db.get_value("Department", self.department, "company") if self.department else None
		if dept_co and dept_co != self.company:
			frappe.throw(_("Departemen {0} bukan milik {1}.").format(self.department, self.company))
		if self.business_unit:
			cc = frappe.db.get_value("Cost Center", self.business_unit, ["company", "is_group"], as_dict=True)
			if not cc or cc.company != self.company:
				frappe.throw(_("Unit bisnis {0} bukan milik {1}.").format(self.business_unit, self.company))
			if cc.is_group:
				frappe.throw(_("Unit bisnis {0} adalah grup; pilih cost center turunannya.").format(self.business_unit))
		if self.payment_purpose:
			p = frappe.db.get_value("Request to Pay Purpose", self.payment_purpose, ["disabled", "is_other"], as_dict=True) or {}
			if p.get("disabled"):
				frappe.throw(_("Tujuan pembayaran {0} sudah nonaktif.").format(self.payment_purpose))
			# Dicek di sini (bukan mandatory_depends_on saja): flag fetch_from baru terisi setelah cek wajib-isi.
			self.purpose_requires_detail = 1 if p.get("is_other") else 0
			if self.purpose_requires_detail and not (self.purpose_detail or "").strip():
				frappe.throw(_("Sebutkan tujuan pembayarannya (tujuan {0}).").format(self.payment_purpose))

	def _validate_invoices(self):
		if not self.invoices:
			frappe.throw(_("Tambahkan minimal satu invoice."))
		leaving_draft = self.workflow_state not in EDITABLE_STATES
		for row in self.invoices:
			if flt(row.amount) <= 0:
				frappe.throw(_("Baris {0}: nominal invoice harus lebih dari 0.").format(row.idx))
			if row.tax_withheld:
				if not (0 < flt(row.tax_rate) < 100):
					frappe.throw(_("Baris {0}: tarif pajak harus antara 0 dan 100%.").format(row.idx))
				if not (row.tax_id or "").strip():
					frappe.throw(_("Baris {0}: isi Tax ID vendor (NPWP / NIK / Thai Tax ID).").format(row.idx))
				if leaving_draft and not row.tax_type:
					frappe.throw(_("Baris {0}: pilih jenis pajak (PPh 23 / PPh 21 / PPh 4(2)).").format(row.idx))
			else:
				row.tax_type = None
			# File invoice boleh menyusul saat Draft, tapi wajib sebelum diajukan.
			if leaving_draft and not row.invoice_file:
				frappe.throw(_("Baris {0}: unggah file invoice sebelum diajukan.").format(row.idx))
		if leaving_draft and self.payment_date and getdate(self.payment_date) < getdate(self.creation or today()):
			frappe.throw(_("Tanggal pembayaran tidak boleh sebelum tanggal pengajuan."))

	def calculate_totals(self):
		"""Pajak di form ini = potongan (PPh / WHT): total dibayar = nominal × (1 − tarif%).
		Contoh data Jotform: 918.750 × 97,5% = 895.781,25."""
		precision = self.precision("total_payment") or 2
		total = tax = 0.0
		for row in self.invoices:
			row.tax_amount = flt(flt(row.amount) * flt(row.tax_rate) / 100, precision) if row.tax_withheld else 0
			if not row.tax_withheld:
				row.tax_rate = 0
			row.net_amount = flt(flt(row.amount) - row.tax_amount, precision)
			total += flt(row.amount)
			tax += row.tax_amount
		self.total_amount = flt(total, precision)
		self.total_tax = flt(tax, precision)
		self.total_payment = flt(total - tax, precision)

	# ── notifikasi per perubahan status (lihat notify.py) ──
	def on_update(self):
		self._state_changed()

	def on_submit(self):
		self._state_changed()

	def before_update_after_submit(self):
		# Pengajuan yang sudah punya Purchase Invoice: "Paid" hanya dari pelunasan PI (Payment Entry),
		# bukan tombol "Mark as Paid" — supaya status tidak berbeda dengan buku besar.
		if (
			self.has_value_changed("workflow_state")
			and self.workflow_state == "Paid"
			and any(r.purchase_invoice for r in self.invoices)
		):
			frappe.throw(
				_("Pengajuan ini sudah dibuatkan Purchase Invoice; status Paid otomatis setelah Payment Entry di-submit.")
			)

	def on_update_after_submit(self):
		if self.workflow_state == "Paid" and not self.paid_on:
			self.db_set("paid_on", today())
		self._state_changed()

	def _state_changed(self):
		if self.has_value_changed("workflow_state"):
			from stock_ops.request_to_pay.notify import on_state_change

			on_state_change(self)


def needs_hod_approval(doc):
	"""Apakah pengajuan ini harus lewat persetujuan HOD (setelah FAT, sebelum Global Team)?

	Di Jotform: departemen OPS yang TIDAK urgent → Approval HOD; yang urgent langsung lanjut.
	Hasilnya disimpan di `doc.requires_hod` dan dipakai kondisi transisi Workflow
	(FAT "Approve" → Pending HOD Approval bila 1, → Pending Global Approval bila 0).

	Aturan diatur Finance di Stock Ops Settings (tanpa ubah kode):
	  - "Departemen Wajib Persetujuan HOD": daftar Department. Department bersifat per company
	    ("Operation and Asset - RMI"), jadi company yang tak punya baris (mis. MET) tidak memakai HOD.
	  - "Urgent Lewati HOD" (default aktif): pengajuan Urgent langsung ke Global Team.
	"""
	if not doc.department:
		return False
	settings = frappe.get_cached_doc("Stock Ops Settings")
	hod_departments = {row.department for row in (settings.get("rtp_hod_departments") or [])}
	if doc.department not in hod_departments:
		return False
	skip_urgent = settings.get("rtp_hod_skip_urgent")
	if skip_urgent is None:
		skip_urgent = 1
	return not (skip_urgent and doc.urgency == "Urgent")
