
class Colors:
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
    END = '\033[0m'

def print_success(message):
    print(f"{Colors.GREEN}{message}{Colors.END}")

def print_error(message):
    print(f"{Colors.RED}{message}{Colors.END}")

def print_warning(message):
    print(f"{Colors.YELLOW}{message}{Colors.END}")

def print_info(message):
    print(f"{Colors.BLUE}{message}{Colors.END}")

def print_bold(message):
    print(f"{Colors.BOLD}{message}{Colors.END}")

