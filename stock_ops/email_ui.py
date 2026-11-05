# Tampilan email notifikasi Stock Ops — satu layout untuk MR, Request to Pay, Klaim Biaya & Kasbon.
#
# Aturan email-client: tabel + style inline (Gmail/Outlook membuang <style>, flexbox, grid).
# Status, nominal & tanggal penting selalu tebal + diberi warna/sorotan agar tidak terlewat.
#
# Dipakai dari Python (notify RTP/HR) dan dari Jinja DocType Notification (hooks `jinja`):
#   {{ stock_ops_mr_email(doc, "pending") }}
#   {{ stock_ops_email(kicker="Leave Request", title="...", status=doc.status, tone="warn",
#                      doc_name=doc.name, fields=[["Karyawan", doc.employee_name, 1], ...],
#                      cta_url="https://...", cta_label="Check Request") }}
import frappe
from frappe import _
from frappe.utils import cstr, escape_html, flt, fmt_money, formatdate, get_fullname, get_url, get_url_to_form
from markupsafe import Markup

BRAND = "#8a6f4e"
BRAND_SOFT = "#efe7db"
FONT = "font-family:'Segoe UI',Roboto,Helvetica,Arial,sans-serif;"
HILITE = "background:#fde68a;color:#78350f;padding:2px 8px;border-radius:6px;"

# tone → (aksen, latar lembut, tinta)
TONES = {
	"warn": ("#d97706", "#fef3c7", "#92400e"),
	"success": ("#16a34a", "#dcfce7", "#166534"),
	"danger": ("#dc2626", "#fee2e2", "#991b1b"),
	"info": ("#2563eb", "#dbeafe", "#1e3a8a"),
	"paid": ("#0d9488", "#ccfbf1", "#115e59"),
	"neutral": ("#64748b", "#f1f5f9", "#334155"),
}


def e(v):
	return escape_html(cstr(v))


def money(amount, doc=None, currency=None):
	currency = currency or (doc.get("currency") if doc else None) or frappe.db.get_default("currency")
	return fmt_money(flt(amount), currency=currency)


def date(d):
	return formatdate(d, "dd MMM yyyy") if d else ""


def _norm_fields(fields):
	out = []
	for f in fields or ():
		f = list(f)
		if len(f) < 2 or f[1] in (None, ""):
			continue
		out.append((cstr(f[0]), cstr(f[1]), bool(f[2]) if len(f) > 2 else False))
	return out


