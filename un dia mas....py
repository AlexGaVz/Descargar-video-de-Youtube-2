import os
import re
import sys
import ctypes
import threading
import subprocess
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from yt_dlp import YoutubeDL
from PIL import Image, ImageTk
import requests
from io import BytesIO
import traceback

# Función para minimizar la ventana de la consola en Windows
def minimize_console():
    if sys.platform == "win32":
        try:
            hwnd = ctypes.windll.kernel32.GetConsoleWindow()
            if hwnd:
                ctypes.windll.user32.ShowWindow(hwnd, 2)  # 2 es el código para minimizar
        except Exception as e:
            print(f"Error al minimizar la consola: {e}")

# Llama a la función al inicio
minimize_console()

# Función para sanitizar nombres de archivo
def sanitize_filename(name):
    return re.sub(r'[<>:"/\\|?*]', '_', name)

# Función para generar un nombre adecuado del archivo
def generar_nombre_archivo(destino, titulo_original):
    archivo_path = os.path.join(destino, f"{titulo_original}")
    return archivo_path

# Función para obtener formatos de video y audio usando yt-dlp
def get_formats(url, progress_callback=None):
    ydl_opts = {
        'skip_download': True,
        'quiet': True,
        'no_warnings': True,
        'dump_single_json': True,
    }

    try:
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            return info
    except Exception as e:
        if progress_callback:
            progress_callback(f"Error al obtener formatos: {e}\n{traceback.format_exc()}")
        return None

# Función para obtener y mostrar formatos y la miniatura
def obtener_formatos():
    url = url_entry.get().strip()
    if not url:
        messagebox.showerror("Error", "Por favor, ingresa una URL válida.")
        return
    threading.Thread(target=proceso_obtener_formatos, args=(url,)).start()

def proceso_obtener_formatos(url):
    try:
        info = get_formats(url, progress_callback=mostrar_error)
        if info:
            global video_formats, audio_formats, video_title, thumbnail_url, channel_name
            video_formats = filter_video_formats(info)
            audio_formats = filter_audio_formats(info)
            video_title = sanitize_filename(info.get('title', 'video_sin_titulo'))
            thumbnail_url = info.get('thumbnail')
            channel_name = sanitize_filename(info.get('uploader', 'Canal_Desconocido'))

            # Mostrar el título original
            titulo_var.set(info.get('title', 'Título no disponible'))

            # Mostrar la miniatura del video
            cargar_miniatura(thumbnail_url)

            # Actualizar los combobox
            video_combo['values'] = [
                f"ID: {f['id']} | Resolución: {f['resolution']} | FPS: {f['fps']} | Tamaño: {formatear_tamano(f['filesize'])} | Bitrate: {f['tbr']}k | PROTO: {f['protocol']}"
                for f in video_formats
            ]
            audio_combo['values'] = [
                f"ID: {a['id']} | Formato: {a['ext']} | Tamaño: {formatear_tamano(a['filesize'])} | Bitrate: {a['abr']}k | PROTO: {a['protocol']} | ASR: {a['asr']}Hz"
                for a in audio_formats
            ]
            seleccionar_mejores_formatos()
    except Exception as e:
        mostrar_error(f"Error al procesar la obtención de formatos: {e}\n{traceback.format_exc()}")

# Función para descargar la descripción del video
def descargar_completo():
    url = url_entry.get().strip()
    if not url:
        messagebox.showerror("Error", "Por favor, ingresa una URL válida.")
        return

    threading.Thread(target=proceso_descargar_completo, args=(url,)).start()

def proceso_descargar_completo(url):
    try:
        info = get_formats(url, progress_callback=mostrar_error)
        if info is None:
            return

        # Obtener la descripción y el título
        descripcion = info.get('description', 'No hay descripción disponible.')
        titulo_original = sanitize_filename(info.get('title', 'video_sin_titulo'))
        destino = os.path.expanduser("~/Downloads")
        archivo_descripcion = os.path.join(destino, f"{titulo_original}_descripcion.txt")

        # Guardar la descripción en un archivo de texto
        with open(archivo_descripcion, 'w', encoding='utf-8') as f:
            f.write(f"Título: {titulo_original}\n\nDescripción:\n{descripcion}")

        messagebox.showinfo("Éxito", f"La descripción se ha guardado correctamente como {archivo_descripcion}.")
    except Exception as e:
        mostrar_error(f"Error al descargar la descripción: {e}\n{traceback.format_exc()}")

