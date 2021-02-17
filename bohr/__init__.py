import logging
import os

from rich.logging import RichHandler

FORMAT = "%(message)s"
logging.basicConfig(
    level="INFO", format=FORMAT, datefmt="[%X]", handlers=[RichHandler()]
)

logger = logging.getLogger("bohr")


root_package_name = "bohr"


def version():
    with open(os.path.join(root_package_name, "VERSION")) as version_file:
        return version_file.read().strip()
