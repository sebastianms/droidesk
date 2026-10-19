# ADL-010: Smoke end-to-end con Playwright Test contra el stack Docker

**Fecha:** 2026-10-19
**Estado:** Activo
**Área:** Calidad
**Autor:** AI Session (decisión del orquestador, Fase 9)

---

## Contexto

Los tests de cada app prueban su lado del contrato por separado: la API con pytest y la web con Vitest y la API simulada. Nada confirma que las piezas reales funcionen juntas: la imagen de la API con sus migraciones y su seed, nginx con su proxy y su CSP, y la SPA compilada en un navegador. La estrategia de calidad dejó la herramienta del smoke para la fase de empaquetamiento ([tech-stack](../specs/tech-stack.md#quality-strategy), T060).

---

## Decisión

Un módulo `e2e/` en la raíz, independiente de las dos apps: tiene su propio `package.json` con `@playwright/test` 1.63.0 fijado, y solo Chromium.
- **Un spec, el recorrido principal**: la solicitante crea un ticket; el agente lo toma y lo deja en espera; la solicitante comenta y el ticket vuelve solo a En progreso; el agente resuelve, la solicitante confirma el cierre y el historial muestra los 8 eventos en orden.
- **Dos contextos de navegador**, uno por perfil, para que las sesiones no se mezclen.
- El test falla ante cualquier error de consola, violación de CSP o excepción de la página.
- **Corre contra un stack ya levantado**, con `DROIDESK_BASE_URL` (por defecto `http://localhost:8080`) y sin `webServer`.
  - El título del ticket es único, así que el smoke funciona en los modos Demo y Vacío y se puede repetir sobre el mismo stack.
- **CI**: el workflow `e2e.yml` levanta el stack con `./setup.sh --yes`, así que también prueba el script de arranque, y después corre el smoke. Si falla, sube el reporte y el trace.

---

## Justificación

- Es la única capa que ejercita el sistema tal como lo usa una persona: navegador, nginx, API y SQLite en Docker.
- Playwright espera solo a que los elementos estén listos (aserciones *web-first*), así que no hacen falta pausas fijas. Además soporta varios contextos aislados en un mismo test y, si falla, retiene un trace que muestra qué pasó.
- Va en un módulo propio para no sumar dependencias de navegador a `apps/web`: las dos apps siguen independientes ([ADL-001](ADL-001-two-apps-openapi-contract.md)).
- Es un solo recorrido, como pide Pareto ([ADL-007](ADL-007-pareto-coverage-gates.md)). Las reglas y sus bordes ya están probados más abajo, donde es rápido y determinista; el smoke solo confirma que el todo funciona.

---

## Consecuencias

### ✅ Positivas
- Detecta lo que los tests unitarios no ven: migraciones que fallan al arrancar, un proxy o una CSP mal configurados, o un contrato que la SPA consume de forma distinta a la que la API publica.
- CI prueba el mismo comando que usará quien clone el repo.

### ⚠️ Trade-offs aceptados
- El job de CI tarda más que los de cada app, porque construye las imágenes y descarga Chromium.
- No mide cobertura y cubre un solo camino: los demás escenarios del [quickstart](../specs/001-ticketing-mvp/quickstart.md) quedan para la prueba manual.
- Solo Chromium: los demás navegadores no aportan riesgo en una SPA sin APIs exóticas.

---

## Alternativas Consideradas

| Alternativa | Razón de descarte |
|-------------|-------------------|
| Smoke por API con `curl` y `jq` | No ejercita la SPA, nginx ni la CSP, que es donde está el riesgo de integración |
| Cypress | Un solo navegador por test complica tener dos perfiles en simultáneo; más pesado |
| Playwright dentro de `apps/web` | Acopla las dependencias de navegador al build de la web |
| Suite e2e de todos los escenarios | Duplica lo que ya prueban los tests de cada app y vuelve lenta y frágil la CI |

---

## Decisiones Relacionadas
- [ADL-001](ADL-001-two-apps-openapi-contract.md): `e2e/` es un tercer módulo independiente.
- [ADL-006](ADL-006-docker-compose-same-origin.md): el smoke corre contra el stack que levanta `setup.sh`.
- [ADL-007](ADL-007-pareto-coverage-gates.md): el smoke cierra la pirámide sin sumar gates de cobertura.

---

## Notas para el AI (Memoria Técnica)
- Usa selectores accesibles: rol y nombre, regiones "Datos", "Comentarios" e "Historial", y botones con nombre exacto. No uses clases CSS.
- Nunca uses `waitForTimeout`. Después de un clic, React Router mantiene la página anterior hasta cargar la siguiente: espera un elemento de la página destino.
- Agrega un spec nuevo solo si cubre un riesgo de integración que los tests de cada app no puedan ver.
- Si cambias la versión de `@playwright/test`, fíjala exacta: cada versión trae su propio build de Chromium.
