"""Admin bot handlers for counter and token management."""

import os
from telegram import Update
from telegram.ext import (
    ContextTypes,
    CommandHandler,
    CallbackQueryHandler,
    ConversationHandler,
    MessageHandler,
    filters,
)

from db.database import (
    get_counters,
    get_counter,
    add_counter,
    rename_counter,
    remove_counter,
    set_counter_status,
    call_next_token,
    call_previous_token,
    recall_current_token,
    get_waiting_tokens,
    get_current_token_for_counter,
    reset_queue,
)
from bot.keyboards import counters_keyboard, counter_actions_keyboard, confirm_keyboard
from web.app import broadcast_update

# Conversation states
WAITING_COUNTER_NAME = 1
WAITING_RENAME_NAME = 2

ADMIN_IDS: set[int] = set()


def _load_admin_ids() -> None:
    raw = os.getenv("ADMIN_IDS", "")
    for part in raw.split(","):
        part = part.strip()
        if part.isdigit():
            ADMIN_IDS.add(int(part))


_load_admin_ids()


def is_admin(user_id: int) -> bool:
    return not ADMIN_IDS or user_id in ADMIN_IDS


async def _require_admin(update: Update) -> bool:
    user = update.effective_user
    if not is_admin(user.id):
        await update.effective_message.reply_text("⛔ Admin only command.")
        return False
    return True


# ---------------------------------------------------------------------------
# /counters
# ---------------------------------------------------------------------------

