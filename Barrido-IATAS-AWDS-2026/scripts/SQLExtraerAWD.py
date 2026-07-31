# Esta es una version de ExtraerAWD con manejo de errores y rutas adaptadas al nuevo flujo unificado.
import pyodbc
import pandas as pd
from datetime import datetime, timedelta
import json
import numpy as np
import sys
import pathlib

# Rutas estandarizadas
_ROOT = pathlib.Path(__file__).parent.parent              # BarridoIATAS-2026/

# Credenciales centralizadas
CONFIG_FILE = _ROOT / "Config" / "CredencialesDBServ4.json"

def extraerSQL(fecha_desde: str) -> str:
    """Ejecuta la consulta SQL con la fecha indicada y guarda los resultados en CSV.

    Args:
        fecha_desde: Fecha minima de Booking_Date en formato 'YYYY-MM-DD'.

    Returns:
        str: Ruta absoluta del CSV generado.

    Raises:
        Exception: Relanza cualquier error para que la UI lo capture.
    """
    now = datetime.now()
    DAY_date = now.strftime("%d-%m-%Y")
    csv_output_path = _ROOT / "workspace" / "Desde_sql" / f"AWD-{DAY_date}.csv"
    csv_output_path.parent.mkdir(parents=True, exist_ok=True)
    csv_output = str(csv_output_path)

    print("Conectando con SQL para extraer AWDs...")
    conn = None
    try:
        with open(CONFIG_FILE, 'r') as f:
            config = json.load(f)

        connection_string = (
            f"DRIVER={config['driver']};"
            f"SERVER={config['server']};"
            f"DATABASE={config['database']};"
            f"UID={config['usr']};"
            f"PWD={config['pwd']};"
        )
        conn = pyodbc.connect(connection_string)

        # La query ahora recibe la fecha como parametro en vez de leerla del archivo SQL
        query = (
            "SELECT [Primary_Awd_Org_Id],[ReservationId] ,[Booking_Date] "
            "FROM [dbAreaCorp].[dbo].[Reservaciones] "
            f"WHERE Booking_Date >= '{fecha_desde}' "
            "ORDER BY Booking_Date DESC"
        )
        print(f"Ejecutando la consulta desde: {fecha_desde}")
        df = pd.read_sql_query(query, conn)

        # Renombrar y limpiar
        # Conservar el valor original de la BD como AWD_res (8 digitos, con el digito extra)
        df_awd = df.rename(columns={'Primary_Awd_Org_Id': 'AWD_res'})
        df_awd["AWD_res"] = df_awd["AWD_res"].astype(str).str.strip()
        df_awd["AWD_res"] = df_awd["AWD_res"].replace('', np.nan)
        df_awd["AWD_res"] = df_awd["AWD_res"].replace('nan', np.nan)
        df_awd = df_awd.dropna(subset=['AWD_res'])

        # Corregir: la BD trae 8 digitos pero deben ser 7.
        # Equivalente a la formula Excel: =IZQUIERDA(A2,5) & DERECHA(A2,LARGO(A2)-6)
        # Elimina el 6to caracter del codigo → awd[:5] + awd[6:]
        df_awd["AWD"] = df_awd["AWD_res"].apply(lambda awd: awd[:5] + awd[6:])

        # Deduplicar sobre el AWD corregido (el que se usara en el barrido)
        df_awd = df_awd.drop_duplicates(subset=['AWD'])

        # Reordenar columnas: AWD primero, luego AWD_res, luego el resto
        cols = ["AWD", "AWD_res"] + [c for c in df_awd.columns if c not in ("AWD", "AWD_res")]
        df_awd = df_awd[cols]

        df_awd.to_csv(csv_output, index=False, encoding='utf-8-sig')
        print(f"CSV generado correctamente: {csv_output}")
        return csv_output

    except FileNotFoundError:
        raise FileNotFoundError(f"No se encontro el archivo de config: '{CONFIG_FILE}'.")
    except KeyError as e:
        raise KeyError(f"Falta la clave '{e}' en {CONFIG_FILE}.")
    except pyodbc.Error as e:
        raise ConnectionError(f"Error de base de datos: {e}")
    finally:
        if conn:
            conn.close()
            print("Conexion cerrada.")


if __name__ == "__main__":
    # Uso standalone: pasa la fecha como argumento o usa hoy - 1 anio
    fecha = sys.argv[1] if len(sys.argv) > 1 else (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d")
    result = extraerSQL(fecha)
    print(f"Archivo generado: {result}")
