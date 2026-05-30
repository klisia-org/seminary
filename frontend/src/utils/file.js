// Display just the file name, not the /private/files/... path.
export function fileName(url) {
  if (!url) return ''
  const base = url.split('/').pop()
  try {
    return decodeURIComponent(base)
  } catch {
    return base
  }
}
