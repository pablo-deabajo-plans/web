# Gordon BetScanner Pro

Aplicacion web en Streamlit para analisis de partidos de futbol con enfoque trader.

El proyecto combina:
- datos historicos en CSV de `football-data.co.uk`,
- calendario y contexto abierto de partido desde ESPN cuando existe,
- un motor probabilistico basado en simulaciones Poisson,
- comparador de cuota real vs cuota justa,
- calculadora de stake con criterio de Kelly,
- exploracion visual de forma, H2H y senales de mercado.

Este README esta escrito para dos perfiles:
- una persona que necesita entender rapidamente que hace la app y como usarla;
- una IA o agente tecnico que entra al repositorio y necesita contexto especifico para continuar el trabajo sin empezar desde cero.

## 1. Objetivo del proyecto

La app sirve para analizar partidos de futbol y detectar posibles apuestas de valor.

Su objetivo no es solo mostrar probabilidades, sino convertir datos historicos y senales operativas en una pantalla util para:
- scouting de partidos,
- comparacion de equipos,
- lectura de mercados,
- gestion de stake,
- y toma de decision rapida desde movil o escritorio.

## 2. Lo que hace la aplicacion hoy

La version actual permite:
- elegir liga y cargar por defecto los partidos de hoy;
- mostrar una lista visual de partidos en tarjetas;
- abrir el analisis de cualquier partido en una sola pantalla;
- calcular probabilidades para `1X2`, `BTTS`, `Over 2.5`, `Over 9.5 corners`, goles esperados y corners esperados;
- destacar automaticamente eventos calientes cuando el modelo supera el umbral de `value bet`;
- comparar cuota real contra cuota justa;
- calcular stake recomendado con `Full Kelly`, `Half Kelly` y `Quarter Kelly`;
- guardar picks favoritos de manera persistente;
- ver estadisticas generales de cada equipo en `global`, `casa` y `fuera`;
- comparar local en casa vs visitante fuera;
- revisar forma reciente;
- explorar ultimos enfrentamientos directos con detalle del partido historico;
- consultar un feed abierto del partido con mercado y contexto adicional cuando ESPN publica esos datos.

## 3. Como calcula las probabilidades

La app usa un enfoque prepartido basado en historico jugado.

### 3.1 Fuentes principales

- Historico de resultados y estadisticas del partido:
  `https://www.football-data.co.uk/`
- Calendario y contexto abierto adicional:
  ESPN public APIs de soccer scoreboard/summary

### 3.2 Variables que usa el modelo

Para cada equipo se calculan:
- rendimiento global de temporada;
- rendimiento como local;
- rendimiento como visitante;
- goles a favor y en contra;
- corners a favor y en contra;
- forma de los ultimos 5 partidos;
- H2H reciente entre ambos equipos.

### 3.3 Logica del modelo

El motor:
1. filtra el historico a partidos ya jugados;
2. calcula estadisticas globales y segmentadas;
3. construye una estimacion de ataque y defensa para cada lado;
4. ajusta ligeramente por forma reciente;
5. ajusta suavemente por H2H reciente;
6. estima `xG local`, `xG visitante`, `corners local` y `corners visitante`;
7. ejecuta `50.000` simulaciones Poisson;
8. obtiene probabilidades de mercados y marcadores mas frecuentes.

### 3.4 Mercados actuales

La app calcula:
- victoria local;
- empate;
- victoria visitante;
- ambos marcan;
- over 2.5 goles;
- under 2.5 goles;
- over 9.5 corners;
- local +1.5 goles;
- visitante +1.5 goles;
- porteria a cero local;
- porteria a cero visitante;
- marcador mas probable;
- top 3 marcadores mas probables.

### 3.5 Lo que el modelo no hace todavia de forma completa

