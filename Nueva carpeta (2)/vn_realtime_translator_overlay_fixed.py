# -*- coding: utf-8 -*-
#
# Programa completo para traducir texto de juegos con una tecla de acceso rápido global.
# Ahora con opción de elegir entre Ollama y Google Translate.
#
# DEPENDENCIAS REQUERIDAS:
# - Python 3.x
# - EasyOCR (para el motor de OCR)
# - Las siguientes bibliotecas de Python:
#   pip install Pillow opencv-python numpy easyocr pygetwindow keyboard customtkinter
#
# Dependencias OPCIONALES (dependiendo del traductor que elijas):
# - Para Google Translate:
#   pip install googletrans
# - Para Ollama:
#   pip install requests
#   (y el servidor de Ollama debe estar en ejecución: ollama run mistral)

import cv2
import numpy as np
import time
from PIL import ImageGrab, Image
import tkinter as tk
from tkinter import font, messagebox
import customtkinter as ctk
import pygetwindow as gw
import sys
import threading
import queue
import keyboard
import subprocess
import os

# --- Dependencias del programa ---
try:
    import easyocr
    easyocr_reader = easyocr.Reader(['en', 'es'])
    print("EasyOCR se ha inicializado correctamente.")
except ImportError:
    print("ERROR: Asegúrate de tener instalada la biblioteca 'easyocr'.")
    print("Ejecuta: pip install easyocr")
    sys.exit()

# Intentar importar las dependencias de los traductores, de forma opcional
try:
    from googletrans import Translator
    google_translator = Translator()
    GOOGLE_TRANSLATE_ENABLED = True
except ImportError:
    print("ADVERTENCIA: La biblioteca 'googletrans' no está instalada. No podrás usar el traductor de Google.")
    print("Para instalarla, ejecuta: pip install googletrans")
    GOOGLE_TRANSLATE_ENABLED = False

try:
    import requests
    OLLAMA_API_URL = "http://localhost:11434/api/generate"
    OLLAMA_MODEL = "mistral"
    OLLAMA_ENABLED = True
except ImportError:
    print("ADVERTENCIA: La biblioteca 'requests' no está instalada. No podrás usar el traductor de Ollama.")
    print("Para instalarla, ejecuta: pip install requests")
    OLLAMA_ENABLED = False

# --- Variables globales y de estado del programa ---
selected_window = None
roi_coords = None
translation_running = False
translation_queue = queue.Queue()
after_id = None
translation_windows = []
last_extracted_text_per_roi = {}
ollama_process = None


def start_ollama_server():
    """
    Inicia el servidor de Ollama si no está en ejecución.
    Espera unos segundos para que se inicialice.
    """
    global ollama_process
    print("Intentando iniciar el servidor de Ollama...")
    try:
        # El comando 'ollama serve'
        command = ["ollama", "serve"]
        
        # Iniciar el proceso de forma asíncrona
        ollama_process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        time.sleep(5) # Esperar a que el servidor se inicialice
        return True
    except FileNotFoundError:
        print("ERROR: El comando 'ollama' no se encontró. Asegúrate de que Ollama está instalado y en el PATH.")
        return False
    except Exception as e:
        print(f"ERROR al iniciar el servidor de Ollama: {e}")
        return False


def show_warning(title, message):
    """Muestra un cuadro de mensaje de advertencia."""
    messagebox.showwarning(title, message)

def get_window_titles():
    """Obtiene los títulos de todas las ventanas visibles."""
    return [w.title for w in gw.getAllWindows() if w.title]

