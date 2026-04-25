# @seminary/portal-shell

Shared chrome (header, portal switcher, session/theme composables) used by
the seminary, frappe_giving, and accreditation Vue 3 SPAs to provide
consistent post-login UX across portals on the same Frappe site.

Consumed via a `file:` reference. No npm publishing required for the seminary
ecosystem.

## Usage

```js
import { PortalHeader, configurePortals, useSession } from '@seminary/portal-shell'
import '@seminary/portal-shell/style.css'

configurePortals({
  brand: { name: 'Seminary', color: '#0D3049' },
  portals: [
    { id: 'student',       label: 'Courses',       url: '/seminary',          roles: ['Student'] },
    { id: 'alumni',        label: 'Alumni',        url: '/seminary/alumni',   roles: ['Alumni'] },
    { id: 'donor',         label: 'Donate',        url: '/donate',            roles: ['Donor'] },
    { id: 'accreditation', label: 'Accreditation', url: '/accreditation',     roles: ['Accreditation User'] },
  ],
})
```

```vue
<template>
  <PortalHeader title="My page">
    <template #actions>
      <slot name="actions" />
    </template>
  </PortalHeader>
</template>
```

`useSession()` reads the Frappe `user_id` cookie and lazily fetches the
user's roles via `/api/method/frappe.client.get_value` so the portal
switcher only shows portals the user can access.