# Función para filtrar y ordenar formatos de video
def filter_video_formats(info):
    video_formats = []
    if 'formats' in info:
        for fmt in info['formats']:
            if (fmt.get('vcodec') != 'none' and 
                fmt.get('format_note') != 'm3u8_native' and 
                fmt.get('protocol', '').startswith('https')):
                filesize = fmt.get('filesize') or fmt.get('filesize_approx') or 0
                video_formats.append({
                    'id': fmt.get('format_id', 'Desconocido'),
                    'resolution': fmt.get('resolution') or f"{fmt.get('width', '0')}x{fmt.get('height', '0')}",
                    'fps': fmt.get('fps', 'Desconocido'),
                    'filesize': filesize,
                    'tbr': fmt.get('tbr', 'Desconocido'),
                    'protocol': fmt.get('protocol', 'Desconocido')
                })
    video_formats.sort(key=lambda x: x['filesize'], reverse=True)
    return video_formats

# Función para filtrar y ordenar formatos de audio
def filter_audio_formats(info):
    audio_formats = []
    if 'formats' in info:
        for fmt in info['formats']:
            if (fmt.get('acodec') != 'none' and 
                fmt.get('ext') == 'm4a' and 
                '-drc' not in fmt.get('format_id', '')):
                filesize = fmt.get('filesize') or fmt.get('filesize_approx') or 0
                audio_formats.append({
                    'id': fmt.get('format_id', 'Desconocido'),
                    'ext': fmt.get('ext', 'Desconocido'),
                    'filesize': filesize,
                    'tbr': fmt.get('tbr', 'Desconocido'),
                    'protocol': fmt.get('protocol', 'Desconocido'),
                    'abr': fmt.get('abr', 'Desconocido'),
                    'asr': fmt.get('asr', 'Desconocido')
                })
    audio_formats.sort(key=lambda x: x['filesize'], reverse=True)
    return audio_formats

# Función para actualizar la selección automática de los mejores formatos
def seleccionar_mejores_formatos():
    if video_formats:
        video_combo.current(0)
        actualizar_detalles_video()
    if audio_formats:
        audio_combo.current(0)
        actualizar_detalles_audio()

# Función para mostrar detalles del formato de video seleccionado
def actualizar_detalles_video(event=None):
    try:
        selected = video_combo.get()
        detalles = ""
        for fmt in video_formats:
            formato = f"ID: {fmt['id']} | Resolución: {fmt['resolution']} | FPS: {fmt['fps']} | Tamaño: {formatear_tamano(fmt['filesize'])} | Bitrate: {fmt['tbr']}k | PROTO: {fmt['protocol']}"
            if formato == selected:
                detalles = f"--- Detalles del Video ---\n{formato}"
                break
        actualizar_cuadro_texto('video', detalles)
    except Exception as e:
        mostrar_error(f"Error al actualizar detalles del video: {e}\n{traceback.format_exc()}")

# Función para mostrar detalles del formato de audio seleccionado
def actualizar_detalles_audio(event=None):
    try:
        selected = audio_combo.get()
        detalles = ""
        for fmt in audio_formats:
            formato = f"ID: {fmt['id']} | Formato: {fmt['ext']} | Tamaño: {formatear_tamano(fmt['filesize'])} | Bitrate: {fmt['abr']}k | PROTO: {fmt['protocol']} | ASR: {fmt['asr']}Hz"
            if formato == selected:
                detalles = f"--- Detalles del Audio ---\n{formato}"
                break
        actualizar_cuadro_texto('audio', detalles)
    except Exception as e:
        mostrar_error(f"Error al actualizar detalles del audio: {e}\n{traceback.format_exc()}")

# Función para formatear el tamaño de archivo
def formatear_tamano(tamano_bytes):
    try:
        if tamano_bytes >= 1024**3:
            return f"{tamano_bytes / (1024**3):.2f}GiB"
        elif tamano_bytes >= 1024**2:
            return f"{tamano_bytes / (1024**2):.2f}MiB"
        elif tamano_bytes >= 1024:
            return f"{tamano_bytes / 1024:.2f}KiB"
        else:
            return f"{tamano_bytes}B"
    except Exception as e:
        mostrar_error(f"Error al formatear el tamaño de archivo: {e}\n{traceback.format_exc()}")
        return "Desconocido"

