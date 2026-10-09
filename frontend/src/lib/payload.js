import { DOC_TYPES } from '../data/mock'

// Ubah objek dokumen app → payload Frappe sesuai DocType.
export function buildPayload(doc) {
  const cfg = DOC_TYPES[doc.type]
  if (cfg.doctype === 'Material Request') return buildMR(doc, cfg)
  if (cfg.doctype === 'Purchase Receipt') return buildPR(doc, cfg)
  return buildSE(doc, cfg)
}

// Purchase Receipt — penerimaan barang dari supplier (menambah stok saat submit).
// Mendukung: link Purchase Order (per item), qty diterima vs ditolak, gudang terima/tolak,
// dan lokasi aset untuk item fixed-asset.
function buildPR(doc) {
  return clean({
    doctype: 'Purchase Receipt',
    company: doc.company,
    posting_date: doc.date,
    supplier: doc.supplier || undefined,
    set_warehouse: doc.targetWarehouse || undefined, // gudang penerimaan (accepted) default
    external_localid: doc.localId,
    stock_ops_geolocation: doc.geo || undefined,
    remarks: doc.remark || undefined,
    items: doc.items.map((i) => {
      const accepted = Number(i.qty) || 0
      const rejected = Number(i.rejectedQty) || 0
      return clean({
        item_code: i.item_code,
        qty: accepted, // accepted qty
        rejected_qty: rejected || undefined,
        received_qty: accepted + rejected,
        uom: i.uom,
        conversion_factor: Number(i.conversionFactor) || 1,
        rate: Number(i.rate) || 0,
        warehouse: doc.targetWarehouse || undefined, // gudang terima (accepted)
        rejected_warehouse: rejected > 0 ? doc.rejectedWarehouse || undefined : undefined,
        asset_location: i.is_fixed_asset ? doc.assetLocation || undefined : undefined,
        // link ke Purchase Order (qty terima divalidasi terhadap qty pesan)
        purchase_order: i.purchase_order || undefined,
        purchase_order_item: i.purchase_order_item || undefined,
        // hindari error "valuation/incoming rate" untuk penerimaan tanpa harga
        allow_zero_valuation_rate: 1
      })
    })
  })
}

function clean(obj) {
  Object.keys(obj).forEach((k) => obj[k] === undefined && delete obj[k])
  return obj
}

function buildMR(doc, cfg) {
  const mrType = doc.type === 'MR' ? 'Material Transfer' : 'Purchase'
  return {
    doctype: 'Material Request',
    material_request_type: mrType,
    company: doc.company,
    transaction_date: doc.date,
    schedule_date: doc.date,
    external_localid: doc.localId,
    stock_ops_geolocation: doc.geo || undefined,
    remarks: doc.remark || undefined,
    items: doc.items.map((i) =>
      clean({
        item_code: i.item_code,
        qty: i.qty,
        uom: i.uom,
        conversion_factor: Number(i.conversionFactor) || 1,
        schedule_date: doc.date,
        warehouse: doc.targetWarehouse || undefined,
        from_warehouse: cfg.source ? doc.sourceWarehouse : undefined
      })
    )
  }
}

function buildSE(doc, cfg) {
  const seType = { SE_IN: 'Material Receipt', SE_OUT: 'Material Issue', SE_TRANSFER: 'Material Transfer' }[doc.type]
  return clean({
    doctype: 'Stock Entry',
    stock_entry_type: seType,
    company: doc.company,
    posting_date: doc.date,
    external_localid: doc.localId,
    stock_ops_geolocation: doc.geo || undefined,
    remarks: doc.remark || undefined,
    // Stock Out: tujuan → cost center seragam (diterapkan server dari Stock Ops Settings)
    stock_ops_purpose: doc.type === 'SE_OUT' ? doc.purpose || undefined : undefined,
    from_warehouse: cfg.source ? doc.sourceWarehouse : undefined,
    to_warehouse: cfg.target ? doc.targetWarehouse : undefined,
    items: doc.items.map((i) =>
      clean({
        item_code: i.item_code,
        qty: i.qty,
        uom: i.uom,
        conversion_factor: Number(i.conversionFactor) || 1,
        s_warehouse: cfg.source ? doc.sourceWarehouse : undefined,
        t_warehouse: cfg.target ? doc.targetWarehouse : undefined,
        // hindari error "valuation rate not found" untuk item tanpa nilai (testing)
        allow_zero_valuation_rate: 1
      })
    )
  })
}
