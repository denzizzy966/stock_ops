// Dummy master data — meniru struktur ERPNext (P0, tanpa backend).
// Di P1 ini diganti hasil fetch /api/resource + cache IndexedDB.

export const COMPANIES = ['Global Magicko', 'RMI Warehouse']

export const WAREHOUSES = [
  'Gudang Utama - GM',
  'Gudang Produksi - GM',
  'Gudang Transit - GM',
  'Toko Jakarta - GM',
  'Toko Bandung - GM',
  'Reject - GM'
]

export const UOMS = ['Nos', 'Box', 'Kg', 'Pcs', 'Liter', 'Pack']

export const SUPPLIERS = ['PT Sumber Makmur', 'CV Aneka Jaya', 'PT Mitra Sentosa']

// Beberapa item contoh. `image` memakai placeholder gradien (data URI) agar tampil tanpa internet.
function ph(label, c1, c2) {
  const svg = `<svg xmlns='http://www.w3.org/2000/svg' width='120' height='120'>
    <defs><linearGradient id='g' x1='0' y1='0' x2='1' y2='1'>
    <stop offset='0' stop-color='${c1}'/><stop offset='1' stop-color='${c2}'/></linearGradient></defs>
    <rect width='120' height='120' rx='14' fill='url(#g)'/>
    <text x='60' y='68' font-size='42' text-anchor='middle' fill='white' font-family='sans-serif'>${label}</text>
  </svg>`
  return 'data:image/svg+xml;utf8,' + encodeURIComponent(svg)
}

export const ITEMS = [
  { item_code: 'ITM-0001', item_name: 'Kabel NYM 2x1.5mm', stock_uom: 'Nos', barcode: '8991234500017', image: ph('🔌', '#0ea5e9', '#0b5cff') },
  { item_code: 'ITM-0002', item_name: 'Lampu LED 12W', stock_uom: 'Pcs', barcode: '8991234500024', image: ph('💡', '#f59e0b', '#ef4444') },
  { item_code: 'ITM-0003', item_name: 'Cat Tembok Putih 5kg', stock_uom: 'Box', barcode: '8991234500031', image: ph('🪣', '#22c55e', '#15803d') },
  { item_code: 'ITM-0004', item_name: 'Pipa PVC 3/4"', stock_uom: 'Nos', barcode: '8991234500048', image: ph('🟦', '#64748b', '#334155') },
  { item_code: 'ITM-0005', item_name: 'Semen Portland 40kg', stock_uom: 'Box', barcode: '8991234500055', image: ph('🧱', '#a16207', '#713f12') },
  { item_code: 'ITM-0006', item_name: 'Keran Air Stainless', stock_uom: 'Pcs', barcode: '8991234500062', image: ph('🚰', '#06b6d4', '#0e7490') },
  { item_code: 'ITM-0007', item_name: 'Sekring MCB 10A', stock_uom: 'Pcs', barcode: '8991234500079', image: ph('⚡', '#eab308', '#ca8a04') },
  { item_code: 'ITM-0008', item_name: 'Lem Kayu 1kg', stock_uom: 'Nos', barcode: '8991234500086', image: ph('🪵', '#d97706', '#92400e') },
  { item_code: 'ITM-0009', item_name: 'Paku Beton 5cm', stock_uom: 'Kg', barcode: '8991234500093', image: ph('📌', '#94a3b8', '#475569') },
  { item_code: 'ITM-0010', item_name: 'Engsel Pintu 4"', stock_uom: 'Pack', barcode: '8991234500109', image: ph('🚪', '#8b5cf6', '#6d28d9') }
]

// Konfigurasi tiap jenis transaksi → DocType + perilaku gudang.
export const DOC_TYPES = {
  MR: {
    key: 'MR', short: 'MR', label: 'Material Request — Transfer',
    doctype: 'Material Request', meta: 'material_request_type=Material Transfer',
    icon: 'request-transfer', color: '#0b5cff', source: true, target: true
  },
  PR: {
    key: 'PR', short: 'PR', label: 'Material Request — Purchase',
    doctype: 'Material Request', meta: 'material_request_type=Purchase',
    icon: 'cart', color: '#7c3aed', source: false, target: true, supplier: true
  },
  SE_IN: {
    key: 'SE_IN', short: 'IN', label: 'Stock In — Material Receipt',
    doctype: 'Stock Entry', meta: 'stock_entry_type=Material Receipt',
    icon: 'stock-in', color: '#16a34a', source: false, target: true, onlineOnly: true
  },
  SE_OUT: {
    key: 'SE_OUT', short: 'OUT', label: 'Stock Out — Material Issue',
    doctype: 'Stock Entry', meta: 'stock_entry_type=Material Issue',
    icon: 'stock-out', color: '#dc2626', source: true, target: false, onlineOnly: true
  },
  SE_TRANSFER: {
    key: 'SE_TRANSFER', short: 'TRF', label: 'Stock Transfer — Material Transfer',
    doctype: 'Stock Entry', meta: 'stock_entry_type=Material Transfer',
    icon: 'transfer', color: '#ea580c', source: true, target: true, onlineOnly: true
  },
  GRN: {
    key: 'GRN', short: 'GRN', label: 'Goods Receipt — Purchase Receipt',
    doctype: 'Purchase Receipt', meta: 'penerimaan barang dari supplier',
    icon: 'receive', color: '#0891b2', source: false, target: true, supplier: true, supplierRequired: true,
    purchaseOrder: true, acceptReject: true, onlineOnly: true
  },
  RET: {
    key: 'RET', short: 'RET', label: 'Goods Return — Purchase Return',
    doctype: 'Purchase Receipt', meta: 'retur barang ke supplier',
    icon: 'return', color: '#b45309', source: false, target: false, supplier: true,
    isReturn: true, onlineOnly: true
  },
  QTN: {
    key: 'QTN', short: 'QTN', label: 'Quotation — Sales',
    doctype: 'Quotation', meta: 'permintaan barang penjualan (ditarik ke Sales Invoice)',
    icon: 'quotation', color: '#0d9488', source: false, target: false,
    customer: true, isQuotation: true, onlineOnly: true
  }
}
// Hanya Material Request (MR/PR) yang boleh dibuat offline (masuk outbox). Stock Entry,
// Penerimaan Barang, & Retur wajib online (kunci stok/valuasi real-time) → onlineOnly.

export const DOC_TYPE_LIST = Object.values(DOC_TYPES)

// Petakan dokumen server (list_recent / get_server_doc) → jenis app (ikon/warna/label).
export function serverTypeKey(d) {
  if (d.doctype === 'Material Request') return d.subtype === 'Purchase' ? 'PR' : 'MR'
  if (d.doctype === 'Purchase Receipt') return d.is_return ? 'RET' : 'GRN'
  if (d.doctype === 'Quotation') return 'QTN'
  return { 'Material Receipt': 'SE_IN', 'Material Issue': 'SE_OUT', 'Material Transfer': 'SE_TRANSFER' }[d.subtype] || 'SE_TRANSFER'
}
