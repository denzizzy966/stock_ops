import { call, uploadFile } from './api'
import { setServerUrl, setToken } from './platform'

// Login app native: user/password → session → tukar jadi api token (disimpan).
// 1) POST /api/method/login (login Frappe yang terlindungi rate-limit/lockout).
// 2) GET get_or_create_token (cookie sesi, GET → tanpa CSRF) → api_key + api_secret.
// Di Capacitor, fetch lewat native (CapacitorHttp) → bebas CORS, cookie dikelola native.
export async function nativeLogin(url, usr, pwd) {
  const base = (url || '').replace(/\/+$/, '')
  if (!base) throw new Error('URL server kosong')
  const r1 = await fetch(`${base}/api/method/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
    body: JSON.stringify({ usr, pwd })
  })
  if (!r1.ok) {
    throw new Error(r1.status === 401 ? 'Email/username atau password salah' : `Login gagal (HTTP ${r1.status})`)
  }
  const r2 = await fetch(`${base}/api/method/stock_ops.api.get_or_create_token`, { headers: { Accept: 'application/json' } })
  if (!r2.ok) throw new Error(`Gagal ambil token (HTTP ${r2.status})`)
  const j = await r2.json()
  const m = j && j.message
  if (!m || !m.api_key || !m.api_secret) throw new Error('Token tidak valid dari server')
  setServerUrl(base)
  setToken(m.api_key, m.api_secret)
  return m
}

// Master data (sekali panggil, untuk cache offline)
export const bootstrap = () => call('stock_ops.api.get_bootstrap')

// Buat dokumen draft (idempoten via external_localid)
export const createTransaction = (payload) =>
  call('stock_ops.api.create_transaction', { data: payload }, { post: true })

// Submit dokumen (online)
export const submitTransaction = (doctype, name) =>
  call('stock_ops.api.submit_transaction', { doctype, name }, { post: true })

// Batalkan dokumen submitted
export const cancelTransaction = (doctype, name) =>
  call('stock_ops.api.cancel_transaction', { doctype, name }, { post: true })

// Dokumen terbaru dari server
export const listRecent = (company, limit = 20) =>
  call('stock_ops.api.list_recent', { company, limit })

// Ringkasan jumlah dokumen bulan ini
export const reportCounts = (company) => call('stock_ops.api.report_counts', { company })

// Saldo stok per gudang user
export const getStockBalance = (opts = {}) => {
  const p = {}
  if (opts.warehouse) p.warehouse = opts.warehouse
  if (opts.company) p.company = opts.company
  return call('stock_ops.api.get_stock_balance', p)
}

// Stock opname: lembar stok sistem + buat Stock Reconciliation
export const getOpnameSheet = (warehouse, company) =>
  call('stock_ops.api.get_opname_sheet', { warehouse, company })
export const createOpname = (warehouse, items, company, externalLocalid) =>
  call('stock_ops.api.create_opname', { warehouse, items, company, external_localid: externalLocalid }, { post: true })

// Item stok menipis (di bawah reorder level / ambang)
export const getLowStock = (company, threshold = 10) =>
  call('stock_ops.api.get_low_stock', { company, threshold })

// Bulk request beli dari item terpilih → satu Material Request (Purchase)
export const bulkPurchaseRequest = (items, company, externalLocalid) =>
  call('stock_ops.api.bulk_purchase_request', { items, company, external_localid: externalLocalid }, { post: true })

// Detail item (info + stok per gudang + mutasi)
export const getItemDetail = (itemCode, company) => call('stock_ops.api.get_item_detail', { item_code: itemCode, company })

// Purchase Order terbuka (untuk Penerimaan Barang) + item PO untuk auto-isi
export const listOpenPurchaseOrders = (company, supplier, search) =>
  call('stock_ops.api.list_open_purchase_orders', { company, supplier, search })
export const getPurchaseOrderItems = (purchaseOrder) =>
  call('stock_ops.api.get_purchase_order_items', { purchase_order: purchaseOrder })

// Retur Barang: Purchase Receipt yang bisa diretur + item + sisa qty, lalu buat retur (is_return)
export const listReturnableReceipts = (company, supplier, search) =>
  call('stock_ops.api.list_returnable_receipts', { company, supplier, search })
export const getReceiptItemsForReturn = (purchaseReceipt) =>
  call('stock_ops.api.get_receipt_items_for_return', { purchase_receipt: purchaseReceipt })
export const createPurchaseReturn = (purchaseReceipt, items, externalLocalid, remarks) =>
  call(
    'stock_ops.api.create_purchase_return',
    { purchase_receipt: purchaseReceipt, items, external_localid: externalLocalid, remarks },
    { post: true }
  )

// Quotation (permintaan barang penjualan) — customer bisa nama existing atau nama bebas (→ Lead).
export const createQuotation = (customer, items, company, externalLocalid, remarks) =>
  call(
    'stock_ops.api.create_quotation',
    { customer, items, company, external_localid: externalLocalid, remarks },
    { post: true }
  )

// Persetujuan (workflow-driven — mengikuti Workflow di server/Desk, tak hardcode aksi)
export const listPendingApprovals = (limit = 50, all = 0) =>
  call('stock_ops.api.list_pending_approvals', { limit, all })
// System Manager: ganti approver permintaan yang Menunggu Persetujuan + cari calon approver
export const changeApprover = (name, approver, reason) =>
  call('stock_ops.api.change_approver', { name, approver, reason }, { post: true })
export const searchUsers = (txt) => call('stock_ops.api.search_users', { txt })
export const getWorkflowTransitions = (doctype, name) =>
  call('stock_ops.api.get_workflow_transitions', { doctype, name })
export const applyWorkflowAction = (doctype, name, action, note) =>
  call('stock_ops.api.apply_workflow_action', { doctype, name, action, note }, { post: true })
export const getApprovalDetail = (name) => call('stock_ops.api.get_approval_detail', { name })

// Status terkini dokumen server (untuk sinkronkan tampilan lokal: docstatus + workflow_state)
export const getDocState = (doctype, name) => call('stock_ops.api.get_doc_state', { doctype, name })
// Detail dokumen server untuk ditampilkan di aplikasi (Daftar > Server)
export const getServerDoc = (doctype, name) => call('stock_ops.api.get_server_doc', { doctype, name })

// Resolve kode (barcode/item_code/nama) → item_code (untuk hasil scan)
export const resolveItem = (code) => call('stock_ops.api.resolve_item', { code })

// Pergerakan stok (Stock Ledger) per gudang user
export const getStockLedger = (opts = {}) => {
  const p = {}
  for (const k of ['item_code', 'warehouse', 'direction', 'from_date', 'to_date', 'company']) {
    if (opts[k]) p[k] = opts[k]
  }
  p.limit = opts.limit || 100
  return call('stock_ops.api.get_stock_ledger', p)
}

// Notifikasi in-app (Notification Log, polling — tanpa Firebase)
export const getNotifications = (limit = 20) => call('stock_ops.api.get_notifications', { limit })
export const markNotificationsRead = (name) =>
  call('stock_ops.api.mark_notifications_read', name ? { name } : {}, { post: true })

export { uploadFile }
