"""
Ponto de entrada do bot Abomination RPG (versão Python).

Roda com: python -m bot.main
"""
import discord
from discord.ext import commands

from bot.config import DISCORD_TOKEN, GUILD_ID
from bot.db.database import init_db

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix=".", intents=intents)

# Lista de cogs (módulos de comandos) a carregar.
# Conforme formos criando skills, itens, combate etc., adicionamos aqui.
COGS_INICIAIS = [
    "bot.cogs.personagem",
    "bot.cogs.skill",
    "bot.cogs.combate",
]


@bot.event
async def on_ready():
    print(f"✅ Bot online como {bot.user}")

    # Sincroniza os slash commands.
    # Se GUILD_ID estiver definido, sincroniza só nesse servidor (instantâneo).
    # Caso contrário, sincroniza globalmente (pode levar até 1h para aparecer).
    if GUILD_ID:
        guild = discord.Object(id=int(GUILD_ID))
        bot.tree.copy_global_to(guild=guild)
        synced = await bot.tree.sync(guild=guild)
        print(f"✅ {len(synced)} comando(s) sincronizado(s) no servidor de testes.")
    else:
        synced = await bot.tree.sync()
        print(f"✅ {len(synced)} comando(s) sincronizado(s) globalmente.")


async def main():
    init_db()
    async with bot:
        for cog in COGS_INICIAIS:
            await bot.load_extension(cog)
        await bot.start(DISCORD_TOKEN)


if __name__ == "__main__":
    import asyncio

    if not DISCORD_TOKEN:
        print("❌ DISCORD_TOKEN não encontrado. Crie um arquivo .env com base no .env.example.")
    else:
        asyncio.run(main())
