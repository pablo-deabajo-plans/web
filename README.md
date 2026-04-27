# Gordon BetScanner

Aplicacion web de analisis de futbol orientada a lectura operativa de partidos, value bets y seguimiento diario de ligas.

La version activa del producto se sirve desde FastAPI y se despliega en Render. El frontend Streamlit legacy se ha retirado del flujo productivo para evitar drift de UX y deuda de mantenimiento.

## Estado actual

- runtime productivo: `backend/app/main.py`
- UI web server-side: `backend/app/web/`
- API protegida: `backend/app/api/`
- pipeline embebido en el servicio web de Render
- persistencia principal: PostgreSQL

## Objetivo

La web esta pensada para responder tres preguntas rapido:

1. que ligas y partidos merecen atencion hoy
2. donde existe ventaja de precio real frente a la cuota justa del modelo
3. con que nivel de confianza y contexto se sostiene esa lectura

## Arquitectura activa

```text
backend/
  app/
    api/
    core/
    domain/
    repositories/
    schemas/
    services/
    web/
    main.py
  workers/
render.yaml
requirements.local.txt
run-local.ps1
```

## Flujo productivo

- `/`
  hub diario de ligas activas
- `/league/{league}`
  vista dedicada por liga
- `/daily-value`
  ranking diario de value bets persistidas
- `/match-detail/{match_id}`
  detalle de partido
- `/health`
  healthcheck

## Principios actuales

- las vistas de valor solo muestran cuotas externas reales almacenadas
- la home y la vista de liga leen datos persistidos y ligeros
- el detalle de partido prioriza estabilidad y evita llamadas externas no esenciales en request-time
- no se mezclan varias arquitecturas de frontend en produccion

## Arranque local

### Requisitos

- Python 3.11 o superior
- PostgreSQL accesible con variables `POSTGRES_*`
- `API_AUTH_KEY`

### Setup

```powershell
.\run-local.ps1 setup
```

### Ejecutar pipeline local

```powershell
.\run-local.ps1 pipeline
```

### Ejecutar web/API local

```powershell
.\run-local.ps1 api
```

### Ejecutar todo

```powershell
.\run-local.ps1 all
```

Tambien puedes usar el runner Python:

```bash
python -m backend.tools.local_runner setup
python -m backend.tools.local_runner pipeline
python -m backend.tools.local_runner api --host 127.0.0.1 --port 8000
python -m backend.tools.local_runner test
python -m backend.tools.local_runner all --host 127.0.0.1 --port 8000
```

## Dependencias locales

Instalacion minima:

```bash
pip install -r backend/requirements.txt
```

Setup local completo:

```bash
pip install -r requirements.local.txt
```

## Despliegue

El blueprint de Render vive en [render.yaml](C:/Users/pablo/Documents/Gordon%20BetScanner/render.yaml).

Reglas actuales:

- un solo servicio web productivo
- scheduler embebido activado en ese servicio
- `autoDeploy` habilitado para la rama `main`
- PostgreSQL externo a la app pero conectado por variables `POSTGRES_*`

## Calidad y deuda tecnica

Las prioridades antes de seguir metiendo features son:

1. mantener una sola via de despliegue y pipeline
2. seguir eliminando request-time work evitable
3. alinear todas las vistas con datos persistidos coherentes
4. reducir residuos legacy y artefactos de codificacion
5. reforzar pruebas de rutas web y servicios criticos

## Notas

- El archivo `lo que tienes que hacer.txt` es una lista de trabajo manual y no debe versionarse.
- Si se toca codigo productivo, el cierre correcto es: verificar, commit, push y comprobar deploy en Render.
