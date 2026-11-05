// Helper menu HR (app HRMS): Klaim Biaya = Expense Claim, Kasbon = Employee Advance.
// `kind` dipakai di URL (#/hr/claim, #/hr/advance) dan API (stock_ops.hr_claims.*).
export const HR_KINDS = {
  claim: { doctype: 'Expense Claim', icon: 'note', color: '#be185d', menu: 'expense_claim' },
  advance: { doctype: 'Employee Advance', icon: 'basket', color: '#4d7c0f', menu: 'employee_advance' }
}

// Status HRMS → kunci i18n (hr.status.*) + gaya badge (pakai kelas badge RTP yang sudah ada).
const STATUS = {
  Draft: { key: 'pending', cls: 'rs-pending' },
  Unpaid: { key: 'unpaid', cls: 'rs-approved' },
  Paid: { key: 'paid', cls: 'rs-paid' },
  'Partially Paid': { key: 'partPaid', cls: 'rs-approved' },
  Claimed: { key: 'claimed', cls: 'rs-paid' },
  Returned: { key: 'returned', cls: 'rs-paid' },
  'Partly Claimed and Returned': { key: 'claimed', cls: 'rs-paid' },
  Rejected: { key: 'rejected', cls: 'rs-rejected' },
  Cancelled: { key: 'cancelled', cls: 'rs-rejected' },
  Submitted: { key: 'approved', cls: 'rs-approved' }
}
// Draft HRMS = menunggu persetujuan (standar HRMS: draft langsung dibagikan ke Expense Approver).
export const hrStatus = (row) => {
  if (row.docstatus === 2 || row.status === 'Cancelled') return STATUS.Cancelled
  return STATUS[row.status] || STATUS.Draft
}

export const HR_ACTIONS = {
  Approve: { key: 'approve', cls: 'ok' },
  Reject: { key: 'reject', cls: 'danger' },
  Discard: { key: 'discard', cls: '' }
}
