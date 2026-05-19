# Calendario Académico

El calendario académico gestiona los términos, las fechas importantes y las reglas de plazos. Todos los aspectos se controlan a través de Desk.

## Descripción general

El calendario académico tiene una estructura por niveles:

### Año Académico:

Contiene términos académicos. Puede utilizarse para activar cuotas específicas.

### Plazo Académico:

Los términos no pueden superponerse. Cada término debe estar completamente contenido dentro de un Año Académico, con fechas de inicio y fin dentro del Año Académico.  
Cada término académico define la estructura de un período de enseñanza: fechas de inicio y fin, ventanas de inscripción, plazos de baja y períodos de evaluación.

## Conceptos clave

- **Término Académico** — la unidad de tiempo fundamental (semestre, trimestre, cuatrimestre)
- **DateRuleResolver** — lógica configurable para calcular plazos académicos en función de las fechas del término
- **Reglas a nivel de término** — la configuración de plazos y políticas reside en el nivel del término, lo que permite diferentes reglas por término
