// Stock Ops — System Manager dapat mengganti approver Permintaan Pembelian yang sedang
// Menunggu Persetujuan (approver di Employee salah / sudah resign). Lihat api.change_approver.
frappe.ui.form.on("Material Request", {
	refresh(frm) {
		if (frm.doc.material_request_type !== "Purchase" || frm.doc.workflow_state !== "Pending Approval") return;
		if (!frappe.user.has_role("System Manager")) return;

		frm.add_custom_button(__("Ganti Approver"), () => {
			const d = new frappe.ui.Dialog({
				title: __("Ganti Approver"),
				fields: [
					{ fieldtype: "Data", fieldname: "current", label: __("Approver saat ini"), read_only: 1, default: frm.doc.stock_ops_approver || "-" },
					{ fieldtype: "Link", fieldname: "approver", label: __("Approver baru"), options: "User", reqd: 1, get_query: () => ({ filters: { enabled: 1 } }) },
					{ fieldtype: "Small Text", fieldname: "reason", label: __("Alasan") },
				],
				primary_action_label: __("Simpan"),
				primary_action(values) {
					frappe.call({
						method: "stock_ops.api.change_approver",
						args: { name: frm.doc.name, approver: values.approver, reason: values.reason },
						freeze: true,
						callback() {
							d.hide();
							frappe.show_alert({ message: __("Approver diganti ke {0}", [values.approver]), indicator: "green" });
							frm.reload_doc();
						},
					});
				},
			});
			d.show();
		});
	},
});
