import sys
import subprocess
def install_package(package):
    for module in package:
        try:
            __import__(module)
        except ImportError:
            print(f"{module} n'est pas installé. Installation en cours...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", module])