def select_roi(main_gui):
    """Permite al usuario seleccionar una región de la pantalla con el mouse."""
    global roi_coords, selected_window

    if selected_window is None:
        show_warning("Error", "Por favor, primero selecciona una ventana.")
        return

    window_x, window_y, window_width, window_height = selected_window.left, selected_window.top, selected_window.width, selected_window.height
    
    # Variables locales para la selección del ratón
    start_x, start_y = None, None
    end_x, end_y = None, None

    def on_mouse_down(event):
        nonlocal start_x, start_y
        start_x, start_y = event.x_root, event.y_root

    def on_mouse_drag(event):
        nonlocal end_x, end_y
        if start_x is not None:
            end_x, end_y = event.x_root, event.y_root
            canvas.coords(rect, start_x - window_x, start_y - window_y, end_x - window_x, end_y - window_y)

    def on_mouse_release(event):
        nonlocal start_x, start_y, end_x, end_y
        if start_x is not None:
            end_x, end_y = event.x_root, event.y_root

            x1 = min(start_x, end_x)
            y1 = min(start_y, end_y)
            x2 = max(start_x, end_x)
            y2 = max(start_y, end_y)
            
            global roi_coords
            roi_coords = (x1, y1, x2, y2)
            
            selection_window.destroy()

            if x2 - x1 > 0 and y2 - y1 > 0:
                main_gui.on_roi_selected()
            else:
                main_gui.log_message("El área de selección es demasiado pequeña.", "error")
                show_warning("Error", "El área de selección es demasiado pequeña.")
        
    selection_window = tk.Toplevel(main_gui)
    selection_window.geometry(f"{window_width}x{window_height}+{window_x}+{window_y}")
    selection_window.attributes('-alpha', 0.2)
    selection_window.attributes('-topmost', True)
    selection_window.overrideredirect(True)
    selection_window.grab_set()

    canvas = tk.Canvas(selection_window, cursor="cross", bg="blue")
    canvas.pack(fill=tk.BOTH, expand=True)

    rect = canvas.create_rectangle(0, 0, 0, 0, outline="red", width=2)

    canvas.bind("<Button-1>", on_mouse_down)
    canvas.bind("<B1-Motion>", on_mouse_drag)
    canvas.bind("<ButtonRelease-1>", on_mouse_release)

    selection_window.wait_window()

# --- Funciones de procesamiento ---
def capture_and_preprocess(roi_coords):
    """Captura una región de la pantalla y la preprocesa para OCR."""
    try:
        captured_image = ImageGrab.grab(bbox=roi_coords)
        img_np = np.array(captured_image)
        original_cv = cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR)
        return original_cv
    except Exception as e:
        print(f"ERROR en la captura o el preprocesamiento: {e}")
        return None

def perform_ocr(image):
    """
    Realiza el reconocimiento de caracteres y devuelve el texto, así como
    las bounding boxes para calcular el tamaño de la fuente.
    """
    if image is None:
        return "", []
    try:
        results = easyocr_reader.readtext(image)
        extracted_text = " ".join([res[1] for res in results])
        bounding_boxes = [res[0] for res in results]
        return extracted_text, bounding_boxes
    except Exception as e:
        print(f"ERROR en el OCR con EasyOCR: {e}")
        return "", []

def calculate_font_size_from_bbox(bounding_boxes):
    """Calcula un tamaño de fuente en puntos basado en la altura de los bounding boxes."""
    if not bounding_boxes:
        return 10
    
    max_height = 0
    for box in bounding_boxes:
        ys = [p[1] for p in box]
        height = max(ys) - min(ys)
        if height > max_height:
            max_height = height
            
    font_size = int(max_height * 0.75)
    font_size = max(5, min(10, font_size))
    
    return font_size

def translate_with_google_translate(text):
    """Envía el texto extraído a la API de Google Translate para su traducción."""
    if not text:
        return ""

    try:
        translated = google_translator.translate(text, dest='es')
        return translated.text
    except Exception as e:
        print(f"ERROR en la traducción con Google Translate: {e}")
        return "[ERROR en la traducción con Google Translate]"

