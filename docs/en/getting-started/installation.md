# Installation

!!! note "Prerequisites"
    SeminaryERP requires a working [Frappe Bench](https://frappeframework.com/docs/user/en/installation) environment with ERPNext installed.

## Install the app

```bash
bench get-app https://github.com/klisia-org/seminary.git
bench --site your-site.localhost install-app seminary
bench --site your-site.localhost migrate
```

## Install the LMS frontend

```bash
cd apps/seminary
yarn install
```

## Development mode

```bash
bench --site your-site.localhost set-config developer_mode 1
bench start
```

The LMS frontend is available at `/seminary` on your site.
