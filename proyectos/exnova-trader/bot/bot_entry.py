import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, "/tmp/ta_install2")
log = open("/tmp/bot_output.log", "a", buffering=1)
sys.stdout = log
sys.stderr = log
os.environ.setdefault("EXNOVA_EMAIL", "dmenamosquera15@gmail.com")
os.environ.setdefault("EXNOVA_PASSWORD", "6715320Dvd.")
os.environ.setdefault("ACCOUNT_TYPE", "PRACTICE")
os.environ["USE_LLM"] = "False"
from main import main
main()
