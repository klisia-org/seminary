# Installation

::: info Prerequisites
SeminaryERP requires a working [Frappe Bench](https://frappeframework.com/docs/user/en/installation) environment with ERPNext installed.
:::

## Install the app

```bash
bench get-app https://github.com/klisia-org/seminary.git
bench --site your-site install-app seminary
bench --site your-site migrate
```

## Install the LMS frontend

```bash
cd apps/seminary/frontend
yarn install
```

## For online payments, install Payments

 ```bash
bench get-app payments
bench --site your-site install-app payments
bench --site your-site migrate
```

The LMS frontend is available at `/seminary` on your site.
