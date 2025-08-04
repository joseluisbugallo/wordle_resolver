import tkinter as tk
from tkinter import ttk, messagebox
import json
from collections import Counter, defaultdict
import threading
import os
import sys
import webbrowser
import urllib.request

# --- Versión de la aplicación ---
__version__ = "1.4.0"

def resource_path(relative_path):
    """ Obtiene la ruta absoluta al recurso, funciona para desarrollo y para PyInstaller """
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

# --- Carga de Diccionario ---
try:
    with open(resource_path("palabras.json"), encoding="utf-8") as f:
        diccionario_es = json.load(f)
except FileNotFoundError:
    messagebox.showerror("Error Crítico", "No se encontró el archivo 'palabras.json'. La aplicación no puede funcionar sin él.")
    sys.exit()
except Exception as e:
    messagebox.showerror("Error Crítico", f"No se pudo cargar el diccionario 'palabras.json':\n{e}")
    sys.exit()

# --- Lógica de Búsqueda (Sin Cambios) ---
def generar_palabras(patron, min_counts, exact_counts, letras_descartadas, posiciones_prohibidas, diccionario):
    longitud = len(patron)
    palabras_posibles = []
    for palabra in diccionario:
        if any(letra in palabra for letra in letras_descartadas if letra not in exact_counts):
            continue
        palabra_valida = True
        palabra_counter = Counter(palabra)
        for i in range(longitud):
            if patron[i] != '_' and patron[i] != palabra[i]:
                palabra_valida = False
                break
            letra_actual = palabra[i]
            if letra_actual in posiciones_prohibidas and i in posiciones_prohibidas[letra_actual]:
                palabra_valida = False
                break
        if not palabra_valida: continue
        todas_letras_restringidas = set(min_counts.keys()) | set(exact_counts.keys()) | letras_descartadas
        for letra in todas_letras_restringidas:
            if letra in exact_counts:
                if palabra_counter[letra] != exact_counts[letra]:
                    palabra_valida = False
                    break
            elif letra in min_counts:
                if palabra_counter[letra] < min_counts[letra]:
                    palabra_valida = False
                    break
            elif letra in letras_descartadas:
                if palabra_counter[letra] > 0:
                    palabra_valida = False
                    break
        if not palabra_valida: continue
        palabras_posibles.append(palabra)
    return palabras_posibles

def sugerir_letras(palabras):
    contador = Counter()
    for palabra in palabras:
        contador.update(set(palabra))
    return contador.most_common()

def mejores_palabras(palabras, letras_mas_frecuentes):
    ranking = []
    for palabra in palabras:
        letras_unicas = set(palabra)
        score = len(letras_unicas)
        frecuencia = sum(letras_mas_frecuentes.get(l, 0) for l in letras_unicas)
        ranking.append((frecuencia, score, palabra))
    ranking.sort(reverse=True)
    return [p for _, _, p in ranking[:10]]


