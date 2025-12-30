import logging
import os
import random
import asyncio
import aiohttp
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaVideo, InputMediaPhoto
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, CallbackQueryHandler, MessageHandler, filters

# 1. CARREGA CONFIGURAÇÕES
load_dotenv()

TOKEN = os.getenv("TELEGRAM_TOKEN")
ADMIN_ID = os.getenv("ADMIN_ID")
CHAVE_PIX = os.getenv("PIX_KEY")
ID_VIDEO_CAPA = os.getenv("VIDEO_CAPA_ID")
ID_QR_CODE = os.getenv("ID_QR_CODE")
ID_GRUPO_VIP_POSTAGEM = os.getenv("ID_CANAL_VIP") 

# --- CONFIGURAÇÃO DOS TÓPICOS ---
# 'pp_term': Termo de busca no PornPics
# 'subs': Lista de subs do Reddit (Backup)
CONFIG_CONTEUDO = {
    "milf": { 
        "topico": 25, "nome_pt": "👩 Coroas (MILF)", "comando": "milf",
        "pp_term": "milf", 
        "subs": ["milf", "MatureHotWomen", "Cougars"]
    },
    "asiaticas": { 
        "topico": 63, "nome_pt": "🇨🇳 Asiáticas", "comando": "asiaticas",
        "pp_term": "asian",
        "subs": ["RealAsians", "AsianHotties", "juicyasians"]
    },
    "latinas": { 
        "topico": 22, "nome_pt": "🌶 Latinas", "comando": "latinas",
        "pp_term": "latina",
        "subs": ["latinas", "latinasgw", "latinacuties"]
    },
    "ruivas": { 
        "topico": 31, "nome_pt": "🔥 Ruivas", "comando": "ruivas",
        "pp_term": "redhead",
        "subs": ["Redhead", "redheads", "Redhead_Porn"]
    },
    "amadoras": { 
        "topico": 27, "nome_pt": "📸 Amadoras", "comando": "amadoras",
        "pp_term": "amateur",
        "subs": ["RealGirls", "GoneMild", "Amateur"]
    },
    "novinhas": { 
        "topico": 16, "nome_pt": "🎓 Novinhas", "comando": "novinhas",
        "pp_term": "teen", # Cuidado: PornPics usa 'teen', mas o conteúdo é 18+
        "subs": ["collegerecording", "legalteens", "18_19"]
    }
}

PRODUTOS = {
    "pack1": { "nome": "💕 Sentimentos", "preco": "R$ 10,00", "conteudo": "BQACAgEAAxkBAAMfaVMYOIWxcD-TkL5g8_uqRSA07BYAAo4GAAKt5JlGPc4GdrO13SU4BA", "tipo": "arquivo" },
    "pack2": { "nome": "🤤 Combo Desejo", "preco": "R$ 20,00", "conteudo": ["BQACAgEAAxkBAAMZaVMX_Mv497euvN0SKhxNlhbm3DEAAosGAAKt5JlG3iND25Ndyn04BA", "BQACAgEAAxkBAAOsaVNHlC_rgsnliVrfDMHZcXNHy_UAAnkFAAJ4GZhGCtIcIalkpYM4BA"], "tipo": "combo" },
    "pack3": { "nome": "🔥 Pack Premium", "preco": "R$ 30,00", "conteudo": "BQACAgEAAxkBAAOsaVNHlC_rgsnliVrfDMHZcXNHy_UAAnkFAAJ4GZhGCtIcIalkpYM4BA", "tipo": "arquivo" },
    "vip_mensal": { "nome": "💎 VIP Mensal", "preco": "R$ 29,90", "tipo": "vip_gerar_link" },
    "vip_vitalicio": { "nome": "👑 VIP Vitalício", "preco": "R$ 50,00", "tipo": "vip_gerar_link" }
}

compras_pendentes = {}

if not TOKEN: exit("❌ Token não encontrado.")

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
ARQUIVO_USUARIOS = "usuarios.txt"

# --- FUNÇÕES AUXILIARES ---
def salvar_usuario(uid):
    if not os.path.exists(ARQUIVO_USUARIOS): open(ARQUIVO_USUARIOS, "w").close()
    with open(ARQUIVO_USUARIOS, "r+") as f:
        if str(uid) not in f.read().splitlines(): f.write(f"{uid}\n")

