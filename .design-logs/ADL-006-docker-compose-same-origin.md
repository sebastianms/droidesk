# ADL-006: Despliegue local con Docker Compose y proxy de mismo origen

**Fecha:** 2026-10-16
**Estado:** Activo
**Área:** Infraestructura
**Autor:** Usuario + AI Session

---

## Contexto

El setup debe ser un solo comando que levante todo con Docker y le pida al usuario la configuración necesaria. Las apps deben seguir siendo independientes ([ADL-001](ADL-001-two-apps-openapi-contract.md)), y la web necesita llamar a la API sin complicaciones de CORS.

---

## Decisión

Docker Compose con dos servicios. `api` corre uvicorn y, al iniciar, aplica las migraciones y carga los datos de demo si están habilitados. `web` es nginx: sirve el build de la SPA y hace de proxy de `/api` hacia `api`. SQLite vive en un volumen nombrado. `setup.sh` verifica Docker, pregunta la configuración, genera el secreto en `.env`, levanta todo y muestra las URLs y los usuarios de demo.

---

## Justificación

El navegador ve un único origen, así que no hay que configurar CORS ni exponer la API por separado. Cada app conserva su propia imagen y su propio ciclo de build. Un único script cumple el pedido de levantar todo con un comando.

---

## Consecuencias

### ✅ Positivas
- Una sola URL para el usuario y la API detrás del mismo origen.
- Las imágenes se pueden desplegar por separado más adelante.
- Los datos sobreviven a reinicios gracias al volumen.

### ⚠️ Trade-offs aceptados
- nginx es una pieza más que configurar en la imagen de la web.
- Migrar al iniciar la API sirve para una sola instancia; con varias réplicas debe pasar a un paso de despliegue.

---

## Alternativas Consideradas

| Alternativa | Razón de descarte |
|-------------|-------------------|
| Servir la SPA desde FastAPI | Acopla las apps y contradice ADL-001 |
| Vite dev server dentro de Docker | No es apto para producción |
| API expuesta aparte con CORS | Más configuración y superficie de error sin beneficio en el MVP |
| Kubernetes | Desproporcionado para un despliegue local |

---

## Decisiones Relacionadas
- [ADL-001](ADL-001-two-apps-openapi-contract.md): una imagen por app.
- [ADL-003](ADL-003-sqlite-mvp-postgres-path.md): el archivo de SQLite vive en un volumen.
- [ADL-004](ADL-004-react-vite-spa.md): la SPA usa una URL base relativa.

---

## Notas para el AI (Memoria Técnica)
- No habilites CORS abierto en la API: el mismo origen lo hace innecesario.
- En desarrollo, el proxy de Vite reemplaza a nginx; las llamadas siguen yendo a `/api` en el mismo origen.
- El único comando de arranque documentado es `./setup.sh`; no agregues pasos manuales al README.
- Con más de una réplica de la API, saca las migraciones del arranque.