# --- Clase principal de la aplicación ---
class WordleSolverApp:
    def __init__(self, root):
        self.root = root
        self.root.title(f"Wordle Solver en Español v{__version__}")
        self.root.geometry("1000x750")

        try:
            icon_path = resource_path("icon.ico")
            self.root.iconbitmap(icon_path)
        except Exception as e:
            print(f"Advertencia: No se pudo cargar el icono de la aplicacion: {e}")

        self.root.resizable(True, True)
        self.root.configure(bg="#121212")

        self.style = ttk.Style()
        self.style.theme_use("clam")

        self.states = ['absent', 'present', 'correct']
        self.colors = {'absent': '#787c7e', 'present': '#c9b458', 'correct': '#6aaa64', 'text': 'white'}

        self.grid_cells = []
        self.palabra_longitud = 5
        self.num_intentos = 6

        self.create_widgets()
        self.update_grid_colors()

        threading.Thread(target=self.check_for_updates, daemon=True).start()

    def create_widgets(self):
        self.root.grid_columnconfigure(0, weight=1, uniform="group1")
        self.root.grid_columnconfigure(1, weight=1, uniform="group1")
        self.root.grid_rowconfigure(0, weight=1)

        control_frame = ttk.Frame(self.root, padding="15", style="Dark.TFrame")
        control_frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        control_frame.grid_rowconfigure(2, weight=1) # Ajuste para el teclado
        control_frame.grid_columnconfigure(0, weight=1)

        result_frame = ttk.Frame(self.root, padding="15", style="Dark.TFrame")
        result_frame.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)
        result_frame.grid_rowconfigure(0, weight=1)
        result_frame.grid_columnconfigure(0, weight=1)

        self.resultado = tk.Text(result_frame, height=25, width=40, wrap="word", padx=10, pady=10, font=("Consolas", 14), relief="flat")
        self.resultado.grid(row=0, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(result_frame, command=self.resultado.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.resultado.config(yscrollcommand=scrollbar.set)

        top_buttons_frame = ttk.Frame(control_frame, style="Dark.TFrame")
        top_buttons_frame.grid(row=0, column=0, sticky="ew", pady=(0, 20))
        top_buttons_frame.grid_columnconfigure(0, weight=1)
        top_buttons_frame.grid_columnconfigure(1, weight=1)
        top_buttons_frame.grid_columnconfigure(2, weight=0)

        self.search_button = ttk.Button(top_buttons_frame, text="🚀 Buscar Palabras", command=self.ejecutar_busqueda_threaded, style="Accent.TButton")
        self.search_button.grid(row=0, column=0, padx=5, sticky="ew")

        self.reset_button = ttk.Button(top_buttons_frame, text="🧹 Limpiar", command=self.reset_grid)
        self.reset_button.grid(row=0, column=1, padx=5, sticky="ew")

        self.help_button = ttk.Button(top_buttons_frame, text="?", command=self.show_help, width=3)
        self.help_button.grid(row=0, column=2, padx=(10, 5), sticky="e")

        self.grid_frame = ttk.Frame(control_frame, style="Dark.TFrame")
        self.grid_frame.grid(row=1, column=0, sticky="n")
        self.create_wordle_grid()
        
        self.spinner_label = ttk.Label(control_frame, text="Introduce un intento o pulsa 'Buscar' para empezar.", anchor="center", wraplength=400, justify="center", style="Dark.TLabel")
        self.spinner_label.grid(row=2, column=0, sticky="s", pady=(20, 0))


        self.configure_styles()

    def configure_styles(self):
        self.style.configure("TButton", font=("Segoe UI", 12), padding=10)
        self.style.configure("Accent.TButton", font=("Segoe UI", 12, "bold"), foreground="white", background="#0078d4")
        self.style.map("Accent.TButton", background=[('active', '#005a9e')])
        
        self.style.configure("Dark.TFrame", background="#121212")
        self.style.configure("Dark.TLabel", foreground="white", background="#121212", font=("Segoe UI", 10))

        self.resultado.configure(bg="#2d2d2d", fg="#cccccc", insertbackground="white")
        self.style.configure("TScrollbar", troughcolor="#2d2d2d", background="#555555", arrowcolor="white")
        self.style.map("TScrollbar", background=[('active', '#666666')])


    def create_wordle_grid(self):
        validate_cmd = self.root.register(lambda text: len(text) <= 1)
        self.grid_cells = []
        for r in range(self.num_intentos):
            row_list = []
            self.grid_frame.grid_rowconfigure(r, weight=1)
            for c in range(self.palabra_longitud):
                self.grid_frame.grid_columnconfigure(c, weight=1)

                cell_container = tk.Frame(self.grid_frame, bg="#121212")
                cell_container.grid(row=r, column=c, padx=4, pady=4, sticky="nsew")
                cell_container.grid_rowconfigure(0, weight=1)
                cell_container.grid_columnconfigure(0, weight=1)

                cell_entry = tk.Entry(
                    cell_container, width=2, font=("Segoe UI", 24, "bold"),
                    justify='center', relief="flat", validate="key",
                    validatecommand=(validate_cmd, '%P')
                )
                cell_entry.grid(row=0, column=0, sticky="nsew", ipady=10)

                state_indicator = tk.Frame(cell_container, height=4, cursor="hand2")
                state_indicator.grid(row=1, column=0, sticky="sew", padx=1, pady=(2, 1))

                cell_data = {'widget': cell_entry, 'state': 'absent', 'indicator': state_indicator}
                row_list.append(cell_data)

                # --- MODIFICADO: Controles de clic específicos ---
                # Clic DERECHO en la casilla de texto para cambiar estado
                cell_entry.bind("<Button-3>", lambda e, row=r, col=c: self.on_cell_click(row, col))
                # Clic IZQUIERDO en el indicador inferior para cambiar estado
                state_indicator.bind("<Button-1>", lambda e, row=r, col=c: self.on_cell_click(row, col))
                
                cell_entry.bind("<KeyRelease>", lambda e, row=r, col=c: self.on_key_release(e, row, col))
            self.grid_cells.append(row_list)

    def show_help(self):
        # --- MODIFICADO: Texto de ayuda actualizado para reflejar los nuevos controles ---
        help_text = """
INSTRUCCIONES DE USO

1. Escribe tus intentos en la parrilla o deja la parrilla vacía
   y pulsa 'Buscar' para ver las mejores palabras iniciales.

2. Cambia el estado de cada letra de dos maneras:
   • Haz CLIC DERECHO sobre la propia letra.
   • Haz CLIC IZQUIERDO en la barra de color de debajo.

   El ciclo de colores es: GRIS → AMARILLO → VERDE.

3. Pulsa "Buscar Palabras" para ver las sugerencias.

4. ¡Haz clic en una palabra sugerida para colocarla
   automáticamente en la siguiente fila vacía!
"""
        messagebox.showinfo("Ayuda - Wordle Solver", help_text)

    def on_cell_click(self, row, col):
        cell_data = self.grid_cells[row][col]
        current_state_index = self.states.index(cell_data['state'])
        next_state_index = (current_state_index + 1) % len(self.states)
        cell_data['state'] = self.states[next_state_index]
        self.update_grid_colors()

    def update_grid_colors(self):
        for row_data in self.grid_cells:
            for cell_data in row_data:
                widget = cell_data['widget']
                state = cell_data['state']
                indicator = cell_data['indicator']
                bg_color = self.colors[state]
                text_color = self.colors['text']
                widget.config(bg=bg_color, fg=text_color, insertbackground=text_color)
                indicator.config(bg=bg_color)

    def reset_grid(self):
        self.resultado.config(state=tk.NORMAL)
        self.resultado.delete(1.0, tk.END)
        self.resultado.config(state=tk.DISABLED)
        for row in self.grid_cells:
            for cell_data in row:
                cell_data['widget'].delete(0, tk.END)
                cell_data['state'] = 'absent'
        self.update_grid_colors()
        self.spinner_label.config(text="Introduce un intento o pulsa 'Buscar' para empezar.")
        if self.grid_cells:
            self.grid_cells[0][0]['widget'].focus_set()

    def on_key_release(self, event, row, col):
        widget = self.grid_cells[row][col]['widget']
        current_text = widget.get()
        if not current_text: return

        widget.delete(0, tk.END)
        widget.insert(0, current_text.upper())
        if event.char.isalpha() and col < self.palabra_longitud - 1:
            self.grid_cells[row][col+1]['widget'].focus_set()

        if event.char.isalpha():
            self._heredar_estado_verde(row, col)
            self.update_grid_colors()

    def _heredar_estado_verde(self, row, col):
        for r_prev in range(row):
            if self.grid_cells[r_prev][col]['state'] == 'correct':
                self.grid_cells[row][col]['state'] = 'correct'
                break

    def _find_next_empty_row(self):
        for i, row in enumerate(self.grid_cells):
            if not row[0]['widget'].get():
                return i
        return -1

    def on_suggestion_click(self, word):
        target_row_index = self._find_next_empty_row()
        if target_row_index == -1:
            messagebox.showinfo("Parrilla Llena", "No hay más filas vacías para colocar la palabra.")
            return

        for i, char in enumerate(word.upper()):
            cell_data = self.grid_cells[target_row_index][i]
            cell_widget = cell_data['widget']
            cell_widget.delete(0, tk.END)
            cell_widget.insert(0, char)
            self._heredar_estado_verde(target_row_index, i)
        self.update_grid_colors()

    def mostrar_resultados(self, palabras):
        self.resultado.config(state=tk.NORMAL)
        self.resultado.delete(1.0, tk.END)

        if not palabras:
            self.resultado.insert("1.0", "🤔 No se encontraron palabras con esos criterios.", "h1")
        else:
            top = mejores_palabras(palabras, dict(sugerir_letras(palabras)))
            self.resultado.insert("1.0", "🏆 MEJORES PALABRAS (clic para usar):\n", "h1")
            for p in top:
                tag_name = f"suggestion_{p}_{threading.get_ident()}"
                self.resultado.insert(tk.END, f"  • {p.upper()}\n", ("list_item", tag_name))
                self.resultado.tag_config(tag_name, foreground="#66b3ff", underline=True)
                self.resultado.tag_bind(tag_name, "<Enter>", lambda e, t=tag_name: self.resultado.config(cursor="hand2"))
                self.resultado.tag_bind(tag_name, "<Leave>", lambda e, t=tag_name: self.resultado.config(cursor=""))
                self.resultado.tag_bind(tag_name, "<Button-1>", lambda e, word=p: self.on_suggestion_click(word))
            self.resultado.insert(tk.END, f"\n\n🔎 Se encontraron {len(palabras)} palabras posibles en total.", "summary")

        self.resultado.tag_config("h1", font=("Segoe UI", 16, "bold"), spacing3=10, foreground="white")
        self.resultado.tag_config("list_item", lmargin1=20, font=("Consolas", 14))
        self.resultado.tag_config("summary", font=("Segoe UI", 10, "italic"), foreground="#bbbbbb")
        
        self.resultado.config(state=tk.DISABLED)
        self.finalizar_busqueda(True, len(palabras))

    def parse_grid_state(self):
        patron = ['_'] * self.palabra_longitud
        posiciones_prohibidas = defaultdict(set)
        min_counts = Counter()
        exact_counts = {}
        for c in range(self.palabra_longitud):
            for r in range(self.num_intentos):
                cell_data = self.grid_cells[r][c]
                if cell_data['state'] == 'correct':
                    letra = cell_data['widget'].get().lower()
                    if letra:
                        patron[c] = letra
                        break
        for r in range(self.num_intentos):
            intento_letras = [self.grid_cells[r][c]['widget'].get().lower() for c in range(self.palabra_longitud)]
            if not any(intento_letras): continue
            intento_counter = Counter(l for l in intento_letras if l)
            feedback_counter = Counter()
            for c, letra in enumerate(intento_letras):
                if not letra: continue
                estado = self.grid_cells[r][c]['state']
                if estado in ['correct', 'present']:
                    feedback_counter[letra] += 1
                if estado == 'present':
                    posiciones_prohibidas[letra].add(c)
            for letra, count in feedback_counter.items():
                min_counts[letra] = max(min_counts[letra], count)
            for letra, count_en_intento in intento_counter.items():
                count_en_feedback = feedback_counter.get(letra, 0)
                if count_en_intento > count_en_feedback:
                    exact_counts[letra] = count_en_feedback
        letras_descartadas = set()
        todas_letras_usadas = set()
        for r in range(self.num_intentos):
            for c in range(self.palabra_longitud):
                letra = self.grid_cells[r][c]['widget'].get().lower()
                if letra:
                    todas_letras_usadas.add(letra)
        letras_con_regla = set(min_counts.keys()) | set(exact_counts.keys())
        letras_descartadas.update(todas_letras_usadas - letras_con_regla)
        for letra, count in exact_counts.items():
            if count == 0:
                letras_descartadas.add(letra)
        return "".join(patron), min_counts, exact_counts, letras_descartadas, posiciones_prohibidas

    def ejecutar_busqueda_threaded(self):
        # --- MODIFICADO: Se eliminó la validación para permitir la búsqueda inicial ---
        self.search_button.config(state=tk.DISABLED)
        self.spinner_label.config(text="⏳ Calculando las mejores palabras...")
        threading.Thread(target=self.ejecutar_busqueda, daemon=True).start()

    def ejecutar_busqueda(self):
        try:
            patron, min_counts, exact_counts, descartadas, prohibidas = self.parse_grid_state()
            diccionario_filtrado = {p for p in diccionario_es if len(p) == self.palabra_longitud}
            palabras = generar_palabras(patron, min_counts, exact_counts, descartadas, prohibidas, diccionario_filtrado)
            self.root.after(0, self.mostrar_resultados, palabras)
        except Exception as e:
            import traceback
            traceback.print_exc()
            messagebox.showerror("Error inesperado", str(e))
            self.root.after(0, self.finalizar_busqueda, False, 0)

    def finalizar_busqueda(self, exito, num_palabras):
        if exito:
            if num_palabras > 0:
                self.spinner_label.config(text="✅ ¡Búsqueda completada! Revisa los resultados.")
            else:
                self.spinner_label.config(text="✅ Búsqueda completada. No se encontraron coincidencias.")
        else:
            self.spinner_label.config(text="❌ Ocurrió un error. Revisa la entrada y prueba de nuevo.")
        self.search_button.config(state=tk.NORMAL)

    def check_for_updates(self):
        repo_url = "https://api.github.com/repos/joseluisbugallo/wordle_resolver/releases/latest"
        try:
            with urllib.request.urlopen(repo_url, timeout=5) as response:
                data = json.loads(response.read().decode())
            latest_version_tag = data['tag_name']
            latest_version = latest_version_tag.lstrip('v')
            if latest_version > __version__:
                download_url = data['html_url']
                self.root.after(0, self.ask_for_update, latest_version, download_url)
        except Exception as e:
            print(f"No se pudo comprobar si hay actualizaciones: {e}")

    def ask_for_update(self, version, url):
        msg = f"Hay una nueva versión disponible: {version}\n\n" \
              f"Tu versión actual es: {__version__}\n\n" \
              "¿Quieres ir a la página de descargas ahora?"
        if messagebox.askyesno("Actualización Disponible", msg):
            webbrowser.open_new_tab(url)


if __name__ == "__main__":
    root = tk.Tk()
    app = WordleSolverApp(root)
    root.mainloop()