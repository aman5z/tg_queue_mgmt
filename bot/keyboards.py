"""Inline and reply keyboard builders."""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def counters_keyboard(counters: list[dict]) -> InlineKeyboardMarkup:
    """Keyboard listing all counters with open/close toggle buttons."""
    buttons = []
    for c in counters:
        status_icon = "🟢" if c["status"] == "open" else "🔴"
        buttons.append(
            [
                InlineKeyboardButton(
                    f"{status_icon} {c['name']} (#{c['id']})",
                    callback_data=f"counter_select:{c['id']}",
                )
            ]
        )
    buttons.append(
        [InlineKeyboardButton("➕ Add Counter", callback_data="counter_add")]
    )
    return InlineKeyboardMarkup(buttons)


def counter_actions_keyboard(counter: dict) -> InlineKeyboardMarkup:
    """Keyboard with token operations for a single counter."""
    cid = counter["id"]
    is_open = counter["status"] == "open"
    toggle_label = "🔴 Close" if is_open else "🟢 Open"
    toggle_cb = f"counter_close:{cid}" if is_open else f"counter_open:{cid}"

    buttons = [
        [
            InlineKeyboardButton("⏭ Next", callback_data=f"token_next:{cid}"),
            InlineKeyboardButton("⏮ Previous", callback_data=f"token_prev:{cid}"),
        ],
        [
            InlineKeyboardButton("🔁 Recall", callback_data=f"token_recall:{cid}"),
            InlineKeyboardButton("🔢 Current", callback_data=f"token_current:{cid}"),
        ],
        [
            InlineKeyboardButton("📋 Waiting", callback_data=f"token_waiting:{cid}"),
        ],
        [
            InlineKeyboardButton(toggle_label, callback_data=toggle_cb),
            InlineKeyboardButton("✏️ Rename", callback_data=f"counter_rename:{cid}"),
            InlineKeyboardButton("🗑 Remove", callback_data=f"counter_remove:{cid}"),
        ],
        [InlineKeyboardButton("« Back", callback_data="counter_list")],
    ]
    return InlineKeyboardMarkup(buttons)


def confirm_keyboard(action: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✅ Yes", callback_data=f"confirm_yes:{action}"),
                InlineKeyboardButton("❌ No", callback_data="confirm_no"),
            ]
        ]
    )
