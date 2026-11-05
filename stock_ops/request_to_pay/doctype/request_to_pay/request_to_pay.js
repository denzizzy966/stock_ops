// Form Desk Request to Pay: pilihan departemen & unit bisnis dibatasi ke company yang dipilih
// (server tetap memvalidasi — ini hanya agar pilihan yang salah tidak muncul).
frappe.ui.form.on("Request to Pay", {
	setup(frm) {
		frm.set_query("department", () => ({ filters: { company: frm.doc.company, is_group: 0 } }));
		frm.set_query("business_unit", () => ({ filters: { company: frm.doc.company, is_group: 0 } }));
		frm.set_query("payment_purpose", () => ({ filters: { disabled: 0 } }));
	},
	company(frm) {
		frm.set_value("department", null);
		frm.set_value("business_unit", null);
	},
	refresh(frm) {
		if (!frm.is_new()) {
			frm.add_custom_button(__("Buka di Aplikasi"), () =>
				window.open(`/stock_ops#/rtp/${encodeURIComponent(frm.doc.name)}`, "_blank")
			);
		}
	},
});

frappe.ui.form.on("Request to Pay Invoice", {
	amount: recalc,
	tax_withheld: recalc,
	tax_rate: recalc,
});

// Pratinjau total di Desk (nilai final dihitung ulang server saat simpan).
function recalc(frm, cdt, cdn) {
	const row = locals[cdt][cdn];
	const tax = row.tax_withheld ? flt((flt(row.amount) * flt(row.tax_rate)) / 100, 2) : 0;
	frappe.model.set_value(cdt, cdn, "tax_amount", tax);
	frappe.model.set_value(cdt, cdn, "net_amount", flt(flt(row.amount) - tax, 2));
	let amount = 0, total_tax = 0;
	(frm.doc.invoices || []).forEach((r) => {
		amount += flt(r.amount);
		total_tax += r.tax_withheld ? flt((flt(r.amount) * flt(r.tax_rate)) / 100, 2) : 0;
	});
	frm.set_value("total_amount", amount);
	frm.set_value("total_tax", total_tax);
	frm.set_value("total_payment", amount - total_tax);
}
