# 3ltrs

Minecraft profile name monitor · Monitor de nombres de perfil de Minecraft

Watches the Mojang API and can request the name change on the official site.
Vigila la API de Mojang y puede pedir el cambio en la web oficial.

---

## English

### Features

- Watch a name (3–16 characters)
- **Automatic**: only tries if the API does not find the profile
- **Manual**: also tries when the API still says taken (API lag)
- Uses the official minecraft.net form
- Success only when the website confirms the change
- **Language picker** at startup (Español / English)

### Requirements

- Python 3.9+

```bash
pip install requests playwright
playwright install chromium
```

### Usage

```bash
python 3ltrs.py
```

1. Choose language (1 = Español, 2 = English)  
2. Enter the name  
3. Choose interface (full / minimal)  
4. Choose detection (automatic / manual)  
5. Sign in on the browser, then press ENTER in the console  

Stop: `CTRL+C`

### Common errors

#### Browser closed

```text
[ERROR]  Browser closed.

  You closed the browser window (or the session was lost).
  Without the browser the monitor cannot continue.
```

**Cause:** you closed Chromium, or the browser profile was locked.  
**Fix:** do not close the window opened by the script. Run again if needed.

#### TargetClosedError

Internal Playwright error when the page/context is gone. The app maps it to **Browser closed**.

#### HTTP 429

API rate limit. The monitor backs off and retries.

---

## Español

### Qué hace

- Vigila un nombre (3–16 caracteres)
- **Automático**: solo intenta si la API no encuentra el perfil
- **Manual**: intenta también si la API sigue diciendo ocupado
- Usa el formulario oficial de minecraft.net
- Solo confirma el éxito cuando la web lo muestra
- **Selector de idioma** al arrancar (Español / English)

### Requisitos

- Python 3.9+

```bash
pip install requests playwright
playwright install chromium
```

### Uso

```bash
python 3ltrs.py
```

1. Elige idioma (1 = Español, 2 = English)  
2. Escribe el nombre  
3. Elige interfaz (completa / minimal)  
4. Elige detección (automática / manual)  
5. Inicia sesión en el navegador y pulsa ENTER en la consola  

Detener: `CTRL+C`

### Errores habituales

#### Navegador cerrado

```text
[ERROR]  Navegador cerrado.

  Cerraste la ventana del navegador (o se perdió la sesión).
  Sin el navegador el monitor no puede seguir.
```

**Causa:** cerraste Chromium o el perfil quedó bloqueado.  
**Qué hacer:** no cierres la ventana que abre el script. Vuelve a ejecutarlo si hace falta.

#### TargetClosedError

Error interno de Playwright cuando la página ya no existe. Se muestra como **Navegador cerrado**.

#### HTTP 429

Límite de la API. El monitor espera y reintenta.

---

## License / Licencia

Personal / educational use. No warranty.  
Uso personal / educativo. Sin garantías.

