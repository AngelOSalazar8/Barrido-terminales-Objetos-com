# Filtra los IATAs extraídos de SQL contra los que ya existen en la BD de destino.
# Consulta la tabla [Iata] de CatalogosYielding para tener siempre la lista real y actualizada.
# Devuelve un CSV solo con los IATAs que aún no están en la BD → esos son los que van al wizard.

import sys
import json
import pathlib
import urllib.parse
from datetime import datetime

import pandas as pd
from sqlalchemy import create_engine, text

# ── Rutas basadas en la ubicación de ESTE archivo ───────────────────────────
_ROOT        = pathlib.Path(__file__).parent.parent          # raíz del repo
_NUEVAS_DIR  = _ROOT / "workspace" / "Filtro_Nuevos"

# Credenciales de la BD de DESTINO (la misma que usa el core de la APP)
_CONFIG_PATH = _ROOT / "Config" / "CredencialesSVRdbpricing.json"


def _get_existentes_en_bd(modo="IATA") -> set:
    """Consulta la BD de destino y devuelve el set de registros ya cargados."""
    with open(_CONFIG_PATH, "r") as f:
        config = json.load(f)
    db = config["db"]

    params = urllib.parse.quote_plus(
        f"DRIVER={{{db['driver']}}};"
        f"SERVER={db['server']};"
        f"DATABASE={db['database']};"
        f"UID={db['usernameDB']};"
        f"PWD={db['passwordDB']}"
    )
    engine = create_engine(f"mssql+pyodbc:///?odbc_connect={params}")
    
    col = "Iata" if modo == "IATA" else "AWD"
    tbl = "dbo.Iata" if modo == "IATA" else "dbo.awd"
    
    with engine.connect() as conn:
        df = pd.read_sql(text(f"SELECT {col} FROM {tbl}"), conn)

    if modo == "IATA":
        existentes = set(df[col].astype(str).str.strip().str.zfill(8))
    else:
        existentes = set(df[col].astype(str).str.strip())
        
    print(f"  · {len(existentes)} {col} ya registrados en la BD de destino.")
    return existentes


def filtrar_nuevos(archivo_sql_csv: str, modo="IATA") -> str:
    """Compara el CSV extraído de SQL contra la BD de destino y guarda solo los IDs nuevos.

    Args:
        archivo_sql_csv: Ruta al CSV generado por ExtraerSQL.
        modo: "IATA" o "AWD" ("IATA" por defecto).

    Returns:
        str: Ruta absoluta del CSV con IDs nuevos, o '' si no hay nuevos.
    """
    _NUEVAS_DIR.mkdir(parents=True, exist_ok=True)
    DAY_date = datetime.now().strftime("%d-%m-%Y")
    
    prefijo = "IATAs" if modo == "IATA" else "AWDs"
    col = "IATA" if modo == "IATA" else "AWD"
    
    archivo_nuevos = str(_NUEVAS_DIR / f"{prefijo}_Nuevas-{DAY_date}.csv")

    print(f"Cargando extracción de SQL: {archivo_sql_csv}")
    df_sql = pd.read_csv(archivo_sql_csv, dtype={col: str})
    
    if modo == "IATA":
        df_sql[col] = df_sql[col].astype(str).str.strip().str.zfill(8)
    else:
        df_sql[col] = df_sql[col].astype(str).str.strip()
        
    print(f"  · {len(df_sql)} registros en la extracción SQL.")

    print(f"Consultando {prefijo} existentes en la BD de destino…")
    existentes = _get_existentes_en_bd(modo)

    df_nuevos = df_sql[~df_sql[col].isin(existentes)]
    
    df_nuevos = df_nuevos.drop_duplicates(subset=[col], keep="first")

    if not df_nuevos.empty:
        df_nuevos.to_csv(archivo_nuevos, index=False, encoding="utf-8-sig")
        print(f"¡ÉXITO! Se encontraron {len(df_nuevos)} {prefijo} nuevos → '{archivo_nuevos}'")
        return archivo_nuevos
    else:
        print(f"No se encontraron {prefijo} nuevos. La BD de destino ya está al día.")
        return ""


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python FiltraNuevosPre.py <ruta_csv_sql> [modo]")
        sys.exit(1)
    
    modo_param = sys.argv[2] if len(sys.argv) > 2 else "IATA"
    resultado = filtrar_nuevos(sys.argv[1], modo=modo_param)
    
    if resultado:
        print(f"Archivo de nuevos: {resultado}")
