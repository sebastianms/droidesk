# ADL-004: Web como SPA en React + Vite

**Fecha:** 2026-10-16
**Estado:** Activo
**Área:** Frontend
**Autor:** Usuario + AI Session

---

## Contexto

El usuario eligió React. La web tiene dos perfiles con vistas distintas, vive detrás de un ingreso y consume solo el contrato OpenAPI ([ADL-001](ADL-001-two-apps-openapi-contract.md)). La interfaz debe ser funcional y clara, con un look & feel inspirado en un droide astromecánico.

---

## Decisión

Una SPA en React con TypeScript estricto y Vite, React Router para las rutas por rol, TanStack Query para el estado de servidor y openapi-fetch con tipos generados por openapi-typescript desde el contrato. Los estilos usan CSS Modules y tokens CSS propios, sin librería de componentes. En producción, nginx sirve el build ([ADL-006](ADL-006-docker-compose-same-origin.md)).

---

## Justificación

Una app interna detrás de un ingreso no necesita SSR ni SEO: una SPA es lo más simple. TanStack Query elimina el código propio de caché y recarga (por ejemplo, refrescar la cola al tomar un ticket). Los tipos generados hacen que un cambio del contrato rompa la compilación, no la experiencia del usuario. Los tokens CSS bastan para el tema del droide.

---

## Consecuencias

### ✅ Positivas
- Build estático, servible por cualquier servidor web.
- Tipos del contrato hasta cada componente.
- Pocas dependencias, todas ampliamente usadas.

### ⚠️ Trade-offs aceptados
- Sin renderizado en servidor: la primera carga trae todo el bundle (aceptable para una app interna).
- Los componentes de UI se escriben a mano: más trabajo inicial que una librería, pero sin dependencias que mantener.

---

## Alternativas Consideradas

| Alternativa | Razón de descarte |
|-------------|-------------------|
| Next.js | SSR y servidor propio innecesarios; más complejidad de despliegue |
| Tailwind + shadcn/ui | Más dependencias y configuración; el tema propio con tokens es suficiente |
| fetch manual con estado local | Reimplementa caché, recarga e invalidación que TanStack Query ya resuelve |

---

## Decisiones Relacionadas
- [ADL-001](ADL-001-two-apps-openapi-contract.md): la web solo depende del contrato.
- [ADL-005](ADL-005-simulated-auth-signed-token.md): guardas de ruta por rol.
- [ADL-006](ADL-006-docker-compose-same-origin.md): la SPA llama a `/api` en el mismo origen.

---

## Notas para el AI (Memoria Técnica)
- No implementes reglas de negocio en la web: las acciones visibles de un ticket salen de lo que la API indica como permitido.
- Usa siempre el cliente tipado generado desde `contracts/openapi.json`; no escribas tipos de la API a mano.
- Las llamadas van al mismo origen bajo `/api`: en desarrollo las resuelve el proxy de Vite y en Docker, nginx. El cliente usa el origen como `baseUrl`, porque las rutas del contrato ya incluyen `/api`.
- Muestra descripciones y comentarios como texto plano; nunca uses `dangerouslySetInnerHTML`.
- Respeta los tokens de `tech-stack.md` (Visual Identity) y no uses arte ni logos oficiales de terceros.

---

## Extensión 2026-10-16 · Plan de la feature 001

Verificado en [research.md](../specs/001-ticketing-mvp/research.md):
- **TypeScript 6** (`~6.0.3`), no 7. TypeScript 7, el port nativo, todavía rompe `openapi-typescript` y `typescript-eslint`. Cuando las herramientas lo soporten, migrar será cambiar la versión.
- **Biome 2.5** para lint y formato, en lugar de ESLint y Prettier (unos 140 paquetes) o del Oxlint que trae el template. Su regla `noDangerouslySetInnerHtml` hace cumplir la nota de texto plano.
- **React Router 8 en modo data**, sin `react-router-dom` (v8 lo eliminó). Las guardas por rol son middleware de ruta.
- **`openapi-react-query`** integra el cliente tipado con TanStack Query.
- **Cliente HTTP**: `baseUrl` es el origen, porque las rutas del contrato ya incluyen `/api`.
- **Sesión**: vive en `sessionStorage`. Al cerrar sesión, también se limpia la caché de consultas.

---

## Extensión 2026-10-17 · Fundaciones (Fase 3)

- **Estilos**: CSS Modules por componente, más `tokens.css` y `base.css` globales, sin estilos inline, para cumplir la CSP de nginx. El foco es un anillo azul de 2 px con un halo holo, porque el holo solo no alcanza contraste AA.
- **El rojo no se usa como color de texto**, porque `--light-alert` sobre el casco no cumple AA. Los errores van en texto `--color-ink` con una `Light` roja.
- **Etiquetas atadas al contrato**: `PRIORITY_LABEL` y `ROLE_LABEL` usan `satisfies Record<…>` sobre los tipos generados, así que un valor nuevo en la API rompe la compilación. Los estados y las acciones se atarán cuando el contrato los exponga (Fase 4).
- **Guardas**: `requireSession` va en el layout y `requireRole` en cada ruta hija. Un perfil que entra a la ruta del otro termina en su propio inicio.
- **Deuda menor**: `api/client.ts` importa la sesión desde `features/auth`. Moverla a un módulo neutral desacoplaría las capas, pero la sacaría del gate de cobertura del flujo crítico.

---

## Extensión 2026-10-18 · Tickets del solicitante (Fase 4)

- **Etiquetas completas**: estados, acciones, prioridades y estados del SLA usan `satisfies Record<…>` sobre los enums del contrato. Así se cierra lo pendiente de la Fase 3.
- **Formularios**: `Field` reúne la etiqueta, la pista y el error de cualquier control; `TextField`, `TextArea` y `Select` se apoyan en él.
  - Se valida en español antes de enviar, contando el largo en puntos de código igual que la API.
  - El foco va al primer campo con error, y un 422 del servidor se asigna al campo que indica su `loc`.
- **Confirmaciones**: `<dialog>` nativo con `showModal()`. El navegador atrapa el foco, Escape cancela y el foco vuelve al botón, sin librería de modales.
- **Acciones**: los botones salen solo de `allowed_actions`, filtrados por un mapa de las acciones de transición atado al contrato. La web no repite la máquina de estados.
- **Listados en tarjetas**, no en tablas, para que se lean en móvil sin scroll horizontal. Las fechas se muestran en es-CL con la zona del navegador.

---

## Extensión 2026-10-18 · Cola del agente (Fase 5)

- **Pestañas como enlaces**: "Cola" y "Asignados a mí" son enlaces con `aria-current="page"`, y la vista vive en la URL (`/agent?view=assigned`), así que sobrevive a recargar. No hace falta el patrón `role="tab"`, que obliga a manejar flechas, para dos vistas que son navegación.
- **Un solo componente de listado**: `TicketList` encapsula carga, error, vacío y tarjetas para "Mis tickets", la cola y los asignados. Cada página aporta solo sus mensajes y si muestra al solicitante.
- **Tras un 409 se refrescan el detalle y los listados**: con caché de 30 s, la cola podía seguir mostrando libre un ticket que otro ya tomó.
- **Solo cancelar pide confirmación**: resolver es reversible (el solicitante reabre), y cerrar ya es la confirmación del solicitante ("Confirmar cierre").
