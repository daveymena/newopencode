#!/usr/bin/env python3
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

os.environ.setdefault("EXNOVA_EMAIL", "dmenamosquera15@gmail.com")
os.environ.setdefault("EXNOVA_PASSWORD", "6715320Dvd.")
os.environ.setdefault("ACCOUNT_TYPE", "PRACTICE")
os.environ["USE_LLM"] = "False"

from main import main
main()