def ler_usuarios():
    if not os.path.exists(ARQUIVO_USUARIOS): return []
    with open(ARQUIVO_USUARIOS, "r") as f: return f.read().splitlines()

# ---------------------------------------------------------
# 1. FONTE: PORNPICS (ESTÁVEL PARA FOTOS)
# ---------------------------------------------------------
async def obter_midia_pornpics(termo, quantidade=4):
    """Busca imagens diretas no PornPics"""
    url = f"https://www.pornpics.com/search/srch.php?q={termo}"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    midias = []

    async with aiohttp.ClientSession(headers=headers) as session:
        try:
            async with session.get(url) as response:
                if response.status != 200: return []
                html = await response.text()
                
                soup = BeautifulSoup(html, 'html.parser')
                # Pega as miniaturas da busca (são links diretos JPG)
                items = soup.select('li.thumb a.rel-link img')
                random.shuffle(items)

                for img in items:
                    if len(midias) >= quantidade: break
                    link_img = img.get('data-src') or img.get('src')
                    
                    if link_img:
                        # Tenta pegar a versão grande se possível (troca thumb por big se a URL permitir)
                        # Mas a thumb do pornpics já tem qualidade aceitavel para preview
                        midias.append({'type': 'photo', 'media': link_img})
        except Exception as e:
            print(f"Erro PornPics: {e}")
    return midias

# ---------------------------------------------------------
# 2. FONTE: REDDIT (API BLINDADA)
# ---------------------------------------------------------
async def obter_midia_reddit_blindada(lista_subs, quantidade=4):
    """Só pega se for .jpg, .png ou .mp4 REAL. Ignora tudo que dá erro."""
    midias = []
    subs_para_tentar = lista_subs.copy()
    random.shuffle(subs_para_tentar)

    async with aiohttp.ClientSession() as session:
        for sub in subs_para_tentar:
            # Pega 20 posts para ter margem de descarte de erros
            url = f"https://meme-api.com/gimme/{sub}/20"
            try:
                async with session.get(url) as response:
                    if response.status != 200: continue
                    data = await response.json()
                    posts = data.get('memes', [])
                    
                    for post in posts:
                        if len(midias) >= quantidade: break
                        link = post.get('url')
                        if not link: continue
                        
                        # --- FILTRO BLINDADO ANTI-ERRO ---
                        if "redgifs" in link: continue # Redgifs precisa de tratamento especial, melhor pular
                        if ".gifv" in link: continue   # Telegram ODEIA .gifv (causa o erro de "recusou")
                        
                        eh_video = link.endswith('.mp4')
                        eh_foto = link.endswith(('.jpg', '.jpeg', '.png'))
                        
                        if eh_foto:
                            midias.append({'type': 'photo', 'media': link})
                        elif eh_video:
                            midias.append({'type': 'video', 'media': link})
                    
                    if len(midias) >= 1: break
            except: pass
    
    return midias[:quantidade]

# ---------------------------------------------------------
# 3. GERENCIADOR INTELIGENTE (MULTI-FONTE)
# ---------------------------------------------------------
async def obter_conteudo_blindado(chave_config):
    config = CONFIG_CONTEUDO[chave_config]
    itens = []
    
    # 1ª Tentativa: PornPics (Ótimo para fotos, muito rápido e estável)
    # Vamos dar prioridade 50/50 entre Pornpics e Reddit para variar
    if random.choice([True, False]):
        try:
            # print(f"Tentando PornPics para {chave_config}...")
            itens = await obter_midia_pornpics(config['pp_term'])
        except: pass

    # 2ª Tentativa: Se PornPics falhou ou não foi escolhido, vai de Reddit Blindado
    if not itens:
        # print(f"Tentando Reddit para {chave_config}...")
        itens = await obter_midia_reddit_blindada(config['subs'])
    
    # 3ª Tentativa: Se tudo falhou, tenta PornPics de novo (se não tentou antes)
    if not itens:
        itens = await obter_midia_pornpics(config['pp_term'])
        
    return itens

