# DECISIONS · DroiDesk

Decisiones de producto y arquitectura del MVP, en versión breve. El detalle técnico vive en los ADL de [`.design-logs/`](.design-logs/) y en los artefactos SDD de [`specs/`](specs/). La conversación que originó cada decisión está en [DEV-LOG.md](DEV-LOG.md).

## Alcance opcional

El enunciado permite elegir a lo más dos funcionalidades opcionales. El criterio de selección, en orden de peso:

1. **Ataca el problema declarado**: la gestión vive en correo y planillas, y nadie sabe cuántas solicitudes hay abiertas, cuánto demoran ni quién las tiene.
2. **Bajo costo para un MVP**: se apoya en datos que el alcance mínimo ya registra (estados, historial y fechas), sin infraestructura nueva.
3. **Bajo riesgo**: sin dependencias externas ni superficie de seguridad nueva.

### Elegidas

| Funcionalidad | Por qué |
|---|---|
| **SLA por prioridad** | Responde "¿cuánto demoran?": el tiempo transcurrido pasa a ser un compromiso por prioridad, con fecha de vencimiento y un estado (en plazo, por vencer, vencido). La cola deja de ser una lista plana y el agente atiende primero lo que está por vencer. Además, prepara el escenario de 5 áreas de soporte, donde cada área tendrá su propia política de SLA. |
| **Comentarios** | Saca la conversación del correo, que es la mitad del problema: las aclaraciones entre solicitante y agente quedan dentro del ticket y en su trazabilidad. También hacen viable el estado "En espera del solicitante": sin un canal en el ticket, el solicitante no sabría qué se le pide. |

El alcance mínimo ya responde "¿quién la tiene?" (un agente toma el ticket) y "¿qué pasó y cuándo?" (trazabilidad). Estas dos opcionales cubren lo que falta: el tiempo y la conversación.

### Descartadas

| Funcionalidad | Criterio de descarte |
|---|---|
| Adjuntos | Se evaluó como alternativa a Comentarios: aclara el problema al crear el ticket, pero no permite pedir información después. Suma almacenamiento, límites de tamaño y tipo, archivos maliciosos y control de descarga. En el MVP se mitiga pegando un enlace a la evidencia en la descripción o en un comentario. Es el primer candidato post-MVP. |
| Notificaciones | Requiere infraestructura de correo y procesos asíncronos. En el MVP, el solicitante ve el estado y los comentarios nuevos al entrar a sus tickets. |
| Reasignación | Tomar un ticket cubre la asignación básica. Reasignar entre agentes agrega flujo y permisos que no atacan el problema declarado. |
| Dashboard de métricas | La cola ya muestra cuántos tickets hay abiertos, quién los tiene y su estado de SLA. Un dashboard agregado gana valor con volumen y con varias áreas. |
| Búsqueda y filtros | Con el volumen del MVP basta la cola ordenada por vencimiento. Se vuelve necesaria a escala. |
| Categorización automática | Depende de un servicio externo (un LLM con API key), suma costo y vuelve no deterministas los tests. El solicitante elige la categoría al crear el ticket. |
