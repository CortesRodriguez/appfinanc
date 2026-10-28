#!/usr/bin/env bash
# Crea el backlog Scrum en GitHub: campos del Project, un issue por CU y sus valores.
#
# Uso (desde la raiz del repo):
#   CONFIRM=si SPRINTS="1" bash scripts/crear_backlog_github.sh      # solo Sprint 1 (prueba)
#   CONFIRM=si SPRINTS="1 2 3 4" bash scripts/crear_backlog_github.sh # todos
#
# Requisitos: gh con login y permisos repo + project. El Project y las etiquetas
# sprint-1..4 ya existen. No es idempotente para los issues: si lo corres dos veces
# sobre el mismo sprint, duplica sus issues. Corre cada sprint una sola vez.

set -u
GH=/opt/homebrew/bin/gh
OWNER=CortesRodriguez
REPO=CortesRodriguez/appfinanc
PROJECT=2
HH_TOTAL=155
SPRINTS="${SPRINTS:-1}"

if [ "${CONFIRM:-}" != "si" ]; then
  echo "Esto crea issues en $REPO (repositorio publico) y los agrega al Project $PROJECT."
  echo "Para continuar: CONFIRM=si SPRINTS=\"1\" bash $0"
  exit 1
fi

# RF|CU|Titulo|Sprint|Estado|Inicio|Fin|HH estimadas|HH reales|Avance|Observacion
ROWS='RF-01.1|CU-01|Seleccionando instrumento y rango temporal|1|Done|2026-07-21|2026-08-03|5|5|100|
RF-02.1|CU-02|Consultando los indicadores de un instrumento|1|Done|2026-07-21|2026-08-03|8|8|100|
RF-02.2|CU-03|Visualizando historial de visitas a instrumentos|1|Done|2026-07-21|2026-08-03|4|4|100|
RF-02.3|CU-04|Consultando el contexto macroeconómico nacional|1|Done|2026-07-21|2026-08-03|5|5|100|
RF-03.1|CU-05|Reutilizando datos recientes desde la caché|1|Done|2026-07-21|2026-08-03|5|2|100|
RF-03.2|CU-06|Cambiando el tipo de gráfico|1|Done|2026-07-21|2026-08-03|4|4|100|
RF-03.3|CU-07|Visualizando los indicadores en la barra lateral|1|Done|2026-07-21|2026-08-03|5|1|100|
RF-06.1|CU-12|Visualizando el nivel de riesgo del indicador|1|Done|2026-07-21|2026-08-03|6|6|100|
RF-07.1|CU-14|Accediendo a la interfaz web del sistema|2|Done|2026-08-04|2026-08-17|4|4|100|
RF-07.2|CU-15|Visualizando en el gráfico el indicador seleccionado|2|Done|2026-08-04|2026-08-17|4|4|100|
RF-07.3|CU-16|Visualizando la cinta de precios|2|Done|2026-08-04|2026-08-17|5|5|100|
RF-07.4|CU-17|Consultando el detalle de la cinta de precios|2|Done|2026-08-04|2026-08-17|6|6|100|
RF-08.1|CU-18|Mostrando el valor original junto a la explicación|2|Done|2026-08-04|2026-08-17|3|3|100|
RF-08.2|CU-19|Mostrando la etiqueta de riesgo|2|Done|2026-08-04|2026-08-17|4|4|100|
RF-08.3|CU-20|Mostrando el indicador de carga|2|Done|2026-08-04|2026-08-17|3|1|100|
RF-09.1|CU-21|Presentando un mensaje de carga/error|2|Done|2026-08-04|2026-08-17|4|2|100|
RF-09.2|CU-22|Consultando el glosario de términos financieros|2|Done|2026-08-04|2026-08-17|5|5|100|
RF-10.1|CU-23|Visualizando el historial de consultas|2|Done|2026-08-04|2026-08-17|4|4|100|
RF-04.1|CU-08|Visualizando información de un indicador|3|Done|2026-08-18|2026-08-31|8|2|100|mejorar la explicación
RF-04.2|CU-09|Visualizando la explicación generada coherente con el dato real|3|Done|2026-08-18|2026-08-31|6|3|100|
RF-05.1|CU-10|Visualizando una explicación en lenguaje natural del indicador|3|Done|2026-08-18|2026-08-31|6|6|100|
RF-05.2|CU-11|Visualizando explicaciones adaptadas a su nivel|3|In Progress|2026-08-18|2026-08-31|5|5|50|
RF-06.2|CU-13|Solicitando la regeneración de una explicación|3|Done|2026-08-18|2026-08-31|5|3|100|
RF-11.1|CU-24|Registrando cuenta de usuario|4|Done|2026-09-01|2026-09-10|6|6|100|
RF-12.1|CU-25|Iniciando y cerrando sesión|4|Done|2026-09-01|2026-10-23|6|6|100|
RF-13.1|CU-26|Recuperando el perfil de aprendizaje|4|Done|2026-09-01|2026-10-23|5|5|100|
RF-13.2|CU-27|Ajustando explicaciones según el perfil|4|Done|2026-09-01|2026-10-23|4|4|100|
RF-14.1|CU-28|Visualizando el indicador más regenerado|4|Done|2026-09-01|2026-10-23|4|4|100|
RF-14.2|CU-29|Visualizando los instrumentos más consultados|4|Done|2026-09-01|2026-10-23|4|4|100|
RF-14.3|CU-30|Visualizando el total de consultas realizadas|4|Done|2026-09-01|2026-10-23|3|3|100|
RF-14.4|CU-31|Presentando la explicación del indicador más difícil|4|Done|2026-09-01|2026-10-23|4|4|100|
RF-14.5|CU-32|Reutilizando la última explicación generada|4|Done|2026-09-01|2026-10-23|5|5|100|'

