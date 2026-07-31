"""
PestañaBarrido.py — Frame de la pestaña "Barrido"
Flujo: Seleccionar fecha → Extraer SQL + Filtrar → Lanzar exe → Subir resultado.
"""

import sys
import pathlib
import subprocess   # necesario para _lanzar_wizard() que abre el .exe compilado
import threading
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime

import pandas as pd

# ── Ajuste de sys.path para módulos de ambos proyectos ──────────────────────
_ROOT       = pathlib.Path(__file__).parent.parent          # raíz del repositorio
_CORE_DIR   = _ROOT / "core"
_SCRIPTS_DIR = _ROOT / "scripts"
for _p in [str(_ROOT), str(_CORE_DIR), str(_SCRIPTS_DIR)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

import data_logic as data_logic      # core/data_logic.py
import database as database          # core/database.py
from SQLExtraerIATA import extraerSQL as extraerSQL_IATA
from SQLExtraerAWD import extraerSQL as extraerSQL_AWD
from FiltraNuevosPre import filtrar_nuevos

# Rutas fijas referidas desde la raíz
_WIZARDS_DIR = _ROOT / "wizards"
_WORKSPACE_DIR = _ROOT / "workspace"
_BARRIDO_CSV_CANDIDATES = [
    _ROOT / "barrido.csv",
    _WIZARDS_DIR / "barrido.csv",
]

_MESES = [
    "01 - Enero", "02 - Febrero", "03 - Marzo", "04 - Abril",
    "05 - Mayo",  "06 - Junio",  "07 - Julio", "08 - Agosto",
    "09 - Sep",   "10 - Oct",    "11 - Nov",   "12 - Dic",
]


# ============================================================
#  Pestaña 2 — Barrido
# ============================================================
class PestanaBarrido(ttk.Frame):
    """
    Recibe el widget de log (tk.Text o compatible con .write()) del main
    para redirigir mensajes de progreso.
    """
    def __init__(self, parent, modo_var, log_widget, **kw):
        super().__init__(parent, **kw)
        self.modo_var = modo_var
        self._log = log_widget
        self._csv_sql: str = ""
        self._csv_nuevos: str = ""
        self._build()

    def _build(self):
        # ── Paso 1: Fecha ────────────────────────────────────────
        frm_top = ttk.LabelFrame(self, text=" Paso 1 — Fecha de extracción SQL ")
        frm_top.pack(fill="x", padx=20, pady=(16, 8))

        ttk.Label(frm_top, text="Booking_Date desde:").grid(
            row=0, column=0, padx=10, pady=10, sticky="w"
        )

        # ── Selector de fecha: 3 Spinbox (sin popup → no hay bug de cierre) ──
        _now = datetime.now()
        date_frame = ttk.Frame(frm_top)
        date_frame.grid(row=0, column=1, padx=6, pady=10, sticky="w")

        self._spin_anio = ttk.Spinbox(
            date_frame, from_=2000, to=2099, width=6,
            font=("Segoe UI", 10), wrap=False
        )
        self._spin_anio.set(_now.year)
        self._spin_anio.pack(side="left")

        ttk.Label(date_frame, text="-", font=("Segoe UI", 10)).pack(side="left")

        self._spin_mes = ttk.Spinbox(
            date_frame, values=_MESES, width=10,
            font=("Segoe UI", 10), wrap=True, state="readonly"
        )
        self._spin_mes.set(_MESES[_now.month - 1])
        self._spin_mes.pack(side="left")

        ttk.Label(date_frame, text="-", font=("Segoe UI", 10)).pack(side="left")

        self._spin_dia = ttk.Spinbox(
            date_frame, from_=1, to=31, width=4,
            font=("Segoe UI", 10), wrap=True
        )
        self._spin_dia.set(f"{_now.day:02d}")
        self._spin_dia.pack(side="left")

        self.btn_extraer = ttk.Button(
            frm_top, text="  Extraer + Filtrar",
            command=self._extraer_y_filtrar
        )
        self.btn_extraer.grid(row=1, column=0, columnspan=2, padx=10, pady=(0, 8), sticky="w")

        self.lbl_extraer_status = ttk.Label(frm_top, text="", font=("Segoe UI", 9))
        self.lbl_extraer_status.grid(
            row=2, column=0, columnspan=2, padx=10, pady=(0, 8), sticky="w"
        )

        # ── Paso 2: Lanzar Wizard ───────────────────────────────
        frm_mid = ttk.LabelFrame(self, text=" Paso 2 — Barrido con Wizard ")
        frm_mid.pack(fill="x", padx=20, pady=8)

        ttk.Label(
            frm_mid,
            text="Lanza el exe del barrido. Espera a que termine antes de continuar.",
            font=("Segoe UI", 9), foreground="#aaaaaa"
        ).pack(anchor="w", padx=10, pady=(6, 2))

        self.btn_wizard = ttk.Button(
            frm_mid, text="  Lanzar exe del barrido",
            command=self._lanzar_wizard, state="disabled"
        )
        self.btn_wizard.pack(anchor="w", padx=10, pady=(4, 10))

        # ── Paso 3: Procesar y Guardar resultado ─────────────────
        frm_bot = ttk.LabelFrame(self, text=" Paso 3 — Procesar y Guardar CSV ")
        frm_bot.pack(fill="x", padx=20, pady=8)

        ttk.Label(
            frm_bot,
            text="Se procesará 'barrido.csv' generado por el wizard para que le agregues el TIPO.",
            font=("Segoe UI", 9), foreground="#aaaaaa"
        ).pack(anchor="w", padx=10, pady=(6, 2))

        frm_bot_btns = ttk.Frame(frm_bot)
        frm_bot_btns.pack(anchor="w", padx=10, pady=(2, 6))

        self.btn_subir = ttk.Button(
            frm_bot_btns, text="  Procesar y Guardar",
            #command=self._subir_resultado, state="disabled" # para que se desbloquee el boton
            command=self._subir_resultado
        )
        self.btn_subir.pack(side="left")

        self.lbl_subir_status = ttk.Label(frm_bot, text="", font=("Segoe UI", 9))
        self.lbl_subir_status.pack(anchor="w", padx=10, pady=(0, 6))

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _get_fecha(self) -> str:
        """Devuelve la fecha seleccionada como string YYYY-MM-DD."""
        anio = int(self._spin_anio.get())
        mes  = int(self._spin_mes.get().split(" - ")[0])   # '03 - Marzo' → 3
        dia  = int(self._spin_dia.get())
        # Valida que la fecha sea real (lanza ValueError si no lo es)
        return datetime(anio, mes, dia).strftime("%Y-%m-%d")

    def _run_in_thread(self, fn):
        threading.Thread(target=fn, daemon=True).start()

    # ── Handlers ──────────────────────────────────────────────────────────────

    def _extraer_y_filtrar(self):
        try:
            fecha = self._get_fecha()
        except ValueError:
            from tkinter import messagebox as _mb
            _mb.showerror("Fecha inválida", "Usa el formato YYYY-MM-DD")
            return

        self.btn_extraer.config(state="disabled")
        self.btn_wizard.config(state="disabled")
        self.btn_subir.config(state="disabled")
        
        def _extraer_sql():
            modo = self.modo_var.get()
            try:
                self.lbl_extraer_status.config(text=f" Extrayendo desde SQL Server ({modo})...")
                self.update_idletasks()

                if modo == "IATA":
                    csv_sql = extraerSQL_IATA(fecha)
                else:
                    csv_sql = extraerSQL_AWD(fecha)

                self._csv_sql = csv_sql

                self.lbl_extraer_status.config(text=" Comparando con la Base de Datos...")
                self.update_idletasks()

                filtrar_nuevos(self._csv_sql, modo)

                self.after(0, lambda: self.btn_wizard.config(state="normal"))
                self.after(0, lambda: self.lbl_extraer_status.config(text=" Extraccion y filtrado completados."))
            except Exception as e:
                err = str(e)
                self.after(0, lambda: self.lbl_extraer_status.config(text=f" {err}"))
                self.after(0, lambda: messagebox.showerror("Error en extraccion", err))
            finally:
                self.after(0, lambda: self.btn_extraer.config(state="normal"))

        self._run_in_thread(_extraer_sql)

    def _lanzar_wizard(self):
        modo = self.modo_var.get()
        exe_path = _WIZARDS_DIR / "iataswizard-v3.exe" if modo == "IATA" else _WIZARDS_DIR / "AWD_mapeo_interfaz.exe"
        if not exe_path.exists():
            messagebox.showerror("Error", f"No se encontró el ejecutable:\n{exe_path}")
            return
        
        try:
            subprocess.Popen(str(exe_path))
            self.btn_subir.config(state="normal")
            self.lbl_extraer_status.config(text=f" Wizard de {modo} en ejecución.")
        except Exception as e:
            messagebox.showerror("Error al lanzar Wizard", str(e))

    def _subir_resultado(self):
        modo = self.modo_var.get()
        csv_path = None
        
        if modo == "IATA":
            candidates = _BARRIDO_CSV_CANDIDATES
        else:
            candidates = []
            # El Wizard de AWD genera nombres con prefijos dinámicos (Ej. AWD_barrido-2026-04-09.csv)
            for directory in [_ROOT, _WIZARDS_DIR]:
                candidates.extend(list(directory.glob("AWD_barrido*.csv")))
                candidates.extend(list(directory.glob("barrido_awd*.csv")))
                
            # Ordenamos por fecha de modificación para tomar el más reciente
            candidates.sort(key=lambda x: x.stat().st_mtime, reverse=True)

        for path in candidates:
            if path.exists():
                csv_path = path
                break

        if not csv_path:
            messagebox.showerror("Atención", f"Aún no existe el archivo de resultados del Wizard ({modo}).\nCompleta el barrido primero.")
            return

        try:
            self.lbl_subir_status.config(text=f" Procesando {csv_path.name} ({modo})…")
            self.update_idletasks()
            out_dir = _WORKSPACE_DIR / "Listo_para_subir"
            out_dir.mkdir(exist_ok=True, parents=True)
            
            if modo == "IATA":
                df = data_logic.process_barrido_file(str(csv_path))
                out_name = out_dir / "barrido_Iatas_para_completar_tipo.csv"
                msg_info = f"Abre '{out_name.name}', rellena la columna 'Tipo' y súbelo desde la Pestaña Subir."
            else:
                df = data_logic.process_awd_file(str(csv_path), is_barrido=True)
                out_name = out_dir / "barrido_awd_procesado.csv"
                msg_info = f"Abre '{out_name.name}', rellena las columnas 'Corporativo' y 'auto_sustituto',\ny luego súbelo desde la Pestaña Subir."
                
            rows = len(df)
            confirm = messagebox.askyesno(
                "Confirmar guardado",
                f"Modo: {modo}\nSe detectaron {rows} registros listos en {csv_path.name}.\n"
                "¿Deseas procesarlos y guardarlos localmente?"
            )
            if confirm:
                df.to_csv(out_name, index=False, encoding="utf-8-sig")
                
                self.lbl_subir_status.config(
                    text=f" {rows} registros guardados en {out_name.name}"
                )
                messagebox.showinfo("Éxito", f"¡Archivo procesado!\n\n{msg_info}")
        except Exception as e:
            self.lbl_subir_status.config(text=" Error al procesar")
            messagebox.showerror("Error al procesar", str(e))
