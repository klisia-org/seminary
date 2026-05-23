// Copyright (c) 2026, Klisia and contributors
// For license information, please see license.txt

// Tokenize a verse on whitespace and decide which tokens are eligible to be
// hidden for memorization. Eligibility = alphanumeric-stripped length >=
// minWordLength. Language-agnostic on purpose so Crowdin-added languages
// don't need a stopword list maintained here.
const STRIP_NON_ALNUM = /[^\p{L}\p{N}]+/gu

export function eligibleBlankIndices(text, minWordLength = 4) {
    if (!text) return []
    const tokens = text.split(/\s+/)
    const eligible = []
    tokens.forEach((tok, idx) => {
        const stripped = tok.replace(STRIP_NON_ALNUM, '')
        if (stripped.length >= minWordLength) eligible.push(idx)
    })
    return eligible
}

// Pick `count` blank positions at random from the eligible set. If count
// exceeds the eligible count, return all eligible positions (graceful
// degradation matches the backend's save-time clamp).
export function pickBlankPositions(text, count, minWordLength = 4) {
    const eligible = eligibleBlankIndices(text, minWordLength)
    if (eligible.length <= count) return eligible
    // Fisher-Yates partial shuffle to draw `count` distinct items.
    const pool = [...eligible]
    for (let i = 0; i < count; i++) {
        const j = i + Math.floor(Math.random() * (pool.length - i))
        ;[pool[i], pool[j]] = [pool[j], pool[i]]
    }
    return pool.slice(0, count).sort((a, b) => a - b)
}

// Fisher-Yates shuffle, returns a new array. Used to shuffle the verse-text
// cards in the matching question UI.
export function shuffle(array) {
    const a = [...array]
    for (let i = a.length - 1; i > 0; i--) {
        const j = Math.floor(Math.random() * (i + 1))
        ;[a[i], a[j]] = [a[j], a[i]]
    }
    return a
}