La app aun no incorpora de forma estable y estructurada:
- alineaciones confirmadas fiables en todas las ligas;
- lesiones y sanciones consistentes por fuente abierta;
- xG real por disparo de cada evento;
- cuotas live consolidadas desde varias casas;
- contexto de arbitro, clima o descanso;
- aprendizaje automatico entrenado sobre historico etiquetado.

Cuando una fuente abierta no trae un dato, la app intenta decirlo claramente en pantalla en vez de inventarlo.

## 4. Flujo de uso para una persona

### 4.1 Buscar un partido

1. Abre la app.
2. Elige la liga.
3. Veras activado por defecto `Partidos de hoy`.
4. Si quieres otro dia, desactiva el toggle y cambia la fecha.
5. Pulsa una tarjeta de partido.
6. El analisis se carga en la misma pantalla.

### 4.2 Leer el analisis

La pantalla principal se interpreta asi:
- `Resumen superior`: partido, marcador mas probable, goles esperados y corners esperados.
- `Senales rapidas`: probabilidades principales del mercado 1X2.
- `Radar instantaneo`: lectura corta del partido.
- `Estadisticas generales`: radiografia de cada equipo.
- `Comparativa equipos`: escenario local en casa vs visitante fuera, forma y H2H.
- `Posibles estadisticas del partido`: proyecciones operativas del cruce.
- `Feed del partido`: datos abiertos adicionales si la fuente los ofrece.
- `Comparador cuota real vs cuota justa`: deteccion de edge y stake.

### 4.3 Usar el comparador de cuotas

1. Introduce la cuota que te ofrece tu casa.
2. La app compara tu cuota con la cuota justa matematica.
3. Si hay ventaja positiva, el panel lo marca como oportunidad mejor que el break-even.
4. Puedes usar Kelly para saber cuanto bankroll arriesgar.

### 4.4 Guardar picks

En la pestaña de cuotas puedes guardar picks favoritos.

Los picks se almacenan en:
- `data/favorite_picks.json`

## 5. Estructura del repositorio

### 5.1 Archivos principales

- `app.py`
  Aplicacion completa de Streamlit. Contiene estilo, logica de datos, modelo, visualizaciones y flujos.

- `requirements.txt`
  Dependencias minimas del proyecto.

- `README.md`
  Documentacion operativa y roadmap.

- `data/favorite_picks.json`
  Persistencia local de favoritos. Puede no existir hasta el primer guardado.

### 5.2 Responsabilidad actual de `app.py`

`app.py` esta centralizado y contiene:
- configuracion de pagina;
- estilos CSS;
- carga de datos;
- normalizacion de nombres;
- integracion de calendario ESPN;
- integracion de resumen ESPN;
- calculo de estadisticas por equipo;
- motor Poisson;
- render de componentes visuales;
- comparador de cuotas;
- Kelly;
- favoritos;
- estado de Streamlit.

Esto funciona, pero a medio plazo conviene dividirlo en modulos.

## 6. Instalacion local

### 6.1 Requisitos

- Python 3.11 o superior recomendado
- pip
- PostgreSQL accesible con las variables `POSTGRES_*`
- secretos cargados via variables de entorno; no se deben hardcodear en el repo

### 6.2 Instalar dependencias

```bash
pip install -r requirements.txt
```

### 6.3 Ejecutar la app

```bash
streamlit run app.py
```

### 6.4 Ejecutar backend local end-to-end

Antes de arrancar backend o Docker, crea un `.env` a partir de `.env.example` y define como minimo:

- `POSTGRES_DB`
- `POSTGRES_USER`
- `POSTGRES_PASSWORD`
- `API_AUTH_KEY`

El proyecto incluye un entrypoint local para backend en Windows PowerShell:

```powershell
.\run-local.ps1 setup
.\run-local.ps1 pipeline
.\run-local.ps1 api
.\run-local.ps1 test
.\run-local.ps1 all
```

`all` hace:
- crear `.venv` si no existe;
- instalar dependencias desde `requirements.local.txt`;
- asegurar el esquema de base de datos;
- ejecutar el pipeline;
- arrancar FastAPI en `127.0.0.1:8000`.

