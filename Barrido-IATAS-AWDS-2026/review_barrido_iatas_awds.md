# Review del Proyecto: Barrido IATAS-AWDS 2026

## Estado General

El proyecto **funciona correctamente** en su flujo principal. Es una app de escritorio en Python+Tkinter con `sv_ttk` dark mode que:
1. Extrae IATAs o AWDs desde SQL Server
2. Filtra los que ya existen en la BD destino
3. Lanza un `.exe` wizard (BZWhll/Amadeus) para hacer el barrido GDS
4. Procesa el resultado y lo guarda listo para subir
5. Sube los registros nuevos a la BD de destino

---

## Pendientes Identificados en las Notas (`notas.txt`)

> [!IMPORTANT]
> Estas son las tareas que quedaron abiertas cuando dejaste el proyecto hace meses.

| # | Pendiente | Archivo afectado | Estado |
|---|-----------|-----------------|--------|
| 1 | **Agregar la columna `TIPO`** al archivo de barrido IATA antes de subirlo | `data_logic.py` → `process_barrido_file()` | La columna se crea como `None` — el usuario debe llenarla manualmente en el CSV antes de subir |
| 2 | **Recompilar el exe del barrido** para solucionar un bug de Tkinter | `wizards/iataswizard-v3.py` | El `.exe` actual podría tener el bug de cierre de ventana. El `.py` ya tiene el fix (usa Spinbox en vez de DatePicker) pero habría que recompilar con PyInstaller |
| 3 | **Consultar con Gabo** si se deben agregar los grupos que no existen o si mejor no sobreescribir los grupos que ya están | `data_logic.py` → `process_barrido_file()` | Actualmente el código **sobreescribe** el grupo con la lógica de `calcular_grupo()` — si Gabo decidió que no debe sobreescribir, habría que ajustarlo |
| 4 | **Asegurarse que los AWDs sean correctos** (formateo de 7 dígitos) | `data_logic.py` → `process_awd_file()` | Ya implementado: se recorta el 6to carácter automáticamente con confirmación del usuario |

---

## Arquitectura del Proyecto

```
Barrido-IATAS-AWDS-2026/
├── main.py                    # Launcher principal (sv_ttk dark)
├── Config/
│   ├── CredencialesDBServ4.json      # BD origen (Reservaciones)
│   ├── CredencialesSVRdbpricing.json # BD destino (IATAs/AWDs)
│   └── reglas_grupo_IATAS.json       # Reglas de clasificacion por grupo
├── components/
│   ├── PestañaBarrido.py      # Pestaña del flujo de barrido (3 pasos)
│   └── PestañaSubir.py        # Pestaña de subida directa de archivo
├── core/
│   ├── data_logic.py          # Logica de transformacion de datos
│   └── database.py            # Conexion y operaciones con SQL Server
├── scripts/
│   ├── SQLExtraerIATA.py      # Extrae IATAs desde dbAreaCorp via pyodbc
│   ├── SQLExtraerAWD.py       # Extrae AWDs desde dbAreaCorp via pyodbc
│   ├── FiltraNuevosPre.py     # Filtra los nuevos vs BD destino (SQLAlchemy)
│   └── requirements.txt       # pandas, pyodbc, numpy, pywin32
├── wizards/
│   ├── iataswizard-v3.exe     # Compilado 32-bit — barrido IATA via BZWhll
│   ├── iataswizard-v3.py      # Fuente del exe anterior
│   ├── AWD_mapeo_interfaz.exe # Compilado — barrido AWD via BZWhll
│   └── AWD_mapeo_interfaz.py  # Fuente del exe anterior
└── workspace/
    ├── Desde_sql/             # CSVs generados por los scripts SQL
    ├── Filtro_Nuevos/         # CSVs de IATAs/AWDs nuevos (input para wizard)
    └── Listo_para_subir/      # CSVs procesados listos para la BD
```

---

## Flujo Operativo (el correcto)

