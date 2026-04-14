# 📚 Biblioteca Escolar — Sistema de Inventario

App web local hecha en Python + Flask. No necesita internet para funcionar.

---

## Requisitos

- Python 3.8 o superior (descárgalo en https://python.org si no lo tienes)

---

## Instalación (primera vez)

### Windows

1. Abre la carpeta `biblioteca` en el Explorador de archivos
2. En la barra de dirección escribe `cmd` y presiona Enter
3. Ejecuta estos comandos uno por uno:

```
python -m pip install flask
python app.py
```

### Mac / Linux

1. Abre Terminal y navega a la carpeta:
```bash
cd ruta/a/biblioteca
pip install flask
python app.py
```

---

## Abrir la app

Después de ejecutar `python app.py`, abre tu navegador y ve a:

**http://localhost:5000**

Usuario: `admin`
Contraseña: `admin123`

> ⚠️ Cambia la contraseña del admin después del primer inicio de sesión (o directamente en la base de datos).

---

## Apagar la app

En la ventana de Terminal o CMD donde está corriendo, presiona `Ctrl + C`.

---

## Datos

Todos los datos se guardan en el archivo `biblioteca.db` que se crea automáticamente en la misma carpeta. Haz copias de ese archivo para tener respaldo.

---

## Funciones principales

- **Inicio**: panel con estadísticas del día, libros que se deben devolver hoy, préstamos vencidos y por vencer.
- **Libros**: inventario por título. Cada libro tiene ejemplares físicos individuales (Ejemplar #1, #2, etc.).
- **Préstamos**: registra quién lleva qué ejemplar, por cuántas semanas (máximo 3). Marca devoluciones con un clic.
- **Donaciones**: registra donantes. Los ejemplares se suman al inventario automáticamente.
- **Reportes**: libros más prestados, stock por categoría, lista de vencidos.
