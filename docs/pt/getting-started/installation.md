# Instalação

!!! note "Pré-requisitos"
    O SeminaryERP requer um ambiente [Frappe Bench](https://frappeframework.com/docs/user/en/installation) em funcionamento, com o ERPNext instalado.

## Instalar o app

```bash
bench get-app https://github.com/klisia-org/seminary.git
bench --site your-site.localhost install-app seminary
bench --site your-site.localhost migrate
```

## Instalar o frontend do LMS

```bash
cd apps/seminary
yarn install
```

## Modo de desenvolvimento

```bash
bench --site your-site.localhost set-config developer_mode 1
bench start
```

O frontend do LMS está disponível em `/seminary` no seu site.
