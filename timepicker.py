from typing import Dict, Tuple, Optional, Callable
from telebot import TeleBot
from telebot.types import InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery

from config import TIMEPICKER_DEFAULT_OPTIONS


class TimePicker:
    """
        TimePicker component for pyTelegramBotAPI (telebot).

        This class allows sending an interactive time picker inline keyboard to a Telegram chat,
        handling user selection of hours and minutes, and calling a callback function when
        the time is selected or cancelled.

        Usage:
            tp = TimePicker(bot, on_time_selected=my_handler)
            tp.register()            # Registers the callback handler on the bot
            tp.send(call, hour=9, minute=30, trip_id=123, language=my_language)

        Attributes:
            language: Current language object used for labels.
            _registered: Boolean indicating if the callback handler is registered.
            trip_id: Optional identifier associated with the picker instance.
    """
    language, command, _registered, trip_id, preset_id = None, None, False, 0, 0

    def __init__(self, bot: TeleBot, on_time_selected: Optional[Callable] = None):
        """
           Initialize the TimePicker.

           Args:
               bot (TeleBot): The TeleBot instance to send messages and handle callbacks.
               on_time_selected (Callable): Callback function to call when user presses OK or Cancel.
                                            Signature: (action, call, hour, minute, trip_id)
                                            'action' can be 'ok', 'cancel', or 'ERROR'.
       """
        self.bot = bot
        assert on_time_selected is not None, "on_time_selected is required"
        self.on_time_selected = on_time_selected
        self._states: Dict[int, Tuple[int, int, int, int, dict]] = {}

    def register(self, command="tp"):
        """
            Register the callback_query handler with the bot.
            This method should be called once after creating the TimePicker instance.
        """
        self.command = command
        if self._registered:
            return self

        @self.bot.callback_query_handler(func=lambda call: bool(call.data and call.data.startswith(f"{command}:")))
        def _handler(call: CallbackQuery):
            self._on_tp(call)

        self._registered = True
        return self

    def send(self, call: CallbackQuery, hour: int = 12, minute: int = 0, opts: dict = None,
             trip_id: int | str = 0, language=None, preset_id: str = "") -> int:
        """
            Send a timepicker message to the chat associated with the given callback query.

            Args:
                call (CallbackQuery): The callback query object to get chat and message info.
                hour (int): Initial hour to display.
                minute (int): Initial minute to display.
                opts (dict): Optional settings, e.g., {"24hour": True, "minute_step": 5}.
                trip_id (int | str): Optional identifier associated with this picker.
                language: Language object containing localized text labels.

            Returns:
                int: The Telegram message_id of the sent timepicker.
        """
        assert language, "language is required"
        self.trip_id, self.language, self.preset_id = trip_id, language, preset_id
        opts = TIMEPICKER_DEFAULT_OPTIONS.copy() if opts is None else {**TIMEPICKER_DEFAULT_OPTIONS, **opts}
        message_id, chat_id = call.message.message_id, call.message.chat.id
        self._states[message_id] = (chat_id, call.from_user.id, hour, minute, opts)
        markup = self._build_kb(message_id, hour, minute, opts)
        self.bot.edit_message_text(f"{language.text.t_6}: {hour:02d}:{minute:02d}", chat_id, message_id,
                                   reply_markup=markup)
        return message_id

    def _build_kb(self, message_id: int, selected_hour: int, selected_minute: int, opts: dict) -> InlineKeyboardMarkup:
        """
            Build the inline keyboard for the timepicker.

            Args:
                message_id (int): Message ID associated with the picker.
                selected_hour (int): Currently selected hour.
                selected_minute (int): Currently selected minute.
                opts (dict): Options dict containing settings like 24hour format and minute_step.

            Returns:
                InlineKeyboardMarkup: The inline keyboard markup with hours, minutes, and controls.
        """
        minute_step = opts.get("minute_step", 5)
        is_24 = opts.get("24hour", True)
        markup = InlineKeyboardMarkup(row_width=4)
        markup.add(
            InlineKeyboardButton(f"🕒 {self.language.text.hours} 🕒",
                                 callback_data=f"{self.command}:none:{message_id}::{self.trip_id}"))
        hours = list(range(0, 24)) if is_24 else list(range(1, 13))
        row = []
        for i, h in enumerate(hours, start=1):
            txt = str(h).zfill(2)
            label = txt if h != selected_hour else f"✅ {txt}"
            cb = InlineKeyboardButton(label, callback_data=f"{self.command}:set_h:{message_id}:{h}:{self.trip_id}")
            row.append(cb)
            if i % 4 == 0:
                markup.add(*row)
                row = []
        if row:
            markup.add(*row)
        markup.add(InlineKeyboardButton(f"⏱️ {self.language.text.minutes} ⏱️",
                                        callback_data=f"{self.command}:none:{message_id}::{self.trip_id}"))
        minutes = list(range(0, 60, minute_step))
        row = []
        for i, m in enumerate(minutes, start=1):
            txt = str(m).zfill(2)
            label = txt if m != selected_minute else f"✅ {txt}"
            cb = InlineKeyboardButton(label, callback_data=f"{self.command}:set_m:{message_id}:{m}:{self.trip_id}")
            row.append(cb)
            if i % 4 == 0:
                markup.add(*row)
                row = []
        if row:
            markup.add(*row)
        markup.add(
            InlineKeyboardButton(f"➖1 {self.language.text.hours_short}",
                                 callback_data=f"{self.command}:delta_h:{message_id}:-1:{self.trip_id}"),
            InlineKeyboardButton(f"➕1 {self.language.text.hours_short}",
                                 callback_data=f"{self.command}:delta_h:{message_id}:1:{self.trip_id}"),
            InlineKeyboardButton(f"➖1 {self.language.text.minutes_short}",
                                 callback_data=f"{self.command}:delta_m:{message_id}:-1:{self.trip_id}"),
            InlineKeyboardButton(f"➕1 {self.language.text.minutes_short}",
                                 callback_data=f"{self.command}:delta_m:{message_id}:1:{self.trip_id}"),
        )
        markup.add(
            InlineKeyboardButton(self.language.text.back,
                                 callback_data=f"{self.command}:cancel:{message_id}::{self.trip_id}"),
            InlineKeyboardButton(self.language.text.apply,
                                 callback_data=f"{self.command}:ok:{message_id}::{self.trip_id}"),
        )
        return markup

    def _on_tp(self, call: CallbackQuery):
        """
            Internal handler for all callback queries related to the timepicker.

            Parses the callback data, updates state, rebuilds the keyboard, and calls the
            user-provided on_time_selected callback when necessary.

            Args:
                call (CallbackQuery): The callback query received from Telegram.
        """
        _, action, message_id, value, trip_id = call.data.split(":", 4)
        message_id = int(message_id)
        state = self._states.get(message_id)
        if not state:
            self.bot.answer_callback_query(call.id)
            return self.on_time_selected("ERROR", call, None, None, trip_id, self.preset_id)
        user_id, chat_id, hour, minute, opts = state
        if call.from_user.id != user_id:
            self.bot.answer_callback_query(call.id)
            return self.on_time_selected("ERROR", call, None, None, trip_id, self.preset_id)
        match action:
            case "none":
                return self.bot.answer_callback_query(call.id)
            case "set_h":
                try:
                    new_h = int(value)
                except (IndexError, ValueError):
                    self.bot.answer_callback_query(call.id)
                    return self.bot.answer_callback_query(call.id, self.language.text.wrong_hour)
                hour = max(1, min(12, new_h)) if not opts.get("24hour", True) else new_h % 24
            case "set_m":
                try:
                    new_m = int(value)
                except (IndexError, ValueError):
                    self.bot.answer_callback_query(call.id)
                    return self.bot.answer_callback_query(call.id, self.language.text.wrong_minute)
                minute = new_m % 60
            case "delta_h":
                try:
                    delta = int(value)
                except (IndexError, ValueError):
                    delta = 0
                hour = (hour + delta) % 24 if opts.get("24hour", True) else ((hour - 1 + delta) % 12) + 1
            case "delta_m":
                try:
                    delta = int(value)
                except (IndexError, ValueError):
                    delta = 0
                total = hour * 60 + minute + delta
                total %= (24 * 60)
                hour = total // 60
                minute = total % 60
                if not opts.get("24hour", True) and hour == 0:
                    hour = 12
            case "ok":
                self.bot.answer_callback_query(call.id)
                self._states.pop(message_id, None)
                return self.on_time_selected(action, call, hour, minute, trip_id, self.preset_id)
            case "cancel":
                self.bot.answer_callback_query(call.id)
                self._states.pop(message_id, None)
                return self.on_time_selected(action, call, None, None, trip_id, self.preset_id)
            case _:
                self.bot.answer_callback_query(call.id)
                return self.on_time_selected("ERROR", call, None, None, trip_id, self.preset_id)
        self._states[message_id] = (user_id, chat_id, hour, minute, opts)
        kb = self._build_kb(message_id, hour, minute, opts)
        self.bot.edit_message_text(f"{self.language.text.t_6}: {hour:02d}:{minute:02d}", chat_id, message_id,
                                   reply_markup=kb)
        return self.bot.answer_callback_query(call.id)
