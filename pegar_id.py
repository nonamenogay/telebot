import logging
import os
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters

# Carrega o token do seu arquivo .env para não precisar copiar e colar
load_dotenv()
TOKEN = os.getenv("TELEGRAM_TOKEN")

# Se não achar o arquivo .env, avisa
if not TOKEN:
    print("❌ ERRO: Token não encontrado. Verifique seu arquivo .env")
    exit()

async def descobrir_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    file_id = "Não encontrado"
    tipo = "Desconhecido"

    # Verifica DOCUMENTO (ZIP, PDF, Arquivos em geral)
    if msg.document:
        file_id = msg.document.file_id
        tipo = "📁 ARQUIVO / ZIP"
        
    # Verifica VÍDEO
    elif msg.video:
        file_id = msg.video.file_id
        tipo = "🎥 VÍDEO"
        
    # Verifica FOTO
    elif msg.photo:
        file_id = msg.photo[-1].file_id # Pega a maior resolução
        tipo = "📸 FOTO"
        
    # Verifica ÁUDIO
    elif msg.voice:
        file_id = msg.voice.file_id
        tipo = "🎤 ÁUDIO"

    # Responde com o ID
    await update.message.reply_text(
        f"🛠 **FERRAMENTA DE ID**\n\n"
        f"Tipo: {tipo}\n"
        f"ID para copiar:\n`{file_id}`",
        parse_mode="Markdown"
    )

if __name__ == '__main__':
    application = ApplicationBuilder().token(TOKEN).build()
    
    # O filtro 'ALL' pega qualquer coisa que você mandar
    application.add_handler(MessageHandler(filters.ALL, descobrir_id))
    
    print("🕵️‍♂️ DETETIVE DE IDs RODANDO...")
    print("Envie ou encaminhe os arquivos para o bot agora.")
    application.run_polling()
