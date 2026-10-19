#!/usr/bin/env bash
# Levanta DroiDesk completo con Docker: configura .env, construye las imágenes y arranca el stack.
set -euo pipefail

readonly ENV_FILE=".env"
readonly DEFAULT_WEB_PORT=8080
readonly DEFAULT_TIMEZONE="America/Santiago"
readonly DEFAULT_BUSINESS_HOURS="09:00-18:00"
readonly DEFAULT_MODE="demo"
readonly DEFAULT_PROJECT_NAME="droidesk"
readonly ZONEINFO_DIR="/usr/share/zoneinfo"
readonly WAIT_TIMEOUT_SECONDS=180
readonly LOG_TAIL_LINES=30

assume_yes=false
answer=""
reply=""

usage() {
  cat <<'EOF'
Uso: ./setup.sh [--yes] [--help]

Levanta DroiDesk con Docker en un solo comando: valida Docker, genera el archivo .env
(con un secreto aleatorio), construye las imágenes y espera a que todo esté sano.

Opciones:
  -y, --yes   Modo no interactivo: no hace preguntas, usa los valores por defecto o los de
              las variables de entorno, y reutiliza .env si ya existe.
  -h, --help  Muestra esta ayuda.

Variables de entorno (valor por defecto de cada pregunta, o su valor en modo --yes):
  DROIDESK_WEB_PORT          Puerto de la web en este equipo (8080).
  DROIDESK_TIMEZONE          Zona horaria IANA de la jornada (America/Santiago).
  DROIDESK_BUSINESS_HOURS    Jornada laboral HH:MM-HH:MM (09:00-18:00).
  DROIDESK_MODE              demo o empty: si se cargan tickets de ejemplo (demo).
                             demo: usuarios y tickets de ejemplo; empty: solo los usuarios.
  COMPOSE_PROJECT_NAME       Cambia el nombre del proyecto de Docker Compose (droidesk).

Para bajar el stack: docker compose down. Para borrar también los datos: docker compose down -v.
EOF
}

info() { printf '%s\n' "$*"; }
warn() { printf 'Aviso: %s\n' "$*" >&2; }
fail() {
  printf 'Error: %s\n' "$*" >&2
  exit 1
}

lowercase() { printf '%s' "$1" | tr '[:upper:]' '[:lower:]'; }

parse_args() {
  local arg
  for arg in "$@"; do
    case $arg in
      -y | --yes) assume_yes=true ;;
      -h | --help)
        usage
        exit 0
        ;;
      *) fail "Opción desconocida: $arg. Usa --help para ver las opciones." ;;
    esac
  done
}

require_docker() {
  command -v docker >/dev/null 2>&1 ||
    fail "No encontré Docker. Instala Docker Engine o Docker Desktop: https://docs.docker.com/get-docker/"
  docker info >/dev/null 2>&1 ||
    fail "El daemon de Docker no responde. Inicia Docker (o Docker Desktop) y revisa que tu usuario tenga permiso para usarlo."
  docker compose version >/dev/null 2>&1 ||
    fail "Falta Docker Compose v2 (el comando 'docker compose'). Instálalo: https://docs.docker.com/compose/install/"
}

port_in_use() { (exec 3<>"/dev/tcp/127.0.0.1/$1") 2>/dev/null; }

# Los validadores explican el motivo por stderr y devuelven distinto de cero si el valor no sirve.
validate_port() {
  local shape='^[1-9][0-9]{0,4}$'
  if [[ ! $1 =~ $shape ]] || [ "$1" -gt 65535 ]; then
    warn "El puerto debe ser un número entre 1 y 65535."
    return 1
  fi
  if port_in_use "$1"; then
    warn "El puerto $1 ya está en uso en este equipo."
    return 1
  fi
}

validate_timezone() {
  local name_shape='^[A-Za-z][A-Za-z0-9_+-]*(/[A-Za-z0-9_+-]+)*$'
  if [[ ! $1 =~ $name_shape ]]; then
    warn "La zona horaria debe tener el formato IANA, por ejemplo America/Santiago."
    return 1
  fi
  if [ -d "$ZONEINFO_DIR" ] && [ ! -f "$ZONEINFO_DIR/$1" ]; then
    warn "No existe la zona horaria '$1'."
    return 1
  fi
}

is_clock_time() { [ "$((10#$1))" -le 23 ] && [ "$((10#$2))" -le 59 ]; }