def render(
	*,
	title,
	kicker="",
	intro="",
	status="",
	tone="info",
	doc_name="",
	amount=None,
	amount_label="",
	amount_sub="",
	fields=(),
	note="",
	note_label="",
	items=(),
	items_title="",
	items_more=0,
	cta_url="",
	cta_label="",
	secondary_url="",
	secondary_label="",
	company="",
	urgent=False,
	preheader="",
):
	"""HTML email lengkap (Markup). `fields`: [(label, nilai, sorot?)]; `items`: [(judul, sub, kanan)]."""
	accent, soft, ink = TONES.get(tone, TONES["info"])
	pre = preheader or " · ".join(x for x in (status, doc_name, cstr(amount or "")) if x)
	h = []
	h.append(
		f'<div style="display:none;max-height:0;overflow:hidden;opacity:0;font-size:1px;line-height:1px;color:#fff">'
		f"{e(pre)}&#8203;&#847;&#8203;&#847;&#8203;&#847;</div>"
	)
	h.append(
		f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" '
		f'style="background:#f4efe8;{FONT}"><tr><td align="center" style="padding:24px 12px">'
		f'<table role="presentation" width="600" cellpadding="0" cellspacing="0" border="0" '
		f'style="width:100%;max-width:600px;background:#ffffff;border:1px solid #e7dfd3;border-radius:16px;'
		f'overflow:hidden;border-collapse:separate">'
	)
	# brand bar
	h.append(
		f'<tr><td style="background:{BRAND};padding:14px 24px;{FONT}">'
		f'<span style="color:#ffffff;font-size:13px;font-weight:800;letter-spacing:2px">STOCK OPS</span>'
		+ (f'<span style="color:{BRAND_SOFT};font-size:12px">&nbsp;&nbsp;·&nbsp;&nbsp;{e(company)}</span>' if company else "")
		+ "</td></tr>"
	)
	if urgent:
		h.append(
			f'<tr><td style="background:#dc2626;padding:10px 24px;color:#ffffff;font-size:14px;font-weight:800;'
			f'letter-spacing:1px;{FONT}">&#9889; {e(_("URGENT — mohon diproses segera"))}</td></tr>'
		)
	# judul
	h.append(f'<tr><td style="padding:26px 24px 6px;{FONT}">')
	if kicker:
		h.append(
			f'<div style="font-size:12px;font-weight:800;letter-spacing:1.5px;text-transform:uppercase;color:{BRAND}">'
			f"{e(kicker)}</div>"
		)
	h.append(f'<div style="margin:6px 0 0;font-size:24px;line-height:1.3;font-weight:800;color:#1f2937">{e(title)}</div>')
	if intro:
		h.append(f'<div style="margin-top:10px;font-size:15px;line-height:1.6;color:#4b5563">{intro}</div>')
	h.append("</td></tr>")
	# status
	if status or doc_name:
		h.append(
			f'<tr><td style="padding:14px 24px 4px"><table role="presentation" width="100%" cellpadding="0" '
			f'cellspacing="0" border="0" style="background:{soft};border-left:6px solid {accent};border-radius:12px">'
			f'<tr><td style="padding:14px 18px;{FONT}">'
			f'<div style="font-size:11px;font-weight:700;letter-spacing:1.5px;text-transform:uppercase;color:{ink}">'
			f'{e(_("Status"))}</div>'
			f'<div style="margin-top:2px;font-size:20px;line-height:1.3;font-weight:800;color:{ink}">{e(status)}</div>'
		)
		# nomor dokumen di bawah status (bukan berdampingan) agar muat di layar HP 360px
		if doc_name:
			h.append(
				f'<div style="margin-top:10px"><span style="display:inline-block;background:#ffffff;'
				f"border:1px solid {accent};border-radius:999px;padding:5px 12px;font-size:13px;font-weight:800;"
				f'color:{ink}">{e(doc_name)}</span></div>'
			)
		h.append("</td></tr></table></td></tr>")
	# nominal besar
	if amount not in (None, ""):
		h.append(
			f'<tr><td style="padding:16px 24px 0;{FONT}">'
			f'<div style="font-size:12px;font-weight:700;letter-spacing:1px;text-transform:uppercase;color:#6b7280">'
			f'{e(amount_label or _("Total"))}</div>'
			f'<div style="margin-top:2px;font-size:30px;line-height:1.2;font-weight:800;color:#111827">{e(amount)}</div>'
			+ (f'<div style="margin-top:2px;font-size:13px;color:#6b7280">{e(amount_sub)}</div>' if amount_sub else "")
			+ "</td></tr>"
		)
	# detail
	rows = _norm_fields(fields)
	if rows:
		h.append(
			'<tr><td style="padding:16px 24px 0"><table role="presentation" width="100%" cellpadding="0" '
			'cellspacing="0" border="0" style="border-collapse:collapse">'
		)
		for label, value, hl in rows:
			v = f'<span style="{HILITE}">{e(value)}</span>' if hl else e(value)
			h.append(
				f'<tr><td valign="top" width="38%" style="padding:10px 12px 10px 0;border-bottom:1px solid #f0ebe3;'
				f'font-size:13px;color:#6b7280;{FONT}">{e(label)}</td>'
				f'<td valign="top" style="padding:10px 0;border-bottom:1px solid #f0ebe3;font-size:14px;font-weight:700;'
				f'color:#111827;{FONT}">{v}</td></tr>'
			)
		h.append("</table></td></tr>")
	# catatan / alasan
	if note:
		h.append(
			f'<tr><td style="padding:18px 24px 0"><table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
			f'border="0" style="background:{soft};border:1px solid {accent};border-radius:12px"><tr>'
			f'<td style="padding:14px 18px;{FONT}"><div style="font-size:12px;font-weight:800;letter-spacing:1px;'
			f'text-transform:uppercase;color:{ink}">{e(note_label or _("Catatan"))}</div>'
			f'<div style="margin-top:4px;font-size:15px;line-height:1.55;font-weight:700;color:#111827">{e(note)}</div>'
			"</td></tr></table></td></tr>"
		)
	# rincian baris
	if items:
		h.append(
			f'<tr><td style="padding:20px 24px 0;{FONT}">'
			f'<div style="font-size:12px;font-weight:800;letter-spacing:1px;text-transform:uppercase;color:#6b7280;'
			f'margin-bottom:6px">{e(items_title or _("Rincian"))}</div>'
			'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" '
			'style="border:1px solid #ddd2c2;border-radius:12px;border-collapse:separate">'
		)
		for i, (head, sub, right) in enumerate(items):
			bg = "#faf7f2" if i % 2 else "#ffffff"
			top = "" if i == 0 else "border-top:1px solid #f0ebe3;"
			h.append(
				f'<tr><td style="background:{bg};{top}padding:10px 14px;{FONT}">'
				f'<div style="font-size:14px;font-weight:700;color:#111827">{e(head)}</div>'
				+ (f'<div style="font-size:12px;color:#6b7280;margin-top:1px">{e(sub)}</div>' if sub else "")
				+ f'</td><td align="right" valign="top" style="background:{bg};{top}padding:10px 14px;font-size:14px;'
				f'font-weight:800;color:#111827;white-space:nowrap;{FONT}">{e(right)}</td></tr>'
			)
		if items_more:
			h.append(
				f'<tr><td colspan="2" style="border-top:1px solid #f0ebe3;padding:8px 14px;font-size:12px;color:#6b7280;{FONT}">'
				f'{e(_("+ {0} baris lainnya").format(items_more))}</td></tr>'
			)
		h.append("</table></td></tr>")
	# tombol
	if cta_url:
		h.append(
			f'<tr><td align="left" style="padding:26px 24px 4px"><table role="presentation" cellpadding="0" '
			f'cellspacing="0" border="0"><tr><td bgcolor="{BRAND}" style="border-radius:12px">'
			f'<a href="{e(cta_url)}" target="_blank" style="display:inline-block;padding:14px 28px;font-size:15px;'
			f'font-weight:800;color:#ffffff;text-decoration:none;border-radius:12px;{FONT}">{e(cta_label or _("Buka"))} &rarr;</a>'
			"</td></tr></table>"
		)
		if secondary_url:
			h.append(
				f'<div style="margin-top:12px;font-size:13px;color:#6b7280;{FONT}">{e(_("atau"))} '
				f'<a href="{e(secondary_url)}" target="_blank" style="color:{BRAND};font-weight:700">'
				f"{e(secondary_label or _('buka di Desk ERPNext'))}</a></div>"
			)
		h.append("</td></tr>")
	# footer
	h.append(
		f'<tr><td style="padding:24px 24px 0"></td></tr><tr><td style="background:#faf7f2;border-top:1px solid #eee7dc;'
		f'padding:16px 24px;font-size:12px;line-height:1.5;color:#9ca3af;{FONT}">'
		f'{e(_("Email otomatis dari Stock Ops — mohon tidak membalas email ini."))}<br>'
		f'<a href="{e(get_url("/stock_ops"))}" style="color:#9ca3af">{e(get_url("/stock_ops"))}</a></td></tr>'
	)
	h.append("</table></td></tr></table>")
	return Markup("".join(h))


