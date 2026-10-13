from rich.console import Console
from rich.theme import Theme

custom_theme = Theme({
    "info":    "cyan",
    "success": "bold green",
    "warning": "bold yellow",
    "error":   "bold red",
    "step":    "bold blue",
    "dim":     "dim white",
})

console = Console(theme = custom_theme)

def log_info(message:str):
    console.print(f"[info]ℹ {message}[/info]")

def log_success(message:str):
    console.print(f"[success]✓ {message}[/success]")

def log_warning(message:str):
    console.print(f"[warning]⚠ {message}[/warning]")

def log_error(message:str):
    console.print(f"[error]✗ {message}[/error]")

def log_step(step:int, message:str):
    console.print(f"[step]→ Step {step}: {message}[/step]")

def log_dim(message:str):
    console.print(f"[dim] {message}[/dim]")