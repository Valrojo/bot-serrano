import os
import asyncio
import discord
import yt_dlp
from discord.ext import commands
from discord import app_commands
from dotenv import load_dotenv

load_dotenv()

intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True

class MusicQueue:
    def __init__(self):
        self.queue = []
        self.is_playing = False

    def append(self, item): self.queue.append(item)
    def pop(self, index=0): return self.queue.pop(index)
    def clear(self): self.queue.clear(); self.is_playing = False
    def __len__(self): return len(self.queue)
    def __getitem__(self, index): return self.queue[index]
    def __delitem__(self, index): del self.queue[index]

queue_handler = MusicQueue()

class SerranoBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix='!serrano ', intents=intents)

    async def setup_hook(self):
        await self.tree.sync()

bot = SerranoBot()

async def connect_to_voice(ctx):
    voice_channel = ctx.user.voice.channel if isinstance(ctx, discord.Interaction) else ctx.author.voice.channel
    voice_client = ctx.guild.voice_client
    if voice_client and voice_client.is_connected():
        if voice_client.channel.id != voice_channel.id:
            await voice_client.move_to(voice_channel)
    else:
        voice_client = await voice_channel.connect(self_deaf=True)
    return voice_client

async def play_next():
    if len(queue_handler) == 0:
        queue_handler.is_playing = False
        return
    queue_handler.is_playing = True
    song = queue_handler.pop(0)
    await process_song(song['ctx'], song['search'])

async def process_song(ctx, search):
    ydl_opts = {
        'format': 'bestaudio[ext=webm][acodec=opus]/bestaudio/best',
        'quiet': True,
        'default_search': 'ytsearch1',
        'noplaylist': True,
        'source_address': '0.0.0.0'  # fuerza IPv4 para menos problemas
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(search, download=False)
            if 'entries' in info:
                info = info['entries'][0]
            url = info['url']
            title = info.get('title', 'desconocido')
    except Exception as e:
        await send_message(ctx, f"❌ Error al obtener info: {str(e)}")
        queue_handler.is_playing = False
        return

    ffmpeg_opts = {
        'before_options': (
            '-reconnect 1 '
            '-reconnect_streamed 1 '
            '-reconnect_delay_max 5 '
            '-thread_queue_size 1024'
        ),
        'options': (
            '-vn '
            '-bufsize 2M '
            '-nostdin'
        )
    }

    try:
        voice_client = await connect_to_voice(ctx)
        source = discord.FFmpegPCMAudio(url, **ffmpeg_opts)
        voice_client.play(
            source,
            after=lambda e: asyncio.run_coroutine_threadsafe(play_next(), bot.loop)
        )
        await send_message(ctx, f"▶️ Reproduciendo: {title}")
    except Exception as e:
        queue_handler.is_playing = False
        await send_message(ctx, f"❌ Error al reproducir: {str(e)}")

async def send_message(ctx, content):
    if isinstance(ctx, discord.Interaction):
        await ctx.followup.send(content)
    else:
        await ctx.send(content)

@bot.tree.command(name="play", description="Reproduce una canción o playlist de YouTube")
async def slash_play(interaction: discord.Interaction, search: str, mode: str = ""):
    if not interaction.user.voice:
        await interaction.response.send_message("¡Únete a un canal de voz primero!", ephemeral=True)
        return
    await interaction.response.send_message(f"🎶 Agregando: {search}")
    await add_to_queue(interaction, search, mode)

@bot.command()
async def play(ctx, *, search: str):
    if not ctx.author.voice:
        await ctx.send("¡Únete a un canal de voz primero!")
        return
    await ctx.send(f"🎶 Agregando: {search}")
    await add_to_queue(ctx, search)

async def add_to_queue(ctx, search, mode=""):
    ydl_opts = {
        'quiet': True,
        'extract_flat': 'in_playlist',
        'skip_download': True
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(search, download=False)
            if 'entries' in info and info.get('_type') == 'playlist':
                limit = len(info['entries']) if mode == "no_limits" else min(10, len(info['entries']))
                for entry in info['entries'][:limit]:
                    url = entry['url'] if entry['url'].startswith('http') else f"https://www.youtube.com/watch?v={entry['url']}"
                    queue_handler.append({'ctx': ctx, 'search': url})
                await send_message(ctx, f"✅ Playlist agregada con {limit} canciones.")
            else:
                queue_handler.append({'ctx': ctx, 'search': search})
    except Exception:
        queue_handler.append({'ctx': ctx, 'search': search})

    if not queue_handler.is_playing:
        await play_next()

@bot.command()
async def stop(ctx):
    vc = ctx.guild.voice_client
    if vc:
        queue_handler.clear()
        vc.stop()
        await vc.disconnect()
        await ctx.send("⏹️ Bot detenido y desconectado.")

@bot.command()
async def pause(ctx):
    vc = ctx.guild.voice_client
    if vc and vc.is_playing():
        vc.pause()
        await ctx.send("⏸️ Pausado.")

@bot.command()
async def resume(ctx):
    vc = ctx.guild.voice_client
    if vc and vc.is_paused():
        vc.resume()
        await ctx.send("▶️ Reanudado.")

@bot.command()
async def next(ctx):
    vc = ctx.guild.voice_client
    if vc and vc.is_playing():
        vc.stop()
        await ctx.send("⏭️ Siguiente canción.")

if __name__ == "__main__":
    bot.run(os.getenv("BOT_TOKEN"))