def stock_ops_email(**kw):
	"""Versi Jinja (untuk Notification buatan sendiri, mis. Leave Request)."""
	allowed = render.__kwdefaults__.keys() | {"title"}
	kw = {k: v for k, v in kw.items() if k in allowed}
	# intro dari template Jinja = teks biasa (di-escape); pakai |safe bila memang ingin HTML.
	if kw.get("intro") and not isinstance(kw["intro"], Markup):
		kw["intro"] = e(kw["intro"])
	return render(**kw)


def stock_ops_fullname(user):
	return get_fullname(user) if user else ""


def _items_cap(rows, limit=8):
	return rows[:limit], max(0, len(rows) - limit)


# ── Material Request (dipanggil dari DocType Notification) ──
MR_EVENTS = {
	# event: (tone, status, judul, intro)
	"pending": ("warn", "Menunggu persetujuan", "Persetujuan Anda diperlukan",
		"<b>{requester}</b> mengajukan permintaan pembelian dan menunggu keputusan Anda."),
	"approved": ("success", "Disetujui", "Siap diproses menjadi Purchase Order",
		"Permintaan pembelian dari <b>{requester}</b> sudah <b>disetujui</b>. Silakan buatkan Purchase Order."),
	"rejected": ("danger", "Ditolak", "Permintaan pembelian Anda ditolak",
		"Permintaan pembelian Anda <b>ditolak</b> oleh <b>{approver}</b>. Lihat alasannya di bawah."),
}


def stock_ops_mr_email(doc, event="pending"):
	tone, status, title, intro = MR_EVENTS.get(event, MR_EVENTS["pending"])
	requester = get_fullname(doc.owner)
	approver = get_fullname(doc.get("stock_ops_approver")) if doc.get("stock_ops_approver") else "-"
	rows = [
		(
			f"{r.item_code} — {r.item_name}" if r.item_name and r.item_name != r.item_code else r.item_code,
			" · ".join(x for x in (r.get("warehouse"), date(r.get("schedule_date"))) if x),
			f"{frappe.format_value(r.qty, {'fieldtype': 'Float'})} {r.uom or r.stock_uom or ''}".strip(),
		)
		for r in doc.get("items") or []
	]
	rows, more = _items_cap(rows)
	app = get_url("/stock_ops#/approvals") if event == "pending" else get_url(
		f"/stock_ops#/sdoc/Material%20Request/{doc.name}"
	)
	return render(
		kicker=_("Permintaan Pembelian"),
		title=_(title),
		intro=_(intro).format(requester=e(requester), approver=e(approver)),
		status=_(status),
		tone=tone,
		doc_name=doc.name,
		company=doc.company,
		fields=[
			(_("Pemohon"), requester),
			(_("Dibutuhkan tanggal"), date(doc.schedule_date), True),
			(_("Gudang tujuan"), doc.get("set_warehouse")),
			(_("Approver"), approver),
			(_("Jumlah item"), len(doc.get("items") or [])),
		],
		note=doc.get("stock_ops_approval_note") if event != "pending" else "",
		note_label=_("Alasan penolakan") if event == "rejected" else _("Catatan approver"),
		items=rows,
		items_more=more,
		items_title=_("Item yang diminta"),
		cta_url=app,
		cta_label=_("Setujui / Tolak di Stock Ops") if event == "pending" else _("Lihat permintaan"),
		secondary_url=get_url_to_form("Material Request", doc.name),
		secondary_label=_("buat Purchase Order di Desk") if event == "approved" else _("buka di Desk ERPNext"),
		preheader=f"{_(status)} · {doc.name} · {requester}",
	)