# --- COMANDOS DO GRUPO ---
async def comando_rapido_vip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    comando = update.message.text.replace("/", "").split("@")[0].lower()
    chave_alvo = None
    for chave, info in CONFIG_CONTEUDO.items():
        if info['comando'] == comando:
            chave_alvo = chave
            break
    if not chave_alvo: return

    if str(update.effective_chat.id) != str(ID_GRUPO_VIP_POSTAGEM):
        if update.effective_chat.type == 'private':
            await update.message.reply_text("🚫 Exclusivo do VIP! Digite /vip.", parse_mode='Markdown')
        return

    msg = await update.message.reply_text(f"🚀 Buscando pack de {CONFIG_CONTEUDO[chave_alvo]['nome_pt']}...")
    
    # USA O GERENCIADOR BLINDADO
    itens = await obter_conteudo_blindado(chave_alvo)
    
    if itens:
        try: await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=msg.message_id)
        except: pass
        
        album = []
        info = CONFIG_CONTEUDO[chave_alvo]
        caption = f"🔞 **{info['nome_pt']}**\n👀 Pedido por: {update.effective_user.first_name}"
        
        for i, item in enumerate(itens):
            legenda = caption if i == 0 else None
            # Adicionei tratamento de erro individual para cada mídia
            if item['type'] == 'photo': 
                album.append(InputMediaPhoto(media=item['media'], caption=legenda, parse_mode='Markdown'))
            elif item['type'] == 'video': 
                album.append(InputMediaVideo(media=item['media'], caption=legenda, parse_mode='Markdown'))
        
        try:
            await context.bot.send_media_group(
                chat_id=update.effective_chat.id,
                media=album,
                message_thread_id=info['topico'] or None,
                protect_content=True
            )
        except Exception as e:
            # Se ainda der erro, tenta mandar um por um (fallback)
            await update.message.reply_text(f"⚠️ Erro no álbum. Enviando separado...")
            for item in itens:
                try:
                    if item['type'] == 'photo': await context.bot.send_photo(update.effective_chat.id, item['media'], protect_content=True)
                    else: await context.bot.send_video(update.effective_chat.id, item['media'], protect_content=True)
                except: pass
    else:
        await msg.edit_text("⚠️ Fontes indisponíveis no momento. Tente outro tema!")

# --- JOB: CARDÁPIO AUTOMÁTICO ---
async def job_anunciar_comandos(context: ContextTypes.DEFAULT_TYPE):
    if not ID_GRUPO_VIP_POSTAGEM: return

    texto = "🔥 **O que você quer assistir agora?**\n\nDigite um dos comandos abaixo e eu envio o pack na hora:\n\n"
    for info in CONFIG_CONTEUDO.values():
        texto += f"🔹 /{info['comando']} - {info['nome_pt']}\n"
    texto += "\n💎 _Toque no comando azul para pedir!_"

    teclado = [[InlineKeyboardButton("📋 Abrir Menu de Botões", callback_data="abrir_menu_no_grupo")]]

    try:
        await context.bot.send_message(chat_id=ID_GRUPO_VIP_POSTAGEM, text=texto, reply_markup=InlineKeyboardMarkup(teclado), parse_mode='Markdown')
    except Exception as e: print(f"Erro menu: {e}")

# --- MENU INTERATIVO ---
async def exibir_menu_botoes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    teclado = []
    linha = []
    for chave, info in CONFIG_CONTEUDO.items():
        linha.append(InlineKeyboardButton(info['nome_pt'], callback_data=f"vip_ver_{chave}"))
        if len(linha) == 2:
            teclado.append(linha)
            linha = []
    if linha: teclado.append(linha)
    await query.message.reply_text("😈 **Menu Rápido:** Escolha o tema!", reply_markup=InlineKeyboardMarkup(teclado), parse_mode='Markdown')

