// Helper Request to Pay: format uang per mata uang company, label & warna status Workflow.
export function fmtMoney(v, currency = 'IDR', locale = 'id') {
  const n = Number(v) || 0
  try {
    return new Intl.NumberFormat(locale === 'en' ? 'en-US' : 'id-ID', {
      style: 'currency',
      currency: currency || 'IDR',
      maximumFractionDigits: 2
    }).format(n)
  } catch {
    return `${currency || ''} ${n.toLocaleString()}`
  }
}

// Workflow state → kunci i18n (rtp.state.*) + gaya badge
export const RTP_STATES = {
  Draft: { key: 'draft', cls: 'rs-draft' },
  'Pending Tax Review': { key: 'tax', cls: 'rs-pending' },
  'Pending FAT Approval': { key: 'fat', cls: 'rs-pending' },
  'Pending HOD Approval': { key: 'hod', cls: 'rs-pending' },
  'Pending Global Approval': { key: 'global', cls: 'rs-pending' },
  Approved: { key: 'approved', cls: 'rs-approved' },
  Paid: { key: 'paid', cls: 'rs-paid' },
  Rejected: { key: 'rejected', cls: 'rs-rejected' }
}
export const stateInfo = (s) => RTP_STATES[s] || RTP_STATES.Draft

// Aksi Workflow → kunci i18n (rtp.action.*) + gaya tombol
export const RTP_ACTIONS = {
  Submit: { key: 'submit', cls: 'brand' },
  Approve: { key: 'approve', cls: 'ok' },
  Reject: { key: 'reject', cls: 'danger' },
  'Mark as Paid': { key: 'paid', cls: 'brand' },
  Reopen: { key: 'reopen', cls: '' }
}

// Hitungan baris invoice — sama dengan server (pajak = potongan): net = nominal × (1 − tarif%)
export function invoiceCalc(inv) {
  const amount = Number(inv.amount) || 0
  const rate = inv.tax_withheld ? Number(inv.tax_rate) || 0 : 0
  const tax = Math.round(amount * rate) / 100
  return { amount, tax, net: Math.round((amount - tax) * 100) / 100 }
}

export const MAX_FILE_MB = 10