def translate_with_ollama(text, retry_count=0):
    """
    Envía el texto extraído a la API local de Ollama para su traducción.
    Si el servidor no responde, intenta iniciarlo una vez.
    """
    if not text:
        return ""

    prompt = f"Traduce el siguiente texto al español de forma concisa y sin rodeos: '{text}'"

    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False
    }

    try:
        response = requests.post(OLLAMA_API_URL, json=payload, timeout=60)
        response.raise_for_status()
        result = response.json()
        translation = result['response'].strip()
        
        # Limpiar la respuesta para que no contenga explicaciones
        if "traducción" in translation.lower() or "aquí está" in translation.lower():
            lines = translation.split('\n')
            translation = next((line for line in lines if line), translation)
        
        return translation
    except requests.exceptions.ConnectionError:
        if retry_count == 0:
            print("No se pudo conectar a Ollama. Intentando iniciar el servidor...")
            if start_ollama_server():
                print("Servidor de Ollama iniciado. Reintentando la traducción...")
                # Esperar un poco más para que el servidor esté listo
                time.sleep(5)
                return translate_with_ollama(text, retry_count=1)
            else:
                return "[ERROR: No se pudo conectar a Ollama. Asegúrate de que Ollama está instalado y en el PATH.]"
        else:
            return "[ERROR: El servidor de Ollama no respondió después de iniciarse.]"
    except requests.exceptions.RequestException as e:
        print(f"ERROR en la conexión con Ollama: {e}")
        return f"[ERROR: No se pudo conectar a Ollama. Asegúrate de que 'ollama run {OLLAMA_MODEL}' está activo.]"
    except Exception as e:
        print(f"ERROR al procesar la respuesta de Ollama: {e}")
        return "[ERROR en la traducción]"

# --- Funciones de la Interfaz de Usuario ---
def create_overlay_window(position_and_size, on_close_callback, initial_text="", opacity=0.9, text_color="black", bg_color="white"):
    """
    Crea una ventana transparente y superpuesta para mostrar el texto,
    con un botón de cierre "X" y capacidad de arrastre.
    """
    x1, y1, x2, y2 = position_and_size
    width = x2 - x1
    height = y2 - y1

    root = ctk.CTkToplevel()
    root.title("Traductor")
    root.overrideredirect(True)
    root.attributes('-topmost', True)
    root.geometry(f"{width}x{height}+{x1}+{y1}")
    
    # La opacidad se aplica a toda la ventana
    root.attributes('-alpha', opacity)
    
    drag_start_x = 0
    drag_start_y = 0

    def on_drag_start(event):
        nonlocal drag_start_x, drag_start_y
        drag_start_x = event.x_root - root.winfo_x()
        drag_start_y = event.y_root - root.winfo_y()

    def on_drag_motion(event):
        nonlocal drag_start_x, drag_start_y
        new_x = event.x_root - drag_start_x
        new_y = event.y_root - drag_start_y
        root.geometry(f"+{new_x}+{new_y}")

    def close_window():
        on_close_callback(root)
        root.destroy()
        
    frame_header = ctk.CTkFrame(root, height=25, fg_color=bg_color, corner_radius=0)
    frame_header.pack(fill=tk.X, anchor="n")
    frame_header.pack_propagate(False)
    
    frame_header.bind("<Button-1>", on_drag_start)
    frame_header.bind("<B1-Motion>", on_drag_motion)
    
    close_button = ctk.CTkButton(frame_header, text="X", command=close_window,
                                 width=20, height=20, corner_radius=5,
                                 fg_color="red", hover_color="darkred",
                                 font=ctk.CTkFont(size=12, weight="bold"))
    close_button.pack(side=tk.RIGHT, padx=5, pady=2)

    frame_content = ctk.CTkFrame(root, fg_color=bg_color)
    frame_content.pack(fill=tk.BOTH, expand=True)
    
    canvas = tk.Canvas(frame_content, bg=bg_color, highlightthickness=0)
    canvas.pack(fill=tk.BOTH, expand=True)

    custom_font = font.Font(family="Helvetica", size=10, weight="bold")

    text_id = canvas.create_text(
        (width) / 2, (height) / 2,
        anchor="center",
        text=initial_text,
        fill=text_color,
        font=custom_font,
        width=width - 20
    )

    return root, canvas, text_id, width, height, frame_header, frame_content

