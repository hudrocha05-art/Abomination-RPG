"""
Carrega as configurações do bot a partir do arquivo .env.
"""
import os
from dotenv import load_dotenv


# override=True garante que o arquivo .env sempre tenha prioridade sobre
# variáveis de ambiente antigas que possam existir no Windows.
load_dotenv(override=True)

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
CLIENT_ID = os.getenv("CLIENT_ID")
GUILD_ID = os.getenv("GUILD_ID")

# Caminho do arquivo do banco de dados SQLite (fica na raiz do projeto)
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "abomination.db")