# Función para actualizar el cuadro de texto de detalles
def actualizar_cuadro_texto(tipo, contenido):
    try:
        if tipo == 'video':
            detalles_video.config(state='normal')
            detalles_video.delete('1.0', tk.END)
            detalles_video.insert(tk.END, contenido)
            detalles_video.config(state='disabled')
        elif tipo == 'audio':
            detalles_audio.config(state='normal')
            detalles_audio.delete('1.0', tk.END)
            detalles_audio.insert(tk.END, contenido)
            detalles_audio.config(state='disabled')
    except Exception as e:
        mostrar_error(f"Error al actualizar el cuadro de texto de detalles: {e}\n{traceback.format_exc()}")

# Función para limpiar caracteres ANSI
def limpiar_ansi(cadena):
    try:
        ansi_escape = re.compile(r'\x1B\[[0-?]*[ -/]*[@-~]')
        return ansi_escape.sub('', cadena)
    except Exception as e:
        mostrar_error(f"Error al limpiar caracteres ANSI: {e}\n{traceback.format_exc()}")
        return cadena

# Función para descargar video y audio seleccionados, incluyendo playlists
def descargar_video_audio():
    url = url_entry.get().strip()
    if not video_combo.get() or not audio_combo.get():
        messagebox.showerror("Error", "Por favor, selecciona tanto un formato de video como de audio.")
        return

    threading.Thread(target=proceso_descargar_video_audio, args=(url,)).start()

def proceso_descargar_video_audio(url):
    try:
        # Obtener información para verificar si es playlist
        info = get_formats(url, progress_callback=mostrar_error)
        if info is None:
            return

        # Establecer el destino en la carpeta de Descargas sin crear carpetas adicionales
        destino = os.path.expanduser("~/Downloads")

        # Generar el nombre del archivo para guardar
        video_title_formatted = sanitize_filename(info.get('title', 'video_sin_titulo'))
        archivo_base = generar_nombre_archivo(destino, video_title_formatted)

        # Descargar video y audio seleccionados
        video_format_id = re.search(r"ID: (\d+)", video_combo.get()).group(1)
        audio_format_id = re.search(r"ID: (\d+)", audio_combo.get()).group(1)

        video_file = f"{archivo_base}_video.mp4"
        audio_file = f"{archivo_base}_audio.m4a"

        ydl_opts_video = {
            'format': video_format_id,
            'outtmpl': video_file,
            'quiet': True,
            'no_warnings': True,
            'progress_hooks': [hook_descargar_video],
        }

        ydl_opts_audio = {
            'format': audio_format_id,
            'outtmpl': audio_file,
            'quiet': True,
            'no_warnings': True,
            'progress_hooks': [hook_descargar_audio],
        }

        # Descargar el video
        with YoutubeDL(ydl_opts_video) as ydl:
            ydl.download([url])

        # Descargar el audio
        with YoutubeDL(ydl_opts_audio) as ydl:
            ydl.download([url])

        # Verificar la existencia de los archivos
        if not os.path.isfile(video_file) or not os.path.isfile(audio_file):
            mostrar_error(f"Error: No se encontraron los archivos de video o audio en {destino}")
            return

        # Combinar video y audio usando ffmpeg
        archivo_combinado = f"{archivo_base}.mp4"
        comando_ffmpeg = [
            'ffmpeg',
            '-i', video_file,
            '-i', audio_file,
            '-c:v', 'copy',
            '-c:a', 'aac',
            '-strict', 'experimental',
            '-y',
            archivo_combinado
        ]

        proceso = subprocess.Popen(comando_ffmpeg, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)

        stderr_output = []
        for linea in proceso.stderr:
            stderr_output.append(linea)
            if 'time=' in linea:
                match = re.search(r'time=(\d+):(\d+):(\d+\.\d+)', linea)
                if match:
                    horas, minutos, segundos = match.groups()
                    total_segundos = int(horas) * 3600 + int(minutos) * 60 + float(segundos)
                    porcentaje = min((total_segundos / 300) * 100, 100)
                    actualizar_progreso_combinacion(porcentaje)
                    root.update_idletasks()

        proceso.wait()

        if proceso.returncode == 0:
            barra_progreso.config(value=100)
            actualizar_porcentaje_texto(100)
            progreso_label.config(text="Proceso completado.")

            # Eliminar archivos temporales de video y audio
            if os.path.exists(video_file):
                os.remove(video_file)
            if os.path.exists(audio_file):
                os.remove(audio_file)

            messagebox.showinfo("Éxito", f"El video se ha descargado y combinado correctamente como {archivo_combinado}.")
        else:
            mostrar_error("Error en la combinación con ffmpeg:\n" + "".join(stderr_output))
            messagebox.showerror("Error", "Ocurrió un error al combinar el video y el audio.")

    except Exception as e:
        mostrar_error(f"Error durante la descarga o combinación: {e}\n{traceback.format_exc()}")