echo "== Campos del Project =="
# Si un campo ya existe, gh avisa y se sigue.
$GH project field-create $PROJECT --owner $OWNER --name "RF/CU" --data-type TEXT >/dev/null 2>&1
$GH project field-create $PROJECT --owner $OWNER --name "Sprint" --data-type SINGLE_SELECT \
  --single-select-options "Sprint 1,Sprint 2,Sprint 3,Sprint 4" >/dev/null 2>&1
$GH project field-create $PROJECT --owner $OWNER --name "Inicio Est." --data-type DATE >/dev/null 2>&1
$GH project field-create $PROJECT --owner $OWNER --name "Fin Est." --data-type DATE >/dev/null 2>&1
$GH project field-create $PROJECT --owner $OWNER --name "HH estimadas" --data-type NUMBER >/dev/null 2>&1
$GH project field-create $PROJECT --owner $OWNER --name "HH reales" --data-type NUMBER >/dev/null 2>&1
$GH project field-create $PROJECT --owner $OWNER --name "% Aporte" --data-type NUMBER >/dev/null 2>&1
$GH project field-create $PROJECT --owner $OWNER --name "Avance %" --data-type NUMBER >/dev/null 2>&1
$GH project field-create $PROJECT --owner $OWNER --name "Observación" --data-type TEXT >/dev/null 2>&1
$GH project link $PROJECT --owner $OWNER --repo $REPO >/dev/null 2>&1

PID=$($GH project view $PROJECT --owner $OWNER --format json --jq .id)
FIELDS=$($GH project field-list $PROJECT --owner $OWNER --format json)
fid()  { echo "$FIELDS" | python3 -c "import sys,json; n=sys.argv[1]; print(next(f['id'] for f in json.load(sys.stdin)['fields'] if f['name']==n))" "$1"; }
opt()  { echo "$FIELDS" | python3 -c "import sys,json; f,o=sys.argv[1:3]; print(next(x['id'] for fl in json.load(sys.stdin)['fields'] if fl['name']==f for x in fl['options'] if x['name']==o))" "$1" "$2"; }

F_RFCU=$(fid "RF/CU"); F_SPRINT=$(fid "Sprint"); F_INI=$(fid "Inicio Est."); F_FIN=$(fid "Fin Est.")
F_HHE=$(fid "HH estimadas"); F_HHR=$(fid "HH reales"); F_APO=$(fid "% Aporte"); F_AVA=$(fid "Avance %")
F_OBS=$(fid "Observación"); F_STATUS=$(fid "Status")

for v in "$PID" "$F_RFCU" "$F_SPRINT" "$F_INI" "$F_FIN" "$F_HHE" "$F_HHR" "$F_APO" "$F_AVA" "$F_OBS" "$F_STATUS"; do
  [ -n "$v" ] || { echo "No se pudo leer un campo del Project. Abortando antes de crear issues."; exit 1; }
done

echo "== Issues (sprints: $SPRINTS) =="
echo "$ROWS" | while IFS='|' read -r RF CU TITULO SPR ESTADO INI FIN HHE HHR AVA OBS; do
  case " $SPRINTS " in *" $SPR "*) ;; *) continue ;; esac

  APORTE=$(awk -v h="$HHE" -v t="$HH_TOTAL" 'BEGIN{printf "%.2f", h/t*100}')
  BODY="**RF:** $RF
**CU:** $CU
**Sprint:** $SPR ($INI a $FIN)
**HH estimadas:** $HHE · **HH reales:** $HHR
**Avance:** $AVA %
**Observación:** ${OBS:--}"

  URL=$($GH issue create -R $REPO --title "$CU · $TITULO" --body "$BODY" \
        --label "sprint-$SPR" --assignee $OWNER 2>&1 | tail -1)
  case "$URL" in https://*) ;; *) echo "FALLO al crear $CU: $URL"; continue ;; esac

  ITEM=$($GH project item-add $PROJECT --owner $OWNER --url "$URL" --format json --jq .id)
  ed() { $GH project item-edit --id "$ITEM" --project-id "$PID" --field-id "$1" "${@:2}" >/dev/null; }

  ed "$F_RFCU"   --text "$RF / $CU"
  ed "$F_SPRINT" --single-select-option-id "$(opt Sprint "Sprint $SPR")"
  ed "$F_INI"    --date "$INI"
  ed "$F_FIN"    --date "$FIN"
  ed "$F_HHE"    --number "$HHE"
  ed "$F_HHR"    --number "$HHR"
  ed "$F_APO"    --number "$APORTE"
  ed "$F_AVA"    --number "$AVA"
  [ -n "$OBS" ] && ed "$F_OBS" --text "$OBS"
  ed "$F_STATUS" --single-select-option-id "$(opt Status "$ESTADO")"

  if [ "$ESTADO" = "Done" ]; then
    $GH issue close "$URL" --reason completed >/dev/null 2>&1
  fi
  echo "OK  $CU  $URL"
done
echo "Listo. Revisa: https://github.com/users/$OWNER/projects/$PROJECT"
