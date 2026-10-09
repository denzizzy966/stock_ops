import { computed } from 'vue'
import { useApp } from '../stores/app'

export const LANGS = [
  { code: 'id', label: 'Indonesia' },
  { code: 'en', label: 'English' }
]

const messages = {
  id: {
    appName: 'Stock Ops',
    common: {
      online: 'Online', offline: 'Offline', save: 'Simpan', saving: 'Menyimpan…',
      close: 'Tutup', add: 'Tambah', delete: 'Hapus', cancel: 'Batal', total: 'Total',
      items: 'item', note: 'Catatan', optional: 'opsional', all: 'Semua', search: 'Cari',
      logout: 'Keluar', yes: 'Ya', viewAll: 'Lihat semua', back: 'Kembali', loading: 'Memuat…', clear: 'Hapus',
      openInDesk: 'Buka di Desk', noDeskPerm: 'Anda tidak punya izin membuka dokumen ini di Desk'
    },
    po: {
      title: 'Pilih Purchase Order', label: 'Purchase Order', choose: 'Pilih Purchase Order',
      searchPlaceholder: 'Cari nomor PO…', none: 'Tidak ada PO terbuka', loaded: '{n} item dari {po} dimuat'
    },
    ret: {
      pickTitle: 'Pilih Penerimaan Barang', receipt: 'Penerimaan Barang (asal)', choose: 'Pilih Penerimaan Barang',
      searchPlaceholder: 'Cari nomor penerimaan…', none: 'Tidak ada penerimaan yang bisa diretur',
      partlyReturned: 'sudah diretur {pct}%', loaded: '{n} item dari {pr} dimuat',
      itemsToReturn: 'Item yang Diretur', pickFirst: 'Pilih penerimaan barang dulu untuk memuat item',
      returnable: 'bisa diretur', totalReturn: 'Total Retur', notePlaceholder: 'Alasan retur (opsional)',
      vReceipt: 'Pilih penerimaan barang yang akan diretur', vQty: 'Isi qty retur minimal 1 item',
      vOver: 'Qty retur melebihi qty yang bisa diretur'
    },
    approval: {
      title: 'Persetujuan', none: 'Tidak ada permintaan menunggu persetujuan', note: 'Catatan (opsional)',
      approve: 'Setujui', reject: 'Tolak', applied: '{name}: {state}',
      pending: 'Menunggu Persetujuan', approved: 'Disetujui', rejected: 'Ditolak',
      menu: 'Persetujuan', submittedForApproval: 'Diajukan untuk persetujuan',
      submitForApproval: 'Ajukan Persetujuan', waiting: 'Menunggu persetujuan line manager…',
      search: 'Cari nomor / pemohon…', reviewTitle: 'Tinjau Permintaan', requester: 'Pemohon',
      reason: 'Alasan penolakan', noReason: '(tidak ada alasan dicantumkan)',
      reopenHint: 'Buka kembali permintaan ini untuk mengajukannya ulang.',
      reopen: 'Buka Kembali & Ajukan Ulang', reopened: '{name} dibuka kembali — silakan ajukan ulang',
      mine: 'Untuk saya', all: 'Semua', approver: 'Approver', changeApprover: 'Ganti Approver',
      newApprover: 'Cari approver baru (nama / email)…', reasonOpt: 'Alasan (opsional)',
      approverChanged: '{name}: approver diganti ke {user}'
    },
    nav: { home: 'Beranda', list: 'Daftar', create: 'Buat', settings: 'Setelan', sync: 'Sync', balance: 'Stok', movement: 'Mutasi' },
    docType: {
      MR: 'Permintaan Transfer Barang',
      PR: 'Permintaan Pembelian Barang',
      SE_IN: 'Stock In (Barang Masuk)',
      SE_OUT: 'Stock Out (Barang Keluar)',
      SE_TRANSFER: 'Transfer Barang',
      GRN: 'Penerimaan Barang (Purchase Receipt)',
      RET: 'Retur Barang (Purchase Return)',
      QTN: 'Penawaran Jual (Quotation)',
      groupMR: 'Permintaan Barang',
      groupSE: 'Stok Barang',
      groupPR: 'Penerimaan Barang',
      groupRET: 'Retur Barang',
      groupQTN: 'Penjualan'
    },
    home: {
      hello: 'Halo, {name} 👋', pendingSync: 'Menunggu sync', synced: 'Tersinkron',
      totalDocs: 'Total dokumen', quickCreate: 'Buat Dokumen', recent: 'Terbaru', menuTitle: 'Menu',
      emptyDocs: 'Belum ada dokumen. Tekan tombol Buat di bawah.',
      offlineBanner: '📴 Mode offline — transaksi tersimpan di Outbox & disinkron saat online.',
      draftLocal: 'Draft lokal',
      lowAlert: '{n} item stok menipis', lowAlertSub: 'Ketuk untuk lihat & minta beli', viewAlerts: 'Lihat',
      menu: { lookup: 'Cari / Scan', balance: 'Stok', movement: 'Mutasi', low: 'Menipis', transfer: 'Transfer', opname: 'Opname' }
    },
    create: { title: 'Buat Dokumen' },
    notif: { title: 'Notifikasi', empty: 'Belum ada notifikasi', markAll: 'Tandai semua dibaca' },
    form: {
      newSuffix: 'Baru', company: 'Perusahaan', date: 'Tanggal', supplier: 'Supplier',
      customer: 'Customer', customerPlaceholder: 'Pilih atau ketik nama customer…',
      customerHint: 'Pilih customer terdaftar, atau ketik nama baru (dibuat sebagai prospek/Lead).',
      vCustomer: 'Pilih atau isi customer',
      companyFromAccount: 'Mengikuti perusahaan akun Anda',
      sourceWh: 'Gudang Asal', targetWh: 'Gudang Tujuan', noItems: 'Belum ada item',
      totalQty: 'Total Qty', photos: 'Foto Barang', addPhoto: 'Tambah foto',
      processing: 'Memproses…', notePlaceholder: 'Keterangan (opsional)',
      photoHint: 'Foto di-upload ke attachment dokumen ({vis}) saat sync.',
      offlineHint: '📴 Offline — tersimpan di Outbox & disinkron otomatis saat online.',
      onlineOnly: '{doc} wajib dibuat saat online', onlineOnlyHint: '📶 Wajib online — hanya Permintaan Barang yang bisa dibuat offline.', onlineOnlyBtn: 'Harus Online',
      location: 'Lokasi', tagLocation: 'Tag Lokasi', locating: 'Mengambil lokasi…', locationOff: 'Lokasi tidak tersedia', viewMap: 'Lihat peta',
      saveSync: 'Simpan & Sync (draft)', saveOutbox: 'Simpan ke Outbox',
      vItems: 'Tambahkan minimal 1 item', vQty: 'Qty item tidak boleh 0',
      vSrc: 'Pilih gudang asal', vTgt: 'Pilih gudang tujuan', vSame: 'Gudang asal & tujuan tidak boleh sama',
      purpose: 'Tujuan', costCenter: 'Cost Center', vPurpose: 'Pilih tujuan barang keluar',
      vSupplier: 'Pilih supplier', whSearch: 'Cari gudang…', whEmpty: 'Gudang tidak ditemukan',
      acceptedWh: 'Gudang Terima', rejectedWh: 'Gudang Tolak', assetLocation: 'Lokasi Aset',
      accepted: 'Terima', rejected: 'Tolak', asset: 'Aset', uom: 'Satuan',
      vRejWh: 'Pilih gudang tolak (ada qty ditolak)', vAssetLoc: 'Pilih lokasi aset (ada item aset)',
      insufficientStock: '⚠️ Stok tidak cukup — butuh {need} {uom}, tersedia {avail} {uom}'
    },
    list: { title: 'Daftar Dokumen', empty: 'Tidak ada dokumen pada filter ini', local: 'Lokal', server: 'Server', openErp: 'Buka di ERPNext' },
    detail: {
      localId: 'Local ID', created: 'Dibuat', error: 'Error', syncNow: 'Sync sekarang',
      syncing: 'Menyinkron…', offlineCantSync: 'Offline — tidak bisa sync',
      submit: 'Submit dokumen', cancel: 'Batalkan dokumen', confirmCancel: 'Batalkan dokumen ini?',
      notFound: 'Dokumen tidak ditemukan', confirmDelete: 'Hapus dokumen ini?'
    },
    report: {
      title: 'Laporan', period: 'Bulan ini', mrGroup: 'Permintaan Barang', seGroup: 'Stok Barang',
      none: 'Belum ada data bulan ini', total: 'Total'
    },
    balance: {
      title: 'Stok Gudang', search: 'Cari item…', empty: 'Tidak ada stok', allWh: 'Semua',
      restricted: 'Gudang Anda', available: 'Tersedia', reserved: 'Reserved', items: 'item'
    },
    movement: {
      title: 'Pergerakan Stok', search: 'Cari item…', empty: 'Belum ada pergerakan',
      all: 'Semua', in: 'Masuk', out: 'Keluar', sisa: 'Sisa', from: 'Dari', to: 'Sampai'
    },
    lookup: {
      title: 'Cari / Scan Item', search: 'Ketik kode / nama item…', scanHint: 'atau scan barcode',
      empty: 'Ketik kode item atau scan barcode', notFound: 'Item tidak ditemukan'
    },
    item: {
      title: 'Detail Item', totalStock: 'Total Stok', perWarehouse: 'Stok per Gudang',
      movements: 'Mutasi Terakhir', barcode: 'Barcode', group: 'Grup', noStock: 'Tidak ada stok di gudang Anda',
      transfer: 'Transfer', stockIn: 'Stock In', stockOut: 'Stock Out'
    },
    low: {
      title: 'Stok Menipis', threshold: 'Ambang', empty: 'Tidak ada stok menipis 👍',
      level: 'Batas', request: 'Minta Beli', items: 'item',
      selectAll: 'Pilih semua', clear: 'Batal', reqQty: 'Req', bulkRequest: 'Request Beli',
      selected: '{n} dipilih', created: 'MR {name} dibuat ({n} item)'
    },
    opname: {
      title: 'Stock Opname', pickWh: 'Pilih gudang', search: 'Cari item…', system: 'Sistem', counted: 'Fisik',
      diff: 'Selisih', empty: 'Tidak ada item di gudang ini', submit: 'Buat Rekonsiliasi',
      noDiff: 'Tidak ada selisih untuk direkonsiliasi', created: 'Rekonsiliasi {name} dibuat ({n} item)',
      changedOnly: 'Hanya item dengan selisih yang dikirim', count: 'item berubah'
    },
    qt: {
      title: 'Transfer Cepat', item: 'Item', pickItem: 'Pilih item…', from: 'Dari Gudang', to: 'Ke Gudang',
      qty: 'Jumlah', available: 'Tersedia', submit: 'Buat Transfer', needItem: 'Pilih item dulu',
      sameWh: 'Gudang asal & tujuan harus beda', needQty: 'Jumlah harus > 0'
    },
    sync: {
      title: 'Sync / Outbox', waiting: '{n} menunggu', syncedN: '{n} tersinkron',
      syncAll: '🔄 Sync semua', autoSync: 'Auto-sync', autoSyncDesc: 'Kirim otomatis saat online',
      outbox: 'Outbox', allSynced: 'Semua sudah tersinkron', sync: 'Sync'
    },
    settings: {
      title: 'Pengaturan', defaults: 'Default Transaksi', companyDefault: 'Perusahaan default',
      company: 'Perusahaan', warehouse: 'Gudang', department: 'Departemen', branch: 'Cabang',
      grade: 'Grade', designation: 'Jabatan', allWarehouses: 'Semua gudang',
      srcDefault: 'Gudang Asal default', tgtDefault: 'Gudang Tujuan default',
      appearance: 'Tampilan & Bahasa', language: 'Bahasa', theme: 'Tema',
      themeSystem: 'Ikut sistem', themeLight: 'Terang', themeDark: 'Gelap',
      design: 'Tampilan', designBlue: 'Blue · ERPNext', designClassic: 'Classic · Klasik', designCompact: 'Compact · Kompak',
      notif: 'Notifikasi', enableNotif: 'Aktifkan notifikasi push', enableNotifDesc: 'Pemberitahuan saat dokumen disubmit',
      testNotif: 'Kirim notifikasi uji', notifOnlyBench: 'Tersedia saat dibuka via server (bukan dev)',
      photoSync: 'Foto & Sync', privatePhoto: 'Foto private', privatePhotoDesc: 'is_private = 1 di attachment',
      autoSync: 'Auto-sync', autoSyncDesc: 'Kirim otomatis saat online',
      saveSettings: 'Simpan Pengaturan', syncOutbox: 'Sync / Outbox', syncOutboxDesc: 'Antrian & status sinkronisasi',
      reports: 'Laporan', reportsDesc: 'Ringkasan dokumen bulan ini',
      getApp: 'Unduh Aplikasi', downloadApk: 'Unduh Android (APK)', downloadApkDesc: 'Aplikasi native untuk Android',
      installPwa: 'Install Web App (PWA)', installPwaDesc: 'Pasang ke layar utama perangkat',
      apkUnavailable: 'Tautan APK belum diatur di Stock Ops Settings', pwaUnavailable: 'Install belum tersedia (buka di Chrome/Android atau sudah terpasang)',
      other: 'Lainnya', backend: 'Backend (P1)', mockVersion: 'Versi mock',
      clearData: '🧹 Bersihkan data lokal', confirmClear: 'Hapus semua dokumen lokal (mock)?'
    },
    login: {
      subtitle: 'Permintaan & Stok Barang — Mobile', email: 'Email', password: 'Password',
      signIn: 'Masuk', mockNote: 'P0 mock — login apa saja diterima. Di P1 terhubung ke sesi ERPNext.',
      server: 'URL Server ERPNext', userId: 'Email / Username',
      nativeNote: 'Login dengan akun ERPNext Anda. Token disimpan di perangkat.'
    },
    status: { pending: 'Pending', syncing: 'Syncing…', synced: 'Synced', error: 'Error', draft: 'Draft', submitted: 'Submitted', cancelled: 'Cancelled', '0': 'Draft', '1': 'Submitted', '2': 'Cancelled' },
    picker: { title: 'Pilih Item', searchPlaceholder: 'Cari nama / kode / barcode…', noMatch: 'Tidak ada item cocok', stockAt: 'Stok tersedia di {wh}' },
    scan: {
      title: 'Scan Barcode', hint: 'Arahkan kamera ke barcode item',
      notFound: 'Item dengan barcode {code} tidak ditemukan', camFail: 'Kamera tidak tersedia / izin ditolak'
    },
    toast: {
      loginOk: 'Login berhasil (mock)', photosAdded: '{n} foto ditambahkan', photoFail: 'Gagal memproses foto',
      savedOutbox: 'Tersimpan di Outbox (offline) — akan disinkron saat online', syncedTo: 'Tersinkron → {doc}',
      syncDelayed: 'Masih offline — sync ditunda', nothingToSync: 'Tidak ada yang perlu disinkron',
      cantSyncOffline: 'Tidak bisa sync — sedang offline', submitFirst: 'Sync dulu sebelum submit',
      submitted: '{doc} disubmit', cancelled: '{doc} dibatalkan', settingsSaved: 'Pengaturan disimpan', dataCleared: 'Data lokal dibersihkan',
      negativeStock: '❌ Stok tidak mencukupi. Server menolak karena stok akan minus (Allow Negative Stock non-aktif). Kurangi qty atau tambah stok dulu.',
      scan: 'Scan: {code} → {name}',
      notifOn: 'Notifikasi diaktifkan', notifOff: 'Notifikasi dimatikan', notifDenied: 'Izin notifikasi ditolak', testSent: 'Notifikasi uji dikirim'
    }
  },
  en: {
    appName: 'Stock Ops',
    common: {
      online: 'Online', offline: 'Offline', save: 'Save', saving: 'Saving…',
      close: 'Close', add: 'Add', delete: 'Delete', cancel: 'Cancel', total: 'Total',
      items: 'items', note: 'Note', optional: 'optional', all: 'All', search: 'Search',
      logout: 'Log out', yes: 'Yes', viewAll: 'View all', back: 'Back', loading: 'Loading…', clear: 'Clear',
      openInDesk: 'Open in Desk', noDeskPerm: 'You do not have permission to open this document in Desk'
    },
    po: {
      title: 'Select Purchase Order', label: 'Purchase Order', choose: 'Select Purchase Order',
      searchPlaceholder: 'Search PO number…', none: 'No open POs', loaded: '{n} items from {po} loaded'
    },
    ret: {
      pickTitle: 'Select Purchase Receipt', receipt: 'Purchase Receipt (source)', choose: 'Select Purchase Receipt',
      searchPlaceholder: 'Search receipt number…', none: 'No returnable receipts',
      partlyReturned: '{pct}% returned', loaded: '{n} items from {pr} loaded',
      itemsToReturn: 'Items to Return', pickFirst: 'Select a purchase receipt first to load items',
      returnable: 'returnable', totalReturn: 'Total Return', notePlaceholder: 'Return reason (optional)',
      vReceipt: 'Select the purchase receipt to return', vQty: 'Enter return qty for at least 1 item',
      vOver: 'Return qty exceeds the returnable qty'
    },
    approval: {
      title: 'Approvals', none: 'No requests awaiting approval', note: 'Note (optional)',
      approve: 'Approve', reject: 'Reject', applied: '{name}: {state}',
      pending: 'Pending Approval', approved: 'Approved', rejected: 'Rejected',
      menu: 'Approvals', submittedForApproval: 'Submitted for approval',
      submitForApproval: 'Submit for Approval', waiting: 'Waiting for line manager approval…',
      search: 'Search no. / requester…', reviewTitle: 'Review Request', requester: 'Requester',
      reason: 'Rejection reason', noReason: '(no reason given)',
      reopenHint: 'Reopen this request to submit it again.',
      reopen: 'Reopen & Resubmit', reopened: '{name} reopened — you can submit it again',
      mine: 'Mine', all: 'All', approver: 'Approver', changeApprover: 'Change Approver',
      newApprover: 'Search new approver (name / email)…', reasonOpt: 'Reason (optional)',
      approverChanged: '{name}: approver changed to {user}'
    },
    nav: { home: 'Home', list: 'Docs', create: 'New', settings: 'Settings', sync: 'Sync', balance: 'Stock', movement: 'Moves' },
    docType: {
      MR: 'Goods Transfer Request',
      PR: 'Purchase Request',
      SE_IN: 'Stock In (Receipt)',
      SE_OUT: 'Stock Out (Issue)',
      SE_TRANSFER: 'Stock Transfer',
      GRN: 'Goods Receipt (Purchase Receipt)',
      RET: 'Goods Return (Purchase Return)',
      QTN: 'Sales Quotation',
      groupMR: 'Material Requests',
      groupSE: 'Stock Entries',
      groupPR: 'Goods Receipt',
      groupRET: 'Goods Return',
      groupQTN: 'Sales'
    },
    home: {
      hello: 'Hi, {name} 👋', pendingSync: 'Pending sync', synced: 'Synced',
      totalDocs: 'Total documents', quickCreate: 'Create Document', recent: 'Recent', menuTitle: 'Menu',
      emptyDocs: 'No documents yet. Tap the Create button below.',
      offlineBanner: '📴 Offline mode — transactions saved to Outbox & synced when online.',
      draftLocal: 'Local draft',
      lowAlert: '{n} low-stock items', lowAlertSub: 'Tap to view & request', viewAlerts: 'View',
      menu: { lookup: 'Find / Scan', balance: 'Stock', movement: 'Moves', low: 'Low Stock', transfer: 'Transfer', opname: 'Count' }
    },
    create: { title: 'Create Document' },
    notif: { title: 'Notifications', empty: 'No notifications', markAll: 'Mark all read' },
    form: {
      newSuffix: 'New', company: 'Company', date: 'Date', supplier: 'Supplier',
      customer: 'Customer', customerPlaceholder: 'Pick or type a customer name…',
      customerHint: 'Pick a registered customer, or type a new name (created as a Lead/prospect).',
      vCustomer: 'Select or enter a customer',
      companyFromAccount: 'Follows your account company',
      sourceWh: 'Source Warehouse', targetWh: 'Target Warehouse', noItems: 'No items yet',
      totalQty: 'Total Qty', photos: 'Item Photos', addPhoto: 'Add photo',
      processing: 'Processing…', notePlaceholder: 'Remark (optional)',
      photoHint: 'Photos are uploaded to the document attachment ({vis}) on sync.',
      offlineHint: '📴 Offline — saved to Outbox & auto-synced when online.',
      onlineOnly: '{doc} must be created online', onlineOnlyHint: '📶 Online required — only Material Requests can be created offline.', onlineOnlyBtn: 'Online required',
      location: 'Location', tagLocation: 'Tag Location', locating: 'Getting location…', locationOff: 'Location unavailable', viewMap: 'View map',
      saveSync: 'Save & Sync (draft)', saveOutbox: 'Save to Outbox',
      vItems: 'Add at least 1 item', vQty: 'Item qty cannot be 0',
      vSrc: 'Select source warehouse', vTgt: 'Select target warehouse', vSame: 'Source & target warehouse must differ',
      purpose: 'Purpose', costCenter: 'Cost Center', vPurpose: 'Select the purpose of this stock out',
      vSupplier: 'Select a supplier', whSearch: 'Search warehouse…', whEmpty: 'No warehouse found',
      acceptedWh: 'Accepted Warehouse', rejectedWh: 'Rejected Warehouse', assetLocation: 'Asset Location',
      accepted: 'Accepted', rejected: 'Rejected', asset: 'Asset', uom: 'Unit',
      vRejWh: 'Select rejected warehouse (some qty rejected)', vAssetLoc: 'Select asset location (asset items present)',
      insufficientStock: '⚠️ Not enough stock — needs {need} {uom}, {avail} {uom} available'
    },
    list: { title: 'Documents', empty: 'No documents for this filter', local: 'Local', server: 'Server', openErp: 'Open in ERPNext' },
    detail: {
      localId: 'Local ID', created: 'Created', error: 'Error', syncNow: 'Sync now',
      syncing: 'Syncing…', offlineCantSync: 'Offline — cannot sync',
      submit: 'Submit document', cancel: 'Cancel document', confirmCancel: 'Cancel this document?',
      notFound: 'Document not found', confirmDelete: 'Delete this document?'
    },
    report: {
      title: 'Reports', period: 'This month', mrGroup: 'Material Requests', seGroup: 'Stock Entries',
      none: 'No data this month yet', total: 'Total'
    },
    balance: {
      title: 'Warehouse Stock', search: 'Search item…', empty: 'No stock', allWh: 'All',
      restricted: 'Your warehouse', available: 'Available', reserved: 'Reserved', items: 'items'
    },
    movement: {
      title: 'Stock Movement', search: 'Search item…', empty: 'No movements yet',
      all: 'All', in: 'In', out: 'Out', sisa: 'Bal', from: 'From', to: 'To'
    },
    lookup: {
      title: 'Find / Scan Item', search: 'Type item code / name…', scanHint: 'or scan barcode',
      empty: 'Type an item code or scan a barcode', notFound: 'Item not found'
    },
    item: {
      title: 'Item Detail', totalStock: 'Total Stock', perWarehouse: 'Stock per Warehouse',
      movements: 'Recent Movements', barcode: 'Barcode', group: 'Group', noStock: 'No stock in your warehouses',
      transfer: 'Transfer', stockIn: 'Stock In', stockOut: 'Stock Out'
    },
    low: {
      title: 'Low Stock', threshold: 'Threshold', empty: 'No low stock items 👍',
      level: 'Limit', request: 'Request', items: 'items',
      selectAll: 'Select all', clear: 'Clear', reqQty: 'Req', bulkRequest: 'Request Purchase',
      selected: '{n} selected', created: 'MR {name} created ({n} items)'
    },
    opname: {
      title: 'Stock Count', pickWh: 'Pick warehouse', search: 'Search item…', system: 'System', counted: 'Counted',
      diff: 'Diff', empty: 'No items in this warehouse', submit: 'Create Reconciliation',
      noDiff: 'No differences to reconcile', created: 'Reconciliation {name} created ({n} items)',
      changedOnly: 'Only changed items are sent', count: 'items changed'
    },
    qt: {
      title: 'Quick Transfer', item: 'Item', pickItem: 'Pick item…', from: 'From Warehouse', to: 'To Warehouse',
      qty: 'Qty', available: 'Available', submit: 'Create Transfer', needItem: 'Pick an item first',
      sameWh: 'Source & target must differ', needQty: 'Qty must be > 0'
    },
    sync: {
      title: 'Sync / Outbox', waiting: '{n} waiting', syncedN: '{n} synced',
      syncAll: '🔄 Sync all', autoSync: 'Auto-sync', autoSyncDesc: 'Send automatically when online',
      outbox: 'Outbox', allSynced: 'Everything is synced', sync: 'Sync'
    },
    settings: {
      title: 'Settings', defaults: 'Transaction Defaults', companyDefault: 'Default company',
      company: 'Company', warehouse: 'Warehouse', department: 'Department', branch: 'Branch',
      grade: 'Grade', designation: 'Designation', allWarehouses: 'All warehouses',
      srcDefault: 'Default source warehouse', tgtDefault: 'Default target warehouse',
      appearance: 'Appearance & Language', language: 'Language', theme: 'Theme',
      themeSystem: 'Follow system', themeLight: 'Light', themeDark: 'Dark',
      design: 'Layout', designBlue: 'Blue · ERPNext', designClassic: 'Classic', designCompact: 'Compact',
      notif: 'Notifications', enableNotif: 'Enable push notifications', enableNotifDesc: 'Alert when a document is submitted',
      testNotif: 'Send test notification', notifOnlyBench: 'Available when opened via server (not dev)',
      photoSync: 'Photo & Sync', privatePhoto: 'Private photos', privatePhotoDesc: 'is_private = 1 on attachment',
      autoSync: 'Auto-sync', autoSyncDesc: 'Send automatically when online',
      saveSettings: 'Save Settings', syncOutbox: 'Sync / Outbox', syncOutboxDesc: 'Queue & sync status',
      reports: 'Reports', reportsDesc: "This month's document summary",
      getApp: 'Get the App', downloadApk: 'Download Android (APK)', downloadApkDesc: 'Native app for Android',
      installPwa: 'Install Web App (PWA)', installPwaDesc: 'Add to your home screen',
      apkUnavailable: 'APK link not set in Stock Ops Settings', pwaUnavailable: 'Install not available (open in Chrome/Android or already installed)',
      other: 'Other', backend: 'Backend (P1)', mockVersion: 'Mock version',
      clearData: '🧹 Clear local data', confirmClear: 'Delete all local documents (mock)?'
    },
    login: {
      subtitle: 'Material Request & Stock Entry — Mobile', email: 'Email', password: 'Password',
      signIn: 'Sign in', mockNote: 'P0 mock — any login accepted. P1 connects to ERPNext session.',
      server: 'ERPNext Server URL', userId: 'Email / Username',
      nativeNote: 'Sign in with your ERPNext account. Token stored on device.'
    },
    status: { pending: 'Pending', syncing: 'Syncing…', synced: 'Synced', error: 'Error', draft: 'Draft', submitted: 'Submitted', cancelled: 'Cancelled', '0': 'Draft', '1': 'Submitted', '2': 'Cancelled' },
    picker: { title: 'Pick Item', searchPlaceholder: 'Search name / code / barcode…', noMatch: 'No matching item', stockAt: 'Available stock at {wh}' },
    scan: {
      title: 'Scan Barcode', hint: 'Point the camera at the item barcode',
      notFound: 'No item with barcode {code}', camFail: 'Camera unavailable / permission denied'
    },
    toast: {
      loginOk: 'Logged in (mock)', photosAdded: '{n} photo(s) added', photoFail: 'Failed to process photo',
      savedOutbox: 'Saved to Outbox (offline) — will sync when online', syncedTo: 'Synced → {doc}',
      syncDelayed: 'Still offline — sync deferred', nothingToSync: 'Nothing to sync',
      cantSyncOffline: 'Cannot sync — currently offline', submitFirst: 'Sync before submitting',
      submitted: '{doc} submitted', cancelled: '{doc} cancelled', settingsSaved: 'Settings saved', dataCleared: 'Local data cleared',
      negativeStock: '❌ Insufficient stock. The server rejected it because stock would go negative (Allow Negative Stock is off). Reduce qty or add stock first.',
      scan: 'Scan: {code} → {name}',
      notifOn: 'Notifications enabled', notifOff: 'Notifications disabled', notifDenied: 'Notification permission denied', testSent: 'Test notification sent'
    }
  }
}

function resolve(dict, key) {
  return key.split('.').reduce((o, k) => (o == null ? o : o[k]), dict)
}

export function useI18n() {
  const app = useApp()
  const locale = computed(() => app.settings.lang || 'id')
  const t = (key, params) => {
    const dict = messages[locale.value] || messages.id
    let s = resolve(dict, key)
    if (s == null) s = resolve(messages.id, key)
    if (s == null) return key
    if (params) for (const p of Object.keys(params)) s = s.replaceAll(`{${p}}`, params[p])
    return s
  }
  return { t, locale }
}