Tambien puedes usar el runner Python directamente:

```bash
python -m backend.tools.local_runner setup
python -m backend.tools.local_runner pipeline
python -m backend.tools.local_runner api --host 127.0.0.1 --port 8000
python -m backend.tools.local_runner test
python -m backend.tools.local_runner all --host 127.0.0.1 --port 8000
```

## 7. Despliegue

### 7.0 Seguridad minima de despliegue

- la API protegida requiere `API_AUTH_KEY`
- el cliente puede enviar la clave por `X-API-Key` o `Authorization: Bearer <API_AUTH_KEY>`
- PostgreSQL no debe publicarse hacia Internet; en Docker queda solo en la red interna
- el mapeo por defecto de la API se limita a `127.0.0.1`

### 7.1 Streamlit Community Cloud

1. Sube el repo a GitHub.
2. Entra en Streamlit Community Cloud.
3. Crea una app nueva.
4. Selecciona el repositorio.
5. Elige `main` como rama.
6. Elige `app.py` como archivo principal.
7. Despliega.

### 7.2 Recomendacion de despliegue actual

Para velocidad y simplicidad:
- usar Streamlit Community Cloud si el proyecto sigue siendo una sola app Streamlit;
- pasar a Render o Docker cuando haya mas fuentes, cache avanzada o servicios auxiliares.

## 8. Guia tecnica para una IA o agente

Esta seccion es intencionalmente especifica.

### 8.1 Que debe entender una IA al entrar al proyecto

Una IA que lea este repositorio debe asumir:
- el proyecto es una app Streamlit de analisis de futbol orientada a trader;
- el archivo principal es `app.py`;
- el motor actual es probabilistico, no ML supervisado;
- la prioridad del producto es UX operativa + utilidad real del analisis;
- el usuario valora mucho que el flujo sea visual, de una sola pantalla y util desde movil;
- no hay backend separado ni API propia por ahora;
- los nombres de equipos pueden venir distintos segun la fuente y deben normalizarse.

### 8.2 Si una IA va a modificar el proyecto, debe respetar estas reglas

- no romper el flujo de una sola pantalla;
- no volver a mover el buscador principal a sidebar;
- no introducir texto visual ambiguo cuando un dato no existe;
- no inventar alineaciones, lesiones o xG si la fuente no los trae;
- mantener el tono de producto trader/profesional;
- preservar compatibilidad movil;
- no eliminar el comparador de cuotas ni Kelly;
- no revertir normalizaciones de nombres ya hechas;
- no introducir cambios destructivos en favoritos.

### 8.3 Prioridades funcionales actuales para una IA

Si un agente tiene que seguir desarrollando, su orden ideal de trabajo es:

1. separar `app.py` en modulos sin romper comportamiento;
2. consolidar una capa de nombres visuales para todos los equipos;
3. conectar cuotas live automaticas al comparador cuando existan;
4. mejorar la trazabilidad del modelo;
5. incorporar mejores fuentes de alineaciones y bajas;
6. crear ranking automatico de mejores picks del dia.

### 8.4 Modulos recomendados para una futura refactorizacion

Si una IA refactoriza, la estructura sugerida es:

- `app.py`
  Orquestacion Streamlit y layout principal.

- `core/model.py`
  Motor Poisson, cuotas justas, Kelly y construccion de mercados.

- `core/stats.py`
  Estadisticas por equipo, forma, H2H, segmentos casa/fuera/global.

- `data/sources.py`
  Descarga de CSV, ESPN scoreboard/summary, cache y parsing.

- `data/teams.py`
  Normalizacion, alias y nombres visuales.

- `ui/components.py`
  Tarjetas, paneles, render de H2H, radar, comparador y estilos.

- `storage/favorites.py`
  Persistencia local de picks favoritos.

### 8.5 Cambios peligrosos o delicados

