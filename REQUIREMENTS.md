# Enunciado

## Contexto

Una organización de ~800 personas necesita reemplazar su gestión de solicitudes de soporte, hoy repartida entre correo y planillas. Nadie sabe cuántas solicitudes hay abiertas, cuánto demoran ni quién las tiene.

Se te pide construir la primera versión de un sistema de tickets.

## Alcance mínimo obligatorio

1. Un solicitante puede crear un ticket (título, descripción, categoría).
2. Un agente de soporte puede ver la cola de tickets, tomar uno y cambiar su estado.
3. Existe trazabilidad: se puede saber qué pasó con un ticket y cuándo.
4. Existen al menos dos perfiles con vistas distintas (solicitante / agente).

## Alcance opcional (elige a lo más dos y descarta el resto, explica cuál descartaste y por qué)

SLA por prioridad · comentarios en el ticket · adjuntos · notificaciones · reasignación · dashboard de métricas · búsqueda y filtros · categorización automática.

## Tus definiciones

Stack, modelo de datos, estados del ticket, autenticación (puede ser simulada), despliegue o local. La interfaz debe ser funcional y clara; no se evalúa diseño visual.

## Entregables

1. Repositorio con el código y las instrucciones para levantarlo.
2. DECISIONS.md:
   - Modelo de datos y por qué.
   - Máquina de estados del ticket y por qué esos estados.
   - Qué dejaste fuera del alcance opcional y con qué criterio.
   - Qué romperías o rediseñarías si esto tuviera que escalar a 50.000 tickets/mes y 5 áreas distintas de soporte.
   - Qué deuda técnica asumiste conscientemente.
3. AI-USAGE.md: qué herramientas de IA usaste, cómo estructuraste el contexto o las reglas del proyecto, qué delegaste completo al agente, dónde tuviste que intervenir y por qué, y qué salida del agente rechazaste.
4. Estrategia de calidad: no esperamos cobertura completa. Esperamos que nos digas qué probaste, qué no, y cómo decidiste dónde poner el esfuerzo de testing.
