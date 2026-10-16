# ADL-007: Gates de cobertura con Pareto: 80 % total y 90 % en el flujo crítico

**Fecha:** 2026-10-16
**Estado:** Activo
**Área:** Otro (Calidad)
**Autor:** Usuario + AI Session

---

## Contexto

El enunciado no espera cobertura completa: pide explicar qué se probó, qué no y cómo se decidió dónde poner el esfuerzo. La skill de SDD exige 90 % por defecto si el proyecto no define un umbral. La primera propuesta fue 90 % en la API y 70 % en la web; el usuario pidió aplicar la ley de Pareto.

---

## Decisión

Cada app (`apps/api` y `apps/web`) debe tener al menos 80 % de cobertura de líneas en total, y el **flujo crítico** al menos 90 %. El flujo crítico es el ciclo de vida del ticket (crear → tomar → cambiar estado → historial), con sus reglas de SLA y la autorización por rol. En la API corresponde a `tickets/`, `sla/`, `audit/` y la autorización de `identity/`; en la web, a `src/features/`. Ambos umbrales son gates del checkpoint de cada bloque.

---

## Justificación

El riesgo no está repartido por igual: un error en una transición de estado, en un vencimiento o en un permiso rompe la promesa central de DroiDesk, mientras que uno en la configuración o en un componente visual se detecta al primer uso. Exigir más donde está el riesgo, y un piso razonable en el resto, pone el esfuerzo donde rinde y evita tests escritos solo para subir un número.

---

## Consecuencias

### ✅ Positivas
- La regla de negocio queda probada a fondo, con sus bordes.
- Un criterio explicable para la estrategia de calidad que pide el enunciado.
- Menos tests frágiles sobre código de bajo riesgo.

### ⚠️ Trade-offs aceptados
- Hasta un 20 % del código fuera del flujo crítico puede quedar sin cubrir.
- Mantener dos reportes de cobertura por app: uno total y uno del flujo crítico.

---

## Alternativas Consideradas

| Alternativa | Razón de descarte |
|-------------|-------------------|
| 90 % parejo en todo (default de la skill SDD) | Esfuerzo alto en código de bajo riesgo |
| 90 % en la API y 70 % en la web (primera propuesta) | Mide por app, no por riesgo: no distingue el flujo crítico |
| Sin umbral | Deja la calidad sin un criterio verificable en el checkpoint |

---

## Decisiones Relacionadas
- [ADL-002](ADL-002-fastapi-sqlmodel-backend.md): el dominio en funciones puras hace barato cubrir el flujo crítico.
- [ADL-004](ADL-004-react-vite-spa.md): la web no duplica reglas, así que su flujo crítico es acotado.

---

## Notas para el AI (Memoria Técnica)
- No bajes de 80 % total ni de 90 % en el flujo crítico para cerrar un bloque.
- Si una ruta del flujo crítico se mueve o se renombra, actualiza en el mismo commit el reporte de coverage que la mide.
- No escribas tests de estilos o de componentes puramente visuales solo para subir el número.
- Prioriza los casos borde del dominio (transiciones inválidas, vencimientos al límite, permisos cruzados) por sobre los caminos felices repetidos.
