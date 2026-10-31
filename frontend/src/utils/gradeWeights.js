// How much each assessment counts for one student (decisions/096). A port of
// seminary/seminary/gradebook_weights.py `compute`, for what the browser shows
// before saving: the assessment page's shares and Simulate Grades on My
// Status. Keep the two in step; the server's answer is the one that grades.

export const DROPPED = 'Dropped'
export const EXCUSED = 'Excused'

const num = (v) => Number(v) || 0

// The rubric rule (095 section 3): typed weights are fixed percents, rows left
// at 0 share what is left; all fixed and not 100 rescales.
function shares(rows) {
  let weights = rows.map((r) => num(r.weight_scac))
  const fixed = weights.filter((w) => w > 0).reduce((a, b) => a + b, 0)
  const auto = weights.filter((w) => w <= 0).length
  const fill = auto && fixed < 100 ? (100 - fixed) / auto : 0
  weights = weights.map((w) => (w > 0 ? w : fill))
  const total = weights.reduce((a, b) => a + b, 0)
  const out = {}
  if (!total) return out
  rows.forEach((r, i) => { out[r.name] = weights[i] / total })
  return out
}

function spread(weights, total) {
  const present = Object.values(weights).reduce((a, b) => a + b, 0)
  const out = {}
  for (const k of Object.keys(weights)) out[k] = present ? (weights[k] * total) / present : 0
  return out
}

const scored = (r) => !!r.graded || num(r.score) > 0

function drops(members, dropLowest, final) {
  const n = Math.min(num(dropLowest), members.length - 1)
  if (n <= 0) return new Set()
  const candidates = members
    .filter((r) => !r.never_drop && (final || scored(r)))
    .sort((a, b) => num(a.score) - num(b.score) || String(a.due_date || '').localeCompare(String(b.due_date || '')))
  return new Set(candidates.slice(0, n).map((r) => r.name))
}

// rows: {name, weight_scac, extracredit_scac, category_code, never_drop,
// due_date, excused, graded, score}. Returns {name: {weight, status}}.
export function computeWeights(rows, categories, final = false) {
  const regular = rows.filter((r) => !r.extracredit_scac)
  const out = {}
  const excused = new Set(regular.filter((r) => r.excused).map((r) => r.name))
  for (const name of excused) out[name] = { weight: 0, status: EXCUSED }

  if (!categories?.length) {
    const counting = {}
    for (const r of regular) if (!excused.has(r.name)) counting[r.name] = num(r.weight_scac)
    const total = regular.reduce((a, r) => a + num(r.weight_scac), 0)
    for (const [name, w] of Object.entries(spread(counting, total))) out[name] = { weight: w, status: null }
    return out
  }

  const byCode = Object.fromEntries(categories.map((c) => [c.category_code, c]))
  const counting = {}
  for (const [code, cat] of Object.entries(byCode)) {
    const members = regular.filter((r) => r.category_code === code && !excused.has(r.name))
    const dropped = drops(members, cat.drop_lowest, final)
    for (const name of dropped) out[name] = { weight: 0, status: DROPPED }
    const left = members.filter((r) => !dropped.has(r.name))
    if (left.length) counting[code] = shares(left)
  }
  const catWeights = {}
  for (const code of Object.keys(counting)) catWeights[code] = num(byCode[code].weight)
  const weights = spread(catWeights, categories.reduce((a, c) => a + num(c.weight), 0))
  for (const [code, rowShares] of Object.entries(counting)) {
    for (const [name, share] of Object.entries(rowShares)) out[name] = { weight: weights[code] * share, status: null }
  }
  for (const r of regular) if (!out[r.name]) out[r.name] = { weight: 0, status: null }
  return out
}

// Each row's share of the final grade before any drop or excuse.
export function nominalWeights(rows, categories) {
  const bare = rows.map((r) => ({ ...r, excused: 0, graded: 0, score: 0 }))
  const out = {}
  for (const [k, v] of Object.entries(computeWeights(bare, categories))) out[k] = v.weight
  return out
}