Una IA debe tener cuidado especial con:
- la logica de deduplicacion entre CSV y ESPN;
- la fecha local `Europe/Madrid`;
- la conversion de nombres `Real Sociedad II -> Real Sociedad B / Sociedad B`;
- el uso de `st.session_state`;
- el render mixto HTML + widgets de Streamlit;
- los datos opcionales de columnas CSV como tiros, corners o tarjetas;
- los feeds abiertos que no son consistentes entre competiciones.

## 9. Limitaciones actuales

- `app.py` es grande y aun no esta modularizado.
- Las fuentes abiertas no siempre publican todos los datos.
- Algunas ligas o jornadas tardan en actualizarse en los CSV.
- ESPN puede ofrecer calendario pero no siempre lineup/injuries/xG.
- El modelo usa una heuristica razonable, pero no un modelo calibrado con backtesting formal.

## 10. Lista priorizada de mejoras recomendadas

### Prioridad alta

1. Modularizar `app.py` en capas `data`, `core`, `ui` y `storage`.
2. Unificar nombres visuales en toda la app para que nunca aparezcan variantes mezcladas.
3. Conectar cuotas abiertas reales al comparador y autocompletar el panel cuando existan.
4. Anadir trazabilidad del modelo mercado a mercado:
   mostrar que peso viene de temporada, casa/fuera, forma y H2H.
5. Crear ranking de mejores value bets del dia por liga.

### Prioridad media

6. Anadir selector `Hoy / Manana / Fin de semana`.
7. Incluir filtros por mercado:
   `1X2`, `BTTS`, `Over`, `Corners`, `Kelly positivo`.
8. Mejorar la lectura del feed del partido con una capa de `disponible / no disponible / pendiente`.
9. Guardar historial de picks con resultado final y ROI.
10. Anadir exportacion a CSV o PDF del analisis.

### Prioridad media-alta de datos

11. Integrar una fuente mas robusta de alineaciones confirmadas y probables.
12. Integrar una fuente fiable de lesiones y sanciones.
13. Integrar xG por disparo o shot map real donde sea posible.
14. Anadir tabla de clasificacion y contexto de temporada desde fuente externa.
15. Introducir backtesting del modelo por liga y mercado.

### Prioridad UX

16. Sustituir algunos `dataframe` por tarjetas comparativas visuales.
17. Crear un `modo movil` con bloques aun mas compactos.
18. Mejorar la pagina inicial con KPIs del dia antes de elegir partido.
19. Anadir semaforos visuales de confianza por mercado.
20. Permitir compartir un partido por URL con parametros.

### Prioridad avanzada

21. Cache inteligente por liga y fecha para reducir llamadas.
22. Tests automaticos para normalizacion de nombres y motor estadistico.
23. Separar configuracion de ligas y aliases en archivos propios.
24. Crear una API interna o capa de servicios si el proyecto crece.
25. Incorporar calibracion estadistica del modelo con validacion historica.

## 11. Roadmap recomendado

### Fase 1: Producto robusto

- modularizacion minima;
- nombres unificados;
- autocompletado de cuotas abiertas;
- ranking de picks del dia;
- historial de picks.

### Fase 2: Calidad de dato

- alineaciones;
- bajas;
- xG por disparo;
- contexto de clasificacion y racha ampliada;
- mejoras de trazabilidad.

### Fase 3: Escalado

- tests;
- arquitectura modular;
- backend ligero si hace falta;
- multiusuario o persistencia remota;
- analitica de rendimiento del modelo.

## 12. Notas finales

El proyecto ya tiene una base fuerte de producto:
- flujo visual claro;
- enfoque trader real;
- una sola pantalla;
- y utilidad inmediata para scouting.

El salto de nivel ahora no pasa tanto por meter mas widgets, sino por:
- mejorar calidad y coherencia de datos;
- hacer el modelo mas explicable;
- y convertir la app en una herramienta diaria de decision con ranking, seguimiento y backtesting.