validate_business_hours() {
  local shape='^([0-9]{2}):([0-9]{2})-([0-9]{2}):([0-9]{2})$'
  if [[ ! $1 =~ $shape ]]; then
    warn "La jornada debe tener el formato HH:MM-HH:MM, por ejemplo 09:00-18:00."
    return 1
  fi
  local open_hour=${BASH_REMATCH[1]} open_minute=${BASH_REMATCH[2]}
  local close_hour=${BASH_REMATCH[3]} close_minute=${BASH_REMATCH[4]}
  if ! is_clock_time "$open_hour" "$open_minute" || ! is_clock_time "$close_hour" "$close_minute"; then
    warn "Las horas van de 00 a 23 y los minutos de 00 a 59."
    return 1
  fi
  if [ "$((10#$open_hour * 60 + 10#$open_minute))" -ge "$((10#$close_hour * 60 + 10#$close_minute))" ]; then
    warn "La apertura debe ser anterior al cierre."
    return 1
  fi
}

validate_mode() {
  if [ "$1" != demo ] && [ "$1" != empty ]; then
    warn "DROIDESK_MODE debe ser demo o empty."
    return 1
  fi
}

read_answer() {
  read -r answer || fail "No hay más respuestas disponibles; ejecuta ./setup.sh en una terminal o usa --yes."
}

# Pregunta con valor por defecto y repregunta hasta que el validador lo acepte. El resultado queda en $reply.
ask_setting() {
  local label=$1 default=$2 validator=$3
  if [ "$assume_yes" = true ]; then
    reply=$default
    "$validator" "$reply" || fail "El valor de '$label' no es válido en modo --yes; corrígelo con su variable de entorno."
    return
  fi
  while true; do
    printf '%s [%s]: ' "$label" "$default"
    read_answer
    reply=${answer:-$default}
    "$validator" "$reply" && return
  done
}

# Pregunta sí/no; el resultado queda en $reply como true o false.
ask_yes_no() {
  local question=$1 default=$2 hint="S/n"
  [ "$default" = true ] || hint="s/N"
  while true; do
    printf '%s [%s]: ' "$question" "$hint"
    read_answer
    case $(lowercase "$answer") in
      "") reply=$default; return ;;
      s | si | sí | y | yes) reply=true; return ;;
      n | no) reply=false; return ;;
      *) warn "Responde S o n." ;;
    esac
  done
}

# Traduce lo que escribió la persona (número o nombre del modo) a demo o empty; falla si no lo reconoce.
mode_from_answer() {
  # vacÍo va con la Í mayúscula: tr opera por bytes y no la pasa a minúscula.
  case $(lowercase "$1") in
    1 | demo) printf 'demo' ;;
    2 | vacio | vacío | vacÍo | empty) printf 'empty' ;;
    *) return 1 ;;
  esac
}

# Explica los modos y pregunta cuál usar; el resultado queda en $reply como demo o empty.
ask_mode() {
  local default=$1 default_choice=1
  [ "$default" = empty ] && default_choice=2
  if [ "$assume_yes" = true ]; then
    reply=$default
    return
  fi
  info "Modo de arranque:"
  info "  1) Demo: usuarios y tickets de ejemplo en distintos estados, con comentarios e historial, para recorrer las funcionalidades."
  info "  2) Vacío: solo los usuarios de demo, sin tickets, para empezar de cero."
  while true; do
    printf 'Elige un modo [%s]: ' "$default_choice"
    read_answer
    reply=$(mode_from_answer "${answer:-$default_choice}") && return
    warn "Responde 1 (Demo) o 2 (Vacío)."
  done
}

generate_secret() {
  if command -v openssl >/dev/null 2>&1; then
    openssl rand -hex 32
  else
    od -An -N32 -tx1 /dev/urandom | tr -d ' \n'
  fi
}

env_value() { sed -n "s/^$1=//p" "$ENV_FILE" | tail -n 1; }

write_env_file() {
  local web_port=$1 timezone=$2 business_hours=$3 mode=$4
  (
    umask 077
    cat >"$ENV_FILE" <<EOF
# Generado por setup.sh. No lo versiones: contiene el secreto de los JWT.
DROIDESK_JWT_SECRET=$(generate_secret)
DROIDESK_DATABASE_URL=sqlite:////data/droidesk.db
DROIDESK_MODE=$mode
DROIDESK_TIMEZONE=$timezone
DROIDESK_BUSINESS_HOURS=$business_hours
DROIDESK_WEB_PORT=$web_port
EOF
  )
  chmod 600 "$ENV_FILE"
}

wants_to_reuse_env() {
  [ -f "$ENV_FILE" ] || return 1
  [ "$assume_yes" = true ] && return 0
  ask_yes_no "Ya existe un archivo $ENV_FILE. ¿Quieres reutilizarlo?" true
  [ "$reply" = true ]
}

