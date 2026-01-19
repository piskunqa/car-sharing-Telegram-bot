import datetime
import calendar
import typing

from telebot import TeleBot
from telebot.types import InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery


class CallbackData:
    """
       Helper class to create and parse structured callback data for Telegram inline keyboards.

       Callback data is limited to 64 characters in Telegram, so this class ensures
       safe creation and parsing with validation.

       Example:
           cb = CallbackData("calendar", "action", "year", "month", "day", "trip_id")
           data = cb.new("DAY", 2025, 11, 25, 42)
           parsed = cb.parse(data)
   """

    def __init__(self, prefix, *parts, sep=":"):
        """
            Initialize a CallbackData instance.

            Args:
                prefix (str): Prefix for this callback type (e.g., 'calendar').
                *parts (str): Names of the parts to include in the callback data.
                sep (str): Separator used to join parts (default ":").

            Raises:
                TypeError: If prefix is not a string or parts are not provided.
                ValueError: If prefix is empty or contains the separator.
        """
        if not isinstance(prefix, str): raise TypeError(f"Prefix must be str, not {type(prefix).__name__}")
        if not prefix: raise ValueError("Prefix can't be empty")
        if sep in prefix: raise ValueError(f"Separator {sep!r} can't be used in prefix")
        if not parts: raise TypeError("Parts were not passed!")
        self.prefix = prefix
        self.sep = sep
        self._part_names = parts

    def new(self, *args, **kwargs) -> str:
        """
            Create a callback data string with the given values.

            Args:
                *args: Positional values corresponding to part names.
                **kwargs: Named values corresponding to part names.

            Returns:
                str: Formatted callback data string.

            Raises:
                ValueError: If required values are missing or contain invalid characters.
                TypeError: If too many arguments are passed.
        """
        args = list(args)
        data = [self.prefix]
        for part in self._part_names:
            value = kwargs.pop(part, None)
            if value is None:
                if args:
                    value = args.pop(0)
                else:
                    raise ValueError(f"Value for {part!r} was not passed!")
            if value is not None and not isinstance(value, str):
                value = str(value)
            if not value:
                raise ValueError(f"Value for part {part!r} can't be empty!")
            if self.sep in value:
                raise ValueError(f"Symbol {self.sep!r} can't be used in parts' values")
            data.append(value)
        if args or kwargs:
            raise TypeError("Too many arguments were passed!")
        callback_data = self.sep.join(data)
        if len(callback_data) > 64:
            raise ValueError("Resulted callback data is too long!")
        return callback_data

    def parse(self, callback_data: str) -> typing.Dict[str, str]:
        """
            Parse a callback data string created with this instance.

            Args:
                callback_data (str): The callback data string to parse.

            Returns:
                Dict[str, str]: Dictionary mapping part names to values, with '@' key as prefix.

            Raises:
                ValueError: If the prefix does not match or part count is invalid.
        """
        prefix, *parts = callback_data.split(self.sep)
        if prefix != self.prefix:
            raise ValueError("Callback data prefix mismatch")
        if len(parts) != len(self._part_names):
            raise ValueError("Invalid parts count")
        return {"@": prefix, **dict(zip(self._part_names, parts))}


def create_calendar(name: str = "calendar", year: int = None, month: int = None, language=None,
                    trip_id: int = None, preset_id: str = "") -> InlineKeyboardMarkup:
    """
        Create an inline keyboard representing a monthly calendar.

        Args:
            name (str): Prefix name for callback data.
            year (int): Year to display (defaults to current year).
            month (int): Month to display (defaults to current month).
            language: Language object containing localized month/day names.
            trip_id (int): Optional trip identifier to include in callback data.

        Returns:
            InlineKeyboardMarkup: Telegram inline keyboard with days and navigation buttons.
    """
    now_day = datetime.datetime.now()
    year = now_day.year if year is None else year
    month = now_day.month if month is None else month
    calendar_callback = CallbackData(name, "action", "year", "month", "day", "trip_id", "preset_id")
    data_ignore = calendar_callback.new("IGNORE", year, month, "!", str(trip_id), preset_id)
    keyboard = InlineKeyboardMarkup(row_width=7)
    keyboard.add(InlineKeyboardButton(list(language.MONTHS_NUM.__dict__.keys())[month - 1] + " " + str(
        year), callback_data=calendar_callback.new("MONTHS", year, month, "!", str(trip_id), preset_id)))
    keyboard.add(*[InlineKeyboardButton(day, callback_data=data_ignore) for day in language.DAYS])
    for week in calendar.monthcalendar(year, month):
        row = []
        for day in week:
            if day == 0:
                row.append(InlineKeyboardButton(" ", callback_data=data_ignore))
            else:
                date_to_check = datetime.datetime(year, month, day)
                if date_to_check < now_day.replace(hour=0, minute=0, second=0, microsecond=0):
                    row.append(InlineKeyboardButton("-", callback_data=data_ignore))
                else:
                    display_day = f"({day})" if date_to_check.date() == now_day.date() else str(day)
                    row.append(InlineKeyboardButton(display_day, callback_data=calendar_callback.new(
                        "DAY", year, month, day, str(trip_id), preset_id)))
        keyboard.add(*row)
    keyboard.add(InlineKeyboardButton("<", callback_data=calendar_callback.new(
        "PREVIOUS-MONTH", year, month, "!", str(trip_id), preset_id)),
                 InlineKeyboardButton(language.text.back, callback_data=calendar_callback.new(
                     "CANCEL", year, month, "!", str(trip_id), preset_id)),
                 InlineKeyboardButton(">", callback_data=calendar_callback.new(
                     "NEXT-MONTH", year, month, "!", str(trip_id), preset_id)),
                 )
    return keyboard


