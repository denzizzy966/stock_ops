import { defineStore } from 'pinia'
import { bootstrap, getStockBalance } from '../lib/service'
import { ITEMS, WAREHOUSES, COMPANIES, UOMS, SUPPLIERS } from '../data/mock'

const LS = 'stockops.master'

function load() {
  try {
    return JSON.parse(localStorage.getItem(LS)) || {}
  } catch {
    return {}
  }
}

// Cache master data (dipakai online & offline). Fallback ke data mock bila kosong.
export const useMaster = defineStore('master', {
  state: () => {
    const s = load()
    return {
      companies: s.companies || [],
      warehouses: s.warehouses || [],
      items: s.items || [],
      uoms: s.uoms || [],
      suppliers: s.suppliers || [],
      customers: s.customers || [], // master Customer (untuk Quotation/penjualan)
      locations: s.locations || [],
      userWarehouses: s.userWarehouses || [],
      employee: s.employee || null, // detail Employee user (company/department/branch/grade/…)
      defaults: s.defaults || null,
      menu: s.menu || {}, // visibilitas menu dari Stock Ops Settings
      caps: s.caps || {}, // kemampuan user (mis. can_cancel) — dari Role Permission
      isApprover: s.isApprover || false, // user adalah approver (leave approver) MR Purchase
      pendingApprovals: s.pendingApprovals || 0, // jumlah MR menunggu persetujuan user
      // Akses Desk (dari server): { can_access, perms: {Doctype: bool} } — untuk tautan "Buka di Desk".
      desk: s.desk || { can_access: false, perms: {} },
      canQuotation: s.canQuotation || false, // user boleh buat Quotation (dari izin server)
      // Tujuan Stock Out → cost center (Stock Ops Settings): [{purpose, cost_center, company}]
      issuePurposes: s.issuePurposes || [],
      issuePurposeRequired: s.issuePurposeRequired || false,
      defaultLang: s.defaultLang || 'id',
      flutterApkUrl: s.flutterApkUrl || '',
      loadedAt: s.loadedAt || null,
      loading: false,
      // Saldo stok per gudang (transient, tak dipersist) → {warehouse: {item_code: actual_qty}}.
      // Dipakai item picker untuk menampilkan stok tersedia sesuai gudang terpilih.
      stockByWh: {}
    }
  },
  getters: {
    hasData: (s) => s.items.length > 0,
    // Menu tampil? default true bila belum dimuat / tak diset di server.
    menuOn: (s) => (key) => s.menu[key] !== false,
    // Boleh cancel dokumen di server? default true bila caps belum dimuat
    // (penegakan sebenarnya tetap di server; ini hanya menyembunyikan tombol).
    canCancel: (s) => s.caps.can_cancel !== false,
    isManager: (s) => s.caps.is_manager === true,
    // Boleh buka dokumen ini di Desk? (System User + izin baca doctype dari server).
    canOpenInDesk: (s) => (doctype) => !!(s.desk && s.desk.can_access && s.desk.perms && s.desk.perms[doctype]),
    // URL Desk untuk sebuah dokumen: /app/<doctype-slug>/<name> (dibuka di tab baru).
    deskUrl: () => (doctype, name) =>
      `/app/${String(doctype || '').toLowerCase().replace(/ /g, '-')}/${encodeURIComponent(name)}`,
    // Item siap pakai untuk picker (normalisasi field + fallback gambar)
    itemList: (s) => (s.items.length ? s.items : ITEMS),
    warehouseNames: (s) => (s.warehouses.length ? s.warehouses.map((w) => w.name) : WAREHOUSES),
    // Gudang milik company tertentu (MR memvalidasi warehouse↔company).
    warehousesForCompany: (s) => (company) => {
      if (!s.warehouses.length) return WAREHOUSES
      const f = s.warehouses.filter((w) => !company || w.company === company)
      return (f.length ? f : s.warehouses).map((w) => w.name)
    },
    companyNames: (s) => (s.companies.length ? s.companies.map((c) => c.name) : COMPANIES),
    uomList: (s) => (s.uoms.length ? s.uoms : UOMS),
    supplierNames: (s) => (s.suppliers.length ? s.suppliers.map((x) => x.supplier) : SUPPLIERS),
    customerNames: (s) => (s.customers || []).map((c) => c.name),
    locationNames: (s) => s.locations || []
  },
  actions: {
    persist() {
      localStorage.setItem(
        LS,
        JSON.stringify({
          companies: this.companies,
          warehouses: this.warehouses,
          items: this.items,
          uoms: this.uoms,
          suppliers: this.suppliers,
          customers: this.customers,
          locations: this.locations,
          userWarehouses: this.userWarehouses,
          employee: this.employee,
          defaults: this.defaults,
          menu: this.menu,
          caps: this.caps,
          isApprover: this.isApprover,
          pendingApprovals: this.pendingApprovals,
          desk: this.desk,
          canQuotation: this.canQuotation,
          issuePurposes: this.issuePurposes,
          issuePurposeRequired: this.issuePurposeRequired,
          defaultLang: this.defaultLang,
          flutterApkUrl: this.flutterApkUrl,
          loadedAt: this.loadedAt
        })
      )
    },
    async load() {
      this.loading = true
      try {
        const b = await bootstrap()
        this.companies = b.companies || []
        this.warehouses = b.warehouses || []
        this.items = (b.items || []).map((it) => ({
          item_code: it.item_code,
          item_name: it.item_name || it.item_code,
          stock_uom: it.stock_uom || 'Nos',
          image: it.image || '',
          barcode: it.barcode || '',
          is_fixed_asset: it.is_fixed_asset ? 1 : 0,
          uoms: Array.isArray(it.uoms) && it.uoms.length ? it.uoms : [{ uom: it.stock_uom || 'Nos', conversion_factor: 1 }]
        }))
        this.uoms = b.uoms || []
        this.suppliers = b.suppliers || []
        this.customers = b.customers || []
        this.locations = b.locations || []
        this.userWarehouses = b.user_warehouses || []
        this.employee = b.employee || null
        this.defaults = b.defaults || null
        this.menu = b.menu || {}
        this.caps = b.caps || {}
        this.isApprover = !!b.is_approver
        this.pendingApprovals = b.pending_approvals || 0
        this.desk = b.desk || { can_access: false, perms: {} }
        this.canQuotation = !!b.can_quotation
        this.issuePurposes = b.issue_purposes || []
        this.issuePurposeRequired = !!b.issue_purpose_required
        this.defaultLang = b.default_lang || 'id'
        this.flutterApkUrl = b.flutter_apk_url || ''
        this.loadedAt = new Date().toISOString()
        this.persist()
        // Terapkan bahasa default server (kecuali user sudah memilih manual)
        const { useApp } = await import('./app')
        useApp().applyServerLang(this.defaultLang)
        return b
      } finally {
        this.loading = false
      }
    },

    // Saldo stok gudang (untuk item picker) — cache per gudang; item tanpa stok → tak ada di map (0).
    async loadWarehouseStock(warehouse, force = false) {
      if (!warehouse) return {}
      if (!force && this.stockByWh[warehouse]) return this.stockByWh[warehouse]
      try {
        const res = await getStockBalance({ warehouse })
        const map = {}
        for (const b of (res && res.balance) || []) map[b.item_code] = b.actual_qty
        this.stockByWh = { ...this.stockByWh, [warehouse]: map }
        return map
      } catch {
        return this.stockByWh[warehouse] || {}
      }
    }
  }
})