announce_setup() {
  if [ "$assume_yes" = true ]; then
    info "Bip-bup. Modo --yes: configuro DroiDesk con los valores por defecto o los de tu entorno."
  else
    info "Bip-bup. Voy a configurar DroiDesk; presiona Enter para aceptar el valor entre corchetes."
  fi
}

create_env_file() {
  announce_setup
  local default_mode=${DROIDESK_MODE:-$DEFAULT_MODE}
  validate_mode "$default_mode" || exit 1
  ask_setting "Puerto de la web" "${DROIDESK_WEB_PORT:-$DEFAULT_WEB_PORT}" validate_port
  local web_port=$reply
  ask_setting "Zona horaria" "${DROIDESK_TIMEZONE:-$DEFAULT_TIMEZONE}" validate_timezone
  local timezone=$reply
  ask_setting "Jornada laboral (HH:MM-HH:MM)" "${DROIDESK_BUSINESS_HOURS:-$DEFAULT_BUSINESS_HOURS}" validate_business_hours
  local business_hours=$reply

  ask_mode "$default_mode"
  local mode=$reply

  write_env_file "$web_port" "$timezone" "$business_hours" "$mode"
  info "Escribí $ENV_FILE con permisos 600 y un secreto aleatorio que no se muestra."
}

# Cambiar de modo no borra datos: los tickets de ejemplo se cargan solo mientras no exista ningún ticket.
warn_if_database_exists() {
  local volume="${COMPOSE_PROJECT_NAME:-$DEFAULT_PROJECT_NAME}_data"
  docker volume inspect "$volume" >/dev/null 2>&1 || return 0
  warn "Ya existe la base de datos de este proyecto (volumen $volume) y conserva sus datos. Para empezar de cero con otro modo, ejecuta 'docker compose down -v' y vuelve a ejecutar ./setup.sh."
}

prepare_env_file() {
  if wants_to_reuse_env; then
    info "Reutilizo el archivo $ENV_FILE existente."
  else
    create_env_file
  fi
  # Compose da prioridad a la variable de entorno sobre .env: se alinea con lo que quedó escrito.
  local web_port
  web_port=$(env_value DROIDESK_WEB_PORT)
  export DROIDESK_WEB_PORT=${web_port:-$DEFAULT_WEB_PORT}
}

start_stack() {
  info "Construyendo y levantando los contenedores (la primera vez puede tardar unos minutos)..."
  if ! docker compose up -d --build --wait --wait-timeout "$WAIT_TIMEOUT_SECONDS"; then
    warn "El stack no quedó sano. Últimas líneas del log de la API:"
    docker compose logs --tail "$LOG_TAIL_LINES" api >&2 || true
    fail "No pude levantar DroiDesk. Corrige el problema y vuelve a ejecutar ./setup.sh."
  fi
}

list_demo_users() {
  docker compose exec -T api python - <<'PY'
import json
import urllib.request

PROFILES = {"requester": "Solicitante", "agent": "Agente"}

with urllib.request.urlopen("http://127.0.0.1:8000/api/v1/auth/users", timeout=5) as response:
    users = json.load(response)

print(f"  {'Usuario':<18}{'Nombre':<20}Perfil")
for user in users:
    print(f"  {user['username']:<18}{user['name']:<20}{PROFILES.get(user['role'], user['role'])}")
PY
}

# Un .env anterior a los modos no trae DROIDESK_MODE (valor vacío): la API arranca en demo.
print_mode() {
  local mode
  mode=$(env_value DROIDESK_MODE)
  case $mode in
    demo | "") info "Modo: Demo (usuarios y tickets de ejemplo)" ;;
    empty) info "Modo: Vacío (solo usuarios)" ;;
    *) info "Modo: $mode" ;;
  esac
}

print_summary() {
  info ""
  info "DroiDesk está listo: http://localhost:$DROIDESK_WEB_PORT"
  print_mode
  info ""
  info "Usuarios de demo:"
  list_demo_users || warn "No pude consultar la lista de usuarios a la API."
  info ""
  info "La contraseña puede ser cualquiera: el ingreso es simulado."
  info "En la pantalla de ingreso, el botón \"?\" también lista estos usuarios."
  info ""
  info "Para bajar el stack: docker compose down"
  info "Para bajarlo y borrar los datos: docker compose down -v"
}

main() {
  parse_args "$@"
  cd "$(dirname "${BASH_SOURCE[0]}")"
  require_docker
  prepare_env_file
  warn_if_database_exists
  start_stack
  print_summary
}

main "$@"
