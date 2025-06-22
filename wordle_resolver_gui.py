import tkinter as tk
from tkinter import ttk, messagebox
import json
import itertools
from collections import Counter, defaultdict
import threading
import os
import sys

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
    diccionario_es = []

# --- Lógica de Búsqueda (sin cambios en su núcleo) ---
def generar_palabras(patron, min_counts, exact_counts, letras_descartadas, posiciones_prohibidas, diccionario):
    longitud = len(patron)
    palabras_posibles = []

    for palabra in diccionario: # Asumimos que el diccionario ya está pre-filtrado por longitud
        
        # Optimización: si una letra descartada no tiene reglas de conteo, la palabra no puede contenerla.
        # Las letras con reglas de conteo (ej. exact_count=1) se manejan más adelante.
        if any(letra in palabra for letra in letras_descartadas if letra not in exact_counts):
            continue

        palabra_valida = True
        palabra_counter = Counter(palabra)

        # Iteramos de una vez para aplicar todas las reglas a la palabra candidata
        for i in range(longitud):
            # 1. Comprobar patrón (letras verdes)
            if patron[i] != '_' and patron[i] != palabra[i]:
                palabra_valida = False
                break
            
            # 2. Comprobar posiciones prohibidas (letras amarillas)
            letra_actual = palabra[i]
            if letra_actual in posiciones_prohibidas and i in posiciones_prohibidas[letra_actual]:
                palabra_valida = False
                break

        if not palabra_valida: continue

        # 3. Comprobar conteo de letras (la lógica clave)
        # Combina todas las letras que tienen alguna restricción
        todas_letras_restringidas = set(min_counts.keys()) | set(exact_counts.keys()) | letras_descartadas
        
        for letra in todas_letras_restringidas:
            # La regla de conteo exacto tiene la máxima prioridad
            if letra in exact_counts:
                if palabra_counter[letra] != exact_counts[letra]:
                    palabra_valida = False
                    break
            # Si no hay regla exacta, usamos la regla de conteo mínimo
            elif letra in min_counts:
                if palabra_counter[letra] < min_counts[letra]:
                    palabra_valida = False
                    break
            # Si no hay reglas de conteo, es una letra descartada simple
            elif letra in letras_descartadas:
                if palabra_counter[letra] > 0:
                    palabra_valida = False
                    break
        
        if not palabra_valida: continue

        # Si la palabra ha superado todos los filtros, es una candidata válida
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
# --- Clase principal de la aplicación ---
class WordleSolverApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Wordle Solver en Español (UI Mejorada)")
        self.root.geometry("1000x700")

        # --- NUEVO: Establecer el icono de la ventana ---
        # Usamos resource_path para que funcione tanto en desarrollo como en el .exe
        try:
            icon_path = resource_path("icon.ico")
            self.root.iconbitmap(icon_path)
        except Exception as e:
            # Si el icono no se carga, la app no se romperá.
            # Simplemente mostrará un mensaje en la consola (si la hay).
            print(f"Advertencia: No se pudo cargar el icono de la aplicacion: {e}")


        self.root.resizable(True, True)

        self.style = ttk.Style()
        self.style.theme_use("clam") 

        self.states = ['absent', 'present', 'correct']
        self.dark_colors = {'absent': '#3a3a3c', 'present': '#b59f3b', 'correct': '#538d4e', 'text': 'white'}
        self.light_colors = {'absent': '#787c7e', 'present': '#c9b458', 'correct': '#6aaa64', 'text': 'white'}
        self.current_colors = self.dark_colors

        self.grid_cells = []
        self.palabra_longitud = 5
        self.num_intentos = 6
        
        self.create_widgets()
        self.update_grid_colors()

    def create_widgets(self):
        self.root.grid_columnconfigure(0, weight=1, uniform="group1")
        self.root.grid_columnconfigure(1, weight=1, uniform="group1")
        self.root.grid_rowconfigure(0, weight=1)

        control_frame = ttk.Frame(self.root, padding="15")
        control_frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        control_frame.grid_rowconfigure(1, weight=1)
        control_frame.grid_columnconfigure(0, weight=1)

        result_frame = ttk.Frame(self.root, padding="15")
        result_frame.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)
        result_frame.grid_rowconfigure(0, weight=1)
        result_frame.grid_columnconfigure(0, weight=1)

        self.resultado = tk.Text(result_frame, height=25, width=40, wrap="word", padx=10, pady=10, font=("Consolas", 14), relief="flat")
        self.resultado.grid(row=0, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(result_frame, command=self.resultado.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.resultado.config(yscrollcommand=scrollbar.set)

        top_buttons_frame = ttk.Frame(control_frame)
        top_buttons_frame.grid(row=0, column=0, sticky="ew", pady=(0, 20))
        top_buttons_frame.grid_columnconfigure(0, weight=1)
        top_buttons_frame.grid_columnconfigure(1, weight=1)

        self.search_button = ttk.Button(top_buttons_frame, text="🚀 Buscar Palabras", command=self.ejecutar_busqueda_threaded, style="Accent.TButton")
        self.search_button.grid(row=0, column=0, padx=5, sticky="ew")
        
        self.reset_button = ttk.Button(top_buttons_frame, text="🧹 Limpiar", command=self.reset_grid)
        self.reset_button.grid(row=0, column=1, padx=5, sticky="ew")

        self.grid_frame = ttk.Frame(control_frame)
        self.grid_frame.grid(row=1, column=0, sticky="n")
        self.create_wordle_grid()
        
        # MODIFICADO: Texto de ayuda actualizado
        self.spinner_label = ttk.Label(control_frame, text="✨ Escribe un intento. Haz clic derecho en una letra para cambiar su estado (gris/amarillo/verde).", anchor="center", wraplength=350)
        self.spinner_label.grid(row=2, column=0, sticky="ew", pady=(20, 0))
        
        self.configure_styles()

    def configure_styles(self):
        self.style.configure("TButton", font=("Segoe UI", 12), padding=10)
        self.style.configure("Accent.TButton", font=("Segoe UI", 12, "bold"), foreground="white", background="#0078d4")
        self.style.map("Accent.TButton", background=[('active', '#005a9e')])
        
        self.resultado.configure(bg="#2d2d2d", fg="#cccccc", insertbackground="white")
        self.style.configure("TScrollbar", troughcolor="#2d2d2d", background="#555555")

    def create_wordle_grid(self):
        validate_cmd = self.root.register(lambda text: len(text) <= 1)
        
        self.grid_cells = []
        for r in range(self.num_intentos):
            row_list = []
            self.grid_frame.grid_rowconfigure(r, weight=1)
            for c in range(self.palabra_longitud):
                self.grid_frame.grid_columnconfigure(c, weight=1)
                
                cell = tk.Entry(
                    self.grid_frame, width=2, font=("Segoe UI", 24, "bold"),
                    justify='center', relief="flat", validate="key",
                    validatecommand=(validate_cmd, '%P')
                )
                cell.grid(row=r, column=c, padx=3, pady=3, sticky="nsew", ipady=10)
                
                cell_data = {'widget': cell, 'state': 'absent'}
                row_list.append(cell_data)

                # MODIFICADO: El cambio de color ahora es con clic derecho (<Button-3>)
                cell.bind("<Button-3>", lambda e, row=r, col=c: self.on_cell_click(row, col))
                cell.bind("<KeyRelease>", lambda e, row=r, col=c: self.on_key_release(e, row, col))
            
            self.grid_cells.append(row_list)

    def on_cell_click(self, row, col):
        """ Cicla entre los estados 'absent', 'present', 'correct' al hacer clic DERECHO. """
        cell_data = self.grid_cells[row][col]
        current_state_index = self.states.index(cell_data['state'])
        next_state_index = (current_state_index + 1) % len(self.states)
        cell_data['state'] = self.states[next_state_index]
        self.update_grid_colors()

    def on_key_release(self, event, row, col):
        if event.char.isalpha() and col < self.palabra_longitud - 1:
            self.grid_cells[row][col+1]['widget'].focus_set()
        
        widget = self.grid_cells[row][col]['widget']
        current_text = widget.get()
        if current_text:
            widget.delete(0, tk.END)
            widget.insert(0, current_text.upper())

    def update_grid_colors(self):
        for r in range(self.num_intentos):
            for c in range(self.palabra_longitud):
                cell_data = self.grid_cells[r][c]
                widget = cell_data['widget']
                state = cell_data['state']
                
                bg_color = self.current_colors[state]
                text_color = self.current_colors['text']
                
                widget.config(bg=bg_color, fg=text_color, insertbackground=text_color)

    def reset_grid(self):
        for row in self.grid_cells:
            for cell_data in row:
                cell_data['widget'].delete(0, tk.END)
                cell_data['state'] = 'absent'
        self.update_grid_colors()
        self.spinner_label.config(text="✨ Parrilla reiniciada. ¡Listo para un nuevo intento!")
        self.resultado.delete(1.0, tk.END)
        # Poner el foco en la primera celda para comodidad del usuario
        self.grid_cells[0][0]['widget'].focus_set()

    # NUEVO: Función para encontrar la próxima fila vacía en la parrilla
    def _find_next_empty_row(self):
        for i, row in enumerate(self.grid_cells):
            # Una fila se considera vacía si su primera celda no tiene texto
            if not row[0]['widget'].get():
                return i
        return -1 # Retorna -1 si no hay filas vacías

    # NUEVO: Función que se ejecuta al hacer clic en una palabra sugerida
    def on_suggestion_click(self, word):
        target_row_index = self._find_next_empty_row()
        
        if target_row_index == -1:
            messagebox.showinfo("Parrilla Llena", "No hay más filas vacías para colocar la palabra.")
            return

        # Rellenar la fila encontrada con la palabra
        for i, char in enumerate(word.upper()):
            cell_widget = self.grid_cells[target_row_index][i]['widget']
            cell_widget.delete(0, tk.END)
            cell_widget.insert(0, char)

    # MODIFICADO: La función `mostrar_resultados` ahora crea enlaces clicables
    # MODIFICADO: Versión corregida y simplificada que SÍ muestra las palabras clicables
    # y elimina la "lista completa".
    def mostrar_resultados(self, palabras):
        """
        Actualiza la UI, mostrando solo las mejores palabras clicables en la parte superior
        y conservando el historial de búsqueda.
        """
        # 1. Poner el widget en modo NORMAL para poder modificarlo
        self.resultado.config(state=tk.NORMAL)

        # 2. Si ya hay contenido, añadir un separador en la parte superior
        if self.resultado.get("1.0", "end-1c").strip():
            separator_line = f"\n{'#'*40}\n\n"
            self.resultado.insert("1.0", separator_line, "separator")

        # 3. Insertar el contenido nuevo, línea por línea, EN ORDEN INVERSO
        # Esto asegura que aparezcan en el orden correcto en la parte superior.

        if palabras:
            # Primero, obtener la lista de las 10 mejores palabras
            top = mejores_palabras(palabras, dict(sugerir_letras(palabras)))

            # Segundo, iterar la lista de mejores palabras EN REVERSA para insertarlas
            for p in reversed(top):
                tag_name = f"suggestion_{p}"
                
                # Insertar la palabra en la parte superior
                self.resultado.insert("1.0", f"  • {p.upper()}\n", ("list_item", tag_name))
                
                # INMEDIATAMENTE después de insertarla, hacerla clicable
                self.resultado.tag_config(tag_name, foreground="#66b3ff", underline=True)
                self.resultado.tag_bind(tag_name, "<Enter>", lambda e, t=tag_name: self.resultado.config(cursor="hand2"))
                self.resultado.tag_bind(tag_name, "<Leave>", lambda e, t=tag_name: self.resultado.config(cursor=""))
                self.resultado.tag_bind(tag_name, "<Button-1>", lambda e, word=p: self.on_suggestion_click(word))

            # Tercero, insertar el encabezado de las mejores palabras
            self.resultado.insert("1.0", "🏆 MEJORES PALABRAS (clic para usar):\n", "h1")
        
        # Cuarto, insertar el resumen de la búsqueda (siempre al principio)
        self.resultado.insert("1.0", f"🔎 Se encontraron {len(palabras)} palabras posibles.\n\n")

        # 5. (Opcional pero recomendado) Reconfigurar estilos generales
        self.resultado.tag_config("h1", font=("Segoe UI", 16, "bold"), spacing3=10)
        self.resultado.tag_config("h2", font=("Segoe UI", 14, "bold"), spacing3=8) # Aunque ya no se use h2, no molesta
        self.resultado.tag_config("list_item", lmargin1=20, font=("Consolas", 14))
        self.resultado.tag_config("separator", font=("Consolas", 10, "italic"), foreground="#777777", justify='center')

        # 6. Volver a poner el widget en modo de solo lectura
        self.resultado.config(state=tk.DISABLED)
        
        self.finalizar_busqueda(True)
    # ... (El resto de las funciones: parse_grid_state, ejecutar_busqueda_threaded, etc., permanecen igual que en la versión corregida anterior) ...
    def parse_grid_state(self):
        """
        Interpreta el estado de la parrilla y devuelve datos estructurados para
        la búsqueda, manejando correctamente las letras duplicadas.
        """
        patron = ['_'] * self.palabra_longitud
        posiciones_prohibidas = defaultdict(set)
        min_counts = Counter()
        exact_counts = {}

        # Primera pasada: Recoger letras verdes (correctas) para establecer el patrón base.
        # Una vez una posición es verde, es la información más fiable.
        for c in range(self.palabra_longitud):
            for r in range(self.num_intentos):
                cell_data = self.grid_cells[r][c]
                if cell_data['state'] == 'correct':
                    letra = cell_data['widget'].get().lower()
                    if letra:
                        patron[c] = letra
                        break 
        
        # Segunda pasada: Procesar fila por fila para deducir conteos.
        for r in range(self.num_intentos):
            intento_letras = [self.grid_cells[r][c]['widget'].get().lower() for c in range(self.palabra_longitud)]
            if not any(intento_letras):
                continue

            intento_counter = Counter(l for l in intento_letras if l)
            feedback_counter = Counter()  # Cuenta de verdes/amarillas en esta fila

            # Recoger feedback (amarillas/verdes) y posiciones prohibidas de esta fila
            for c, letra in enumerate(intento_letras):
                if not letra: continue
                
                estado = self.grid_cells[r][c]['state']
                if estado in ['correct', 'present']:
                    feedback_counter[letra] += 1
                if estado == 'present':
                    posiciones_prohibidas[letra].add(c)
            
            # Actualizar conteo mínimo global con la información de esta fila
            for letra, count in feedback_counter.items():
                min_counts[letra] = max(min_counts[letra], count)

            # Deducir conteos exactos de letras grises
            for letra, count_en_intento in intento_counter.items():
                count_en_feedback = feedback_counter.get(letra, 0)
                if count_en_intento > count_en_feedback:
                    # Si adivinamos más letras de las que "acertamos", sabemos el conteo exacto.
                    exact_counts[letra] = count_en_feedback

        # Tercera pasada: Determinar el conjunto final de letras descartadas.
        letras_descartadas = set()
        todas_letras_usadas = set()
        for r in range(self.num_intentos):
            for c in range(self.palabra_longitud):
                letra = self.grid_cells[r][c]['widget'].get().lower()
                if letra:
                    todas_letras_usadas.add(letra)
        
        # Las letras con reglas son las que sabemos que están (o cuyo conteo conocemos).
        letras_con_regla = set(min_counts.keys()) | set(exact_counts.keys())
        
        # Una letra se descarta si se usó pero nunca fue verde o amarilla.
        letras_descartadas.update(todas_letras_usadas - letras_con_regla)
        
        # También se descarta explícitamente si su conteo exacto es cero.
        for letra, count in exact_counts.items():
            if count == 0:
                letras_descartadas.add(letra)

        return "".join(patron), min_counts, exact_counts, letras_descartadas, posiciones_prohibidas

    def ejecutar_busqueda_threaded(self):
        self.search_button.config(state=tk.DISABLED)
        self.spinner_label.config(text="⏳ Calculando las mejores palabras...")
        threading.Thread(target=self.ejecutar_busqueda, daemon=True).start()

    def ejecutar_busqueda(self):
        try:
            # La firma de parse_grid_state y generar_palabras ha cambiado.
            patron, min_counts, exact_counts, descartadas, prohibidas = self.parse_grid_state()
            
            # Filtrar diccionario solo por longitud una vez
            diccionario_filtrado = {p for p in diccionario_es if len(p) == self.palabra_longitud}
            
            # Llamar a la nueva función generar_palabras con los argumentos correctos
            palabras = generar_palabras(patron, min_counts, exact_counts, descartadas, prohibidas, diccionario_filtrado)
            
            # --- Actualización de la UI (en el hilo principal) ---
            self.root.after(0, self.mostrar_resultados, palabras)

        except Exception as e:
            # Es buena práctica imprimir el error para depuración
            import traceback
            traceback.print_exc()
            messagebox.showerror("Error inesperado", str(e))
            self.root.after(0, self.finalizar_busqueda, False)

    def finalizar_busqueda(self, exito):
        """Restaura la UI después de que la búsqueda termina."""
        if exito:
            self.spinner_label.config(text="✅ ¡Búsqueda completada! Revisa los resultados.")
        else:
            self.spinner_label.config(text="❌ Ocurrió un error durante la búsqueda.")
        self.search_button.config(state=tk.NORMAL)

if __name__ == "__main__":
    root = tk.Tk()
    app = WordleSolverApp(root)
    root.mainloop()
