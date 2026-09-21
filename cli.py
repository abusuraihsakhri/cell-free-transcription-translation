"""Compatibility entry point for the packaged TXTL command-line interface."""

import sys

from txtl_simulator.cli import main


if __name__ == "__main__":
    sys.exit(main())
