# Sanguinius
Una herramienta de escritorio en Python para la traducción en tiempo real de texto en juegos (como novelas visuales) mediante una superposición. Utiliza OCR para extraer texto y ofrece traducción a través de la API de Google Translate o un modelo local de Ollama.

Guía de Instalación y Uso de VN Realtime Translator
Este tutorial te guiará a través de la instalación de todos los componentes necesarios para que el programa funcione correctamente, desde el entorno de desarrollo hasta los traductores.

1. Requisitos Previos (Descargas Iniciales)
Antes de empezar, debes tener instalado Python, Git y, si quieres la opción de traducción local, Ollama. Haz clic en los siguientes enlaces para descargarlos.

Python (Versión 3.9 o superior):

Descarga desde el sitio oficial: https://www.python.org/downloads/

Importante: Durante la instalación, asegúrate de marcar la casilla "Add Python to PATH". Esto permitirá que los comandos de Python funcionen desde cualquier lugar en tu terminal.

Git:

Descarga desde el sitio oficial: https://git-scm.com/downloads

Git se usará para descargar el código del programa desde GitHub. Puedes instalarlo con las opciones por defecto.

Ollama (Opcional, para traducción local):

Descarga desde el sitio oficial: https://ollama.com/download

Si prefieres usar solo el traductor de Google, puedes omitir este paso.

2. Obtener el Código y Preparar el Entorno
Ahora que tienes los requisitos instalados, vamos a descargar el código y a preparar un entorno de desarrollo aislado.

1. Descargar el programa
Abre tu terminal de comandos (CMD en Windows, PowerShell o Git Bash) y ejecuta el siguiente comando para descargar la carpeta del proyecto.

Bash

git clone https://github.com/TuUsuario/vn-realtime-translator.git
⚠️ Nota: Reemplaza https://github.com/TuUsuario/vn-realtime-translator.git con la URL real de tu repositorio.

2. Navegar a la carpeta del programa
Usa el comando cd para entrar en la carpeta que acabas de descargar:

Bash

cd vn-realtime-translator
3. Crear y activar el entorno virtual
Es una buena práctica instalar las librerías en un entorno virtual para no afectar otras instalaciones de Python en tu sistema.

Crear el entorno virtual:

Bash

python -m venv venv
Activar el entorno virtual:

Bash

venv\Scripts\activate
Verás que el nombre de tu terminal cambia para indicar que el entorno está activo.

3. Instalar Dependencias y Configuraciones
Con el entorno virtual activado, instala todas las librerías de Python necesarias para que el programa funcione.

1. Instalar las librerías Python
Ejecuta este comando en tu terminal para instalar todas las dependencias:

Bash

pip install Pillow opencv-python numpy easyocr pygetwindow keyboard customtkinter googletrans requests
googletrans y requests son las librerías para los traductores. No te preocupes si no vas a usar una de ellas, la otra seguirá funcionando.

easyocr es el motor de reconocimiento de texto que necesitará descargar modelos de idioma la primera vez que se ejecute el programa.

2. Descargar el modelo de Ollama (Opcional)
Si instalaste Ollama, ejecuta este comando en una terminal nueva (puedes dejar la anterior abierta) para descargar el modelo de lenguaje mistral, que es el que se usa en el código.

Bash

ollama run mistral
Si te pregunta si quieres descargar el modelo, escribe Y y presiona Enter. Espera a que termine la descarga. Puedes cerrar esta terminal cuando termine.

4. Ejecutar el Programa y Uso Básico
Ya estás listo para usar el programa.

Asegúrate de que tu entorno virtual esté activo ((venv) debe aparecer en la terminal).

Ejecuta el programa con el siguiente comando:

Bash

python vn_realtime_translator_overlay_fixed.py
Se abrirá la interfaz gráfica. Desde ahí, podrás:

Seleccionar motor de traducción: Elegir entre Ollama y Google Translate.

Seleccionar Ventana del Juego: Elegir la ventana del juego o aplicación que quieres traducir.

Seleccionar Área de OCR: Usar el mouse para dibujar una caja alrededor de la zona de la pantalla que quieres capturar.

Establecer Tecla de acceso rápido: Definir la combinación de teclas que, al ser presionada, activará la traducción.

¡Y eso es todo! Ahora puedes disfrutar de tu traductor en tiempo real.







