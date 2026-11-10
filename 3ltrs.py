#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
3ltrs Profile Name Monitor

Vigila un nombre y puede pedir el cambio en minecraft.net.

Dependencias:
    pip install requests playwright
    playwright install chromium

Nota:
    La API de Mojang a veces tarda minutos u horas en actualizarse.
    Un 200 no siempre significa que el nombre siga bloqueado en la web,
    ni un 204/404 garantiza el cambio. Solo cuenta la confirmación en
    la página oficial.
"""

from __future__ import annotations

import logging
import os
import re
import sys
import time
import traceback
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

DEPENDENCY_ERROR: Optional[str] = None

try:
    import requests
except ImportError as exc:
    requests = None  # type: ignore[assignment]
    DEPENDENCY_ERROR = f"Falta la dependencia 'requests': {exc}"

try:
    from playwright.sync_api import (
        Error as PlaywrightError,
        Locator,
        Page,
        TimeoutError as PlaywrightTimeoutError,
        sync_playwright,
    )
except ImportError as exc:
    Locator = Page = object  # type: ignore[misc,assignment]
    PlaywrightTimeoutError = TimeoutError  # type: ignore[assignment]
    PlaywrightError = Exception  # type: ignore[assignment,misc]
    sync_playwright = None  # type: ignore[assignment]
    DEPENDENCY_ERROR = f"Falta Playwright o no se puede importar: {exc}"


class BrowserClosedError(RuntimeError):
    """El usuario cerró el navegador o el contexto de Playwright se perdió."""
    pass


def is_browser_closed_error(exc: BaseException) -> bool:
    """Detecta cierre de página/contexto/navegador de Playwright."""
    name = type(exc).__name__
    if name in {"TargetClosedError", "BrowserClosedError"}:
        return True
    msg = str(exc).lower()
    return (
        "target page, context or browser has been closed" in msg
        or "browser has been closed" in msg
        or "context has been closed" in msg
        or "target closed" in msg
    )


def safe_wait(page: Page, ms: int) -> None:
    """Espera sin tumbar el programa si el navegador ya está cerrado."""
    try:
        page.wait_for_timeout(ms)
    except Exception as exc:
        if is_browser_closed_error(exc):
            raise BrowserClosedError(
                "El navegador se cerró. El monitor no puede continuar."
            ) from exc
        raise


# ============================================================================
# CONFIGURACIÓN
# ============================================================================

@dataclass(frozen=True)
class Config:
    profile_url: str = "https://www.minecraft.net/es-es/msaprofile"
    api_url: str = "https://api.mojang.com/users/profiles/minecraft/{}"
    browser_profile: Path = Path.home() / "minecraft_brave_profile"
    log_directory: Path = Path.home() / "minecraft_name_monitor_logs"
    poll_interval: float = 30.0
    field_timeout_ms: int = 15_000
    max_modal_attempts: int = 4
    max_failed_submissions: int = 4
    backoff_min: float = 20.0
    backoff_max: float = 180.0
    request_timeout: float = 12.0
    force_attempt_cooldown: float = 45.0


CONFIG = Config()


class Color:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"

    # Interfaz en cian; gris para secundario
    CYAN = "\033[36m"
    BRIGHT_CYAN = "\033[96m"
    GRAY = "\033[90m"
    # Solo éxito
    BRIGHT_GREEN = "\033[92m"


if os.name == "nt":
    os.system("")


def paint(text: str, color: str, *, bold: bool = False) -> str:
    weight = Color.BOLD if bold else ""
    return f"{weight}{color}{text}{Color.RESET}"


def clear_screen() -> None:
    os.system("cls" if os.name == "nt" else "clear")


def line(char: str = "─", width: int = 68, color: str = Color.GRAY) -> str:
    return paint(char * width, color)


def logo() -> None:
    """Logo 3 LTRS en cian, letras separadas (sin parecer 3LItrs)."""
    print()
    print(paint("╔════════════════════════════════════════════════════════════════════╗",
                Color.BRIGHT_CYAN, bold=True))
    print(
        paint("║  ", Color.BRIGHT_CYAN)
        + paint("██████╗", Color.BRIGHT_CYAN, bold=True) + paint("  ", Color.BRIGHT_CYAN)
        + paint("██╗     ", Color.CYAN, bold=True)
        + paint("████████╗", Color.BRIGHT_CYAN, bold=True) + paint(" ", Color.BRIGHT_CYAN)
        + paint("██████╗ ", Color.CYAN, bold=True)
        + paint("███████╗", Color.BRIGHT_CYAN, bold=True)
        + paint(" ║", Color.BRIGHT_CYAN)
    )
    print(
        paint("║  ", Color.BRIGHT_CYAN)
        + paint("╚════██╗", Color.CYAN, bold=True) + paint("  ", Color.BRIGHT_CYAN)
        + paint("██║     ", Color.BRIGHT_CYAN, bold=True)
        + paint("╚══██╔══╝", Color.CYAN, bold=True) + paint(" ", Color.BRIGHT_CYAN)
        + paint("██╔══██╗", Color.BRIGHT_CYAN, bold=True)
        + paint("██╔════╝", Color.CYAN, bold=True)
        + paint(" ║", Color.BRIGHT_CYAN)
    )
    print(
        paint("║  ", Color.BRIGHT_CYAN)
        + paint(" █████╔╝", Color.BRIGHT_CYAN, bold=True) + paint("  ", Color.BRIGHT_CYAN)
        + paint("██║     ", Color.CYAN, bold=True)
        + paint("   ██║   ", Color.BRIGHT_CYAN, bold=True) + paint(" ", Color.BRIGHT_CYAN)
        + paint("██████╔╝", Color.CYAN, bold=True)
        + paint("███████╗", Color.BRIGHT_CYAN, bold=True)
        + paint(" ║", Color.BRIGHT_CYAN)
    )
    print(
        paint("║  ", Color.BRIGHT_CYAN)
        + paint(" ╚═══██╗", Color.CYAN, bold=True) + paint("  ", Color.BRIGHT_CYAN)
        + paint("██║     ", Color.BRIGHT_CYAN, bold=True)
        + paint("   ██║   ", Color.CYAN, bold=True) + paint(" ", Color.BRIGHT_CYAN)
        + paint("██╔══██╗", Color.BRIGHT_CYAN, bold=True)
        + paint("╚════██║", Color.CYAN, bold=True)
        + paint(" ║", Color.BRIGHT_CYAN)
    )
    print(
        paint("║  ", Color.BRIGHT_CYAN)
        + paint("███████║", Color.BRIGHT_CYAN, bold=True) + paint("  ", Color.BRIGHT_CYAN)
        + paint("███████╗", Color.CYAN, bold=True)
        + paint("   ██║   ", Color.BRIGHT_CYAN, bold=True) + paint(" ", Color.BRIGHT_CYAN)
        + paint("██║  ██║", Color.CYAN, bold=True)
        + paint("███████║", Color.BRIGHT_CYAN, bold=True)
        + paint(" ║", Color.BRIGHT_CYAN)
    )
    print(
        paint("║  ", Color.BRIGHT_CYAN)
        + paint("╚══════╝", Color.CYAN, bold=True) + paint("  ", Color.BRIGHT_CYAN)
        + paint("╚══════╝", Color.BRIGHT_CYAN, bold=True)
        + paint("   ╚═╝   ", Color.CYAN, bold=True) + paint(" ", Color.BRIGHT_CYAN)
        + paint("╚═╝  ╚═╝", Color.BRIGHT_CYAN, bold=True)
        + paint("╚══════╝", Color.CYAN, bold=True)
        + paint(" ║", Color.BRIGHT_CYAN)
    )
    print(
        paint("║", Color.BRIGHT_CYAN)
        + paint("               3  L  T  R  S  ·  MINECRAFT TOOL", Color.CYAN, bold=True)
        + paint("              ║", Color.BRIGHT_CYAN)
    )
    print(paint("╚════════════════════════════════════════════════════════════════════╝",
                Color.BRIGHT_CYAN, bold=True))
    print(paint("                      PROFILE  MONITOR", Color.CYAN, bold=True))
    print()


def section(title: str, subtitle: Optional[str] = None) -> None:
    print()
    print(paint(title.upper(), Color.BRIGHT_CYAN, bold=True))
    if subtitle:
        print(paint(subtitle, Color.CYAN))
    print(line(color=Color.CYAN))
    print()


def status(label: str, message: str, color: str = Color.CYAN) -> None:
    stamp = datetime.now().strftime("%H:%M:%S")
    print(
        f"{paint(stamp, Color.GRAY)}  "
        f"{paint(f'[{label}]', color, bold=True)}  "
        f"{message}"
    )


def pause(message: str = "Pulsa ENTER para continuar...") -> None:
    input("\n" + paint(message, Color.GRAY))


def show_help() -> None:
    clear_screen()
    logo()
    section("Ayuda", "Lo esencial para usar el monitor.")

    print(paint("Retrasos de Mojang", Color.BRIGHT_CYAN, bold=True))
    print(paint("  La API pública no es en tiempo real.", Color.CYAN))
    print(paint("  Puede tardar minutos (a veces horas) en actualizarse.", Color.CYAN))
    print(paint("  Por eso existe el modo MANUAL.", Color.CYAN))
    print()

    print(paint("Modos", Color.BRIGHT_CYAN, bold=True))
    print(paint("  AUTOMÁTICO  → solo intenta si la API no encuentra el perfil.", Color.CYAN))
    print(paint("  MANUAL      → intenta aunque la API diga ocupado.", Color.CYAN))
    print()

    print(paint("Ctrl+F en el navegador", Color.BRIGHT_CYAN, bold=True))
    print(paint("  Si no aparece el botón de cambio, busca en la página:", Color.CYAN))
    print(paint("  «Cambiar nombre de perfil» o «Change Profile Name».", Color.CYAN))
    print(paint("  Es la búsqueda del navegador, no del script.", Color.CYAN))
    print()

    print(paint("Controles", Color.BRIGHT_CYAN, bold=True))
    print(paint("  CTRL+C  → detiene el monitor", Color.CYAN))
    print(paint("  AYUDA   → abre esta guía", Color.CYAN))
    print(paint("  SALIR   → cierra antes de arrancar", Color.CYAN))
    print()
    print(line())
    pause()


# ============================================================================
# INTERFAZ
# ============================================================================

def ask_name() -> Optional[str]:
    section("Nombre de perfil", "El nombre que quieres vigilar.")
    print(paint("  3–16 caracteres: letras, números o _", Color.GRAY))
    print(paint("  SALIR  cierra  ·  AYUDA  abre la guía", Color.GRAY))
    print()

    while True:
        value = input(paint("  Nombre  › ", Color.BRIGHT_CYAN, bold=True)).strip()

        if value.lower() in {"salir", "exit", "quit"}:
            return None

        if value.lower() in {"ayuda", "help", "h", "?"}:
            show_help()
            clear_screen()
            logo()
            section("Nombre de perfil", "El nombre que quieres vigilar.")
            print(paint("  3–16 caracteres: letras, números o _", Color.GRAY))
            print(paint("  SALIR  cierra  ·  AYUDA  abre la guía", Color.GRAY))
            print()
            continue

        if re.fullmatch(r"[A-Za-z0-9_]{3,16}", value):
            clear_screen()
            logo()
            print(paint("NOMBRE LISTO", Color.BRIGHT_CYAN, bold=True))
            print()
            print(f"  {paint(value, Color.BRIGHT_CYAN, bold=True)}")
            print()
            return value

        status("VALIDACIÓN", "Ese nombre no cumple las reglas.", Color.BRIGHT_CYAN)


def ask_mode() -> bool:
    section("Interfaz", "Cuánto detalle quieres ver.")

    print(f"  {paint('1', Color.BRIGHT_CYAN, bold=True)}  COMPLETO")
    print(paint("     Logs, HTTP y cada paso del monitor.", Color.GRAY))
    print()
    print(f"  {paint('2', Color.BRIGHT_CYAN, bold=True)}  MINIMAL")
    print(paint("     Solo lo importante y el resultado.", Color.GRAY))
    print()
    print(f"  {paint('H', Color.BRIGHT_CYAN, bold=True)}  AYUDA")
    print()

    while True:
        choice = input(paint("  Opción [1/2/H] › ", Color.BRIGHT_CYAN)).strip().lower()

        if choice in {"h", "ayuda", "help", "?"}:
            show_help()
            clear_screen()
            logo()
            section("Interfaz", "Cuánto detalle quieres ver.")
            print(f"  {paint('1', Color.BRIGHT_CYAN, bold=True)}  COMPLETO")
            print(paint("     Logs, HTTP y cada paso del monitor.", Color.GRAY))
            print()
            print(f"  {paint('2', Color.BRIGHT_CYAN, bold=True)}  MINIMAL")
            print(paint("     Solo lo importante y el resultado.", Color.GRAY))
            print()
            print(f"  {paint('H', Color.BRIGHT_CYAN, bold=True)}  AYUDA")
            print()
            continue

        if choice in {"1", "completo", "c", "full", ""}:
            selected, detailed = "COMPLETO", True
            break
        if choice in {"2", "minimo", "mínimo", "minimal", "m", "min"}:
            selected, detailed = "MINIMAL", False
            break

        status("OPCIÓN", "Elige 1, 2 o H.", Color.BRIGHT_CYAN)

    clear_screen()
    logo()
    print(paint("LISTO", Color.BRIGHT_CYAN, bold=True))
    print()
    print(f"  Interfaz: {paint(selected, Color.BRIGHT_CYAN, bold=True)}")
    print()
    print(line())
    return detailed


def ask_detection_mode() -> bool:
    """True = MANUAL (intentar aunque la API diga ocupado)."""
    section("Detección", "Cómo reaccionar a la API de Mojang.")

    print(paint("  La API a veces va retrasada. MANUAL sigue intentando", Color.CYAN))
    print(paint("  en la web aunque diga que el nombre está ocupado.", Color.CYAN))
    print()
    print(f"  {paint('1', Color.BRIGHT_CYAN, bold=True)}  AUTOMÁTICO")
    print(paint("     Solo si la API no encuentra el perfil (204/404).", Color.GRAY))
    print()
    print(f"  {paint('2', Color.BRIGHT_CYAN, bold=True)}  MANUAL")
    print(paint("     Intenta también cuando la API dice ocupado.", Color.GRAY))
    print()
    print(f"  {paint('H', Color.BRIGHT_CYAN, bold=True)}  AYUDA")
    print()

    while True:
        choice = input(paint("  Opción [1/2/H] › ", Color.BRIGHT_CYAN)).strip().lower()

        if choice in {"h", "ayuda", "help", "?"}:
            show_help()
            clear_screen()
            logo()
            section("Detección", "Cómo reaccionar a la API de Mojang.")
            print(paint("  La API a veces va retrasada. MANUAL sigue intentando", Color.CYAN))
            print(paint("  en la web aunque diga que el nombre está ocupado.", Color.CYAN))
            print()
            print(f"  {paint('1', Color.BRIGHT_CYAN, bold=True)}  AUTOMÁTICO")
            print(paint("     Solo si la API no encuentra el perfil (204/404).", Color.GRAY))
            print()
            print(f"  {paint('2', Color.BRIGHT_CYAN, bold=True)}  MANUAL")
            print(paint("     Intenta también cuando la API dice ocupado.", Color.GRAY))
            print()
            print(f"  {paint('H', Color.BRIGHT_CYAN, bold=True)}  AYUDA")
            print()
            continue

        if choice in {"1", "automatico", "automático", "auto", "a", ""}:
            selected, force = "AUTOMÁTICO", False
            break
        if choice in {"2", "manual", "m", "forzado", "force"}:
            selected, force = "MANUAL", True
            break

        status("OPCIÓN", "Elige 1, 2 o H.", Color.BRIGHT_CYAN)

    clear_screen()
    logo()
    print(paint("LISTO", Color.BRIGHT_CYAN, bold=True))
    print()
    print(f"  Detección: {paint(selected, Color.BRIGHT_CYAN, bold=True)}")
    print()
    if force:
        print(paint("  Se intentará el formulario aunque la API diga ocupado.", Color.CYAN))
    else:
        print(paint("  Solo se intentará si la API no encuentra el perfil.", Color.CYAN))
    print()
    print(line())
    return force


# ============================================================================
# LOGGING Y API
# ============================================================================

def configure_logging(detailed: bool) -> Path:
    CONFIG.log_directory.mkdir(parents=True, exist_ok=True)
    log_path = CONFIG.log_directory / (
        f"monitor_{datetime.now():%Y%m%d_%H%M%S}.log"
    )

    handlers: list[logging.Handler] = [
        logging.FileHandler(log_path, encoding="utf-8")
    ]
    if detailed:
        handlers.append(logging.StreamHandler(sys.stdout))

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
        handlers=handlers,
        force=True,
    )
    logging.info(
        "Monitor iniciado. Interfaz: %s",
        "COMPLETO" if detailed else "MINIMAL",
    )
    return log_path


def check_name_api(name: str, session: requests.Session) -> tuple[str, Optional[int], str]:
    url = CONFIG.api_url.format(name)

    try:
        response = session.get(url, timeout=CONFIG.request_timeout)
        code = response.status_code

        if code == 200:
            return "ocupado", code, "La API dice que el perfil existe."
        if code in (204, 404):
            return "no_encontrado", code, "La API no encuentra el perfil."
        if code == 429:
            retry_after = response.headers.get("Retry-After")
            suffix = f" Retry-After={retry_after}" if retry_after else ""
            return "rate_limit", code, f"Límite de consultas.{suffix}"

        return "desconocido", code, f"HTTP inesperado: {code}."

    except requests.Timeout:
        return "desconocido", None, "Tiempo de espera agotado."
    except requests.ConnectionError:
        return "desconocido", None, "Sin conexión con la API."
    except requests.RequestException as exc:
        logging.exception("Error consultando la API")
        return "desconocido", None, f"Error de petición: {exc}"


# ============================================================================
# AUTOMATIZACIÓN WEB
# ============================================================================

def find_visible_locator(page: Page, selectors: list[str],
                         *, enabled_only: bool = True) -> Optional[Locator]:
    for selector in selectors:
        try:
            elements = page.locator(selector)
            for index in range(min(elements.count(), 20)):
                item = elements.nth(index)
                if not item.is_visible():
                    continue
                if enabled_only and not item.is_enabled():
                    continue
                return item
        except Exception:
            continue
    return None


def open_name_dialog(page: Page) -> bool:
    selectors = [
        'button[data-aem-contentname="Change Profile Name"]',
        'button:has-text("Cambiar nombre de perfil")',
        'button:has-text("Change Profile Name")',
        'button:has-text("Cambiar nombre")',
        'a:has-text("Cambiar nombre de perfil")',
        'a:has-text("Change Profile Name")',
        'button:has-text("Cambiar tu nombre")',
    ]
    button = find_visible_locator(page, selectors)
    if button is None:
        return False

    try:
        button.click(timeout=5_000)
        safe_wait(page, 800)
        return True
    except BrowserClosedError:
        raise
    except Exception as exc:
        if is_browser_closed_error(exc):
            raise BrowserClosedError(
                "El navegador se cerró. El monitor no puede continuar."
            ) from exc
        logging.exception("No se pudo abrir el diálogo de cambio")
        return False


def find_name_field(page: Page) -> Optional[Locator]:
    selectors = [
        'input[placeholder*="nombre" i]',
        'input[placeholder*="name" i]',
        'input[name*="name" i]',
        'input[name*="nombre" i]',
        'input[type="text"]',
        'input:not([type="hidden"])',
    ]
    return find_visible_locator(page, selectors)


def find_submit_button(page: Page) -> Optional[Locator]:
    selectors = [
        'button[data-aem-contentname="Set Profile Name"]',
        'button:has-text("Cambiar nombre")',
        'button:has-text("Change Name")',
        'button:has-text("Set Profile Name")',
        'button:has-text("Guardar")',
        'button:has-text("Save")',
        'button[type="submit"]',
    ]
    return find_visible_locator(page, selectors, enabled_only=False)


def dialog_is_open(page: Page) -> bool:
    indicators = (
        "Cambiar tu nombre de perfil",
        "Change your profile name",
        "Nuevo nombre de perfil",
        "New profile name",
    )
    try:
        body = page.locator("body").inner_text(timeout=3_000).lower()
        return any(text.lower() in body for text in indicators)
    except Exception:
        return False


def name_already_exists(page: Page) -> bool:
    patterns = (
        "este nombre de perfil ya existe",
        "this profile name already exists",
        "nombre de perfil ya existe",
        "profile name already exists",
        "already taken",
        "not available",
    )
    try:
        body = page.locator("body").inner_text(timeout=4_000).lower()
        return any(pattern in body for pattern in patterns)
    except Exception:
        return False


def minecraft_confirmed_success(page: Page) -> bool:
    messages = (
        "nombre cambiado",
        "name changed",
        "successfully changed",
        "profile name updated",
        "nombre actualizado",
        "nombre de perfil actualizado",
        "your profile name has been updated",
        "el nombre de tu perfil se ha actualizado",
        "se ha cambiado el nombre",
    )
    try:
        body = page.locator("body").inner_text(timeout=5_000).lower()
        return any(message in body for message in messages)
    except Exception:
        return False


def fill_name_field(field: Locator, name: str) -> bool:
    try:
        field.click(timeout=3_000)
        field.fill("")
        field.fill(name, timeout=5_000)
        return field.input_value(timeout=2_000).strip() == name
    except Exception as exc:
        if is_browser_closed_error(exc):
            raise BrowserClosedError(
                "El navegador se cerró. El monitor no puede continuar."
            ) from exc
        logging.exception("No se pudo introducir el nombre")
        return False


def submit_name_change(page: Page, name: str, detailed: bool) -> tuple[bool, str]:
    """Intenta el cambio. Si el navegador se cierra, lanza BrowserClosedError."""
    try:
        if not dialog_is_open(page):
            if not open_name_dialog(page):
                return False, (
                    "No se abrió el formulario. "
                    "Usa Ctrl+F en el navegador y busca «Cambiar nombre de perfil»."
                )

        try:
            page.wait_for_function(
                """() => Array.from(document.querySelectorAll('input'))
                    .some(el => el.offsetParent !== null && !el.disabled)""",
                timeout=CONFIG.field_timeout_ms,
            )
        except PlaywrightTimeoutError:
            return False, "No apareció el campo de nombre."

        field = find_name_field(page)
        if field is None:
            return False, "No hay un campo de nombre visible."

        for attempt in range(1, CONFIG.max_modal_attempts + 1):
            if detailed:
                status(
                    "FORMULARIO",
                    f"Intento {attempt}/{CONFIG.max_modal_attempts}.",
                    Color.BRIGHT_CYAN,
                )

            if not fill_name_field(field, name):
                safe_wait(page, 500)
                continue

            safe_wait(page, 900)

            if name_already_exists(page):
                logging.info("Minecraft indica que el nombre ya existe.")
                try:
                    field.fill("")
                except Exception as exc:
                    if is_browser_closed_error(exc):
                        raise BrowserClosedError(
                            "El navegador se cerró. El monitor no puede continuar."
                        ) from exc
                safe_wait(page, 700)
                continue

            button = find_submit_button(page)
            if button is None:
                logging.warning("No se encontró el botón de confirmación.")
                safe_wait(page, 500)
                continue

            deadline = time.monotonic() + 8
            while time.monotonic() < deadline:
                try:
                    disabled = (
                        button.get_attribute("aria-disabled") == "true"
                        or button.get_attribute("disabled") is not None
                    )
                    if button.is_enabled() and not disabled:
                        break
                except Exception as exc:
                    if is_browser_closed_error(exc):
                        raise BrowserClosedError(
                            "El navegador se cerró. El monitor no puede continuar."
                        ) from exc

                if name_already_exists(page):
                    break
                safe_wait(page, 250)
            else:
                logging.warning("El botón no se habilitó.")
                continue

            if name_already_exists(page):
                continue

            try:
                button.click(timeout=5_000)
                safe_wait(page, 2_500)
            except Exception as exc:
                if is_browser_closed_error(exc):
                    raise BrowserClosedError(
                        "El navegador se cerró. El monitor no puede continuar."
                    ) from exc
                logging.exception("Error al enviar el formulario")
                continue

            if minecraft_confirmed_success(page):
                return True, "Minecraft ha confirmado el cambio."

            if dialog_is_open(page) and name_already_exists(page):
                safe_wait(page, 700)
                continue

            if not dialog_is_open(page):
                safe_wait(page, 1_500)
                if minecraft_confirmed_success(page):
                    return True, "Minecraft ha confirmado el cambio."
                return False, "El formulario se cerró sin confirmación clara."

            return False, "Minecraft no ha confirmado el cambio."

        return False, "Se agotaron los intentos del formulario."

    except BrowserClosedError:
        raise
    except Exception as exc:
        if is_browser_closed_error(exc):
            raise BrowserClosedError(
                "El navegador se cerró. El monitor no puede continuar."
            ) from exc
        raise


# ============================================================================
# NOTIFICACIONES
# ============================================================================

def notify_success(name: str) -> None:
    message = f"¡Cambio de nombre confirmado por Minecraft!\n\nNuevo nombre: {name}"

    if os.name == "nt":
        try:
            import winsound
            winsound.MessageBeep(winsound.MB_ICONASTERISK)
        except Exception:
            logging.warning("No se pudo reproducir el sonido.")

        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(
                0, message, "3ltrs", 0x40 | 0x1000
            )
            return
        except Exception:
            logging.warning("No se pudo mostrar la notificación de Windows.")

    print()
    print(line("═", color=Color.BRIGHT_GREEN))
    print(paint("  CAMBIO CONFIRMADO", Color.BRIGHT_GREEN, bold=True))
    print()
    print(f"  Nuevo nombre: {paint(name, Color.BRIGHT_CYAN, bold=True)}")
    print()
    print(line("═", color=Color.BRIGHT_GREEN))


# ============================================================================
# PROGRAMA PRINCIPAL
# ============================================================================

def run_monitor(name: str, detailed: bool, force_attempt: bool) -> None:
    log_path = configure_logging(detailed)
    logging.info(
        "Detección: %s",
        "MANUAL" if force_attempt else "AUTOMÁTICO",
    )

    section("Monitor activo", "Sigue abierto mientras esta ventana lo esté.")

    print(f"  Nombre     : {paint(name, Color.BRIGHT_CYAN, bold=True)}")
    print(f"  Intervalo  : {CONFIG.poll_interval:.0f} s")
    print(
        f"  Detección  : "
        f"{paint('MANUAL' if force_attempt else 'AUTOMÁTICO', Color.BRIGHT_CYAN, bold=True)}"
    )
    print(f"  Log        : {paint(str(log_path), Color.GRAY)}")
    print()
    print(paint("  Inicia sesión en el navegador cuando se abra.", Color.CYAN))
    print(paint("  Si no ves el botón: Ctrl+F → «Cambiar nombre de perfil».", Color.GRAY))
    print(paint("  CTRL+C en esta consola para detener.", Color.GRAY))
    print()
    print(line())

    CONFIG.browser_profile.mkdir(parents=True, exist_ok=True)
    interval = CONFIG.poll_interval
    query_number = 0
    failed_submissions = 0
    last_force_attempt = 0.0

    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (compatible; 3ltrs/2.1)",
        "Accept": "application/json",
    })

    with sync_playwright() as playwright:
        try:
            context = playwright.chromium.launch_persistent_context(
                user_data_dir=str(CONFIG.browser_profile),
                headless=False,
                viewport={"width": 1280, "height": 900},
                args=[
                    "--disable-background-timer-throttling",
                    "--disable-renderer-backgrounding",
                    "--disable-backgrounding-occluded-windows",
                ],
            )
        except Exception as exc:
            session.close()
            logging.exception("No se pudo iniciar Chromium")
            raise RuntimeError(
                "No se pudo iniciar Chromium. Ejecuta "
                "'py -m playwright install chromium'. Si el perfil está "
                "abierto en otro proceso, ciérralo y reintenta. "
                f"Detalle: {exc}"
            ) from exc

        try:
            page = context.pages[0] if context.pages else context.new_page()
            logging.info("Abriendo %s", CONFIG.profile_url)
            try:
                page.goto(
                    CONFIG.profile_url,
                    wait_until="domcontentloaded",
                    timeout=90_000,
                )
            except Exception as exc:
                raise RuntimeError(
                    "No se pudo abrir minecraft.net. Revisa la conexión. "
                    f"Detalle: {exc}"
                ) from exc

            section("Inicio de sesión", "Entra en tu cuenta en el navegador.")
            print(paint("  Cuando veas tu perfil, pulsa ENTER aquí.", Color.CYAN))
            print()
            input(paint("  Perfil listo  › ", Color.BRIGHT_CYAN))
            logging.info("Usuario listo.")

            while True:
                query_number += 1
                state, http_code, message = check_name_api(name, session)

                if detailed:
                    code_text = str(http_code) if http_code is not None else "—"
                    status(
                        f"CONSULTA {query_number:04d}",
                        f"HTTP {code_text} · {message}",
                        Color.BRIGHT_CYAN,
                    )
                    logging.info(
                        "Consulta #%d | %s | %s",
                        query_number, code_text, message,
                    )
                elif state == "ocupado":
                    status("OCUPADO", f"{name} sigue en la API.", Color.GRAY)
                elif state == "no_encontrado":
                    status(
                        "POSIBLEMENTE LIBRE",
                        "La API no lo encuentra. Se comprueba en la web.",
                        Color.BRIGHT_CYAN,
                    )
                elif state == "rate_limit":
                    status("ESPERA", "La API ha limitado las consultas.", Color.CYAN)
                else:
                    status("API", message, Color.GRAY)

                if state == "rate_limit":
                    interval = min(
                        max(interval * 1.8, CONFIG.backoff_min),
                        CONFIG.backoff_max,
                    )
                    logging.warning("Rate limit; pausa %.1fs.", interval)
                    time.sleep(interval)
                    continue

                if state in {"ocupado", "no_encontrado"}:
                    interval = max(CONFIG.poll_interval, interval * 0.85)

                should_try = False
                reason = ""

                if state == "no_encontrado":
                    should_try = True
                    reason = "API sin perfil."
                elif force_attempt and state == "ocupado":
                    now = time.monotonic()
                    if now - last_force_attempt >= CONFIG.force_attempt_cooldown:
                        should_try = True
                        reason = "Modo MANUAL (API dice ocupado, posible desfase)."
                        last_force_attempt = now
                    elif detailed:
                        remaining = (
                            CONFIG.force_attempt_cooldown
                            - (now - last_force_attempt)
                        )
                        status(
                            "COOLDOWN",
                            f"Siguiente intento forzado en ~{remaining:.0f}s.",
                            Color.GRAY,
                        )

                if should_try:
                    if failed_submissions >= CONFIG.max_failed_submissions:
                        status(
                            "PAUSA",
                            "Varios intentos sin confirmar. Esperando un poco.",
                            Color.BRIGHT_CYAN,
                        )
                        time.sleep(max(interval * 3, 30))
                        failed_submissions = 0
                        continue

                    logging.info("Intento en Minecraft. Motivo: %s", reason)
                    if detailed:
                        status("INTENTO", reason, Color.BRIGHT_CYAN)

                    try:
                        success, detail = submit_name_change(page, name, detailed)
                    except BrowserClosedError as exc:
                        logging.warning("Navegador cerrado durante el intento.")
                        raise BrowserClosedError(str(exc)) from exc

                    logging.info("Resultado: %s | %s", success, detail)

                    if success:
                        notify_success(name)
                        logging.info("Cambio confirmado. Fin.")
                        pause("Pulsa ENTER para cerrar...")
                        return

                    failed_submissions += 1
                    status("SIN CONFIRMACIÓN", detail, Color.BRIGHT_CYAN)
                    time.sleep(max(interval, 10.0))
                elif state == "ocupado":
                    failed_submissions = 0

                time.sleep(interval)

        except BrowserClosedError:
            raise
        finally:
            session.close()
            try:
                context.close()
            except Exception:
                logging.info("El navegador ya estaba cerrado o no se pudo cerrar.")
            logging.info("Sesión finalizada.")


def main() -> None:
    clear_screen()
    logo()

    if sys.version_info < (3, 9):
        status(
            "PYTHON",
            f"Hace falta Python 3.9+. Tienes {sys.version.split()[0]}.",
            Color.BRIGHT_CYAN,
        )
        pause("Actualiza Python e inténtalo de nuevo.")
        return

    if DEPENDENCY_ERROR or requests is None or sync_playwright is None:
        status(
            "DEPENDENCIAS",
            DEPENDENCY_ERROR or "Faltan dependencias.",
            Color.BRIGHT_CYAN,
        )
        print()
        print(paint("  En CMD o PowerShell:", Color.GRAY))
        print()
        print(paint("  py -m pip install --upgrade pip", Color.BRIGHT_CYAN))
        print(paint("  py -m pip install requests playwright", Color.BRIGHT_CYAN))
        print(paint("  py -m playwright install chromium", Color.BRIGHT_CYAN))
        print()
        pause("Cuando termine, vuelve a ejecutar el programa.")
        return

    print(paint("  Escribe AYUDA en los menús si necesitas la guía.", Color.GRAY))
    print()

    name = ask_name()
    if name is None:
        clear_screen()
        logo()
        status("SALIDA", "Cerrado por el usuario.", Color.GRAY)
        return

    detailed = ask_mode()
    force_attempt = ask_detection_mode()

    try:
        run_monitor(name, detailed, force_attempt)
    except KeyboardInterrupt:
        print()
        status("DETENIDO", "Monitor parado (CTRL+C).", Color.CYAN)
        logging.info("Interrupción manual.")
    except BrowserClosedError as exc:
        print()
        print(line(color=Color.BRIGHT_CYAN))
        status("ERROR", "Navegador cerrado.", Color.BRIGHT_CYAN)
        print()
        print(paint("  Cerraste la ventana del navegador (o se perdió la sesión).", Color.CYAN))
        print(paint("  Sin el navegador el monitor no puede seguir.", Color.CYAN))
        print()
        print(paint(f"  Detalle: {exc}", Color.GRAY))
        print()
        print(paint("  Vuelve a ejecutar el programa si quieres continuar.", Color.GRAY))
        print(line(color=Color.BRIGHT_CYAN))
        logging.warning("BrowserClosedError: %s", exc)
        pause()
    except Exception as exc:
        if is_browser_closed_error(exc):
            print()
            print(line(color=Color.BRIGHT_CYAN))
            status("ERROR", "Navegador cerrado.", Color.BRIGHT_CYAN)
            print()
            print(paint("  Cerraste la ventana del navegador (o se perdió la sesión).", Color.CYAN))
            print(paint("  Sin el navegador el monitor no puede seguir.", Color.CYAN))
            print()
            print(paint("  Vuelve a ejecutar el programa si quieres continuar.", Color.GRAY))
            print(line(color=Color.BRIGHT_CYAN))
            logging.warning("Navegador cerrado: %s", exc)
            pause()
            return

        print()
        status("ERROR", "Ha fallado algo inesperado.", Color.BRIGHT_CYAN)
        traceback.print_exc()
        logging.exception("Error fatal")
        print()
        print(paint("  Dependencias:", Color.GRAY))
        print(paint("  pip install requests playwright", Color.BRIGHT_CYAN))
        print(paint("  playwright install chromium", Color.BRIGHT_CYAN))
        pause()


if __name__ == "__main__":
    main()
