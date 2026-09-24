<!--
  Moved to @seminary/portal-shell so the accreditation SPA renders the same frame
  (ADR 075's "one primitive, not nine" applies across the portals, not just within
  this one). This shim keeps the existing import path working.
-->
<script>
import { PageHeader } from '@seminary/portal-shell'
export default PageHeader
</script>