```
[Paso 1] Seleccionar fecha → "Extraer + Filtrar"
         ├─ SQLExtraerIATA/AWD.py → workspace/Desde_sql/
         └─ FiltraNuevosPre.py   → workspace/Filtro_Nuevos/

[Paso 2] "Lanzar exe del barrido"
         ├─ IATA: iataswizard-v3.exe  → selecciona el CSV de Filtro_Nuevos/
         └─ AWD:  AWD_mapeo_interfaz.exe → selecciona el CSV de Filtro_Nuevos/
         └─ El wizard genera: barrido.csv (IATA) o AWD_barrido-YYYY-MM-DD.csv (AWD)

[Paso 3] "Procesar y Guardar"
         └─ workspace/Listo_para_subir/
              ├─ barrido_Iatas_para_completar_tipo.csv   (abrirlo y llenar Tipo)
              └─ barrido_awd_procesado.csv               (abrirlo y llenar Corporativo + auto_sustituto)

[Paso 4] Pestaña "Subir Datos"
         └─ Seleccionar el archivo completado → "Procesar y Subir"
```

---

## Bugs / Problemas Conocidos

> [!WARNING]
> Revisa estos puntos antes de correrlo.

### 1. `iataswizard-v3.exe` puede tener el bug de Tkinter (ventana no cierra bien)
- El `.py` fuente ya fue corregido (cambio de `DatePicker` a `Spinbox` triple)
- El `.exe` actual en `wizards/` fue compilado **antes** de ese fix
- **Accion requerida:** Recompilar si el wizard sigue sin cerrar correctamente

### 2. El boton "Procesar y Guardar" esta desbloqueado aunque no se corra el wizard
- En `PestañaBarrido.py` linea 142-143 se ve un comentario que dice `# para que se desbloquee el boton`
- El `state="disabled"` fue comentado intencionalmente durante pruebas — no deberia quedarse asi en produccion
- **Accion requerida:** Decidir si reenables el bloqueo del boton o lo dejas libre (actualmente libre = permite procesar sin haber corrido el wizard)

### 3. `AWD_mapeo_interfaz.py` no usa sv_ttk (interfaz vieja sin dark mode)
- Este wizard fue el original y no fue actualizado como el de IATA
- No tiene manejo de errores en `clickedGenerar()` (si el filename esta vacio, llama igualmente a `BarridoAwdWizard('')` y truena)
- El `.exe` ya compilado lo encapsula, pero si lo recompilas habria que arreglar eso

### 4. `requirements.txt` incompleto — faltan `sqlalchemy` y `sv_ttk`
- El archivo solo lista: `pandas`, `pyodbc`, `numpy`, `pywin32`
- Pero el proyecto usa: `sqlalchemy` (en `database.py` y `FiltraNuevosPre.py`) y `sv_ttk` (en `main.py`)
- **Accion requerida:** Actualizar `requirements.txt`

### 5. La tabla AWD en `FiltraNuevosPre.py` se llama `dbo.awd` (minusculas)
- En linea 38: `tbl = "dbo.awd"` — si la tabla en SQL Server es sensible a mayusculas, podria fallar
- En `database.py` → `upload_data()` se usa `table_name="AWD"` → asegurate de que coincida

---

## Recomendaciones para Correrlo Hoy

1. **Verifica las credenciales** en `Config/CredencialesDBServ4.json` (BD origen) y `Config/CredencialesSVRdbpricing.json` (BD destino) — los servidores podrian haber cambiado o las credenciales expirado

2. **Instala las dependencias faltantes** si cambias de equipo:
   ```bash
   pip install pandas pyodbc numpy pywin32 sqlalchemy sv_ttk openpyxl
   ```

3. **Corre el launcher** (requiere Python 64-bit para la UI):
   ```bash
   python main.py
   ```
   - Los wizards `.exe` ya estan compilados en 32-bit para BZWhll — no los ejecutes directamente, usa el launcher

4. **Para IATA:** despues del Paso 3, abre `barrido_Iatas_para_completar_tipo.csv`, llena la columna `Tipo` y luego ve a la pestaña Subir

5. **Para AWD:** despues del Paso 3, abre `barrido_awd_procesado.csv`, llena las columnas `Corporativo` y `auto_sustituto`, y luego sube

---

## Deuda Tecnica Menor

| Archivo | Observacion |
|---------|-------------|
| `iataswizard-v3.py` | La lista `AGRUPACION` esta duplicada con la logica de `reglas_grupo_IATAS.json`. Podria unificarse en el futuro |
| `AWD_mapeo_interfaz.py` | Usa `from tkinter import *` (wildcard import), estilo antiguo |
| `AWD_mapeo_wizard.py` | No fue revisado — podria ser una version alternativa o descartada |
| `db/` | Contiene solo archivos SQL (`.sql`), el nombre de la carpeta es un poco confuso vs `core/database.py` |
