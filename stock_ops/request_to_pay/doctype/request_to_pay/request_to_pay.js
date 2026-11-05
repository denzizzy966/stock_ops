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
		const pending = (frm.doc.invoices || []).filter((r) => !r.purchase_invoice);
		if (
			frm.doc.docstatus === 1 &&
			frm.doc.workflow_state === "Approved" &&
			pending.length &&
			frappe.model.can_create("Purchase Invoice")
		) {
			frm.add_custom_button(__("Buat Purchase Invoice"), () => make_purchase_invoices(frm), __("Buat"));
		}
		const billed = (frm.doc.invoices || []).filter((r) => r.purchase_invoice);
		if (billed.length) {
			frm.add_custom_button(
				__("Purchase Invoice"),
				() => frappe.set_route("List", "Purchase Invoice", { request_to_pay: frm.doc.name }),
				__("Lihat")
			);
			if (frm.doc.workflow_state === "Approved") {
				frm.set_intro(
					__("Purchase Invoice sudah dibuat ({0}/{1} invoice). Status menjadi Paid otomatis setelah semuanya lunas lewat Payment Entry.", [
						billed.length,
						frm.doc.invoices.length,
					]),
					"blue"
				);
			}
		}
	},
});

// Dialog "Buat Purchase Invoice": satu blok per baris invoice yang belum punya PI.
// Supplier terisi dari baris / pilihan sebelumnya / nama yang sama; bila tidak ada → pilih,
// atau centang "Supplier baru" (dibuat dari nama vendor + Tax ID). Akun biaya disarankan dari
// akun terakhir supplier itu. Hasilnya PI DRAFT — Finance memeriksa lalu submit.
function make_purchase_invoices(frm) {
	frappe.call({
		method: "stock_ops.request_to_pay.accounting.get_billing_dialog",
		args: { name: frm.doc.name },
		freeze: true,
	}).then(({ message: data }) => {
		if (!data.rows.length) return frappe.msgprint(__("Semua invoice sudah punya Purchase Invoice."));
		const fmt = (v) => format_currency(v, data.currency);
		const fields = [];
		if (data.missing_tax_accounts.length) {
			fields.push({
				fieldtype: "HTML",
				options: `<div class="alert alert-warning small">${__(
					"Akun pajak {0} untuk {1} belum diatur di Stock Ops Settings → Akun Pajak Dipotong.",
					[data.missing_tax_accounts.join(", "), data.company]
				)}</div>`,
			});
		}
		data.rows.forEach((r, i) => {
			const tax = r.tax_withheld
				? ` · ${__("Pajak")} ${r.tax_rate}%: <b>− ${fmt(r.tax_amount)}</b>`
				: "";
			const src = { row: __("dari pengajuan"), history: __("pilihan sebelumnya"), name: __("nama sama") }[
				r.supplier_source
			];
			fields.push(
				{ fieldtype: "Section Break", label: `${__("Invoice")} ${r.idx}` },
				{
					fieldtype: "HTML",
					options: `<div class="small" style="margin-bottom:8px"><b>${frappe.utils.escape_html(
						r.vendor_name || ""
					)}</b> · ${__("No.")} ${frappe.utils.escape_html(r.invoice_no || "—")}<br>${__("Nominal")} ${fmt(
						r.amount
					)}${tax} · ${__("Dibayar")} <b>${fmt(r.net_amount)}</b></div>`,
				},
				{
					fieldtype: "Link",
					fieldname: `supplier_${i}`,
					label: __("Supplier"),
					options: "Supplier",
					default: r.supplier,
					description: r.supplier
						? __("Saran: {0}", [src])
						: r.similar.length
						? __("Mirip: {0}", [r.similar.map(frappe.utils.escape_html).join(", ")])
						: __("Belum ada supplier yang cocok."),
					onchange() {
						// Supplier diganti → sarankan akun terakhir supplier itu (bila akun belum diisi).
						const sup = dialog.get_value(`supplier_${i}`);
						if (!sup || dialog.get_value(`account_${i}`)) return;
						frappe.call({
							method: "stock_ops.request_to_pay.accounting.suggest_expense_account",
							args: { supplier: sup, company: data.company },
						}).then(({ message }) => message && dialog.set_value(`account_${i}`, message));
					},
				},
				{
					fieldtype: "Check",
					fieldname: `new_${i}`,
					label: __("Supplier baru: \"{0}\"", [frappe.utils.escape_html(r.vendor_name || "")]),
					depends_on: `eval:!doc.supplier_${i}`,
					hidden: data.can_create_supplier ? 0 : 1,
				},
				{ fieldtype: "Column Break" },
				{
					fieldtype: "Link",
					fieldname: `account_${i}`,
					label: __("Akun Biaya"),
					options: "Account",
					default: r.expense_account,
					reqd: 1,
					get_query: () => ({ filters: { company: data.company, is_group: 0 } }),
				},
				...(r.tax_withheld
					? [
							{
								fieldtype: "Select",
								fieldname: `tax_type_${i}`,
								label: __("Jenis Pajak"),
								options: ["PPh 23", "PPh 21", "PPh 4(2)"],
								default: r.tax_type,
								reqd: 1,
							},
					  ]
					: [])
			);
		});
		const dialog = new frappe.ui.Dialog({
			title: __("Buat Purchase Invoice · {0}", [frm.doc.name]),
			size: "large",
			fields,
			primary_action_label: __("Buat Draft"),
			primary_action(values) {
				const rows = data.rows.map((r, i) => ({
					row: r.row,
					supplier: values[`supplier_${i}`] || null,
					new_supplier: values[`new_${i}`] ? 1 : 0,
					expense_account: values[`account_${i}`],
					tax_type: values[`tax_type_${i}`] || null,
				}));
				const miss = rows.find((x) => !x.supplier && !x.new_supplier);
				if (miss) {
					const r = data.rows.find((x) => x.row === miss.row);
					return frappe.msgprint(
						data.can_create_supplier
							? __("Invoice {0}: pilih Supplier atau centang Supplier baru.", [r.idx])
							: __("Invoice {0}: pilih Supplier. Supplier baru dibuat oleh Purchase Manager.", [r.idx])
					);
				}
				frappe.call({
					method: "stock_ops.request_to_pay.accounting.make_purchase_invoices",
					args: { name: frm.doc.name, rows },
					freeze: true,
					freeze_message: __("Membuat Purchase Invoice..."),
				}).then(({ message }) => {
					dialog.hide();
					const made = message.created || [];
					frappe.show_alert({ message: __("{0} Purchase Invoice draft dibuat", [made.length]), indicator: "green" });
					if (made.length === 1) frappe.set_route("Form", "Purchase Invoice", made[0].purchase_invoice);
					else frappe.set_route("List", "Purchase Invoice", { request_to_pay: frm.doc.name });
				});
			},
		});
		dialog.show();
	});
}

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