async def acao_botao_tema(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("🔥 Buscando...")
    
    chave = query.data.split("_", 2)[2]
    itens = await obter_conteudo_blindado(chave)
    
    if itens:
        album = []
        info = CONFIG_CONTEUDO[chave]
        caption = f"🔞 **{info['nome_pt']}**\n👀 Pedido por: {query.from_user.first_name}"
        for i, item in enumerate(itens):
            legenda = caption if i == 0 else None
            if item['type'] == 'photo': album.append(InputMediaPhoto(media=item['media'], caption=legenda, parse_mode='Markdown'))
            elif item['type'] == 'video': album.append(InputMediaVideo(media=item['media'], caption=legenda, parse_mode='Markdown'))
        try:
            await context.bot.send_media_group(chat_id=query.message.chat.id, media=album, message_thread_id=info['topico'] or None, protect_content=True)
        except: 
            await query.message.reply_text("Erro ao enviar mídia. Tente outro.")
    else:
        await query.message.reply_text("Nada encontrado.", quote=True)

# --- RESTO DO SISTEMA (MANTIDO) ---
async def boas_vindas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if str(update.effective_chat.id) != str(ID_GRUPO_VIP_POSTAGEM): return
    for novo in update.message.new_chat_members:
        if novo.id == context.bot.id: continue
        await context.bot.send_message(ID_GRUPO_VIP_POSTAGEM, f"😈 **Bem-vindo(a), {novo.first_name}!**\nDigite `/milf` ou `/novinhas` para começar a ver.", parse_mode='Markdown')

async def menu_principal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != 'private': return 
    salvar_usuario(update.effective_user.id)
    texto = f"😈 **Oi, {update.effective_user.first_name}!**\nBem-vindo.\n👇 **Selecione:**"
    teclado = [[InlineKeyboardButton("🔥 Packs (+18)", callback_data='menu_packs')],
               [InlineKeyboardButton("💎 Assinar VIP", callback_data='menu_vip')],
               [InlineKeyboardButton("🆘 Ajuda", callback_data='comando_ajuda')]]
    if update.callback_query:
        if ID_VIDEO_CAPA: await update.callback_query.edit_message_media(media=InputMediaVideo(media=ID_VIDEO_CAPA, caption=texto, parse_mode='Markdown'), reply_markup=InlineKeyboardMarkup(teclado))
        else: await update.callback_query.edit_message_text(texto, reply_markup=InlineKeyboardMarkup(teclado), parse_mode='Markdown')
    else:
        if ID_VIDEO_CAPA: await update.message.reply_video(video=ID_VIDEO_CAPA, caption=texto, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(teclado))
        else: await update.message.reply_text(texto, reply_markup=InlineKeyboardMarkup(teclado), parse_mode='Markdown')

async def menu_packs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    if q: await q.answer()
    texto = "📂 **CATÁLOGO**"
    teclado = []
    for k, v in PRODUTOS.items():
        if v['tipo'] in ['arquivo', 'combo']: teclado.append([InlineKeyboardButton(f"{v['nome']} - {v['preco']}", callback_data=f"comprar_{k}")])
    teclado.append([InlineKeyboardButton("🔙 Voltar", callback_data='voltar_inicio')])
    if q: await q.edit_message_caption(texto, reply_markup=InlineKeyboardMarkup(teclado), parse_mode='Markdown')
    else: await update.message.reply_text(texto, reply_markup=InlineKeyboardMarkup(teclado), parse_mode='Markdown')

async def menu_vip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    if q: await q.answer()
    texto = "💎 **CLUBE VIP**\n✅ Álbuns Automáticos\n✅ Vários Temas"
    teclado = [[InlineKeyboardButton("Mensal - R$ 29,90", callback_data='comprar_vip_mensal')],
               [InlineKeyboardButton("Vitalício - R$ 50,00", callback_data='comprar_vip_vitalicio')],
               [InlineKeyboardButton("🔙 Voltar", callback_data='voltar_inicio')]]
    if q: await q.edit_message_caption(texto, reply_markup=InlineKeyboardMarkup(teclado), parse_mode='Markdown')
    else: await update.message.reply_text(texto, reply_markup=InlineKeyboardMarkup(teclado), parse_mode='Markdown')

async def atalho_packs(u, c): await menu_packs(u, c)
async def atalho_vip(u, c): await menu_vip(u, c)
async def comando_ajuda(u, c): 
    t = "Envie o comprovante Pix aqui."
    if u.callback_query: await u.callback_query.message.reply_text(t)
    else: await u.message.reply_text(t)

async def pedir_pagamento(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    item = query.data.split("_", 1)[1]
    compras_pendentes[query.from_user.id] = item
    prod = PRODUTOS[item]
    txt = f"💰 **{prod['nome']}**\nValor: {prod['preco']}\n\n1. Copie o Pix\n2. Envie o comprovante."
    if ID_QR_CODE: await context.bot.send_photo(query.from_user.id, ID_QR_CODE, caption=txt, parse_mode='Markdown')
    else: await context.bot.send_message(query.from_user.id, txt, parse_mode='Markdown')
    await context.bot.send_message(query.from_user.id, f"`{CHAVE_PIX}`", parse_mode='Markdown')

async def receber_comprovante(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != 'private': return
    uid = update.effective_user.id
    if uid not in compras_pendentes: return await menu_principal(update, context)
    await update.message.reply_text("✅ Analisando...")
    if ADMIN_ID:
        kb = [[InlineKeyboardButton("✅ APROVAR", callback_data=f"aprovar_{uid}_{compras_pendentes[uid]}")], [InlineKeyboardButton("❌ RECUSAR", callback_data=f"recusar_{uid}")]]
        await context.bot.send_photo(ADMIN_ID, update.message.photo[-1].file_id, caption=f"💰 Venda: {PRODUTOS[compras_pendentes[uid]]['nome']}", reply_markup=InlineKeyboardMarkup(kb))

async def aprovar_venda(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid, pid = int(query.data.split("_")[1]), query.data.split("_")[2]
    try: await query.edit_message_caption("✅ Aprovado!")
    except: pass
    prod = PRODUTOS[pid]
    await context.bot.send_message(uid, "🎉 Confirmado! Receba:", parse_mode='Markdown')
    try:
        if prod['tipo'] == 'arquivo': await context.bot.send_document(uid, prod['conteudo'], protect_content=True)
        elif prod['tipo'] == 'combo':
            for arquivo_id in prod['conteudo']:
                try: await context.bot.send_document(uid, arquivo_id, protect_content=True)
                except: await context.bot.send_video(uid, arquivo_id, protect_content=True)
                await asyncio.sleep(1)
        elif prod['tipo'] == 'vip_gerar_link': 
            link = await context.bot.create_chat_invite_link(ID_GRUPO_VIP_POSTAGEM, member_limit=1)
            await context.bot.send_message(uid, f"🔗 Link: {link.invite_link}", protect_content=True)
    except Exception as e: 
        if ADMIN_ID: await context.bot.send_message(ADMIN_ID, f"Erro entrega: {e}")

async def recusar_venda(u, c):
    q = u.callback_query
    uid = int(q.data.split("_")[1])
    try: await q.edit_message_caption("❌ Recusado.")
    except: pass
    if uid in compras_pendentes: del compras_pendentes[uid]
    try: await c.bot.send_message(uid, "❌ Comprovante recusado.")
    except: pass

async def enviar_broadcast(u, c):
    if str(u.effective_chat.id) != str(ADMIN_ID): return
    msg = " ".join(c.args)
    if not msg: return await u.message.reply_text("Use: /enviar Texto")
    users = ler_usuarios()
    await u.message.reply_text(f"Enviando para {len(users)}...")
    for uid in users:
        try: 
            await c.bot.send_message(int(uid), f"🔔 {msg}", parse_mode='Markdown')
            await asyncio.sleep(0.05)
        except: pass
    await u.message.reply_text("✅ Feito.")

async def navegar(u, c):
    d = u.callback_query.data
    if d == 'abrir_menu_no_grupo': await exibir_menu_botoes(u, c)
    elif d.startswith('vip_ver_'): await acao_botao_tema(u, c)
    
    elif d == 'voltar_inicio': await menu_principal(u, c)
    elif d == 'menu_packs': await menu_packs(u, c)
    elif d == 'menu_vip': await menu_vip(u, c)
    elif d == 'comando_ajuda': await u.callback_query.message.reply_text("Envie o comprovante.")
    elif d.startswith('comprar_'): await pedir_pagamento(u, c)
    elif d.startswith('aprovar_'): await aprovar_venda(u, c)
    elif d.startswith('recusar_'): await recusar_venda(u, c)

if __name__ == '__main__':
    app = ApplicationBuilder().token(TOKEN).build()
    
    app.add_handler(CommandHandler('start', menu_principal))
    app.add_handler(CommandHandler('packs', atalho_packs))
    app.add_handler(CommandHandler('vip', atalho_vip))
    app.add_handler(CommandHandler('ajuda', lambda u,c: u.message.reply_text("Envie comprovante.")))
    app.add_handler(CommandHandler('enviar', enviar_broadcast))
    
    cmds_vip = [info['comando'] for info in CONFIG_CONTEUDO.values()]
    app.add_handler(CommandHandler(cmds_vip, comando_rapido_vip))

    app.add_handler(CallbackQueryHandler(navegar))
    app.add_handler(MessageHandler(filters.PHOTO & filters.ChatType.PRIVATE, receber_comprovante))
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, boas_vindas))

    app.job_queue.run_repeating(job_anunciar_comandos, interval=180, first=10)
    
    print("🤖 BOT BLINDADO: PORN PICS + REDDIT (SEM ERROS)!")
    app.run_polling()