def create_months_calendar(name: str = "calendar", year: int = None, language=None,
                           trip_id: int = None, preset_id: str = "") -> InlineKeyboardMarkup:
    """
        Create an inline keyboard representing all months for the given year.

        Args:
            name (str): Prefix name for callback data.
            year (int): Year for which months are displayed (defaults to current year).
            language: Language object containing localized month names.
            trip_id (int): Optional trip identifier to include in callback data.

        Returns:
            InlineKeyboardMarkup: Telegram inline keyboard with months as buttons.
    """
    months_num = language.MONTHS_NUM.__dict__
    months = list(months_num.keys())
    year = datetime.datetime.now().year if year is None else year
    calendar_callback = CallbackData(name, "action", "year", "month", "day", "trip_id")
    keyboard = InlineKeyboardMarkup()
    for i, month in enumerate(zip(months[0::2], months[1::2])):
        keyboard.add(InlineKeyboardButton(month[0], callback_data=calendar_callback.new(
            "MONTH", year, months_num[month[0]], "!", str(trip_id), preset_id)),
                     InlineKeyboardButton(month[1], callback_data=calendar_callback.new(
                         "MONTH", year, months_num[month[1]], "!", str(trip_id), preset_id)))
    return keyboard


def calendar_query_handler(bot: TeleBot, call: CallbackQuery, name: str, action: str, year: str, month: str, day: str,
                           language, trip_id, preset_id) -> None | bool | datetime.datetime | tuple[str, None]:
    """
        Handle a callback query for the calendar inline keyboard.

        Updates the calendar view if navigating months or selects a day.

        Args:
            bot (TeleBot): The bot instance.
            call (CallbackQuery): CallbackQuery received from Telegram.
            name (str): Calendar prefix name.
            action (str): Action extracted from callback data (e.g., "DAY", "NEXT-MONTH").
            year (str): Year string from callback data.
            month (str): Month string from callback data.
            day (str): Day string from callback data.
            language: Language object for localization.
            trip_id: Trip ID included in callback data.

        Returns:
            datetime.datetime | tuple | None:
                - datetime for selected day
                - ("CANCEL", None) if cancelled
                - None if navigation or ignore
    """
    current = datetime.datetime(int(year), int(month), 1)
    match action:
        case "IGNORE":
            return bot.answer_callback_query(callback_query_id=call.id)
        case "DAY":
            return datetime.datetime(int(year), int(month), int(day))
        case "PREVIOUS-MONTH":
            prev_month = current - datetime.timedelta(days=1)
            bot.edit_message_text(
                text=call.message.text,
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                reply_markup=create_calendar(
                    language=language,
                    trip_id=trip_id,
                    year=int(prev_month.year),
                    month=int(prev_month.month),
                    name=name,
                    preset_id=preset_id))
            return None
        case "NEXT-MONTH":
            next_month = current + datetime.timedelta(days=31)
            bot.edit_message_text(
                text=call.message.text,
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                reply_markup=create_calendar(
                    language=language,
                    trip_id=trip_id,
                    year=int(next_month.year),
                    month=int(next_month.month),
                    name=name,
                    preset_id=preset_id))
            return None
        case "MONTHS":
            bot.edit_message_text(
                text=call.message.text,
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                reply_markup=create_months_calendar(
                    language=language,
                    trip_id=trip_id,
                    year=current.year,
                    name=name,
                    preset_id=preset_id))
            return None
        case "MONTH":
            bot.edit_message_text(
                text=call.message.text,
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                reply_markup=create_calendar(
                    language=language,
                    trip_id=trip_id,
                    year=int(year),
                    month=int(month),
                    name=name,
                    preset_id=preset_id))
            return None
        case "CANCEL":
            return "CANCEL", None
        case _:
            bot.answer_callback_query(callback_query_id=call.id, text="ERROR!")
            bot.delete_message(chat_id=call.message.chat.id, message_id=call.message.message_id)
            return None
