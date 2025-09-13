import os
from dotenv import load_dotenv
from dotenv import dotenv_values

# Recargamos las variables de entorno (del archivo .env)
load_dotenv()

# Guardamos las variables de entorno
VARIABLES_DE_ENTORNO = dotenv_values(".env")
GEMINI_API_KEY = VARIABLES_DE_ENTORNO["GEMINI_API_KEY"]
ELEVENLABS_API_KEY = VARIABLES_DE_ENTORNO["ELEVENLABS_API_KEY"]

