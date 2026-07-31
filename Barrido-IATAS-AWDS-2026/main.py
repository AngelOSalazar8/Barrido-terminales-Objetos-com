"""
main.py — Launcher integrado IATA 2026
Punto de entrada único. Solo contiene la ventana principal (App).
Las pestañas están en Pestañas/PestañaSubir.py y Pestañas/PestañaBarrido.py.
"""

import sys
import pathlib
import tkinter as tk
from tkinter import ttk

import sv_ttk

# ── Agrega la carpeta components al path para poder importar los módulos ──────
_ROOT      = pathlib.Path(__file__).parent
_TABS_DIR  = _ROOT / "components"
if str(_TABS_DIR) not in sys.path:
    sys.path.insert(0, str(_TABS_DIR))

from PestañaSubir   import PestanaSubir    # noqa: E402
from PestañaBarrido import PestanaBarrido  # noqa: E402


# ============================================================
#  Utilidad: redirige print() al widget Text de log
# ============================================================
class _TextLogger:
    """Redirige stdout al widget Text del panel de log."""
    def __init__(self, widget: tk.Text):
        self._widget = widget
        self._orig   = sys.stdout

    def write(self, msg: str):
        self._widget.configure(state="normal")
        self._widget.insert(tk.END, msg)
        self._widget.see(tk.END)
        self._widget.configure(state="disabled")
        self._orig.write(msg)

    def flush(self):
        self._orig.flush()


# ============================================================
#  Ventana principal
# ============================================================
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("IATAs 2026")
        self.geometry("640x580")
        self.resizable(True, True)
        sv_ttk.set_theme("dark")
        self._build()

    def _build(self):
        # ── Log compartido (construido antes que las pestañas) ──
        log_frame = ttk.LabelFrame(self, text=" Log de actividad ")
        log_frame.pack(side="bottom", fill="x", padx=10, pady=6)

        log_text = tk.Text(
            log_frame, height=7, state="disabled",
            font=("Consolas", 8), bg="#111111", fg="#cccccc",
            relief="flat", wrap="word"
        )
        scroll = ttk.Scrollbar(log_frame, orient="vertical", command=log_text.yview)
        log_text.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        log_text.pack(fill="both", expand=True, padx=4, pady=4)

        self._logger = _TextLogger(log_text)
        sys.stdout = self._logger

        # ── Modo Operativo (Selector IATA / AWD) ────────────────
        modo_frame = ttk.Frame(self)
        modo_frame.pack(fill="x", padx=10, pady=(10, 0))
        
        self.modo_var = tk.StringVar(value="IATA")
        
        ttk.Label(modo_frame, text="Modo Operativo:", font=("Segoe UI", 10, "bold")).pack(side="left")
        ttk.Radiobutton(modo_frame, text="IATA", variable=self.modo_var, value="IATA").pack(side="left", padx=(10, 0))
        ttk.Radiobutton(modo_frame, text="AWD", variable=self.modo_var, value="AWD").pack(side="left", padx=10)

        # ── Notebook (pestañas) ─────────────────────────────────
        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True, padx=10, pady=(10, 0))

        tab_subir   = PestanaSubir(notebook, modo_var=self.modo_var)
        tab_barrido = PestanaBarrido(notebook, log_widget=self._logger, modo_var=self.modo_var)

        notebook.add(tab_subir,   text="    Subir Datos  ")
        notebook.add(tab_barrido, text="    Barrido  ")

    def destroy(self):
        sys.stdout = self._logger._orig
        super().destroy()


if __name__ == "__main__":
    app = App()
    app.mainloop()
