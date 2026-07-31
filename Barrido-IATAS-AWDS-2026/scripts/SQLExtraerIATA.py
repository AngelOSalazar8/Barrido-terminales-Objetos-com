# Se conecta a la base de datos, filtra y extrae los IATAs y los guarda en un csv quitando
# espacios vacios y duplicados, ademas de cambiarle el nombre a la columna y guardarlo
# en un csv para ejecutar el barrido de IATA.

import json
import sys
import pathlib
from datetime import datetime


import pandas as pd
import pyodbc

# Rutas basadas en la ubicación de ESTE archivo
_ROOT = pathlib.Path(__file__).parent.parent              # raíz del repo
CONFIG_FILE = _ROOT / "Config" / "CredencialesDBServ4.json"
IATA_EXTRAIDO_DIR = _ROOT / "workspace" / "Desde_sql"


def extraerSQL(fecha_desde: str) -> str:
    """Ejecuta la consulta SQL con la fecha indicada y guarda los resultados en CSV.

    Args:
        fecha_desde: Fecha mínima de Booking_Date en formato 'YYYY-MM-DD'.

    Returns:
        str: Ruta absoluta del CSV generado.

    Raises:
        Exception: Relanza cualquier error para que la UI lo capture.
    """
    now = datetime.now()
    DAY_date = now.strftime("%d-%m-%Y")
    IATA_EXTRAIDO_DIR.mkdir(parents=True, exist_ok=True)
    csv_output = str(IATA_EXTRAIDO_DIR / f"IATAs-{DAY_date}.csv")

    print("Conectando con SQL...")
    conn = None
    try:
        with open(CONFIG_FILE, "r") as f:
            db = json.load(f)

        connection_string = (
            f"DRIVER={db['driver']};"
            f"SERVER={db['server']};"
            f"DATABASE={db['database']};"
            f"UID={db['usr']};"
            f"PWD={db['pwd']};"
        )
        conn = pyodbc.connect(connection_string)

        # ATC_Iata_Num es nvarchar(10): ya viene como texto con ceros intactos.
        # No se necesita CAST ni RIGHT — pyodbc lo entrega directamente como string.
        query = (
            "SELECT [ReservationId], [Booking_Date], [ATC_Iata_Num] "
            "FROM [dbAreaCorp].[dbo].[Reservaciones] "
            f"WHERE [Booking_Date] >= '{fecha_desde}' "
            "ORDER BY Booking_Date DESC"
        )
        print(f"Ejecutando la consulta desde: {fecha_desde}")
        df = pd.read_sql_query(query, conn)

        # Renombrar y limpiar (el campo ya viene como texto de 8 dígitos desde SQL)
        df_IATA = df.rename(columns={"ATC_Iata_Num": "IATA"})
        df_IATA["IATA"] = df_IATA["IATA"].astype(str).str.strip()
        
        # Filtrar valores vacíos o nulos ANTES de rellenar los ceros
        df_IATA = df_IATA[(df_IATA["IATA"] != "") & (df_IATA["IATA"] != "None")].dropna(subset=["IATA"])
        
        # Rellenar con ceros a la izquierda para garantizar 8 dígitos (ej. "123" -> "00000123")
        df_IATA["IATA"] = df_IATA["IATA"].str.zfill(8)

        df_IATA.to_csv(csv_output, index=False, encoding="utf-8-sig")
        print(f"CSV generado correctamente: {csv_output}")
        return csv_output

    except FileNotFoundError:
        raise FileNotFoundError(f"No se encontró el archivo de config: '{CONFIG_FILE}'.")
    except KeyError as e:
        raise KeyError(f"Falta la clave '{e}' en {CONFIG_FILE}.")
    except pyodbc.Error as e:
        raise ConnectionError(f"Error de base de datos: {e}")
    finally:
        if conn:
            conn.close()
            print("Conexión cerrada.")


if __name__ == "__main__":
    # Uso standalone: pasa la fecha como argumento o usa hoy - 3 años
    from datetime import timedelta
    fecha = sys.argv[1] if len(sys.argv) > 1 else (datetime.now() - timedelta(days=1095)).strftime("%Y-%m-%d")
    result = extraerSQL(fecha)
    print(f"Archivo generado: {result}")
