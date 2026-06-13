# Instalación},{

:::info Prerrequisitos
SeminaryERP requiere un entorno [Frappe Bench](https://frappeframework.com/docs/user/en/installation) funcional con ERPNext instalado.
:::

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

## Para pagos en línea, instale pagos

 ```bash
 pagos bench get-app
 bench --site your-site install-app payments
 bench --site your-site migrate
 ```

El frontend del LMS está disponible en `/seminary` en su sitio.