# Hooks de progreso para actualizar la barra de progreso
def hook_descargar_video(d):
    if d['status'] == 'downloading':
        porcentaje_str = limpiar_ansi(d['_percent_str']).strip('%')
        try:
            porcentaje = float(porcentaje_str)
            barra_progreso.config(value=porcentaje / 3)
            actualizar_porcentaje_texto(porcentaje / 3)
            root.update_idletasks()
        except ValueError:
            mostrar_error(f"Error al convertir porcentaje de video: {porcentaje_str}")

def hook_descargar_audio(d):
    if d['status'] == 'downloading':
        porcentaje_str = limpiar_ansi(d['_percent_str']).strip('%')
        try:
            porcentaje = float(porcentaje_str) + 33.33
            barra_progreso.config(value=porcentaje)
            actualizar_porcentaje_texto(porcentaje)
            root.update_idletasks()
        except ValueError:
            mostrar_error(f"Error al convertir porcentaje de audio: {porcentaje_str}")

def actualizar_progreso_combinacion(porcentaje):
    porcentaje_completo = porcentaje + 66.67
    barra_progreso.config(value=porcentaje_completo)
    actualizar_porcentaje_texto(porcentaje_completo)
    root.update_idletasks()

# Función para actualizar el porcentaje numérico en la barra de progreso
def actualizar_porcentaje_texto(porcentaje):
    porcentaje_str = f"%{porcentaje:.2f}"
    progreso_label.config(text=f"Progreso: {porcentaje_str}")

# Función para mostrar la miniatura
def cargar_miniatura(url):
    try:
        response = requests.get(url)
        img_data = response.content
        img = Image.open(BytesIO(img_data))
        img.thumbnail((200, 150))  # Ajustar tamaño de la miniatura
        img_tk = ImageTk.PhotoImage(img)
        thumbnail_label.config(image=img_tk)
        thumbnail_label.image = img_tk  # Guardar referencia para evitar que la imagen se elimine
    except Exception as e:
        mostrar_error(f"Error al cargar la miniatura: {e}\n{traceback.format_exc()}")

# Función para mostrar errores en el cuadro de advertencias
def mostrar_error(mensaje):
    cuadro_advertencia.config(state='normal')
    cuadro_advertencia.insert(tk.END, f"{mensaje}\n")
    cuadro_advertencia.config(state='disabled')
    print(mensaje)  # También imprime el error en la consola para mayor detalle

# Configuración de la ventana principal con Scrollbar y Modo Oscuro
root = tk.Tk()
root.title("Descargador de Videos de YouTube")
root.geometry("864x869")
root.minsize(864, 869)
root.resizable(True, True)

# Colores para el modo oscuro
bg_color = "#2e2e2e"
fg_color = "#ffffff"
entry_bg = "#3e3e3e"
text_bg = "#4e4e4e"

# Crear un Canvas y un Frame dentro para permitir scroll
canvas = tk.Canvas(root, borderwidth=0, background=bg_color)
frame = tk.Frame(canvas, background=bg_color)
vsb = tk.Scrollbar(root, orient="vertical", command=canvas.yview)
canvas.configure(yscrollcommand=vsb.set)

vsb.pack(side="right", fill="y")
canvas.pack(side="left", fill="both", expand=True)
canvas.create_window((4, 4), window=frame, anchor="nw")

def on_frame_configure(event):
    canvas.configure(scrollregion=canvas.bbox("all"))

frame.bind("<Configure>", on_frame_configure)

# Continuación de la configuración de la interfaz

# URL de entrada
tk.Label(frame, text="Ingresa la URL del video de YouTube:", font=('Arial', 10, 'bold'), bg=bg_color, fg=fg_color).pack(pady=(10, 5), padx=20, anchor='w')
url_entry = tk.Entry(frame, width=80, font=('Arial', 10), bg=entry_bg, fg=fg_color, insertbackground=fg_color)
url_entry.pack(pady=(0, 10), padx=20)

