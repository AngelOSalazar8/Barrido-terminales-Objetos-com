"""
PestañaSubir.py — Frame de la pestaña "Subir Datos"

Soporta dos acciones:
  - Insertar nuevos: flujo original. Si hay duplicados, ofrece exportarlos.
  - Actualizar existentes: carga un archivo, verifica que los IDs existan
    en la BD y hace UPDATE en los campos que vengan en el archivo.
    No modifica import_date.
"""

import os
import sys
import pathlib
from datetime import datetime
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

# ── Ajuste de sys.path ────────────────────────────────────────────────────────
_ROOT     = pathlib.Path(__file__).parent.parent
_CORE_DIR = _ROOT / "core"
_PARA_ACTUALIZAR_DIR = _ROOT / "workspace" / "Para_Actualizar"

for _p in [str(_ROOT), str(_CORE_DIR)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

import data_logic
import database


# ============================================================
#  Pestaña 1 — Subir / Actualizar
# ============================================================
class PestanaSubir(ttk.Frame):
    def __init__(self, parent, modo_var, **kw):
        super().__init__(parent, **kw)
        self.modo_var       = modo_var
        self.file_path      = ""
        self._df_duplicados = None   # duplicados capturados en modo Insertar
        self._build()

    def _build(self):
        # ── Accion: Insertar / Actualizar ────────────────────────
        frm_accion = ttk.LabelFrame(self, text=" Accion ")
        frm_accion.pack(fill="x", padx=20, pady=(16, 6))

        self.accion_var = tk.StringVar(value="insertar")
        ttk.Radiobutton(
            frm_accion, text="Insertar nuevos",
            variable=self.accion_var, value="insertar",
            command=self._on_accion_change
        ).pack(side="left", padx=16, pady=8)
        ttk.Radiobutton(
            frm_accion, text="Actualizar existentes",
            variable=self.accion_var, value="actualizar",
            command=self._on_accion_change
        ).pack(side="left", padx=6, pady=8)

        # ── Selector de archivo ──────────────────────────────────
        ttk.Label(self, text="Selecciona el archivo Excel/CSV con las IATAs/AWDs",
                  font=("Segoe UI", 11)).pack(pady=(10, 4))

        self.lbl_filename = ttk.Label(
            self, text="Sin archivo seleccionado...",
            font=("Segoe UI", 10, "italic"), foreground="#888888"
        )
        self.lbl_filename.pack(pady=4)

        btn_frame = ttk.Frame(self)
        btn_frame.pack(pady=8)

        ttk.Button(btn_frame, text="  Seleccionar archivo",
                   command=self._select_file).pack(side="left", padx=6)

        self.btn_upload = ttk.Button(
            btn_frame, text="  Procesar y Subir",
            command=self._dispatch, state="disabled"
        )
        self.btn_upload.pack(side="left", padx=6)

        self.lbl_status = ttk.Label(self, text="", font=("Segoe UI", 9))
        self.lbl_status.pack(pady=4)

        # ── Panel de duplicados (oculto hasta que aparezcan) ─────
        self.frm_dupes = ttk.LabelFrame(
            self, text=" Registros ya existentes detectados "
        )
        # No se llama pack() aqui — se muestra dinamicamente

        self.lbl_dupes_info = ttk.Label(
            self.frm_dupes, text="", font=("Segoe UI", 9), foreground="#aaaaaa"
        )
        self.lbl_dupes_info.pack(padx=10, pady=(6, 2), anchor="w")

        self.btn_exportar = ttk.Button(
            self.frm_dupes, text="  Exportar duplicados para revisar",
            command=self._exportar_duplicados
        )
        self.btn_exportar.pack(padx=10, pady=(2, 10), anchor="w")

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _on_accion_change(self):
        if self.accion_var.get() == "actualizar":
            self.btn_upload.config(text="  Cargar y Actualizar")
        else:
            self.btn_upload.config(text="  Procesar y Subir")
        self._hide_dupes_panel()

    def _dispatch(self):
        """Enruta al metodo correcto segun la accion seleccionada."""
        if self.accion_var.get() == "actualizar":
            self._cargar_y_actualizar()
        else:
            self._procesar_y_subir()

    def _show_dupes_panel(self, count, modo):
        self.lbl_dupes_info.config(
            text=f"{count} registro(s) {modo} ya existen en la BD. "
                 "Exportalos, edita los campos que deseas cambiar y "
                 "subelos en modo 'Actualizar existentes'."
        )
        self.frm_dupes.pack(fill="x", padx=20, pady=(0, 8))

    def _hide_dupes_panel(self):
        self.frm_dupes.pack_forget()
        self._df_duplicados = None

    def _select_file(self):
        path = filedialog.askopenfilename(
            title="Seleccionar archivo",
            filetypes=[("Excel/CSV", "*.xlsx *.xls *.csv"), ("Todos", "*.*")]
        )
        if path:
            self.file_path = path
            self.lbl_filename.config(text=os.path.basename(path), foreground="#e0e0e0")
            self.btn_upload.config(state="normal")
            self.lbl_status.config(text="")
            self._hide_dupes_panel()

    # ── Modo Insertar ─────────────────────────────────────────────────────────

    def _procesar_y_subir(self):
        if not self.file_path:
            return
        modo = self.modo_var.get()
        try:
            self.lbl_status.config(text=f" Procesando archivo como {modo}...")
            self.update_idletasks()
            self._hide_dupes_panel()

            if modo == "IATA":
                df     = data_logic.process_file(self.file_path)
                tbl    = "Iata"
                id_col = "Iata"
            else:
                df     = data_logic.process_awd_file(self.file_path)
                tbl    = "AWD"
                id_col = "AWD"

            self.lbl_status.config(text=" Validando duplicados en BD...")
            self.update_idletasks()

            df_new     = database.get_new_records(df, table_name=tbl, id_col=id_col)
            rows_total = len(df)
            rows_new   = len(df_new)
            rows_dupes = rows_total - rows_new

            # Capturar duplicados y mostrar panel si los hay
            if rows_dupes > 0:
                df_dupes = df[~df[id_col].isin(df_new[id_col])].copy()
                # Quitar import_date del export — no es relevante para actualizacion
                cols_exp = [c for c in df_dupes.columns if c != "import_date"]
                self._df_duplicados = df_dupes[cols_exp]
                self._show_dupes_panel(rows_dupes, modo)

            if rows_new == 0:
                messagebox.showwarning(
                    "Atencion",
                    f"Todos los registros ({modo}) ya existen en la BD.\n"
                    "No se insertara ningun registro.\n\n"
                    "Puedes exportarlos con el boton de abajo y subirlos "
                    "en modo 'Actualizar existentes'."
                )
                self.lbl_status.config(text=" Archivo omitido (todos duplicados).")
                return

            confirm = messagebox.askyesno(
                "Confirmar subida",
                f"MODO: {modo}\nSe detectaron {rows_total} registros en total:\n"
                f"  {rows_new} Nuevos para insertar\n"
                f"  {rows_dupes} Ya existentes (se omitiran)\n\n"
                f"¿Deseas subir los {rows_new} registros nuevos a la BD ({tbl})?"
            )
            if confirm:
                database.upload_data(df_new, table_name=tbl)
                self.lbl_status.config(text=f" {rows_new} subidos | {rows_dupes} omitidos")
                messagebox.showinfo(
                    "Exito",
                    f"Carga completada ({modo})!\n\nRegistros nuevos agregados: {rows_new}"
                )
        except Exception as e:
            self.lbl_status.config(text=" Error — revisa el log")
            messagebox.showerror("Error Critico", str(e))

    def _exportar_duplicados(self):
        """Guarda los duplicados capturados en workspace/Para_Actualizar/."""
        if self._df_duplicados is None or self._df_duplicados.empty:
            messagebox.showwarning("Sin datos", "No hay duplicados para exportar.")
            return
        try:
            _PARA_ACTUALIZAR_DIR.mkdir(parents=True, exist_ok=True)
            modo  = self.modo_var.get()
            fecha = datetime.now().strftime("%d-%m-%Y_%H%M")
            out   = _PARA_ACTUALIZAR_DIR / f"duplicados_{modo}-{fecha}.csv"
            self._df_duplicados.to_csv(out, index=False, encoding="utf-8-sig")
            messagebox.showinfo(
                "Exportado",
                f"Archivo guardado:\n{out}\n\n"
                "Abrelo, edita los campos que deseas cambiar y subelo "
                "en modo 'Actualizar existentes'."
            )
        except Exception as e:
            messagebox.showerror("Error al exportar", str(e))

    # ── Modo Actualizar ───────────────────────────────────────────────────────

    def _cargar_y_actualizar(self):
        """Lee el archivo, verifica existencia en BD y hace UPDATE."""
        if not self.file_path:
            return
        modo = self.modo_var.get()
        try:
            self.lbl_status.config(text=f" Leyendo archivo para actualizar ({modo})...")
            self.update_idletasks()

            df = data_logic.process_file_for_update(self.file_path, modo)

            if modo == "IATA":
                tbl    = "Iata"
                id_col = "Iata"
            else:
                tbl    = "AWD"
                id_col = "AWD"

            cols_upd = [c for c in df.columns if c not in (id_col, "import_date")]

            self.lbl_status.config(text=" Verificando cuales existen en BD...")
            self.update_idletasks()

            df_existing   = database.get_existing_records(df, table_name=tbl, id_col=id_col)
            rows_total    = len(df)
            rows_existing = len(df_existing)
            rows_skip     = rows_total - rows_existing

            if rows_existing == 0:
                messagebox.showwarning(
                    "Atencion",
                    f"Ninguno de los {rows_total} registros del archivo existe en la BD.\n"
                    "No hay nada que actualizar.\n\n"
                    "Verifica que el archivo tenga el modo correcto (IATA / AWD)."
                )
                self.lbl_status.config(text=" Sin registros para actualizar.")
                return

            confirm = messagebox.askyesno(
                "Confirmar actualizacion",
                f"MODO: {modo} — Actualizar\n\n"
                f"Registros en el archivo : {rows_total}\n"
                f"  {rows_existing} Existen en BD  →  se actualizaran\n"
                f"  {rows_skip} No existen en BD  →  se omitiran\n\n"
                f"Columnas a actualizar:\n  {', '.join(cols_upd)}\n\n"
                "NOTA: import_date no se modifica.\n\n"
                "¿Confirmas la actualizacion?"
            )
            if confirm:
                updated = database.update_records(
                    df_existing, table_name=tbl, id_col=id_col, cols_to_update=cols_upd
                )
                self.lbl_status.config(text=f" {updated} registros actualizados.")
                messagebox.showinfo(
                    "Exito",
                    f"Actualizacion completada ({modo})!\n\n"
                    f"Registros actualizados : {updated}\n"
                    f"Omitidos (no existen)  : {rows_skip}"
                )
        except Exception as e:
            self.lbl_status.config(text=" Error — revisa el log")
            messagebox.showerror("Error Critico", str(e))
