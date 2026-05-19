# Instalación},{

!!! note "Prerrequisitos"
    SeminaryERP requiere un entorno [Frappe Bench](https://frappeframework.com/docs/user/en/installation) funcional con ERPNext instalado.

## Instalar la aplicación

```bash
bench get-app https://github.com/klisia-org/seminary.git
bench --site your-site.localhost install-app seminary
bench --site your-site.localhost migrate
```

## Instalar el frontend del LMS

```bash
cd apps/seminary
yarn install
```

## Modo de desarrollo

```bash
bench --site your-site.localhost set-config developer_mode 1
bench start
```

El frontend del LMS está disponible en `/seminary` en su sitio.
