import json
import pathlib
import urllib.parse
from sqlalchemy import create_engine
import pandas as pd
from sqlalchemy import text


# Ruta al config.json relativa a la raíz del proyecto
CONFIG_PATH = pathlib.Path(__file__).parent.parent / 'Config' / 'CredencialesSVRdbpricing.json'

def get_db_connection():
    with open(CONFIG_PATH, 'r') as f:
        config = json.load(f)
    
    db_conf = config['db']
    
    params = urllib.parse.quote_plus(
        f"DRIVER={{{db_conf['driver']}}};"
        f"SERVER={db_conf['server']};"
        f"DATABASE={db_conf['database']};"
        f"UID={db_conf['usernameDB']};"
        f"PWD={db_conf['passwordDB']}"
    )
    
    # fast_executemany=True acelera mucho la subida si son miles de datos
    engine = create_engine(f"mssql+pyodbc:///?odbc_connect={params}", fast_executemany=True)
    return engine


def get_new_records(df, table_name="Iata", schema="dbo", id_col="Iata"):
    engine = get_db_connection()
    try:
        with engine.begin() as connection:
            query = text(f"SELECT {id_col} FROM {schema}.{table_name}")
            existing_df = pd.read_sql(query, connection)
            
            df_temp = df.copy()
            
            if id_col == "Iata":
                existing_keys = set(existing_df[id_col].astype(str).str.strip().str.zfill(8))
                df_temp["_clean_id"] = df_temp[id_col].astype(str).str.strip().str.zfill(8)
            else:
                existing_keys = set(existing_df[id_col].astype(str).str.strip())
                df_temp["_clean_id"] = df_temp[id_col].astype(str).str.strip()
            
            df_new = df_temp[~df_temp["_clean_id"].isin(existing_keys)].drop(columns=["_clean_id"])
            return df_new
    except Exception as e:
        print(f"Error SQL: {e}")
        raise e

def upload_data(df, table_name="Iata", schema="dbo"):
    if df.empty:
        return 0
    engine = get_db_connection()
    try:
        with engine.begin() as connection:
            df.to_sql(table_name, con=connection, schema=schema, if_exists='append', index=False)
            return len(df)
    except Exception as e:
        print(f"Error SQL: {e}")
        raise e


def get_existing_records(df, table_name="Iata", schema="dbo", id_col="Iata"):
    """Retorna el subconjunto de df cuyos IDs YA existen en la BD.
    Es el inverso de get_new_records.

    IMPORTANTE: La columna id_col en el DataFrame devuelto contiene el valor
    TAL COMO ESTA ALMACENADO EN LA BD (no el del archivo de entrada).
    Esto garantiza que el UPDATE WHERE siempre matchee, independientemente de
    si la BD guarda IATAs con o sin cero inicial.
    """
    engine = get_db_connection()
    try:
        with engine.begin() as connection:
            query = text(f"SELECT {id_col} FROM {schema}.{table_name}")
            existing_df = pd.read_sql(query, connection)

            df_temp = df.copy()

            if id_col == "Iata":
                # Mapa: clave_normalizada(8 digitos) → valor_real_en_bd
                id_map = {
                    str(v).strip().zfill(8): str(v).strip()
                    for v in existing_df[id_col].dropna()
                }
                existing_keys = set(id_map.keys())
                df_temp["_clean_id"] = df_temp[id_col].astype(str).str.strip().str.zfill(8)
            else:
                id_map = {
                    str(v).strip(): str(v).strip()
                    for v in existing_df[id_col].dropna()
                }
                existing_keys = set(id_map.keys())
                df_temp["_clean_id"] = df_temp[id_col].astype(str).str.strip()

            df_existing = df_temp[df_temp["_clean_id"].isin(existing_keys)].copy()

            # Reemplazar el ID con el valor real almacenado en la BD
            # para que el UPDATE WHERE siempre matchee
            df_existing[id_col] = df_existing["_clean_id"].map(id_map)
            df_existing = df_existing.drop(columns=["_clean_id"])
            return df_existing
    except Exception as e:
        print(f"Error SQL: {e}")
        raise e


def update_records(df, table_name="Iata", schema="dbo", id_col="Iata", cols_to_update=None):
    """Actualiza registros existentes en la BD. No modifica import_date.

    Para cada fila del DataFrame construye y ejecuta un UPDATE parametrizado.
    Los valores NULL se inyectan como literales directamente en el SQL para
    evitar el fallo silencioso de pyodbc al bindear None como parametro nombrado.

    Args:
        df:             DataFrame con los registros a actualizar.
        table_name:     Nombre de la tabla.
        schema:         Schema de la tabla.
        id_col:         Columna que es la llave primaria (no se actualiza).
        cols_to_update: Lista de columnas a actualizar. Si None, usa todas
                        las del df excepto id_col e import_date.

    Returns:
        int: Numero de filas efectivamente actualizadas (rowcount > 0).
    """
    if df.empty:
        return 0

    if cols_to_update is None:
        cols_to_update = [
            c for c in df.columns
            if c not in (id_col, "import_date")
        ]

    # Conservar solo las que existen en el df
    cols_to_update = [c for c in cols_to_update if c in df.columns]
    if not cols_to_update:
        raise ValueError("No hay columnas validas para actualizar.")

    engine = get_db_connection()
    count = 0
    no_match = 0

    try:
        with engine.begin() as connection:
            for _, row in df.iterrows():
                set_parts  = []   # fragmentos del SET clause
                params_row = {}   # parametros nombrados (solo valores no-NULL)

                for col in cols_to_update:
                    val = row[col]

                    # Detectar NULL de forma robusta (NaN, None, NaT, etc.)
                    try:
                        is_null = bool(pd.isnull(val))
                    except Exception:
                        is_null = False

                    if is_null:
                        # NULL se escribe directo en el SQL — evita fallo de pyodbc
                        set_parts.append(f"{col} = NULL")
                    else:
                        set_parts.append(f"{col} = :{col}")
                        # Convertir numpy scalars a tipos Python nativos
                        params_row[col] = val.item() if hasattr(val, "item") else val

                if not set_parts:
                    continue

                params_row[id_col] = row[id_col]
                stmt_row = text(
                    f"UPDATE {schema}.{table_name} "
                    f"SET {', '.join(set_parts)} "
                    f"WHERE {id_col} = :{id_col}"
                )
                result = connection.execute(stmt_row, params_row)

                if result.rowcount > 0:
                    count += 1
                else:
                    no_match += 1
                    print(f"  AVISO: {id_col}='{row[id_col]}' no encontrado en la BD.")

        print(f"Actualizados {count} registros en {schema}.{table_name}."
              + (f" ({no_match} no encontrados)" if no_match else ""))
        return count
    except Exception as e:
        print(f"Error SQL: {e}")
        raise e