# Botón para obtener formatos
get_formats_button = tk.Button(frame, text="Obtener formatos", command=obtener_formatos, font=('Arial', 10), bg="#4e4e4e", fg=fg_color)
get_formats_button.pack(pady=(0, 10), padx=20, anchor='center')

# Cuadro para mostrar el título original del video
titulo_var = tk.StringVar(value="Título del video")
titulo_label = tk.Label(frame, textvariable=titulo_var, font=('Arial', 10), bg=bg_color, fg=fg_color)
titulo_label.pack(pady=(0, 10), padx=20, anchor='w')

# Combobox para mostrar formatos de video
tk.Label(frame, text="Formatos de Video:", font=('Arial', 10, 'bold'), bg=bg_color, fg=fg_color).pack(pady=(0, 5), padx=20, anchor='w')
video_combo = ttk.Combobox(frame, width=90, state='readonly', font=('Arial', 10))
video_combo.pack(pady=(0, 10), padx=20)
video_combo.bind("<<ComboboxSelected>>", actualizar_detalles_video)

# Combobox para mostrar formatos de audio
tk.Label(frame, text="Formatos de Audio:", font=('Arial', 10, 'bold'), bg=bg_color, fg=fg_color).pack(pady=(10, 5), padx=20, anchor='w')
audio_combo = ttk.Combobox(frame, width=90, state='readonly', font=('Arial', 10))
audio_combo.pack(pady=(0, 10), padx=20)
audio_combo.bind("<<ComboboxSelected>>", actualizar_detalles_audio)

# Mostrar la miniatura del video
thumbnail_label = tk.Label(frame, bg=bg_color)
thumbnail_label.pack(pady=(10, 10), padx=20)

# Cuadro de texto para detalles de formato
tk.Label(frame, text="Detalles:", font=('Arial', 10, 'bold'), bg=bg_color, fg=fg_color).pack(pady=(10, 5), padx=20, anchor='w')
detalles_frame = tk.Frame(frame, bg=bg_color)
detalles_frame.pack(pady=(0, 10), padx=20, fill='both', expand=True)

detalles_video = scrolledtext.ScrolledText(detalles_frame, width=80, height=5, state='disabled', bg=text_bg, fg=fg_color, font=('Arial', 10))
detalles_video.pack(pady=(0, 5), padx=5, fill='x')

detalles_audio = scrolledtext.ScrolledText(detalles_frame, width=80, height=5, state='disabled', bg=text_bg, fg=fg_color, font=('Arial', 10))
detalles_audio.pack(pady=(0, 5), padx=5, fill='x')

# Cuadro de texto para mostrar errores y advertencias
tk.Label(frame, text="Errores y Advertencias:", font=('Arial', 10, 'bold'), bg=bg_color, fg=fg_color).pack(pady=(10, 5), padx=20, anchor='w')
cuadro_advertencia = scrolledtext.ScrolledText(frame, width=80, height=5, state='disabled', bg='#ffdddd', fg='black', font=('Arial', 10))
cuadro_advertencia.pack(pady=(0, 10), padx=20, fill='x')

# Barra de progreso y etiqueta de progreso
progreso_label = tk.Label(frame, text="Progreso: %00.00", font=('Arial', 10, 'bold'), bg=bg_color, fg=fg_color)
progreso_label.pack(pady=(0, 5), padx=20, anchor='w')

barra_progreso = ttk.Progressbar(frame, orient="horizontal", length=800, mode="determinate")
barra_progreso.pack(pady=(0, 10), padx=20, fill='x')

# Botones para descargar el video y descargar la descripción completa
button_frame = tk.Frame(frame, bg=bg_color)
button_frame.pack(pady=(0, 10), padx=20, anchor='w')

download_button = tk.Button(button_frame, text="Descargar", command=descargar_video_audio, bg='#1e90ff', fg='white', font=('Arial', 10, 'bold'))
download_button.pack(side='left', padx=(0, 10))

download_full_button = tk.Button(button_frame, text="Descargar Completo", command=descargar_completo, bg='#4e4e4e', fg='white', font=('Arial', 10, 'bold'))
download_full_button.pack(side='left')

# Variables globales
video_formats = []
audio_formats = []
video_title = ""
thumbnail_url = ""
channel_name = ""

# Ejecutar la ventana principal
root.mainloop()
