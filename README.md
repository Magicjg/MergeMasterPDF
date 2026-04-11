# MergeMasterPDF

Aplicacion de escritorio para Windows hecha en Python para unir, ordenar, dividir y revisar PDFs desde una sola interfaz.

[Descargar release portable](https://github.com/Magicjg/MergeMasterPDF/releases/tag/v1.0.1)

## Lo que puedes hacer

- Unir varios PDF en un solo archivo
- Combinar documentos por nombre
- Separar PDFs por paginas
- Eliminar paginas concretas
- Rotar paginas
- Reordenar paginas con editor visual
- Ver miniaturas y vista previa
- Arrastrar y soltar archivos
- Guardar y cargar proyectos
- Cambiar entre tema claro y oscuro

## Descarga recomendada

La forma mas comoda de usar MergeMasterPDF es el build portable para Windows:

1. Descarga [MergeMasterPDF-v1.0.1-windows-x64.zip](https://github.com/Magicjg/MergeMasterPDF/releases/download/v1.0.1/MergeMasterPDF-v1.0.1-windows-x64.zip)
2. Extrae la carpeta
3. Ejecuta `MergeMasterPDF.exe`

## Capturas

### Tema claro

![Tema claro](screenshots/theme_lith.png)

### Tema oscuro

![Tema oscuro](screenshots/theme_dark.png)

### Vista previa

![Vista previa](screenshots/preview.png)

### Editor visual

![Editor visual](screenshots/editor.png)

## Desarrollo local

Requisitos:

- Python 3.14 o compatible
- Dependencias de [requirements.txt](requirements.txt)

Instalacion:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Ejecutar desde codigo fuente:

```powershell
.\.venv\Scripts\python.exe .\MergeMasterPDF.py
```

## Build para Windows

Generar ejecutable portable:

```powershell
.\build_windows.ps1
```

Salida esperada:

- `dist\MergeMasterPDF\MergeMasterPDF.exe`
- `dist\MergeMasterPDF-v1.0.1-windows-x64.zip`

Si quieres generar tambien instalador:

```powershell
$env:MMP_BUILD_INSTALLER="1"
.\build_windows.ps1
```

## Notas

- `config.json` se guarda junto al proyecto al ejecutar desde codigo fuente.
- En el build empaquetado la configuracion se guarda en `%APPDATA%\MergeMasterPDF`.
- `build/`, `dist/` e instaladores quedan fuera del repo.

## Licencia

Uso personal gratuito.

El uso comercial, redistribucion o venta requiere permiso del autor. Revisa [LICENSE.txt](LICENSE.txt).

## Autor

Alan Juarez
