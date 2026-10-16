---
name: design-logger
description: Use when a significant architectural, technological, or design decision is made. Captures the "why" behind technical choices in Architectural Decision Logs (ADLs) to prevent context loss.
---

# 📓 Design Logger — Arquitecto de la Memoria Técnica

## Overview
El Design Logger es una habilidad especializada en capturar y preservar el **por qué** detrás de las decisiones técnicas. Su misión es documentar decisiones arquitectónicas, tecnológicas o de diseño para evitar el problema del "Context Wall" (pérdida de historial de decisiones).

## When to Use This Skill
- Cuando se decide usar una **nueva librería o framework**.
- Cuando se define un **patrón arquitectónico core** (ej: repository pattern, event-driven, etc.).
- Cuando se elige una **estrategia de esquema de base de datos**.
- Cuando el usuario pide explícitamente "registrar una decisión" o "crear un ADL".
- Después de una discusión técnica donde se llegó a un compromiso o "trade-off".

---

## 🛠️ Workflow de Implementación

### 1. Preparación
1. **Explorar el entorno**: Usa `list_dir` para ver el directorio raíz.
2. **Asegurar el directorio**: Todos los logs viven en `.design-logs/`. Si no existe, se creará al escribir el primer archivo.
3. **Determinar la secuencia**: Revisa los archivos `ADL-NNN-*` existentes para determinar el **siguiente número secuencial** (ej: si existe `ADL-012`, el siguiente es `013`). Si no hay ninguno, empieza con `001`.

### 2. Estructurar la Decisión
- **Nombre del archivo**: `.design-logs/ADL-{NNN}-{titulo-kebab-case}.md`
- **Título Corto**: kebab-case, máximo 5 palabras (ej: `adl-001-use-sqlite-for-cache.md`).

### 3. Redactar el ADL
Usa la herramienta `write_to_file` para crear el archivo usando la siguiente plantilla obligatoria. Rellena toda la información basada en la conversación; no dejes placeholders vacíos. Usa `[Pendiente de clarificar]` si un detalle es desconocido.

```markdown
# ADL-{NNN}: {Título Descriptivo en Lenguaje Natural}

**Fecha:** {YYYY-MM-DD}
**Estado:** Activo
**Área:** {Frontend | Backend | Infraestructura | Base de Datos | Arquitectura | Seguridad | Otro}
**Autor:** {Usuario o "AI Session"}

---

## Contexto
{Describe la situación narrativa, el problema a resolver y las restricciones}

---

## Decisión
{Una o dos oraciones directas sobre qué se decidió exactamente}

---

## Justificación
{Por qué esta opción y no otra. Razones fundamentales para el AI y el equipo}

---

## Consecuencias

### ✅ Positivas
- {consecuencia positiva 1}

### ⚠️ Trade-offs aceptados
- {limitación o desventaja 1}

---

## Alternativas Consideradas

| Alternativa | Razón de descarte |
|-------------|-------------------|
| {Opción A}  | {Por qué se descartó} |

---

## Decisiones Relacionadas
- Ninguna aún / o enlaces a otros ADL.

---

## Notas para el AI (Memoria Técnica)
- {Crítico: Instrucciones directas en imperativo para no violar esta decisión en el futuro. Ej: "No sugieras cambiar a MongoDB, la estructura relacional es intencional por X."}
```

### 4. Confirmación
Una vez guardado el archivo, entrega un reporte final al usuario en este formato:

```text
📓 Design Log registrado

Archivo: .design-logs/ADL-{NNN}-{titulo-kebab-case}.md
Decisión: {título en lenguaje natural}
Área: {área principal}

La decisión ha sido documentada exitosamente.
```

---

## Reglas de Comportamiento AI
- **Idioma de Interacción**: Toda comunicación con el usuario debe ser en **Español Neutro**.
- **Proactividad**: Si se toma una decisión importante durante la charla, sugiere registrarla usando esta habilidad.
- **Preservar Contexto**: Siempre vincula a ADLs previos si la nueva decisión los modifica o complementa.
- **Sin placeholders**: Nunca entregues un archivo con `{...}` o `[Placeholder]`. Deduce del contexto o pregunta.