def update_overlay_window(canvas, text_id, new_text, container_width, container_height, font_size, text_color):
    """
    Actualiza el texto en el canvas de la ventana de superposición usando el
    tamaño de fuente calculado y el color de texto.
    """
    custom_font = font.Font(family="Helvetica", size=font_size, weight="bold")
    canvas.itemconfig(text_id, text=new_text, font=custom_font, width=container_width - 20, fill=text_color)
    canvas.coords(text_id, container_width / 2, container_height / 2)

class StyleOptionsWindow(ctk.CTkToplevel):
    def __init__(self, master, app_instance):
        super().__init__(master)
        self.title("Opciones de Estilo")
        self.geometry("300x250")
        self.transient(master) # Mantiene la ventana encima de la principal
        self.grab_set() # Deshabilita la interacción con la ventana principal
        
        self.app_instance = app_instance
        self.create_widgets()

    def create_widgets(self):
        main_frame = ctk.CTkFrame(self, corner_radius=10)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        ctk.CTkLabel(main_frame, text="Opciones de Estilo:", font=ctk.CTkFont(size=14, weight="bold")).pack(fill=tk.X, padx=10, pady=(10, 5))

        # Control de opacidad
        ctk.CTkLabel(main_frame, text="Opacidad del Fondo:", font=ctk.CTkFont(size=12)).pack(fill=tk.X, padx=10, pady=(5,0))
        self.opacity_slider = ctk.CTkSlider(main_frame, from_=0, to=100, command=self.update_app_style)
        self.opacity_slider.set(int(self.app_instance.opacity * 100))
        self.opacity_slider.pack(fill=tk.X, padx=10, pady=5)
        
        # Control de color de texto
        ctk.CTkLabel(main_frame, text="Color del Texto:", font=ctk.CTkFont(size=12)).pack(fill=tk.X, padx=10, pady=(5,0))
        self.text_color_selector = ctk.CTkOptionMenu(main_frame, values=["Negro", "Blanco"], command=self.update_app_style)
        self.text_color_selector.set(self.app_instance.text_color.capitalize())
        self.text_color_selector.pack(fill=tk.X, padx=10, pady=5)

        # Control de color de fondo
        ctk.CTkLabel(main_frame, text="Color del Fondo:", font=ctk.CTkFont(size=12)).pack(fill=tk.X, padx=10, pady=(5,0))
        self.bg_color_selector = ctk.CTkOptionMenu(main_frame, values=["Blanco", "Negro"], command=self.update_app_style)
        self.bg_color_selector.set(self.app_instance.bg_color.capitalize())
        self.bg_color_selector.pack(fill=tk.X, padx=10, pady=5)
    
    def update_app_style(self, *args):
        self.app_instance.opacity = self.opacity_slider.get() / 100
        self.app_instance.text_color = self.text_color_selector.get().lower()
        self.app_instance.bg_color = self.bg_color_selector.get().lower()
        self.app_instance.update_translation_windows_style()

