"""Evaluación reproducible del sistema de triaje sobre el conjunto etiquetado.

Dos modos:

    # Solo recuperación: mide distancias y cobertura del corpus.
    # No invoca el modelo de lenguaje, así que es gratuito e instantáneo.
    docker compose run --rm backend python eval/evaluate.py --recuperacion

    # Evaluación completa: ejecuta el pipeline y contrasta la clasificación.
    docker compose run --rm backend python eval/evaluate.py

El modo de recuperación es el que se usa para calibrar MAX_DISTANCE: reporta la
distribución de distancias separando los casos con respaldo documental esperado
de los que no lo tienen, y propone un umbral en el intervalo que los separa.

CONSUMO DE CUOTA: el modo completo son 28 casos x 2 llamadas al proveedor, que
en el plan gratuito de Groq consumen prácticamente el límite diario de 200.000
tokens. Una segunda ejecución el mismo día falla con error 429 en los últimos
casos. Planifique una evaluación completa por día, o use --recuperacion, que no
invoca al modelo y por tanto no consume cuota.
"""
import argparse
import json
import sys
import time
from pathlib import Path

import requests

from rag.config import MAX_DISTANCE
from rag.query_rag import query_symptoms

CASES_PATH = Path(__file__).resolve().parent / "cases.json"
API_URL = "http://localhost:5000/api/triage"
SEVERIDAD = {"Verde": 1, "Amarillo": 2, "Rojo": 3}


def cargar_casos() -> list[dict]:
    return json.loads(CASES_PATH.read_text(encoding="utf-8"))["casos"]


# --------------------------------------------------------------------------- #
#  Modo recuperación
# --------------------------------------------------------------------------- #

def evaluar_recuperacion(casos: list[dict]) -> None:
    """Mide distancias y cobertura sin invocar el LLM.

    Se busca con el texto crudo del paciente. Es el escenario más exigente:
    en producción la consulta se enriquece con la traducción clínica, así que
    las distancias reales serán iguales o mejores que las de aquí.
    """
    con_respaldo: list[float] = []
    sin_respaldo: list[float] = []
    aciertos_guia = fallos_guia = 0

    print(f"{'Caso':<6} {'Mejor':>7}  {'Guía esperada':<34} {'Guía recuperada':<34} ")
    print("-" * 92)

    for caso in casos:
        # Sin umbral: se quiere ver la distribución completa, no la filtrada.
        fragmentos = query_symptoms(caso["sintomas"], k=4, max_distance=2.0)
        mejor = fragmentos[0] if fragmentos else None
        distancia = mejor["distancia"] if mejor else float("nan")
        recuperada = mejor["guia"] if mejor else "—"
        esperadas = caso["guias_esperadas"]

        if esperadas:
            con_respaldo.append(distancia)
            guias_top = {f["guia"] for f in fragmentos}
            if guias_top & set(esperadas):
                aciertos_guia += 1
                marca = "OK"
            else:
                fallos_guia += 1
                marca = "FALLO"
        else:
            sin_respaldo.append(distancia)
            marca = "(sin respaldo esperado)"

        print(f"{caso['id']:<6} {distancia:>7.4f}  {(esperadas[0] if esperadas else '—'):<34} {recuperada:<34} {marca}")

    print()
    _resumen_distribucion(con_respaldo, sin_respaldo)

    total = aciertos_guia + fallos_guia
    if total:
        print(f"\nCobertura del corpus: {aciertos_guia}/{total} casos recuperaron una guía esperada "
              f"({aciertos_guia / total:.0%})")


def _resumen_distribucion(con_respaldo: list[float], sin_respaldo: list[float]) -> None:
    def stats(valores: list[float]) -> str:
        if not valores:
            return "sin datos"
        return (f"min={min(valores):.4f}  mediana={sorted(valores)[len(valores) // 2]:.4f}  "
                f"max={max(valores):.4f}  n={len(valores)}")

    print("DISTRIBUCIÓN DE DISTANCIAS")
    print(f"  Casos CON respaldo esperado : {stats(con_respaldo)}")
    print(f"  Casos SIN respaldo esperado : {stats(sin_respaldo)}")

    if con_respaldo and sin_respaldo:
        peor_acierto = max(con_respaldo)
        mejor_ruido = min(sin_respaldo)
        print(f"\n  Peor acierto      : {peor_acierto:.4f}")
        print(f"  Mejor falso positivo: {mejor_ruido:.4f}")
        if peor_acierto < mejor_ruido:
            sugerido = round((peor_acierto + mejor_ruido) / 2, 2)
            print(f"  Los grupos se separan limpiamente.")
            print(f"  UMBRAL SUGERIDO: {sugerido}   (MAX_DISTANCE actual: {MAX_DISTANCE})")
        else:
            print(f"  ATENCIÓN: los grupos se solapan. Ningún umbral los separa sin error.")
            print(f"  Revise los casos mal recuperados antes de ajustar MAX_DISTANCE.")


