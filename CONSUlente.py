import sqlite3
from datetime import datetime
import calendar

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
    ConversationHandler
)

from apscheduler.schedulers.asyncio import AsyncIOScheduler

# TOKEN = "8601723788:AAGpGzXT4EqYlluivPVwSu2nQssQiMtD-vQ"
import os
TOKEN = os.getenv("TOKEN")
CHAT_ID = None
DB_NAME = "spese.db"

# Stati conversazione
IMPORTO, CATEGORIA, DESCRIZIONE = range(3)

CATEGORIE = ["Cibo", "Trasporti", "Casa", "Lory & Maty", "Svago", "Beauty", "Altro"]

# -------------------------
# DATABASE
# -------------------------
def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    c.execute("""
    CREATE TABLE IF NOT EXISTS spese (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        data TEXT,
        importo REAL,
        categoria TEXT,
        descrizione TEXT
    )
    """)

    conn.commit()
    conn.close()


def salva_spesa(data, importo, categoria, descrizione):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    c.execute(
        "INSERT INTO spese (data, importo, categoria, descrizione) VALUES (?, ?, ?, ?)",
        (data, importo, categoria, descrizione)
    )

    conn.commit()
    conn.close()


def get_spese(inizio, fine):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    c.execute("""
        SELECT importo, categoria FROM spese
        WHERE data BETWEEN ? AND ?
    """, (inizio, fine))

    data = c.fetchall()
    conn.close()
    return data


# -------------------------
# MENU
# -------------------------
def main_menu():
    keyboard = [
        [InlineKeyboardButton("➕ Aggiungi spesa", callback_data="add")],
        [InlineKeyboardButton("📊 Report mese", callback_data="report_mese")],
        [InlineKeyboardButton("📈 Report 15 giorni", callback_data="report_15")]
    ]
    return InlineKeyboardMarkup(keyboard)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global CHAT_ID
    CHAT_ID = update.effective_chat.id

    await update.message.reply_text(
        "👋 Benvenuto in CONSUlente",
        reply_markup=main_menu()
    )


# -------------------------
# FLOW INSERIMENTO SPESA
# -------------------------
async def start_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    await query.message.reply_text("💰 Inserisci l'importo:")
    return IMPORTO


async def get_importo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        context.user_data["importo"] = float(update.message.text)
    except:
        await update.message.reply_text("❌ Inserisci un numero valido")
        return IMPORTO

    keyboard = [[InlineKeyboardButton(cat, callback_data=cat)] for cat in CATEGORIE]

    await update.message.reply_text(
        "📂 Scegli categoria:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return CATEGORIA


async def get_categoria(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    context.user_data["categoria"] = query.data

    await query.message.reply_text("📝 Inserisci descrizione:")
    return DESCRIZIONE


async def get_descrizione(update: Update, context: ContextTypes.DEFAULT_TYPE):
    descrizione = update.message.text

    data = datetime.now().strftime("%Y-%m-%d")
    salva_spesa(
        data,
        context.user_data["importo"],
        context.user_data["categoria"],
        descrizione
    )

    await update.message.reply_text("✅ Spesa salvata!", reply_markup=main_menu())
    return ConversationHandler.END


# -------------------------
# REPORT
# -------------------------
def genera_report(inizio, fine):
    spese = get_spese(inizio, fine)

    totale = sum([s[0] for s in spese])

    categorie = {}
    for imp, cat in spese:
        categorie[cat] = categorie.get(cat, 0) + imp

    testo = f"📊 {inizio} → {fine}\nTotale: {totale:.2f}€\n\n"

    for cat, val in categorie.items():
        testo += f"{cat}: {val:.2f}€\n"

    return testo


async def report_mese(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    oggi = datetime.now()
    inizio = oggi.replace(day=1).strftime("%Y-%m-%d")
    fine = oggi.strftime("%Y-%m-%d")

    testo = genera_report(inizio, fine)
    await query.message.reply_text(testo, reply_markup=main_menu())


async def report_15(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    oggi = datetime.now()
    inizio = oggi.replace(day=1).strftime("%Y-%m-%d")
    fine = oggi.replace(day=15).strftime("%Y-%m-%d")

    testo = genera_report(inizio, fine)
    await query.message.reply_text(testo, reply_markup=main_menu())


# -------------------------
# REMINDER
# -------------------------
async def send_message(app, text):
    if CHAT_ID:
        await app.bot.send_message(chat_id=CHAT_ID, text=text, reply_markup=main_menu())


# -------------------------
# MAIN
# -------------------------
async def main():
    init_db()

    app = ApplicationBuilder().token(TOKEN).build()

    conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(start_add, pattern="add")],
        states={
            IMPORTO: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_importo)],
            CATEGORIA: [CallbackQueryHandler(get_categoria)],
            DESCRIZIONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_descrizione)],
        },
        fallbacks=[]
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(conv)
    app.add_handler(CallbackQueryHandler(report_mese, pattern="report_mese"))
    app.add_handler(CallbackQueryHandler(report_15, pattern="report_15"))

    scheduler = AsyncIOScheduler(timezone="Europe/Rome")

    scheduler.add_job(lambda: send_message(app, "💸 Inserisci le spese"), "cron", hour=8)
    scheduler.add_job(lambda: send_message(app, "⏰ Reminder spese"), "cron", hour=13)
    scheduler.add_job(lambda: send_message(app, "📊 Hai inserito tutto?"), "cron", hour=22)

    scheduler.start()

    print("🤖 CONSUlente attivo")
    await app.run_polling()


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