class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Control del Traductor")
        # Nuevo tamaño para la interfaz más ancha
        self.geometry("800x650") 
        self.after_id = None
        self.hotkey = None
        self.is_running = False
        self.selected_window_title = None
        self.opacity = 0.9 # Nuevo: Opacidad por defecto
        self.text_color = "black" # Nuevo: Color de texto por defecto
        self.bg_color = "white" # Nuevo: Color de fondo por defecto

        ctk.set_appearance_mode("Dark")
        ctk.set_default_color_theme("blue")
        
        self.create_widgets()
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def log_message(self, message, message_type="info"):
        """Inserta un mensaje en el recuadro de seguimiento con un color específico."""
        self.log_box.configure(state=tk.NORMAL)
        self.log_box.insert(tk.END, f"{time.strftime('[%H:%M:%S]')} {message}\n", (message_type,))
        self.log_box.see(tk.END)
        self.log_box.configure(state=tk.DISABLED)

    def update_translation_windows_style(self, *args):
        """Actualiza la opacidad y el color del texto en todos los recuadros activos."""

        # Actualiza el color del tag de la consola para reflejar la elección del usuario
        self.log_box.tag_config("translated", foreground=self.text_color)
        
        global translation_windows
        for window_data in translation_windows:
            root = window_data['root']
            if root and root.winfo_exists():
                root.attributes('-alpha', self.opacity)
                
                # Actualizar el color del texto en el canvas si el texto existe
                if window_data['text_id']:
                    window_data['canvas'].itemconfig(window_data['text_id'], fill=self.text_color)
                
                window_data['frame_content'].configure(fg_color=self.bg_color)
                window_data['canvas'].configure(bg=self.bg_color)
                window_data['frame_header'].configure(fg_color=self.bg_color)
    
    def open_style_options(self):
        StyleOptionsWindow(self, self)

    def create_widgets(self):
        main_frame = ctk.CTkFrame(self, corner_radius=10)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # --- Contenedor principal para los paneles izquierdo y derecho ---
        main_content_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        main_content_frame.pack(fill=tk.BOTH, expand=True)

        # --- Panel Izquierdo: Recuadro de seguimiento ---
        log_frame = ctk.CTkFrame(main_content_frame, corner_radius=8)
        log_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(5, 2.5), pady=5)
        ctk.CTkLabel(log_frame, text="Recuadro de seguimiento:", font=ctk.CTkFont(size=12, weight="bold")).pack(fill=tk.X, padx=10, pady=(10, 5))
        
        self.log_box = ctk.CTkTextbox(log_frame, height=350, corner_radius=5, state=tk.DISABLED, wrap=tk.WORD)
        self.log_box.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        self.log_box.tag_config("success", foreground="green")
        self.log_box.tag_config("error", foreground="red")
        self.log_box.tag_config("info", foreground="gray")
        self.log_box.tag_config("detected", foreground="cyan")
        self.log_box.tag_config("translated", foreground=self.text_color)

        # --- Panel Derecho: Opciones de Traductor y Ventana ---
        right_panel_frame = ctk.CTkFrame(main_content_frame, fg_color="transparent")
        right_panel_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(2.5, 5), pady=5)
        
        # Sección de selección del motor de traducción
        translator_frame = ctk.CTkFrame(right_panel_frame, corner_radius=8)
        translator_frame.pack(fill=tk.X, padx=5, pady=5)
        ctk.CTkLabel(translator_frame, text="Seleccionar motor de traducción:", font=ctk.CTkFont(size=12, weight="bold")).pack(fill=tk.X, padx=10, pady=(10, 5))
        
        translator_options = []
        if GOOGLE_TRANSLATE_ENABLED:
            translator_options.append("Google Translate")
        if OLLAMA_ENABLED:
            translator_options.append("Ollama")

        if not translator_options:
            translator_options.append("No hay traductores disponibles")
            self.log_message("No se encontraron traductores. Revisa las advertencias en la terminal.", "error")
        
        self.translator_selector = ctk.CTkOptionMenu(translator_frame, values=translator_options)
        self.translator_selector.pack(fill=tk.X, padx=10, pady=10)
        self.translator_selector.set(translator_options[0] if translator_options else "")
        
        # Sección de Ventana y ROI
        window_frame = ctk.CTkFrame(right_panel_frame, corner_radius=8)
        window_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        ctk.CTkLabel(window_frame, text="Seleccionar Ventana del Juego:", font=ctk.CTkFont(size=12, weight="bold")).pack(fill=tk.X, padx=10, pady=(10, 5))

        self.window_list_frame = ctk.CTkScrollableFrame(window_frame, height=150)
        self.window_list_frame.pack(fill=tk.X, padx=10, pady=5)
        self.window_buttons = {}
        self.refresh_windows_list()
        
        ctk.CTkButton(window_frame, text="Refrescar Lista", command=self.refresh_windows_list).pack(fill=tk.X, padx=10, pady=(0, 5))
        
        self.roi_label = ctk.CTkLabel(window_frame, text="ROIs activos: 0", font=ctk.CTkFont(size=12, weight="bold"))
        self.roi_label.pack(fill=tk.X, padx=10, pady=(0, 10))
        
        # --- Controles inferiores ---
        bottom_controls_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        bottom_controls_frame.pack(fill=tk.X, padx=5, pady=5)

        # Botón para seleccionar el área de OCR
        ctk.CTkButton(bottom_controls_frame, text="Seleccionar Área de OCR", command=self.on_select_roi_button).pack(fill=tk.X, padx=5, pady=2)

        # Botón para abrir la ventana de opciones de estilo (NUEVO)
        ctk.CTkButton(bottom_controls_frame, text="Opciones de Estilo", command=self.open_style_options).pack(fill=tk.X, padx=5, pady=2)

        # Sección de Tecla de Acceso Rápido
        hotkey_frame = ctk.CTkFrame(bottom_controls_frame, corner_radius=8)
        hotkey_frame.pack(fill=tk.X, padx=5, pady=5)
        ctk.CTkLabel(hotkey_frame, text="Tecla de acceso rápido:", font=ctk.CTkFont(size=12, weight="bold")).pack(fill=tk.X, padx=10, pady=(10, 5))
        self.hotkey_entry = ctk.CTkEntry(hotkey_frame, placeholder_text="Ej: f1, ctrl+q, alt+s")
        self.hotkey_entry.pack(fill=tk.X, padx=10, pady=2)
        ctk.CTkButton(hotkey_frame, text="Establecer Tecla", command=self.set_hotkey).pack(fill=tk.X, padx=10, pady=10)


    def get_window_titles(self):
        return [w.title for w in gw.getAllWindows() if w.title]

    def select_window_by_title(self, title):
        if self.selected_window_title:
            prev_button = self.window_buttons.get(self.selected_window_title)
            if prev_button:
                prev_button.configure(fg_color=("#3B8ED0", "#1F6AA5"))
        
        self.selected_window_title = title
        new_button = self.window_buttons.get(title)
        if new_button:
            new_button.configure(fg_color=("green", "darkgreen"))
            self.log_message(f"Ventana seleccionada: {title}", "success")


    def refresh_windows_list(self):
        for widget in self.window_list_frame.winfo_children():
            widget.destroy()
        self.window_buttons.clear()
        self.selected_window_title = None

        window_titles = self.get_window_titles()
        if not window_titles:
            ctk.CTkLabel(self.window_list_frame, text="No se encontraron ventanas abiertas.", text_color="red").pack(fill=tk.X, padx=5, pady=5)
            self.log_message("No se encontraron ventanas disponibles.", "error")
            return

        for title in sorted(window_titles):
            if title:
                button = ctk.CTkButton(self.window_list_frame, text=title, anchor="w",
                                       command=lambda t=title: self.select_window_by_title(t))
                button.pack(fill=tk.X, padx=5, pady=2)
                self.window_buttons[title] = button
        
        self.log_message("Lista de ventanas actualizada.", "info")


    def on_select_roi_button(self):
        global selected_window
        selected_title = self.selected_window_title
        if selected_title:
            try:
                selected_window = gw.getWindowsWithTitle(selected_title)[0]
                select_roi(self)
            except IndexError:
                show_warning("Error", f"La ventana '{selected_title}' ya no está disponible.")
                self.refresh_windows_list()
                selected_window = None
        else:
            show_warning("Error", "Por favor, primero selecciona una ventana de la lista.")

    def set_hotkey(self):
        new_hotkey = self.hotkey_entry.get().strip()
        if new_hotkey:
            self.stop_hotkey()
            self.hotkey = new_hotkey
            try:
                keyboard.add_hotkey(self.hotkey, self.start_translation_thread)
                self.log_message(f"Tecla '{self.hotkey}' configurada. Pulsa para traducir.", "success")
            except ValueError:
                self.log_message(f"La tecla '{new_hotkey}' no es válida.", "error")
                show_warning("Error de Tecla", f"La tecla '{new_hotkey}' no es válida. Intente con 'f1', 'ctrl+q', 'alt+s', etc.")
                self.hotkey = None
        else:
            self.log_message("Entrada de tecla vacía. Intente de nuevo.", "info")
            show_warning("Entrada de Tecla Vacía", "Por favor, introduce una tecla válida.")

    def stop_hotkey(self):
        if self.hotkey:
            keyboard.unhook_all_hotkeys()
            self.log_message("Hotkey desvinculada.", "info")
            self.hotkey = None

    def on_roi_selected(self):
        global roi_coords, translation_windows
        
        if roi_coords:
            def on_close_overlay(closed_root):
                global translation_windows, last_extracted_text_per_roi
                translation_windows = [w for w in translation_windows if w['root'] is not closed_root]
                
                for key in list(last_extracted_text_per_roi.keys()):
                    if key not in [w['id'] for w in translation_windows]:
                        del last_extracted_text_per_roi[key]

                self.roi_label.configure(text=f"ROIs activos: {len(translation_windows)}")
                self.log_message(f"Recuadro de traducción cerrado. ROIs activos: {len(translation_windows)}", "info")

            new_id = len(translation_windows)
            new_root, new_canvas, new_text_id, width, height, frame_header, frame_content = create_overlay_window(
                roi_coords, on_close_overlay, initial_text="Esperando traducción...",
                opacity=self.opacity, text_color=self.text_color, bg_color=self.bg_color
            )
            translation_windows.append({
                'id': new_id,
                'root': new_root,
                'canvas': new_canvas,
                'text_id': new_text_id,
                'roi_coords': roi_coords,
                'width': width,
                'height': height,
                'frame_header': frame_header,
                'frame_content': frame_content
            })
            last_extracted_text_per_roi[new_id] = ""

            self.roi_label.configure(text=f"ROIs activos: {len(translation_windows)}")
            self.log_message(f"Recuadro de traducción creado en {roi_coords}. ROIs activos: {len(translation_windows)}", "success")
        else:
            self.log_message("No se pudo crear el recuadro, no hay coordenadas ROI.", "error")

    def start_translation_thread(self):
        global translation_running, translation_windows
        
        if not translation_windows:
            self.log_message("Por favor, selecciona un área de OCR primero.", "error")
            show_warning("Error", "Debes seleccionar un área de captura primero.")
            return
        
        translator_choice = self.translator_selector.get()
        if translator_choice == "Google Translate" and not GOOGLE_TRANSLATE_ENABLED:
            show_warning("Error", "El traductor de Google no está disponible. Revisa la terminal para más detalles.")
            return
        if translator_choice == "Ollama" and not OLLAMA_ENABLED:
            show_warning("Error", "El traductor de Ollama no está disponible. Revisa la terminal para más detalles.")
            return

        if not translation_running:
            translation_running = True
            self.log_message(f"Iniciando tarea de traducción con {translator_choice} para {len(translation_windows)} áreas...", "info")
            threading.Thread(target=self.translation_task, daemon=True).start()
            if self.after_id is None:
                self.check_translation_queue()
        else:
            self.log_message("Ya hay una traducción en curso. Por favor, espera.", "info")

    def translation_task(self):
        global translation_running, translation_windows, last_extracted_text_per_roi
        
        current_translator = self.translator_selector.get()

        # Ocultar temporalmente los recuadros para que no interfieran con la captura de pantalla
        hidden_roots = []
        for window_data in translation_windows:
            root = window_data['root']
            if root and root.winfo_exists():
                root.withdraw()
                hidden_roots.append(root)

        # Esperar un momento para que las ventanas se oculten completamente
        time.sleep(0.1)

        try:
            if selected_window:
                try:
                    selected_window.activate()
                except Exception as e:
                    self.log_message(f"Error al activar la ventana: {e}", "error")

            for window_data in translation_windows:
                roi_id = window_data['id']
                roi_coords = window_data['roi_coords']
                
                preprocessed_image = capture_and_preprocess(roi_coords)

                if preprocessed_image is not None:
                    extracted_text, bounding_boxes = perform_ocr(preprocessed_image)

                    if extracted_text and extracted_text != last_extracted_text_per_roi.get(roi_id, ""):
                        self.log_message(f"Texto detectado en ROI {roi_id}: {extracted_text}", "detected")
                        last_extracted_text_per_roi[roi_id] = extracted_text
                        
                        if current_translator == "Google Translate":
                            translated_text = translate_with_google_translate(extracted_text)
                        elif current_translator == "Ollama":
                            translated_text = translate_with_ollama(extracted_text)
                        else:
                            translated_text = "[Error: Traductor no seleccionado]"
                        
                        font_size = calculate_font_size_from_bbox(bounding_boxes)
                        
                        translation_queue.put({'id': roi_id, 'text': translated_text, 'font_size': font_size, 'text_color': self.text_color})
                        self.log_message(f"Traducción para ROI {roi_id}: {translated_text}", "translated")
                    elif not extracted_text:
                        if last_extracted_text_per_roi.get(roi_id, "") != "":
                             last_extracted_text_per_roi[roi_id] = ""
                             translation_queue.put({'id': roi_id, 'text': "", 'font_size': 10, 'text_color': self.text_color})
                             self.log_message(f"No se detectó texto en ROI {roi_id}.", "info")

        except Exception as e:
            self.log_message(f"Error en el hilo de traducción: {e}", "error")
            translation_queue.put({'id': -1, 'text': "[ERROR en el hilo de traducción]", 'font_size': 10, 'text_color': self.text_color})
        finally:
            translation_running = False
            for root in hidden_roots:
                if root and root.winfo_exists():
                    root.deiconify()

    def check_translation_queue(self):
        global translation_windows
        try:
            while not translation_queue.empty():
                message = translation_queue.get_nowait()
                roi_id = message['id']
                translated_text = message['text']
                font_size = message['font_size']
                text_color = message['text_color']


                window_to_update = next((w for w in translation_windows if w['id'] == roi_id), None)

                if window_to_update and window_to_update['root'] and window_to_update['root'].winfo_exists():
                    update_overlay_window(window_to_update['canvas'], window_to_update['text_id'], translated_text,
                                          window_to_update['width'], window_to_update['height'], font_size, text_color)
                elif window_to_update:
                    self.log_message(f"El recuadro {roi_id} no existe. Eliminando de la lista.", "error")
                    self.on_close_overlay(window_to_update['root'])
        except queue.Empty:
            pass
        
        if translation_windows:
            self.after_id = self.after(100, self.check_translation_queue)
        else:
            if self.after_id:
                self.after_cancel(self.after_id)
                self.after_id = None
                self.log_message("No hay recuadros activos, deteniendo el chequeo de la cola.", "info")

    def on_close(self):
        self.stop_hotkey()
        global ollama_process
        if ollama_process and ollama_process.poll() is None:
            ollama_process.terminate()
            print("Servidor de Ollama terminado.")
        for window_data in translation_windows:
            if window_data['root'] and window_data['root'].winfo_exists():
                window_data['root'].destroy()
        self.destroy()

if __name__ == "__main__":
    app = App()
    app.mainloop()