# --------------------------------------------------------------------------- #
#  Modo completo
# --------------------------------------------------------------------------- #

def evaluar_completo(casos: list[dict], url: str, pausa: float) -> None:
    exactos = seguros = subtriaje = errores = 0
    clinicos = [c for c in casos if c["color_esperado"]]
    matriz: dict[tuple, int] = {}

    print(f"{'Caso':<6} {'Esperado':<10} {'Obtenido':<10} {'Fuentes':>8}  Resultado")
    print("-" * 78)

    for indice, caso in enumerate(casos):
        # Cada caso son dos llamadas al proveedor. Sin pausa, la tanda completa
        # supera el límite de peticiones por minuto del plan gratuito y algunos
        # casos fallan con error de servicio que no refleja un defecto real.
        if indice:
            time.sleep(pausa)
        payload = {"symptoms": caso["sintomas"], "edad": caso["edad"], "sexo": caso["sexo"]}
        if caso["gestante"] is not None:
            payload["gestante"] = caso["gestante"]
        payload.update(caso.get("vitales") or {})

        try:
            respuesta = requests.post(url, json=payload, timeout=180)
            datos = respuesta.json()
        except requests.RequestException as exc:
            print(f"{caso['id']:<6} {'—':<10} {'ERROR':<10} {'—':>8}  {exc}")
            errores += 1
            continue

        if respuesta.status_code != 200:
            print(f"{caso['id']:<6} {str(caso['color_esperado'] or '—'):<10} {'HTTP ' + str(respuesta.status_code):<10} "
                  f"{'—':>8}  {str(datos.get('error'))[:40]}")
            errores += 1
            continue

        obtenido = datos["color_triage"]
        n_fuentes = len(datos.get("fuentes_rag", []))
        esperado = caso["color_esperado"]

        if esperado is None:
            # Controles no clínicos: no hay color correcto; se revisan a mano.
            print(f"{caso['id']:<6} {'(control)':<10} {obtenido:<10} {n_fuentes:>8}  "
                  f"revisar: {datos['diagnostico_presuntivo'][:38]}")
            continue

        matriz[(esperado, obtenido)] = matriz.get((esperado, obtenido), 0) + 1
        if obtenido == esperado:
            exactos += 1
            veredicto = "exacto"
        elif SEVERIDAD[obtenido] > SEVERIDAD[esperado]:
            seguros += 1
            veredicto = "sobre-triaje (seguro)"
        else:
            subtriaje += 1
            veredicto = "SUB-TRIAJE (inseguro)"

        print(f"{caso['id']:<6} {esperado:<10} {obtenido:<10} {n_fuentes:>8}  {veredicto}")

    n = len(clinicos)
    print(f"\nRESULTADOS SOBRE {n} CASOS CLÍNICOS")
    print(f"  Coincidencia exacta : {exactos}/{n}  ({exactos / n:.0%})")
    print(f"  Sobre-triaje        : {seguros}/{n}  ({seguros / n:.0%})   aceptable")
    print(f"  Sub-triaje          : {subtriaje}/{n}  ({subtriaje / n:.0%})   crítico")
    print(f"  Errores de ejecución: {errores}")
    print(f"\n  Seguridad clínica (exacto + sobre-triaje): {(exactos + seguros) / n:.0%}")

    if matriz:
        print("\nMATRIZ DE CONFUSIÓN  (fila = esperado, columna = obtenido)")
        colores = ["Verde", "Amarillo", "Rojo"]
        print(f"{'':<10}" + "".join(f"{c:>10}" for c in colores))
        for esperado in colores:
            fila = "".join(f"{matriz.get((esperado, obtenido), 0):>10}" for obtenido in colores)
            print(f"{esperado:<10}{fila}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluación del sistema de triaje.")
    parser.add_argument("--recuperacion", action="store_true",
                        help="Solo recuperación: sin llamadas al LLM, para calibrar el umbral.")
    parser.add_argument("--url", default=API_URL, help=f"Endpoint de triaje (por defecto {API_URL}).")
    parser.add_argument("--pausa", type=float, default=2.0,
                        help="Segundos entre casos, para no exceder el límite de peticiones (por defecto 2).")
    args = parser.parse_args()

    casos = cargar_casos()
    print(f"Conjunto de evaluación: {len(casos)} casos\n")

    if args.recuperacion:
        evaluar_recuperacion(casos)
    else:
        evaluar_completo(casos, args.url, args.pausa)


if __name__ == "__main__":
    sys.exit(main())
