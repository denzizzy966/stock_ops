import { defineStore } from 'pinia'
import { DOC_TYPES } from '../data/mock'
import { uuid, todayStr, stripHtml, isNegativeStockError } from '../lib/util'
import { useApp } from './app'
import { useMaster } from './master'
import { useI18n } from '../lib/i18n'
import { buildPayload } from '../lib/payload'
import { createTransaction, submitTransaction, cancelTransaction, createPurchaseReturn, createQuotation, getDocState, applyWorkflowAction, uploadFile } from '../lib/service'
import { getPhoto, deletePhotosByLocalId } from '../lib/idb'

const LS = 'stockops.docs'

// Terjemahkan error server jadi pesan yang jelas. Error "stok minus" (Allow Negative
// Stock non-aktif) diberi awalan Indonesia + detail asli (item/gudang) tetap disertakan.
function friendlyError(e, t) {
  const s = e && e.message ? e.message : String(e)
  if (isNegativeStockError(s)) {
    const detail = stripHtml(s)
    return detail ? `${t('toast.negativeStock')} — ${detail}` : t('toast.negativeStock')
  }
  return s
}

function load() {
  try {
    return JSON.parse(localStorage.getItem(LS)) || []
  } catch {
    return []
  }
}

// Status dokumen:
//  draft   = tersimpan lokal, online, belum disubmit di server   (sudah punya remoteName)
//  pending = dibuat offline, menunggu sync                         (outbox)
//  syncing = sedang dikirim
//  synced  = sudah dibuat di server (punya remoteName)            (= draft online juga)
//  error   = gagal validasi server
export const useDocs = defineStore('docs', {
  state: () => ({
    docs: load()
  }),
  getters: {
    sorted: (s) => [...s.docs].sort((a, b) => (a.createdAt < b.createdAt ? 1 : -1)),
    outbox: (s) => s.docs.filter((d) => ['pending', 'syncing', 'error'].includes(d.status)),
    pendingCount: (s) => s.docs.filter((d) => ['pending', 'error'].includes(d.status)).length,
    byLocalId: (s) => (id) => s.docs.find((d) => d.localId === id)
  },
  actions: {
    persist() {
      localStorage.setItem(LS, JSON.stringify(this.docs))
    },

    newDraft(typeKey) {
      const cfg = DOC_TYPES[typeKey]
      const app = useApp()
      const master = useMaster()
      // Company dari server (Employee/Settings) bila ada; jika tidak, default lokal.
      const company = (master.defaults && master.defaults.company) || app.settings.company
      // Gudang sumber default dari Stock Ops Settings; jika kosong, default lokal.
      const srcDefault = (master.defaults && master.defaults.source_warehouse) || app.settings.defaultSourceWarehouse
      return {
        localId: uuid(),
        type: typeKey,
        doctype: cfg.doctype,
        company,
        date: todayStr(),
        sourceWarehouse: cfg.source ? srcDefault : '',
        // Untuk dokumen penerimaan (hanya target: Stock In / Purchase Receipt) default-kan
        // gudang penerima ke gudang default bila target khusus belum diset.
        targetWarehouse: cfg.target ? app.settings.defaultTargetWarehouse || (cfg.source ? '' : srcDefault) : '',
        supplier: '',
        // Quotation (penawaran penjualan): customer existing atau nama bebas (→ Lead)
        customer: '',
        // Penerimaan Barang (Purchase Receipt): referensi PO + gudang tolak + lokasi aset
        purchaseOrder: '',
        rejectedWarehouse: '',
        assetLocation: '',
        // Retur Barang (Purchase Return): Purchase Receipt asal yang diretur
        returnAgainst: '',
        // Stock Out: tujuan barang keluar (dipetakan ke cost center di server)
        purpose: '',
        // Status workflow (mis. MR Purchase: Pending Approval / Approved / Rejected)
        workflowState: null,
        remark: '',
        geo: '',
        items: [],
        photos: [], // [{ id, dataUrl }]
        status: 'pending',
        remoteName: null,
        error: null,
        createdAt: new Date().toISOString()
      }
    },

    // Simpan dokumen baru ke "outbox". Jika online + autoSync → langsung disinkron.
    async save(doc) {
      const app = useApp()
      const { t } = useI18n()
      // Stock Entry / Penerimaan / Retur wajib online — tidak boleh masuk outbox offline.
      const cfg = DOC_TYPES[doc.type]
      if (cfg && cfg.onlineOnly && !app.online) {
        app.notify(t('form.onlineOnly', { doc: t('docType.' + doc.type) }), 'error')
        return null
      }
      doc.status = 'pending'
      doc.createdAt = doc.createdAt || new Date().toISOString()
      this.docs.unshift(doc)
      this.persist()
      if (app.online && app.settings.autoSync) {
        await this.syncOne(doc.localId)
      } else {
        app.notify(t('toast.savedOutbox'), 'warn')
      }
      return doc
    },

    // Kirim ke ERPNext: buat dokumen draft (idempoten) lalu upload foto & lampirkan.
    async syncOne(localId) {
      const app = useApp()
      const { t } = useI18n()
      const doc = this.byLocalId(localId)
      if (!doc || doc.status === 'synced') return
      if (!app.online) {
        app.notify(t('toast.syncDelayed'), 'warn')
        return
      }
      doc.status = 'syncing'
      this.persist()
      try {
        // 1) buat dokumen (server cek external_localid → cegah duplikat saat retry)
        if (!doc.remoteName) {
          const cfg = DOC_TYPES[doc.type]
          let res
          if (cfg && cfg.isReturn) {
            // Retur barang: make_return_doc (qty negatif) atas Purchase Receipt asal
            const items = doc.items.map((i) => ({ item_code: i.item_code, qty: Number(i.qty) || 0 }))
            res = await createPurchaseReturn(doc.returnAgainst, items, doc.localId, doc.remark)
          } else if (cfg && cfg.isQuotation) {
            // Quotation: customer + item + qty (rate 0 — harga diisi sales nanti di Desk)
            const items = doc.items.map((i) => ({ item_code: i.item_code, qty: Number(i.qty) || 0, uom: i.uom }))
            res = await createQuotation(doc.customer, items, doc.company, doc.localId, doc.remark)
          } else {
            res = await createTransaction(buildPayload(doc))
          }
          doc.remoteName = res.name
          this.persist()
        }
        // 2) upload foto yang belum terkirim (Blob dari IndexedDB), lampirkan ke dokumen
        for (const p of doc.photos) {
          if (p.uploaded) continue
          const rec = await getPhoto(p.id)
          const blob = rec ? rec.blob : null
          if (!blob) {
            p.uploaded = true // tidak ada blob (mis. data lama) — lewati
            continue
          }
          await uploadFile(blob, {
            doctype: doc.doctype,
            docname: doc.remoteName,
            isPrivate: app.settings.privatePhotos,
            filename: p.name || 'foto.jpg'
          })
          p.uploaded = true
          this.persist()
        }
        doc.status = 'synced'
        doc.error = null
        this.persist()
        app.notify(t('toast.syncedTo', { doc: doc.remoteName }), 'success')
      } catch (e) {
        doc.status = 'error'
        doc.error = friendlyError(e, t)
        this.persist()
        app.notify(doc.error, 'error')
      }
    },

    async syncAll() {
      const app = useApp()
      const { t } = useI18n()
      if (!app.online) {
        app.notify(t('toast.cantSyncOffline'), 'warn')
        return
      }
      const pend = this.docs.filter((d) => ['pending', 'error'].includes(d.status))
      if (!pend.length) {
        app.notify(t('toast.nothingToSync'), 'info')
        return
      }
      for (const d of pend) {
        await this.syncOne(d.localId)
      }
    },

    // Submit (online) — docstatus 1 via whitelisted method.
    async submit(localId) {
      const app = useApp()
      const { t } = useI18n()
      const doc = this.byLocalId(localId)
      if (!doc) return
      if (doc.status !== 'synced' || !doc.remoteName) {
        app.notify(t('toast.submitFirst'), 'warn')
        return
      }
      try {
        const res = await submitTransaction(doc.doctype, doc.remoteName)
        doc.workflowState = (res && res.workflow_state) || null
        // Purchase MR yang masuk workflow tetap docstatus 0 (Menunggu Persetujuan).
        doc.submitted = res && res.docstatus === 1
        this.persist()
        if (doc.workflowState === 'Pending Approval') {
          app.notify(t('approval.submittedForApproval') + ' → ' + doc.remoteName, 'success')
        } else {
          app.notify(t('toast.submitted', { doc: doc.remoteName }), 'success')
        }
      } catch (e) {
        app.notify(friendlyError(e, t), 'error')
      }
    },

    // Sinkronkan status dari server (workflow_state + docstatus) — mis. setelah approver
    // menyetujui, requester melihat "Disetujui" bukan "Menunggu Persetujuan" yang basi.
    async refreshState(localId) {
      const app = useApp()
      const doc = this.byLocalId(localId)
      if (!doc || !doc.remoteName || !app.online) return
      try {
        const s = await getDocState(doc.doctype, doc.remoteName)
        if (!s) return
        if (s.workflow_state) doc.workflowState = s.workflow_state
        doc.approvalNote = s.approval_note || null
        doc.submitted = s.docstatus === 1
        doc.cancelled = s.docstatus === 2
        this.persist()
      } catch {
        // diamkan — tampilan tetap pakai status lokal terakhir
      }
    },

    // Pemohon membuka kembali permintaan yang ditolak (Rejected → Draft) agar bisa diajukan ulang.
    async reopen(localId) {
      const app = useApp()
      const { t } = useI18n()
      const doc = this.byLocalId(localId)
      if (!doc || !doc.remoteName || doc.workflowState !== 'Rejected') return
      try {
        const res = await applyWorkflowAction(doc.doctype, doc.remoteName, 'Reopen')
        doc.workflowState = (res && res.workflow_state) || 'Draft'
        doc.approvalNote = null
        doc.submitted = false
        this.persist()
        app.notify(t('approval.reopened', { name: doc.remoteName }), 'success')
      } catch (e) {
        app.notify(friendlyError(e, t), 'error')
      }
    },

    // Batalkan dokumen submitted (docstatus 2)
    async cancel(localId) {
      const app = useApp()
      const { t } = useI18n()
      const doc = this.byLocalId(localId)
      if (!doc || !doc.submitted || !doc.remoteName) return
      try {
        await cancelTransaction(doc.doctype, doc.remoteName)
        doc.submitted = false
        doc.cancelled = true
        this.persist()
        app.notify(t('toast.cancelled', { doc: doc.remoteName }), 'success')
      } catch (e) {
        app.notify(friendlyError(e, t), 'error')
      }
    },

    remove(localId) {
      this.docs = this.docs.filter((d) => d.localId !== localId)
      this.persist()
      deletePhotosByLocalId(localId).catch(() => {})
    }
  }
})
