# Migraciones de base de datos (Alembic)

## Schemas activos

| Schema | Archivo origen | Propósito |
|--------|---------------|-----------|
| `public` | `schema.sql` | Esquema operacional legacy (tablas de producción actuales) |
| `app` | `domain_schemas.sql` | Capa de aplicación (users, sessions, favorites) |
| `sports` | `domain_schemas.sql` | Modelo de dominio deportivo (leagues, teams, matches, odds) |
| `model` | `domain_schemas.sql` | Pipeline ML (features, predictions, backtests) |

## Convención

- Cada migración afecta un único schema.
- Nombrar con prefijo del schema: `add_sports_player_index`, `alter_public_picks_add_column`.
- Las migraciones deben incluir `downgrade()`.

## Comandos habituales

```bash
# Crear nueva migración vacía
alembic revision -m "descripcion_corta"

# Autogenerar desde modelos SQLAlchemy (si se añaden en el futuro)
alembic revision --autogenerate -m "descripcion_corta"

# Aplicar todas las migraciones pendientes
alembic upgrade head

# Ver estado actual
alembic current

# Revertir última migración
alembic downgrade -1
```

Ejecutar desde el directorio `backend/` donde está `alembic.ini`.
