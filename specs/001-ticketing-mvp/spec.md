# Feature Specification: Ticketing MVP

**Feature**: `001-ticketing-mvp` · **Rama de especificación**: `phase/02-mvp-spec`
**Created**: 2026-10-16
**Status**: Draft
**Input**: [REQUIREMENTS.md](../../REQUIREMENTS.md), [mission.md](../mission.md) y el alcance opcional elegido: SLA por prioridad y comentarios ([DECISIONS.md](../../DECISIONS.md#alcance-opcional)).

Las user stories US1 a US5 se implementan en las fases 4 a 8 del [roadmap](../roadmap.md). Los dos perfiles y el ingreso simulado son la base común de todas y se entregan en la fase de fundaciones.

## Clarifications

### Session 2026-10-16

- Q: ¿Quién define la prioridad de un ticket? → A: El solicitante la sugiere al crear el ticket, guiado por una descripción de cada nivel, y cualquier agente puede ajustarla mientras el ticket no esté Resuelto ni Cerrado; el vencimiento se recalcula y el cambio queda en el historial (FR-019, US5).
- Q: ¿El tiempo En espera pausa el plazo del SLA? → A: Sí. Mientras está En espera el plazo no se consume y el SLA se muestra "En pausa"; al volver, el ticket retoma el plazo que le quedaba. Una espera que empieza con el ticket ya vencido no lo devuelve a En plazo (FR-021, FR-023, US5).
- Q: ¿Qué pasa cuando el solicitante comenta un ticket En espera? → A: Vuelve solo a En progreso y el plazo se reanuda; el cambio queda en el historial a nombre del solicitante (FR-018, FR-011, US4).
- Q: ¿Puede el solicitante cancelar un ticket? → A: Sí, solo mientras está Abierto. Cancelado es un estado final, sale de la cola y no cuenta para el SLA (FR-011, FR-023, US1).
- Q: ¿Qué plazos tiene cada prioridad y desde cuándo un ticket está "Por vencer"? → A (revisada por el usuario para un equipo chico): el plazo corre en tiempo hábil, de lunes a viernes de 09:00 a 18:00 en la zona horaria de la organización. Crítica 4 horas hábiles, Alta 1 día hábil, Media 3 días hábiles y Baja 5 días hábiles: lo urgente sigue corto, porque es lo que más afecta al usuario, y lo demás se alarga. "Por vencer" cuando queda menos del 25 % del plazo. Plazos, jornada y zona horaria son configuración, no comportamiento (FR-020, FR-021, FR-023).

### Session 2026-10-17 · Revisión del usuario

- Q: ¿Cómo se ingresa? → A: Con un formulario de login de usuario y contraseña que siempre responde OK, sin importar los valores, más un selector de perfil. Reemplaza la primera versión, en la que se elegía un usuario de una lista. Un usuario nuevo se crea con el perfil elegido; uno existente conserva el suyo, para que el rol de alguien que ya existe nunca lo decida el cliente (FR-001).
- Q: ¿Se pueden crear usuarios desde el login? → A (segunda revisión del usuario): No, para no crear usuarios sin límite. Los usuarios vienen precreados por perfil y el login solo acepta a los existentes, con cualquier contraseña. El selector de perfil se elimina, y un ícono "?" muestra los usuarios de demo y su perfil (FR-001).

### Session 2026-10-18 · Revisión del usuario

- Q: ¿Cómo se sabe que un ticket tiene conversación sin abrirlo? → A: Los listados (Mis tickets, Cola y Asignados a mí) muestran cuántos comentarios tiene cada ticket, y el panel de comentarios del detalle muestra el total (FR-017a).
- Q: ¿Se puede responder a un comentario puntual? → A: Sí. Un comentario puede citar a otro del mismo ticket como respuesta: se muestra con el autor y un extracto del original, enlazado a él. La cita es de un solo nivel (FR-017b).
- Q: ¿Se pueden filtrar y ordenar los listados? → A: Sí. Mis tickets, Cola y Asignados a mí se filtran por prioridad y por estado del SLA, y se ordenan por vencimiento, por prioridad o por los más recientes. Cada vista conserva su orden por defecto, y los filtros quedan en la URL. En el MVP se aplican en la web sobre el listado completo (FR-024a).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Crear y seguir mis tickets (Priority: P1)

Como solicitante, quiero registrar una solicitud de soporte con título, descripción y categoría, y ver en qué estado están todas mis solicitudes, para no depender del correo ni preguntar por su avance.

**Why this priority**: es el obligatorio 1 y el punto de entrada de todo el flujo. Sin tickets no hay cola, historial ni SLA.

**Independent Test**: ingresar como solicitante, crear un ticket y verlo en "Mis tickets" en estado Abierto y sin asignar.

**Acceptance Scenarios**:
1. **Given** soy solicitante, **When** creo un ticket con título, descripción y categoría válidos, **Then** el ticket queda en estado Abierto, sin agente asignado, y aparece en "Mis tickets".
2. **Given** dejo vacío el título, la descripción o la categoría, **When** intento crear el ticket, **Then** el sistema indica qué falta y no lo crea.
3. **Given** tengo varios tickets, **When** abro "Mis tickets", **Then** veo cada uno con su estado, quién lo atiende (o "sin asignar") y su fecha de creación, del más reciente al más antiguo.
4. **Given** otro solicitante tiene tickets, **When** abro "Mis tickets" o intento abrir uno de los suyos, **Then** no veo ni puedo abrir tickets ajenos.
5. **Given** soy solicitante, **When** ingreso, **Then** veo la vista del solicitante y no tengo acceso a la cola ni a las acciones de agente.
6. **Given** un ticket mío que sigue Abierto y que ya no necesito, **When** lo cancelo, **Then** queda Cancelado, sale de la cola de los agentes y el cambio queda en el historial.

---

### User Story 2 - Cola del agente: tomar y cambiar estado (Priority: P1)

Como agente de soporte, quiero ver la cola de tickets, tomar uno y moverlo por su ciclo de vida, para que siempre se sepa quién atiende cada solicitud y en qué estado está.

**Why this priority**: es el obligatorio 2 y responde "¿quién la tiene?", uno de los tres problemas declarados.

**Independent Test**: con tickets abiertos de demo, ingresar como agente, tomar uno, pasarlo a Resuelto y comprobar que el solicitante lo ve resuelto.

**Acceptance Scenarios**:
1. **Given** soy agente, **When** abro la cola, **Then** veo todos los tickets que no están en un estado final (Cerrado o Cancelado), con su estado, solicitante, categoría y agente asignado, y puedo cambiar a la vista de los asignados a mí.
2. **Given** un ticket Abierto sin asignar, **When** lo tomo, **Then** queda asignado a mí y pasa a En progreso.
3. **Given** otro agente tomó el ticket un instante antes que yo, **When** intento tomarlo, **Then** el sistema me avisa que ya fue tomado y la asignación no cambia.
4. **Given** un ticket En progreso asignado a mí, **When** lo marco como Resuelto o lo dejo En espera, **Then** su estado cambia.
5. **Given** una transición fuera del ciclo de vida (por ejemplo, de Abierto a Cerrado) o un ticket asignado a otro agente, **When** intento moverlo, **Then** el sistema lo rechaza y explica por qué.
6. **Given** abro un ticket, **When** veo su detalle, **Then** solo se me ofrecen las acciones permitidas para mi perfil y para el estado del ticket.
7. **Given** un ticket Resuelto, **When** su solicitante confirma la solución o lo reabre, **Then** pasa a Cerrado o vuelve a En progreso, respectivamente.

---

### User Story 3 - Historial del ticket (Priority: P1)

Como solicitante o agente, quiero ver todo lo que pasó con un ticket —quién hizo qué y cuándo—, para entender su situación sin preguntarle a nadie.

**Why this priority**: es el obligatorio 3 y lo que hoy se pierde entre correos y planillas.

**Independent Test**: crear, tomar y resolver un ticket; su historial muestra los tres hechos en orden, cada uno con autor, fecha y hora.

**Acceptance Scenarios**:
1. **Given** un ticket con cambios, **When** abro su detalle, **Then** veo su historial en orden cronológico: creación, asignación, cada cambio de estado (con el estado anterior y el nuevo), cada cambio de prioridad y cada comentario, con autor, fecha y hora.
2. **Given** el historial de un ticket, **When** cualquier usuario lo consulta, **Then** no existe forma de editar ni borrar sus entradas.
3. **Given** soy solicitante, **When** abro el historial de uno de mis tickets, **Then** lo veo completo, y no puedo ver el historial de tickets ajenos.

---

### User Story 4 - Comentarios en el ticket (Priority: P2)

Como solicitante o agente, quiero conversar dentro del ticket para pedir o dar información sin volver al correo.

**Why this priority**: opcional elegido. Saca la conversación del correo y hace posible el estado En espera.

**Independent Test**: el agente comenta pidiendo un dato, el solicitante responde, y ambos ven la conversación en el ticket y en su historial.

**Acceptance Scenarios**:
1. **Given** un ticket que no está Cerrado, **When** su solicitante o un agente escribe un comentario, **Then** queda visible para ambos con autor, fecha y hora, y aparece en el historial.
2. **Given** un comentario vacío o más largo que el máximo permitido, **When** intento enviarlo, **Then** se rechaza con un mensaje claro.
3. **Given** un ticket Cerrado o Cancelado, **When** intento comentarlo, **Then** el sistema no lo permite.
4. **Given** un ticket En espera, **When** su solicitante comenta, **Then** el ticket vuelve solo a En progreso, el plazo del SLA se reanuda y el cambio queda en el historial a nombre del solicitante.

---

### User Story 5 - SLA por prioridad (Priority: P2)

Como agente, quiero saber cuánto plazo le queda a cada ticket según su prioridad y atender primero lo que está por vencer. Como solicitante, quiero saber para cuándo está comprometida la solución.

**Why this priority**: opcional elegido. Responde "¿cuánto demoran?" y convierte la cola en una lista de trabajo ordenada por urgencia.

**Independent Test**: crear tickets con distintas prioridades y comprobar que cada uno muestra su vencimiento y su estado de SLA, y que la cola los ordena por urgencia.

**Acceptance Scenarios**:
1. **Given** un ticket nuevo con prioridad asignada, **When** se registra en horario hábil, **Then** su vencimiento es el momento en que se agota el plazo de esa prioridad, contando solo tiempo hábil (por ejemplo, un ticket Alta creado el lunes a las 10:00 vence el martes a las 10:00).
2. **Given** un ticket creado fuera de la jornada (de noche o en fin de semana), **When** se registra, **Then** su plazo empieza a correr al inicio de la siguiente jornada hábil (un ticket Alta creado el viernes a las 20:00 vence el lunes a las 18:00).
3. **Given** un ticket abierto, **When** queda menos del 25 % de su plazo hábil, **Then** su SLA se muestra "Por vencer"; si ya pasó el vencimiento, "Vencido"; en otro caso, "En plazo".
4. **Given** un ticket Resuelto o Cerrado, **When** veo su SLA, **Then** se muestra "Cumplido" si se resolvió antes del vencimiento o "Incumplido" si no.
5. **Given** soy agente, **When** abro la cola, **Then** los tickets aparecen ordenados por vencimiento, del más urgente al menos urgente.
6. **Given** soy solicitante, **When** creo un ticket, **Then** elijo su prioridad con la ayuda de una descripción de cada nivel, y Media viene preseleccionada.
7. **Given** soy agente y el ticket no está Resuelto ni Cerrado, **When** ajusto su prioridad, **Then** el vencimiento se recalcula desde la creación y el cambio queda en el historial con el valor anterior y el nuevo.
8. **Given** un ticket En espera dentro de su plazo, **When** pasa el tiempo, **Then** su SLA se muestra "En pausa" y, al volver a En progreso, retoma el plazo hábil que le quedaba y su vencimiento se recalcula desde ese momento.

---

### Edge Cases

- **Toma simultánea**: dos agentes toman el mismo ticket al mismo tiempo; solo uno lo obtiene y el otro recibe un aviso.
- **Ticket ajeno**: un solicitante intenta abrir el ticket de otro; el sistema responde como si no existiera, para no revelar información.
- **Agente no disponible**: un ticket asignado solo lo mueve su agente; la reasignación está fuera del alcance (ver Assumptions).
- **Transición inválida**: cualquier cambio de estado fuera del ciclo de vida se rechaza con una explicación.
- **Reapertura tardía**: un ticket reabierto después de su vencimiento sigue Vencido; reabrir no reinicia el plazo.
- **Prioridad inflada**: si un solicitante marca como Crítica algo que no lo es, un agente la ajusta; el vencimiento se recalcula y el cambio queda registrado.
- **Espera sobre un ticket vencido**: si el ticket ya venció, pasarlo a En espera no lo devuelve a En plazo; sigue Vencido.
- **Fuera de jornada**: un ticket creado de noche, en fin de semana o mientras termina la jornada empieza a consumir su plazo al inicio de la siguiente jornada hábil; ningún ticket vence fuera del horario hábil.
- **Feriados**: en el MVP, un feriado de lunes a viernes cuenta como día hábil.
- **Cancelación tardía**: si un agente ya tomó el ticket, el solicitante no puede cancelarlo; puede comentarlo para pedir que se resuelva. Si cancelar y tomar ocurren a la vez, solo una de las dos acciones prospera.
- **Resuelto sin confirmación**: si el solicitante nunca confirma, el ticket queda Resuelto y cuenta como resuelto para el SLA.
- **Textos al límite**: título de 120 caracteres, descripción de 5.000 y comentario de 2.000 se aceptan; un carácter más se rechaza.
- **Contenido con formato**: descripciones y comentarios con etiquetas o símbolos se muestran tal cual se escribieron, sin interpretarse.
- **Usuario inexistente**: el ingreso lo rechaza con un mensaje que remite a la ayuda de usuarios de demo. Nunca se crean usuarios desde el login.
- **Sesión vencida**: si la sesión del usuario expira, vuelve a la pantalla de ingreso sin perder datos ya guardados.
- **Cola vacía**: si no hay tickets por atender, la cola lo indica con un mensaje claro.

## Requirements *(mandatory)*

### Functional Requirements

**Perfiles y acceso**
- **FR-001**: El sistema MUST permitir ingresar con un formulario de usuario y contraseña. El ingreso es simulado: los usuarios vienen precreados por perfil y cualquier contraseña es válida. La pantalla ofrece una ayuda (ícono "?") con los usuarios de demo y su perfil.
- **FR-002**: El sistema MUST ofrecer dos perfiles, solicitante y agente, cada uno con su propia vista.
- **FR-003**: El sistema MUST impedir que un solicitante acceda a la vista o a las acciones de agente.
- **FR-004**: El sistema MUST mostrar a cada solicitante solo sus propios tickets, con su historial y comentarios.

**Tickets (US1)**
- **FR-005**: Un solicitante MUST poder crear un ticket con título (obligatorio, máximo 120 caracteres), descripción (obligatoria, máximo 5.000) y categoría (obligatoria, de una lista predefinida).
- **FR-006**: Todo ticket nuevo MUST quedar en estado Abierto y sin agente asignado.
- **FR-007**: El solicitante MUST ver la lista de sus tickets con estado, agente asignado (o "sin asignar") y fecha de creación, del más reciente al más antiguo.

**Cola y ciclo de vida (US2)**
- **FR-008**: Un agente MUST ver la cola con todos los tickets que no están en un estado final (estado, solicitante, categoría y agente asignado) y una vista con solo los asignados a él.
- **FR-009**: Un agente MUST poder tomar un ticket Abierto sin asignar; al tomarlo, el ticket queda asignado a ese agente y pasa a En progreso.
- **FR-010**: Si dos agentes intentan tomar el mismo ticket, solo uno MUST lograrlo; el otro recibe un aviso.
- **FR-011**: El sistema MUST aplicar este ciclo de vida y rechazar, con una explicación, cualquier otra transición:

  | Desde | Hacia | Quién |
  |---|---|---|
  | Abierto | En progreso | Un agente, al tomarlo |
  | En progreso | En espera | El agente asignado |
  | En espera | En progreso | El agente asignado, o automáticamente cuando el solicitante comenta (FR-018) |
  | En progreso | Resuelto | El agente asignado |
  | Resuelto | Cerrado | El solicitante del ticket |
  | Resuelto | En progreso | El solicitante del ticket (reapertura) |
  | Abierto | Cancelado | El solicitante del ticket, mientras ningún agente lo haya tomado |

  Cerrado y Cancelado son estados finales.

- **FR-012**: Al consultar un ticket, el sistema MUST indicar qué acciones están permitidas para quien lo consulta.

**Historial (US3)**
- **FR-013**: El sistema MUST registrar cada cambio de un ticket —creación, asignación, cambio de estado, cambio de prioridad y comentario— con su autor, fecha y hora, y con el valor anterior y el nuevo cuando corresponda.
- **FR-014**: El historial MUST ser de solo lectura: nadie puede editar ni borrar sus entradas.
- **FR-015**: El solicitante (de sus tickets) y los agentes MUST poder ver el historial completo de un ticket en orden cronológico.

**Comentarios (US4)**
- **FR-016**: El solicitante del ticket y cualquier agente MUST poder comentar un ticket que no esté en un estado final (texto obligatorio, máximo 2.000 caracteres).
- **FR-017**: Los comentarios MUST mostrarse en orden cronológico, con autor, fecha y hora, como texto sin interpretar, y quedar en el historial.
- **FR-017a**: Los listados de tickets MUST mostrar cuántos comentarios tiene cada ticket, y el detalle MUST mostrar el total en su sección de comentarios.
- **FR-017b**: Un comentario MAY citar a otro comentario del mismo ticket como respuesta; la cita MUST mostrar el autor y un extracto del original y llevar a él. Citar un comentario de otro ticket MUST rechazarse.
- **FR-018**: Un comentario del solicitante sobre un ticket En espera MUST devolverlo automáticamente a En progreso; el cambio de estado queda en el historial a nombre del solicitante y el plazo del SLA se reanuda.

**SLA (US5)**
- **FR-019**: Cada ticket MUST tener una prioridad: Crítica, Alta, Media o Baja. El solicitante la elige al crear el ticket, guiado por una descripción de cada nivel (Media viene preseleccionada), y cualquier agente puede ajustarla mientras el ticket no esté Resuelto ni en un estado final.
- **FR-020**: Cada prioridad MUST tener un plazo de resolución en tiempo hábil: Crítica 4 horas hábiles, Alta 1 día hábil, Media 3 días hábiles y Baja 5 días hábiles. Un día hábil es una jornada de lunes a viernes, de 09:00 a 18:00 (9 horas hábiles), en la zona horaria de la organización.
- **FR-021**: El plazo de un ticket MUST consumirse solo en tiempo hábil y nunca mientras está En espera; su vencimiento es el momento en que el plazo se agota. Un ticket creado fuera de la jornada empieza a consumir su plazo al inicio de la siguiente. Una espera que empieza cuando el ticket ya venció no lo devuelve a En plazo.
- **FR-022**: Si la prioridad cambia, el vencimiento MUST recalcularse desde la creación y el cambio quedar en el historial.
- **FR-023**: El sistema MUST mostrar el estado del SLA de cada ticket: En plazo, Por vencer (queda menos del 25 % del plazo hábil) o Vencido mientras no esté resuelto; En pausa mientras está En espera dentro de plazo; y Cumplido o Incumplido una vez resuelto. Los tickets Cancelados no tienen estado de SLA ni cuentan para el cumplimiento.
- **FR-024**: La cola del agente MUST ordenarse por vencimiento, del más urgente al menos urgente; a igual vencimiento, por antigüedad.
- **FR-024a**: Los listados de tickets MUST permitir filtrar por prioridad y por estado del SLA, y ordenar por vencimiento, por prioridad (de Crítica a Baja y, a igual prioridad, por vencimiento) o por los más recientes; sin filtros, cada vista conserva su orden por defecto (FR-024).
- **FR-025**: El estado del ticket y del SLA MUST comunicarse con texto, no solo con color.

### Key Entities

- **Usuario**: persona que usa DroiDesk; tiene nombre, correo y un perfil (solicitante o agente).
- **Ticket**: una solicitud de soporte; tiene título, descripción, categoría, prioridad, estado, solicitante, agente asignado (opcional), vencimiento (o, mientras está En espera, el plazo hábil que le queda) y los momentos clave de su ciclo (creación, resolución, cierre o cancelación).
- **Categoría**: clasificación que elige el solicitante de una lista predefinida.
- **Política de SLA**: el plazo de resolución, en tiempo hábil, asociado a cada prioridad.
- **Calendario hábil**: los días (lunes a viernes) y el horario (09:00 a 18:00) en que corre el plazo, en la zona horaria de la organización.
- **Evento del historial**: un hecho ocurrido en un ticket, con su tipo, autor, momento y los valores anterior y nuevo; nunca cambia.
- **Comentario**: un mensaje de la conversación de un ticket, con autor, momento y texto.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Un solicitante crea un ticket en menos de 1 minuto desde que ingresa.
- **SC-002**: Al abrir la cola, el ticket más urgente aparece primero, y un agente lo identifica en menos de 10 segundos.
- **SC-003**: El 100 % de los cambios de un ticket aparece en su historial con autor y momento.
- **SC-004**: En ninguna situación un solicitante ve tickets, historial ni comentarios de otro solicitante.
- **SC-005**: Dos agentes que toman el mismo ticket al mismo tiempo nunca quedan ambos asignados.
- **SC-006**: Ningún ticket queda en un estado o transición fuera del ciclo de vida definido.
- **SC-007**: Para cualquier periodo se puede calcular qué porcentaje de los tickets resueltos se resolvió dentro de su SLA.

## Assumptions

- Categorías, plazos de SLA y usuarios de demo vienen precargados, y la app no crea usuarios. El MVP no tiene pantallas de administración.
- Categorías iniciales: Hardware, Software, Accesos y cuentas, Red y conectividad, y Otro.
- La jornada hábil por defecto es de lunes a viernes, de 09:00 a 18:00, y la zona horaria de la organización se define al instalar. Los feriados no se consideran en el MVP.
- Los plazos por prioridad, el umbral de "Por vencer", la jornada y la zona horaria son configuración: cambiarlos no requiere cambiar el comportamiento del sistema.
- Un ticket Resuelto que el solicitante no confirma permanece Resuelto; el cierre automático queda diferido.
- No hay reasignación (opcional descartado): un ticket asignado solo lo mueve su agente.
- Los comentarios no se editan ni se borran, igual que el historial.
- Mientras US5 no esté implementada, la cola se ordena por antigüedad.
- Fechas y horas se muestran en la zona horaria del usuario.
- Volumen del MVP: una organización de ~800 personas, del orden de decenas de tickets por día.
