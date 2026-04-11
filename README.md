# MergeMasterPDF

Aplicacion de escritorio en Python para unir, ordenar, dividir y previsualizar archivos PDF desde una sola interfaz.

## Funciones

- Unir varios PDF en un solo archivo
- Combinar archivos por nombre
- Separar PDF por paginas
- Eliminar paginas de un PDF
- Rotar paginas
- Reordenar paginas con editor visual
- Vista previa y miniaturas
- Soporte para arrastrar y soltar
- Guardar y cargar proyectos
- Tema oscuro y claro

## Descarga recomendada

La forma recomendada de usar MergeMasterPDF es el build portable:

1. Descarga el archivo `MergeMasterPDF-v1.0.1-windows-x64.zip`
2. Extrae la carpeta
3. Ejecuta `MergeMasterPDF.exe`

## Capturas

![Tema claro](screenshots/theme_lith.png)
![Tema oscuro](screenshots/theme_dark.png)
![Vista previa](screenshots/preview.png)
![Editor visual](screenshots/editor.png)

## Requisitos para desarrollo

- Python 3.14 o compatible
- Dependencias de `requirements.txt`

## Instalacion local

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Ejecutar desde codigo fuente

```powershell
.\.venv\Scripts\python.exe .\MergeMasterPDF.py
```

## Generar build para Windows

```powershell
.\build_windows.ps1
```

El script genera por defecto:

- `dist\MergeMasterPDF\MergeMasterPDF.exe`
- `dist\MergeMasterPDF-v1.0.1-windows-x64.zip`

Si quieres generar tambien instalador:

```powershell
$env:MMP_BUILD_INSTALLER="1"
.\build_windows.ps1
```

## Notas

- `config.json` se guarda junto al proyecto al ejecutar desde codigo fuente y en `%APPDATA%\MergeMasterPDF` al usar el build empaquetado.
- `build/`, `dist/` e instaladores quedan fuera del repo.

## Licencia

Uso personal gratuito.

El uso comercial, redistribucion o venta requiere permiso del autor. Revisa [LICENSE.txt](LICENSE.txt).

## Autor

Alan Juarez
