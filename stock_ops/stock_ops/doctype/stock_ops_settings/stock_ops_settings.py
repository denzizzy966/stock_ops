# Copyright (c) 2026, RMI and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class StockOpsSettings(Document):
	def validate(self):
		self.validate_issue_purposes()

	def validate_issue_purposes(self):
		"""Tujuan Stock Out: cost center harus non-grup & tiap tujuan unik per perusahaan."""
		seen = set()
		for row in self.get("issue_purposes") or []:
			row.purpose = (row.purpose or "").strip()
			cc = frappe.db.get_value("Cost Center", row.cost_center, ["company", "is_group"], as_dict=True)
			if not cc:
				continue
			if cc.is_group:
				frappe.throw(_("Baris {0}: Cost Center {1} adalah grup — pilih cost center non-grup.").format(row.idx, row.cost_center))
			key = (row.purpose.lower(), cc.company)
			if key in seen:
				frappe.throw(_("Baris {0}: Tujuan \"{1}\" sudah ada untuk perusahaan {2}.").format(row.idx, row.purpose, cc.company))
			seen.add(key)