async def cmd_counters(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _require_admin(update):
        return
    counters = await get_counters()
    if not counters:
        await update.message.reply_text(
            "No counters yet. Use /addcounter <name> to create one."
        )
        return
    await update.message.reply_text(
        "📋 *Counter List*\nTap a counter to manage it.",
        parse_mode="Markdown",
        reply_markup=counters_keyboard(counters),
    )


# ---------------------------------------------------------------------------
# /addcounter <name>
# ---------------------------------------------------------------------------

async def cmd_addcounter(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _require_admin(update):
        return
    if not context.args:
        await update.message.reply_text("Usage: /addcounter <name>")
        return
    name = " ".join(context.args).strip()
    counter = await add_counter(name)
    await broadcast_update()
    await update.message.reply_text(f"✅ Counter *{name}* (ID {counter['id']}) created.", parse_mode="Markdown")


# ---------------------------------------------------------------------------
# /renamecounter <id> <name>
# ---------------------------------------------------------------------------

async def cmd_renamecounter(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _require_admin(update):
        return
    if len(context.args) < 2:
        await update.message.reply_text("Usage: /renamecounter <id> <new name>")
        return
    try:
        cid = int(context.args[0])
    except ValueError:
        await update.message.reply_text("Counter ID must be a number.")
        return
    new_name = " ".join(context.args[1:]).strip()
    await rename_counter(cid, new_name)
    await broadcast_update()
    await update.message.reply_text(f"✅ Counter {cid} renamed to *{new_name}*.", parse_mode="Markdown")


# ---------------------------------------------------------------------------
# /removecounter <id>
# ---------------------------------------------------------------------------

async def cmd_removecounter(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _require_admin(update):
        return
    if not context.args:
        await update.message.reply_text("Usage: /removecounter <id>")
        return
    try:
        cid = int(context.args[0])
    except ValueError:
        await update.message.reply_text("Counter ID must be a number.")
        return
    counter = await get_counter(cid)
    if not counter:
        await update.message.reply_text("Counter not found.")
        return
    await remove_counter(cid)
    await broadcast_update()
    await update.message.reply_text(f"🗑 Counter {cid} removed.")


# ---------------------------------------------------------------------------
# /opencounter <id>  /closecounter <id>
# ---------------------------------------------------------------------------

async def cmd_opencounter(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _require_admin(update):
        return
    if not context.args:
        await update.message.reply_text("Usage: /opencounter <id>")
        return
    try:
        cid = int(context.args[0])
    except ValueError:
        await update.message.reply_text("Counter ID must be a number.")
        return
    await set_counter_status(cid, "open")
    await broadcast_update()
    counter = await get_counter(cid)
    await update.message.reply_text(f"🟢 Counter *{counter['name']}* is now open.", parse_mode="Markdown")


async def cmd_closecounter(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _require_admin(update):
        return
    if not context.args:
        await update.message.reply_text("Usage: /closecounter <id>")
        return
    try:
        cid = int(context.args[0])
    except ValueError:
        await update.message.reply_text("Counter ID must be a number.")
        return
    await set_counter_status(cid, "closed")
    await broadcast_update()
    counter = await get_counter(cid)
    await update.message.reply_text(f"🔴 Counter *{counter['name']}* is now closed.", parse_mode="Markdown")


# ---------------------------------------------------------------------------
# /status
# ---------------------------------------------------------------------------

async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    counters = await get_counters()
    lines = ["📊 *Queue Status*\n"]
    for c in counters:
        icon = "🟢" if c["status"] == "open" else "🔴"
        waiting = await get_waiting_tokens(c["id"])
        current = await get_current_token_for_counter(c["id"])
        cur_txt = f"serving #{current['token_number']}" if current else "idle"
        lines.append(f"{icon} *{c['name']}* — {cur_txt}, {len(waiting)} waiting")
    await update.effective_message.reply_text(
        "\n".join(lines) if len(lines) > 1 else "No counters configured.",
        parse_mode="Markdown",
    )


# ---------------------------------------------------------------------------
# /resetqueue
# ---------------------------------------------------------------------------

async def cmd_resetqueue(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _require_admin(update):
        return
    await update.message.reply_text(
        "⚠️ Are you sure you want to reset ALL queues?",
        reply_markup=confirm_keyboard("resetqueue"),
    )


# ---------------------------------------------------------------------------
# /help
# ---------------------------------------------------------------------------

async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (
        "🤖 *Queue Management Bot*\n\n"
        "*Admin Commands:*\n"
        "/counters — list counters\n"
        "/addcounter <name> — add counter\n"
        "/renamecounter <id> <name> — rename\n"
        "/removecounter <id> — remove\n"
        "/opencounter <id> — open counter\n"
        "/closecounter <id> — close counter\n"
        "/resetqueue — clear all queues\n"
        "/status — overall status\n"
        "/qr — generate QR for token page\n"
        "/help — this message\n\n"
        "*Customer Commands:*\n"
        "/start — take a token\n"
    )
    await update.effective_message.reply_text(text, parse_mode="Markdown")


# ---------------------------------------------------------------------------
# /qr — generate QR code for /take page
# ---------------------------------------------------------------------------

async def cmd_qr(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _require_admin(update):
        return
    base_url = os.getenv("BASE_URL", "http://localhost:8000")
    take_url = f"{base_url}/take"
    try:
        import qrcode
        import io
        qr = qrcode.make(take_url)
        buf = io.BytesIO()
        qr.save(buf, format="PNG")
        buf.seek(0)
        await update.message.reply_photo(
            photo=buf,
            caption=f"📲 Scan to take a token\n{take_url}",
        )
    except ImportError:
        await update.message.reply_text(
            f"QR library not installed. Direct link: {take_url}"
        )


# ---------------------------------------------------------------------------
# Inline keyboard callbacks
# ---------------------------------------------------------------------------

async def callback_counter_select(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        await query.answer("Admin only.", show_alert=True)
        return
    cid = int(query.data.split(":")[1])
    counter = await get_counter(cid)
    if not counter:
        await query.edit_message_text("Counter not found.")
        return
    current = await get_current_token_for_counter(cid)
    waiting = await get_waiting_tokens(cid)
    cur_txt = f"#{current['token_number']}" if current else "none"
    text = (
        f"🏷 *{counter['name']}* (ID {cid})\n"
        f"Status: {'🟢 Open' if counter['status'] == 'open' else '🔴 Closed'}\n"
        f"Current: {cur_txt}\n"
        f"Waiting: {len(waiting)}"
    )
    await query.edit_message_text(
        text, parse_mode="Markdown", reply_markup=counter_actions_keyboard(counter)
    )


async def callback_counter_list(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    counters = await get_counters()
    await query.edit_message_text(
        "📋 *Counter List*\nTap a counter to manage it.",
        parse_mode="Markdown",
        reply_markup=counters_keyboard(counters),
    )


async def callback_counter_open(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    cid = int(query.data.split(":")[1])
    await set_counter_status(cid, "open")
    await broadcast_update()
    counter = await get_counter(cid)
    await query.edit_message_text(
        f"🟢 *{counter['name']}* opened.",
        parse_mode="Markdown",
        reply_markup=counter_actions_keyboard(counter),
    )


async def callback_counter_close(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    cid = int(query.data.split(":")[1])
    await set_counter_status(cid, "closed")
    await broadcast_update()
    counter = await get_counter(cid)
    await query.edit_message_text(
        f"🔴 *{counter['name']}* closed.",
        parse_mode="Markdown",
        reply_markup=counter_actions_keyboard(counter),
    )


async def callback_token_next(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    cid = int(query.data.split(":")[1])
    token = await call_next_token(cid)
    await broadcast_update()
    counter = await get_counter(cid)
    if token:
        msg = f"⏭ Now serving *#{token['token_number']}*"
        if token.get("customer_name"):
            msg += f" — {token['customer_name']}"
    else:
        msg = "📭 No more tokens in queue."
    await query.edit_message_text(
        msg, parse_mode="Markdown", reply_markup=counter_actions_keyboard(counter)
    )


async def callback_token_prev(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    cid = int(query.data.split(":")[1])
    token = await call_previous_token(cid)
    await broadcast_update()
    counter = await get_counter(cid)
    if token:
        msg = f"⏮ Reverted to *#{token['token_number']}*"
    else:
        msg = "⏮ No previous token available."
    await query.edit_message_text(
        msg, parse_mode="Markdown", reply_markup=counter_actions_keyboard(counter)
    )


async def callback_token_recall(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    cid = int(query.data.split(":")[1])
    token = await recall_current_token(cid)
    await broadcast_update()
    counter = await get_counter(cid)
    if token:
        msg = f"🔁 Recalled *#{token['token_number']}*"
    else:
        msg = "🔁 No current token to recall."
    await query.edit_message_text(
        msg, parse_mode="Markdown", reply_markup=counter_actions_keyboard(counter)
    )


async def callback_token_current(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    cid = int(query.data.split(":")[1])
    token = await get_current_token_for_counter(cid)
    counter = await get_counter(cid)
    if token:
        msg = f"🔢 Current token: *#{token['token_number']}*"
        if token.get("customer_name"):
            msg += f"\nCustomer: {token['customer_name']}"
        if token.get("purpose"):
            msg += f"\nPurpose: {token['purpose']}"
    else:
        msg = "No token currently being served."
    await query.edit_message_text(
        msg, parse_mode="Markdown", reply_markup=counter_actions_keyboard(counter)
    )


async def callback_token_waiting(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    cid = int(query.data.split(":")[1])
    waiting = await get_waiting_tokens(cid)
    counter = await get_counter(cid)
    if waiting:
        lines = [f"📋 *Waiting ({len(waiting)})*"]
        for t in waiting[:20]:
            name = t.get("customer_name") or "—"
            lines.append(f"  • #{t['token_number']} — {name}")
        if len(waiting) > 20:
            lines.append(f"  …and {len(waiting) - 20} more")
        msg = "\n".join(lines)
    else:
        msg = "📭 Queue is empty."
    await query.edit_message_text(
        msg, parse_mode="Markdown", reply_markup=counter_actions_keyboard(counter)
    )


async def callback_counter_rename(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    cid = int(query.data.split(":")[1])
    context.user_data["renaming_counter_id"] = cid
    await query.edit_message_text(
        f"✏️ Send the new name for counter {cid}:"
    )
    return WAITING_RENAME_NAME


async def callback_counter_remove(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    cid = int(query.data.split(":")[1])
    counter = await get_counter(cid)
    await query.edit_message_text(
        f"🗑 Remove counter *{counter['name']}*?",
        parse_mode="Markdown",
        reply_markup=confirm_keyboard(f"remove_counter:{cid}"),
    )


async def callback_confirm_yes(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    action = query.data.split(":", 1)[1]

    if action == "resetqueue":
        await reset_queue()
        await broadcast_update()
        await query.edit_message_text("✅ All queues have been reset.")
    elif action.startswith("remove_counter:"):
        cid = int(action.split(":")[1])
        counter = await get_counter(cid)
        name = counter["name"] if counter else str(cid)
        await remove_counter(cid)
        await broadcast_update()
        await query.edit_message_text(f"✅ Counter *{name}* removed.", parse_mode="Markdown")


async def callback_confirm_no(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer("Cancelled.")
    await query.edit_message_text("❌ Action cancelled.")


async def callback_counter_add(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("➕ Send the name for the new counter:")
    return WAITING_COUNTER_NAME


# ---------------------------------------------------------------------------
# Conversation: receive new counter name
# ---------------------------------------------------------------------------

async def receive_counter_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    name = update.message.text.strip()
    if not name:
        await update.message.reply_text("Name cannot be empty. Try again:")
        return WAITING_COUNTER_NAME
    counter = await add_counter(name)
    await broadcast_update()
    await update.message.reply_text(
        f"✅ Counter *{name}* (ID {counter['id']}) created.",
        parse_mode="Markdown",
    )
    return ConversationHandler.END


async def receive_rename_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    name = update.message.text.strip()
    cid = context.user_data.get("renaming_counter_id")
    if not name or not cid:
        await update.message.reply_text("Something went wrong. Use /renamecounter <id> <name> instead.")
        return ConversationHandler.END
    await rename_counter(cid, name)
    await broadcast_update()
    await update.message.reply_text(
        f"✅ Counter {cid} renamed to *{name}*.",
        parse_mode="Markdown",
    )
    return ConversationHandler.END


# ---------------------------------------------------------------------------
# Handler registration helper
# ---------------------------------------------------------------------------

def register_admin_handlers(app) -> None:
    """Register all admin-related handlers with the bot application."""
    app.add_handler(CommandHandler("counters", cmd_counters))
    app.add_handler(CommandHandler("addcounter", cmd_addcounter))
    app.add_handler(CommandHandler("renamecounter", cmd_renamecounter))
    app.add_handler(CommandHandler("removecounter", cmd_removecounter))
    app.add_handler(CommandHandler("opencounter", cmd_opencounter))
    app.add_handler(CommandHandler("closecounter", cmd_closecounter))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("resetqueue", cmd_resetqueue))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("qr", cmd_qr))

    # Inline keyboard callbacks (exclude add/rename — handled by ConversationHandler below)
    app.add_handler(CallbackQueryHandler(callback_counter_list, pattern="^counter_list$"))
    app.add_handler(CallbackQueryHandler(callback_counter_select, pattern="^counter_select:"))
    app.add_handler(CallbackQueryHandler(callback_counter_open, pattern="^counter_open:"))
    app.add_handler(CallbackQueryHandler(callback_counter_close, pattern="^counter_close:"))
    app.add_handler(CallbackQueryHandler(callback_counter_remove, pattern="^counter_remove:"))
    app.add_handler(CallbackQueryHandler(callback_token_next, pattern="^token_next:"))
    app.add_handler(CallbackQueryHandler(callback_token_prev, pattern="^token_prev:"))
    app.add_handler(CallbackQueryHandler(callback_token_recall, pattern="^token_recall:"))
    app.add_handler(CallbackQueryHandler(callback_token_current, pattern="^token_current:"))
    app.add_handler(CallbackQueryHandler(callback_token_waiting, pattern="^token_waiting:"))
    app.add_handler(CallbackQueryHandler(callback_confirm_yes, pattern="^confirm_yes:"))
    app.add_handler(CallbackQueryHandler(callback_confirm_no, pattern="^confirm_no$"))

    # ConversationHandler: inline "Add Counter" / "Rename" buttons trigger a text reply flow
    conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(callback_counter_add, pattern="^counter_add$"),
            CallbackQueryHandler(callback_counter_rename, pattern="^counter_rename:"),
        ],
        states={
            WAITING_COUNTER_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_counter_name)
            ],
            WAITING_RENAME_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_rename_name)
            ],
        },
        fallbacks=[],
        per_user=True,
    )
    app.add_handler(conv)
