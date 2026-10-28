#!/usr/bin/env python3
"""Agrega al Project de GitHub las columnas de corte y el avance por sprint.

Uso (desde la raiz del repo):
  python3 scripts/agregar_cortes_github.py              # prueba: solo muestra, no escribe
  CONFIRM=si python3 scripts/agregar_cortes_github.py   # aplica los cambios

Hace tres cosas:
  1. Crea los campos de seleccion "Estado Inicial", "Corte 18/08", "Corte 01/09" y
     "Corte 70%" (Pendiente / En proceso / Finalizado) si no existen.
  2. Rellena esos campos para cada item del Project, DERIVANDO el estado de las
     fechas (ver abajo). Tu Excel no trae el estado real en cada corte.
  3. Escribe en el README del Project el avance por sprint y el global.

Regla de los cortes: un CU esta "Finalizado" en un corte si su estado final es Done
y su Fin Est. es anterior o igual a la fecha del corte. Si su estado final no es Done
y ya empezo, queda "En proceso"; si no, "Pendiente".
  - Corte 18/08  -> 2026-08-18
  - Corte 01/09  -> 2026-09-01
  - Corte 70%    -> fecha en que las HH estimadas acumuladas llegan a >= 70% del total
                    (con tus datos, el cierre del Sprint 3: 31-ago). Es una definicion
                    mia: ajustala si tu profesor usa otra.
Corre este script DESPUES de crear los 4 sprints con crear_backlog_github.sh.
"""

import json
import os
import subprocess
import sys
from datetime import date

GH = "/opt/homebrew/bin/gh"
OWNER = "CortesRodriguez"
PROJECT = "2"
OPCIONES = "Pendiente,En proceso,Finalizado"
CAMPOS_CORTE = ["Estado Inicial", "Corte 18/08", "Corte 01/09", "Corte 70%"]
APPLY = os.environ.get("CONFIRM") == "si"


def gh(*args):
    r = subprocess.run([GH, *args], capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"gh {' '.join(args)}\n{r.stderr.strip()}")
    return r.stdout


def leer():
    campos = json.loads(gh("project", "field-list", PROJECT, "--owner", OWNER, "--format", "json"))["fields"]
    items = json.loads(gh("project", "item-list", PROJECT, "--owner", OWNER, "--format", "json", "--limit", "200"))["items"]
    return campos, items


def main():
    campos, items = leer()
    por_nombre = {c["name"]: c for c in campos}
    if not items:
        sys.exit("El Project no tiene items. Corre antes crear_backlog_github.sh.")

    filas = []
    for it in items:
        fin = it.get("fin Est.")
        if not fin:
            print(f"Aviso: '{it.get('title')}' no tiene Fin Est.; se omite.")
            continue
        filas.append({
            "id": it["id"],
            "titulo": it["title"],
            "sprint": it.get("sprint", ""),
            "done": it.get("status") == "Done",
            "fin": date.fromisoformat(fin),
            "hh": float(it.get("hH estimadas") or 0),
            "avance": float(it.get("avance %") or 0),
        })

    # Fecha del corte 70 %: primer fin de sprint donde las HH estimadas acumuladas >= 70 %.
    total_hh = sum(f["hh"] for f in filas)
    acumulado = 0.0
    corte70 = None
    for fin in sorted({f["fin"] for f in filas}):
        acumulado += sum(f["hh"] for f in filas if f["fin"] == fin)
        if total_hh and acumulado / total_hh >= 0.70:
            corte70 = fin
            break
    cortes = {
        "Corte 18/08": date(2026, 8, 18),
        "Corte 01/09": date(2026, 9, 1),
        "Corte 70%": corte70,
    }
    print(f"Items: {len(filas)} | HH estimadas: {total_hh:g} | fecha Corte 70%: {corte70}")
    if len(filas) < 32:
        # Con items de menos, el 70 % se calcularia sobre un total equivocado.
        aviso = (f"hay {len(filas)} de 32 items; el Corte 70% y el avance global saldrian mal. "
                 "Crea antes los 4 sprints con crear_backlog_github.sh.")
        if APPLY:
            sys.exit("Abortado: " + aviso)
        print("ATENCION: " + aviso)

    def estado(f, corte):
        if f["done"] and f["fin"] <= corte:
            return "Finalizado"
        return "En proceso" if not f["done"] else "Pendiente"

    # 1) Crear campos que falten
    for nombre in CAMPOS_CORTE:
        if nombre in por_nombre:
            continue
        print(f"{'Crea' if APPLY else 'Crearia'} campo: {nombre}")
        if APPLY:
            gh("project", "field-create", PROJECT, "--owner", OWNER, "--name", nombre,
               "--data-type", "SINGLE_SELECT", "--single-select-options", OPCIONES)
    if APPLY:
        campos, _ = leer()
        por_nombre = {c["name"]: c for c in campos}

    project_id = json.loads(gh("project", "view", PROJECT, "--owner", OWNER, "--format", "json"))["id"]

    # 2) Rellenar valores
    for f in sorted(filas, key=lambda x: (x["fin"], x["titulo"])):
        valores = {"Estado Inicial": "Pendiente"}
        for nombre, fecha in cortes.items():
            valores[nombre] = estado(f, fecha) if fecha else "Pendiente"
        print(f["titulo"][:48].ljust(48), " | ".join(f"{k.split()[-1]}={v}" for k, v in valores.items()))
        if not APPLY:
            continue
        for nombre, valor in valores.items():
            campo = por_nombre[nombre]
            opcion = next(o["id"] for o in campo["options"] if o["name"] == valor)
            gh("project", "item-edit", "--id", f["id"], "--project-id", project_id,
               "--field-id", campo["id"], "--single-select-option-id", opcion)

    # 3) README con avance por sprint y global (promedio simple del avance de cada CU)
    por_sprint = {}
    for f in filas:
        por_sprint.setdefault(f["sprint"], []).append(f["avance"])
    lineas = ["## Avance", "", "| Sprint | CU | Avance |", "|---|---|---|"]
    for sprint in sorted(por_sprint):
        v = por_sprint[sprint]
        lineas.append(f"| {sprint} | {len(v)} | {sum(v) / len(v):.0f} % |")
    todos = [f["avance"] for f in filas]
    lineas.append(f"| **Global** | **{len(todos)}** | **{sum(todos) / len(todos):.0f} %** |")
    lineas += ["", f"HH estimadas: {total_hh:g}. El avance es el promedio simple del avance de cada CU."]
    readme = "\n".join(lineas)
    print("\nREADME del Project:\n" + readme)
    if APPLY:
        gh("project", "edit", PROJECT, "--owner", OWNER, "--readme", readme)
        print("\nListo. Revisa: https://github.com/users/CortesRodriguez/projects/2")
    else:
        print("\n(Prueba: no se escribio nada. Para aplicar: CONFIRM=si python3 scripts/agregar_cortes_github.py)")


if __name__ == "__main__":
    main()
