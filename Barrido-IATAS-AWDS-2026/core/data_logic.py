import pandas as pd
from datetime import datetime
import os
import json
_CONF_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'Config', 'reglas_grupo_IATAS.json')

def cargar_reglas_grupo():
    try:
        with open(_CONF_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error cargando reglas de grupo: {e}")
        return {}

_reglas_grupo = cargar_reglas_grupo()

def calcular_grupo(nombre):
    if not isinstance(nombre, str): return "OTRO"
    nombre_upper = nombre.upper()
    
    for substr, grupo in _reglas_grupo.items():
        if substr in nombre_upper:
            return grupo
            
    return "OTRO"

"""
Aplica formato a el DF para adecuarlo a la BD
"""

def process_file(filepath):
    """
    Lee el archivo, fuerza IATA como texto (para ceros a la izquierda),
    elimina duplicados y agrega fecha con hora.
    """
    ext = os.path.splitext(filepath)[1].lower()
    
    # IMPORTANTE: dtype=str asegura que '00123' no se convierta en '123'
    if ext == '.csv':
        df = pd.read_csv(filepath, dtype={'IATA': str, 'NOMBRE': str})
    elif ext in ['.xls', '.xlsx']:
        df = pd.read_excel(filepath, dtype={'IATA': str, 'NOMBRE': str})
    else:
        raise ValueError("Formato no soportado. Usa CSV o Excel.")

    # 1. Normalizar nombres de columnas
    df.columns = df.columns.str.strip() 
    df = df.rename(columns={
        "IATA": "Iata",    # Como en tu base de datos
        "NOMBRE": "Nombre" # Como en tu base de datos
    })

    # 1. Identificar los duplicados (crea un filtro de True/False)
    # keep='first' marca como True los duplicados que se borrarían (el 2do, 3ro, etc.)
    mask_duplicados = df.duplicated(subset=['Iata'], keep='first')

    # 2. Filtrar el DataFrame para ver qué se va a borrar
    filas_duplicadas = df[mask_duplicados]

    print("Estos son los registros duplicados que se eliminarán:")
    print(filas_duplicadas)

    # 3. Ahora sí, aplicas tu código original para limpiar el DataFrame
    df = df.drop_duplicates(subset=['Iata'], keep='first')
    # 3. Agregar import_date con HORA exacta (como en tu imagen)
    df['import_date'] = datetime.now()
    
    # 3.5. Autocompletar 'Grupo' si no viene en el excel original
    if "Grupo" not in df.columns:
        df["Grupo"] = df["Nombre"].apply(calcular_grupo)
    else:
        # Rellenar solo los nulos si existe pero viene vacía
        df["Grupo"] = df["Grupo"].fillna(df["Nombre"].apply(calcular_grupo))

    #df.to_csv('IATASNuevas-con-import-date.csv', index=False)

    # 4. Seleccionar columnas finales
    # NO incluimos idIATA porque SQL Server lo genera automáticamente (Identity)
    cols_to_upload = ['Iata', 'Nombre', 'Grupo', 'Tipo', 'import_date']
    
    # Validar que existan las columnas
    missing_cols = [c for c in cols_to_upload if c not in df.columns]
    if missing_cols:
        raise ValueError(f"El archivo no tiene las columnas requeridas o están mal escritas: {missing_cols}")

    return df[cols_to_upload]


def process_barrido_file(filepath):
    """
    Procesa el barrido.csv generado por iataswizard-v3.

    Columnas de entrada : IATA, NOMBRE, Grupo, phone, sales_territory_code, country, addr
    Columnas de salida  : Iata, Nombre, Grupo, Tipo (None), import_date
    """
    df = pd.read_csv(filepath, dtype={"IATA": str, "NOMBRE": str})
    df.columns = df.columns.str.strip()
    df = df.rename(columns={"IATA": "Iata", "NOMBRE": "Nombre"})

    dupes = df.duplicated(subset=["Iata"], keep="first")
    if dupes.any():
        print(f"Duplicados eliminados: {dupes.sum()}")
    df = df.drop_duplicates(subset=["Iata"], keep="first")

    df["Grupo"]       = df["Nombre"].apply(calcular_grupo) # Calculado automáticamente sobrescribe lo de iataswizard
    df["Tipo"]        = None           # el wizard no lo extrae
    df["import_date"] = datetime.now()

    cols = ["Iata", "Nombre", "Grupo", "Tipo", "import_date"]
    missing = [c for c in cols if c not in df.columns]
    if missing:
        raise ValueError(f" no tiene las columnas esperadas: {missing}")

    print(f"barrido.csv: {len(df)} registros listos para subir.")
    return df[cols]

def process_awd_file(filepath, is_barrido=False):
    """
    Lee el archivo AWD, lo limpia de duplicados y vacíos.
    Asegura las columnas de inserción directa para AWD.
    Si is_barrido=True, crea las columnas vacías para que el usuario las llene.
    Si is_barrido=False (subida final), exige que las columnas ya vengan en el Excel.
    """
    ext = os.path.splitext(filepath)[1].lower()
    
    if ext == '.csv':
        df = pd.read_csv(filepath, dtype={'AWD': str})
    elif ext in ['.xls', '.xlsx']:
        df = pd.read_excel(filepath, dtype={'AWD': str})
    else:
        raise ValueError("Formato no soportado. Usa CSV o Excel.")

    df.columns = df.columns.str.strip() 

    if 'AWD' not in df.columns:
        raise ValueError("El archivo no contiene la columna 'AWD'")

    df['AWD'] = df['AWD'].astype(str).str.strip()
    
    # Validar si hay > 8 caracteres al subir el archivo
    awds_largos = df[df['AWD'].str.len() > 8]
    if not awds_largos.empty:
        print("==================================================")
        print(" ATENCION: AWDs con más de 8 caracteres detectados en subida")
        print("==================================================")
        for val in awds_largos["AWD"].tolist():
            print(f" - {val}")
        print("==================================================")
        
        import tkinter.messagebox as mb
        import tkinter as tk
        root = tk._default_root
        
        respuesta = mb.askyesno(
            title="AWDs de más de 8 caracteres",
            message=f"Se detectaron {len(awds_largos)} AWD(s) con más de 8 caracteres.\n"
                    "Fueron impresos en la consola para tu revisión.\n\n"
                    "¿Deseas aplicarles la corrección (recortar el 6to carácter) a estos registros?",
            parent=root
        )
        if respuesta:
            print("Aplicando corrección a los AWDs > 8 caracteres...")
            df['AWD'] = df['AWD'].apply(lambda awd: awd[:5] + awd[6:] if len(awd) > 8 else awd)

    # Validar y retirar el cero a la izquierda si el AWD tiene 8 caracteres
    df['AWD'] = df['AWD'].apply(lambda x: x[1:] if len(x) == 8 and x.startswith('0') else x)

    df = df[df['AWD'] != 'nan']
    df = df[df['AWD'] != '']
    df = df.drop_duplicates(subset=['AWD'], keep='first')

    cols_expected = ['AWD', 'Company', 'Division', 'Addr1', 'Addr2', 'Addr3','Ctry']
    
    missing_cols = [c for c in cols_expected if c not in df.columns]
    if missing_cols:
        raise ValueError(f"Faltan las columnas base de AWD: {missing_cols}")

    df = df.rename(columns={'Fecha Ingreso': 'Fecha_Ingreso'})
    df = df.rename(columns={'AutoSustituto': 'auto_sustituto'})
    if is_barrido:
        # Generar "plantilla" metiéndoles valores nulos para que el usuario los rellene
        df['Corporativo']  = None
        df['auto_sustituto'] = None
        df['Ejecutivo']    = None
        df['Fecha_Ingreso'] = None
        
    else:
        # Subida estricta: las columnas manuales deben venir en el archivo
        cols_manuales = ['Corporativo', 'auto_sustituto', 'Ejecutivo', 'Fecha_Ingreso']
        faltantes = [c for c in cols_manuales if c not in df.columns]
        if faltantes:
            raise ValueError(
                f"Faltan las columnas que debes llenar manualmente antes de subir: {faltantes}"
            )

    df['import_date'] = datetime.now()
    df['Fecha_Ingreso'] = pd.to_datetime(df['Fecha_Ingreso'], errors='coerce')
    
    cols_to_upload = [
        'AWD', 'Company', 'Division', 'Addr1', 'Addr2',
        'Addr3', 'Ctry', 'Corporativo', 'auto_sustituto',
        'Ejecutivo', 'Fecha_Ingreso', 'import_date'
    ]

    return df[cols_to_upload]


def process_file_for_update(filepath, modo="IATA"):
    """Lee un archivo CSV/Excel para el flujo de ACTUALIZACION.

    A diferencia de process_file / process_awd_file:
      - No agrega import_date (no aplica para UPDATE).
      - Solo conserva las columnas que existen en la tabla de destino.
        Columnas extra en el archivo (YEAR, COUNTRY, VENDOR, etc.) se ignoran.
      - No exige que todas las columnas actualizables esten presentes.

    Args:
        filepath: Ruta al archivo CSV o Excel.
        modo:     'IATA' o 'AWD'.

    Returns:
        DataFrame listo para pasar a database.update_records().
    """
    # Columnas actualizables por modo (las que realmente existen en la tabla)
    _IATA_UPDATABLE = {"Nombre", "Grupo", "Tipo"}
    _AWD_UPDATABLE  = {
        "Company", "Division", "Addr1", "Addr2", "Addr3",
        "Ctry", "Corporativo", "auto_sustituto", "Ejecutivo", "Fecha_Ingreso"
    }

    ext = os.path.splitext(filepath)[1].lower()

    if modo == "IATA":
        dtype_map = {'IATA': str, 'Iata': str}
        id_col    = "Iata"
        allowed   = _IATA_UPDATABLE
    else:
        dtype_map = {'AWD': str}
        id_col    = "AWD"
        allowed   = _AWD_UPDATABLE

    if ext == '.csv':
        df = pd.read_csv(filepath, dtype=dtype_map)
    elif ext in ['.xls', '.xlsx']:
        df = pd.read_excel(filepath, dtype=dtype_map)
    else:
        raise ValueError("Formato no soportado. Usa CSV o Excel.")

    df.columns = df.columns.str.strip()

    # Normalizar nombre del ID si viene como 'IATA' en lugar de 'Iata'
    if modo == "IATA" and "IATA" in df.columns and "Iata" not in df.columns:
        df = df.rename(columns={"IATA": "Iata"})

    if id_col not in df.columns:
        raise ValueError(f"El archivo no contiene la columna '{id_col}'.")

    # Normalizar formato del ID
    if modo == "IATA":
        df[id_col] = df[id_col].astype(str).str.strip().str.zfill(8)
    else:
        df[id_col] = df[id_col].astype(str).str.strip()

    # Limpiar filas sin ID valido
    df = df[df[id_col].notna()]
    df = df[~df[id_col].isin(["", "nan", "None"])]
    df = df.drop_duplicates(subset=[id_col], keep='first')

    # Conservar solo el ID + columnas que existen en la tabla de destino
    # Columnas extra en el archivo (YEAR, COUNTRY, VENDOR, etc.) se descartan
    cols_en_archivo  = set(df.columns) - {id_col, "import_date"}
    cols_validas     = cols_en_archivo & allowed
    cols_ignoradas   = cols_en_archivo - allowed

    if cols_ignoradas:
        print(f"  Columnas ignoradas (no existen en la tabla): {sorted(cols_ignoradas)}")

    keep = [id_col] + sorted(cols_validas)
    df   = df[keep]

    if len(keep) == 1:
        raise ValueError(
            f"El archivo no contiene ninguna columna actualizable para modo {modo}.\n"
            f"Columnas validas: {sorted(allowed)}"
        )

    print(f"Archivo para actualizar ({modo}): {len(df)} registros | "
          f"columnas a actualizar: {sorted(cols_validas)}")
    return df
