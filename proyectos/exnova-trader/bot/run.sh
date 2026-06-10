#!/usr/bin/env nix-shell
#! nix-shell -i python3 -p python3Packages.pandas python3Packages.requests python3Packages.websocket-client python3Packages.rich
"""
Entry point — nix-shell shebang loads all system deps, then imports ta from pip.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, "/tmp/ta_install2")  # ta + python-dotenv (pip-installed)

os.environ.setdefault("EXNOVA_EMAIL", "dmenamosquera15@gmail.com")
os.environ.setdefault("EXNOVA_PASSWORD", "6715320Dvd.")
os.environ.setdefault("ACCOUNT_TYPE", "PRACTICE")
os.environ["USE_LLM"] = "False"

from main import main
main()
