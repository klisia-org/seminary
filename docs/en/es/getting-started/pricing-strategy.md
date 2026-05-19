# Estrategia de precios

SeminaryERP cobra a los estudiantes creando facturas a partir de **Categorías de Cuotas**, cada una vinculada a un **Artículo** de ERPNext con un precio en una **Lista de Precios**. El grado de granularidad que dé a esos Artículos es una decisión estratégica que afecta la elaboración de informes, la previsión y el trabajo necesario para cambiar los precios más adelante.

## Precios agrupados vs. granulares

Ambos enfoques siguientes producen el mismo total de la factura. No son equivalentes para el seminario.

| Enfoque A — _agrupado_            | Enfoque B — _granular_                   |
| --------------------------------- | ---------------------------------------- |
| Curso de 1 h: 250 | Hora de crédito: 200     |
| Curso de 2 h: 450 | Inscripción al curso: 50 |

**El Enfoque A** es más rápido de configurar. Los precios están incorporados en cada Artículo a nivel de curso.

**El Enfoque B** separa _lo que varía con la carga de créditos_ (costo de docencia por crédito) de _lo que es fijo por inscripción_ (costo administrativo). Esto permite:

- Proyectar ingresos según escenarios de matrícula (p. ej., "¿qué pasa si la carga promedio baja de 12 a 9 créditos?")
- Aumentar las tarifas por crédito sin tocar cada Artículo de curso
- Aplicar becas o descuentos solo a la parte por crédito
- Informar con claridad sobre los ingresos administrativos vs. académicos

Para cualquier seminario que no sea muy pequeño, **prefiera el Enfoque B**. El esfuerzo inicial de modelado se compensa la primera vez que necesite ajustar precios o justificar un presupuesto.

## Pautas prácticas

- **Un Artículo por factor de costo**, no por curso. Horas de crédito, inscripción, cuota de tecnología, acceso a biblioteca, alojamiento — cada uno es su propio Artículo.
- **Mantenga pequeño el número de Listas de Precios.** Cada lista adicional multiplica la carga de mantenimiento. Agregue una lista solo cuando la estructura de precios _entera_ difiera genuinamente (p. ej., los estudiantes internacionales pagan tarifas diferentes en todos los conceptos), no para descuentos puntuales — use becas o Reglas de Precios para esos.
- **Asigne cada evento facturable a una Categoría de Cuotas.** Esto es lo que hace que la facturación sea automática: cuando el estudiante se inscribe, se abre el período o se activa el disparador por crédito, SeminaryERP crea las líneas de factura correctas a partir de la Categoría de Cuotas.
- **Reevalúe antes de su primer período, no después.** Cambiar el modelo de precios una vez que existan facturas es doloroso; acertarlo antes de la puesta en producción es barato.

## Relacionado

- [Configuración inicial](initial-setup.md) — la secuencia completa de configuración
- [Artículo de ERPNext](https://docs.frappe.io/erpnext/item) · [Lista de Precios](https://docs.frappe.io/erpnext/price-lists) · [Precio de Artículo](https://docs.frappe.io/erpnext/item-price)
