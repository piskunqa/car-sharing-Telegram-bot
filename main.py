from datetime import datetime, time as t, timedelta
from io import BytesIO
from os.path import join

import telebot
from peewee import fn
from telebot.types import (Message, CallbackQuery, BotCommand, InlineKeyboardButton, InlineKeyboardMarkup)

import datepicker
from config import texts, BOT_TOKEN, IMG_DIR, PLACES, START_COMMAND, LANGUAGE_COMMAND, MENU_COMMAND
from models import Users, Trips, Presets, TakeASeat
from routing import get_address
from timepicker import TimePicker
from utils import chunks, get_handler_for_command

bot = telebot.TeleBot(BOT_TOKEN, threaded=True, num_threads=15, skip_pending=True)
bot.set_my_commands([
    BotCommand("/start", START_COMMAND),
    BotCommand("/language", LANGUAGE_COMMAND),
    BotCommand("/menu", MENU_COMMAND),
])

# load images
with open(join(IMG_DIR, 't_15.jpg'), 'rb') as f: t_15_img = f.read()
with open(join(IMG_DIR, 't_42.jpg'), 'rb') as f: error_image = f.read()

# calendars
calendar_callback = datepicker.CallbackData("calendar_callback", "action", "year", "month", "day")
change_calendar_callback = datepicker.CallbackData("change_date", "action", "year", "month", "day")


@bot.callback_query_handler(func=lambda call: call.data.startswith('update:'))
def update_all_handler(call):
    _, trip_id = call.data.split(":", 1)
    trip = Trips.get_by_id(trip_id)
    user = trip.user
    text = texts[user.language]
    bot.answer_callback_query(call.id)
    start_date_time = datetime.combine(trip.start_date, trip.start_time)
    start_dt = start_date_time - timedelta(hours=1)
    end_dt = start_date_time + timedelta(hours=1)
    result = list()
    markup = telebot.types.InlineKeyboardMarkup()
    bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text=text.text.loading)
    for i in Trips.select().where(
            (Trips.role == "driver") &
            (Trips.user != user) &
            (Trips.status == 1) &
            (Trips.id != trip.id) &
            (fn.TIMESTAMP(Trips.start_date, Trips.start_time).between(start_dt, end_dt))
    ):
        state, index = i.on_route(trip)
        if state:
            result.append((index, i))
    data = list(sorted(result, key=lambda x: x[0], reverse=True))[:10]
    if not data:
        return bot.answer_callback_query(call.id, text=text.t_5)
    for chunk in chunks(data, 2):
        markup.row(
            *[InlineKeyboardButton(text=f"{i[1].start_date} {i[1].start_time}",
                                   callback_data=f"pt:{i[1].id}:{trip_id}:")
              for i in chunk])
    markup.row(InlineKeyboardButton(text=text.text.back, callback_data=f"trip_dt:{trip_id}"))
    return bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id,
                                 text=text.text.pick_mach, reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data.startswith("show_last_menu"))
def show_last_menu(call, text=None):
    if not text:
        user = get_user(call)
        text = texts[user.lang]
    markup = telebot.types.InlineKeyboardMarkup()
    markup.add(
        telebot.types.InlineKeyboardButton(text=text.text.my_trips, callback_data='my_trips_menu'),
        telebot.types.InlineKeyboardButton(text=text.text.new_trip, callback_data='new_drive'),
        # telebot.types.InlineKeyboardButton(text=text.text.t_3, callback_data='update_all')
    )
    if isinstance(call, CallbackQuery):
        if ":" in call.data:
            _, command = call.data.split(":", 1)
            if command == "del":
                bot.delete_message(chat_id=call.from_user.id, message_id=call.message.message_id)
                return bot.send_message(chat_id=call.message.chat.id, text=text.text.menu, reply_markup=markup)
        return bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id,
                                     text=text.text.menu, reply_markup=markup)
    else:
        return bot.send_message(chat_id=call.chat.id, text=text.text.menu, reply_markup=markup)


def on_time_selected(action, call, hour, minute, trip_id, preset_id=''):
    trip = Trips.get_or_none(id=trip_id)
    user = trip.user
    text = texts[user.lang]
    match action:
        case "ok":
            trip.start_time = t(hour=hour, minute=minute)
            trip.status = 1
            trip.save()
            show_last_menu(call, text)
        case "cancel":
            trip.start_date = None
            trip.save()
            now = datetime.now()
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text=text.text.t_27,
                reply_markup=datepicker.create_calendar(
                    name=calendar_callback.prefix,
                    year=now.year,
                    month=now.month,
                    language=text,
                    trip_id=trip.id,
                    preset_id=preset_id
                ),
            )
        case _:
            if trip:
                trip.delete_instance()
            markup = InlineKeyboardMarkup()
            markup.add(InlineKeyboardButton(text=text.text.restart, callback_data='to_start:!'))
            msg_text = text.text.error
            bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text=msg_text,
                                  reply_markup=markup)


def on_time_edit(action, call, hour, minute, trip_id, preset_id=''):
    trip = Trips.get_or_none(id=trip_id)
    user = trip.user
    text = texts[user.lang]
    match action:
        case "ok":
            trip.start_time = t(hour=hour, minute=minute)
            trip.save()
        case "cancel":
            pass
        case _:
            bot.answer_callback_query(call.id, text=text.text.t_11, show_alert=True)
    call.data = f"edit_st:{trip.id}"
    trips_details_handler(call)


timepicker = TimePicker(bot, on_time_selected=on_time_selected).register()
edit_timepicker = TimePicker(bot, on_time_selected=on_time_edit).register(command="etp")


def get_user(message: Message | CallbackQuery):
    user, is_created = Users.get_or_create(telegram_id=message.from_user.id)
    if user.telegram_username is None:
        user.telegram_username = message.from_user.username
    full_name = f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}".strip() or None
    if user.telegram_full_name is None and full_name is not None:
        user.telegram_full_name = full_name
    if is_created:
        if message.from_user.language_code in texts:
            user.language = message.from_user.language_code
    if user.dirty_fields:
        user.save()
    return user


def start_function(message, user):
    markup = InlineKeyboardMarkup()
    text = texts[user.lang]

    bot.delete_message(message.chat.id, message.message_id)
    if not message.from_user.username:
        markup.row(InlineKeyboardButton(text=text.text.restart, callback_data='to_start:!'))
        bot.send_message(chat_id=message.chat.id, text=text.text.t_16)
    else:
        markup.row(
            InlineKeyboardButton(text=text.text.t_13, callback_data='driver:'),
            InlineKeyboardButton(text=text.text.t_14, callback_data='passenger:'),
            InlineKeyboardButton(text=text.text.t_45, callback_data='load_from_preset'),
        )
        markup.row(InlineKeyboardButton(text=text.text.menu, callback_data='show_last_menu:del'))
        bot.send_photo(message.chat.id, BytesIO(t_15_img),
                       caption=f"{text.text.t_15}\n{text.text.t_63}\n\n{text.text.t_17}",
                       reply_markup=markup)


@bot.message_handler(commands=['start'], chat_types=["private"])
def start(message: Message):
    user = get_user(message)
    return pick_language(message, input_user=user) if user.language is None else start_function(message, user=user)


@bot.message_handler(commands=['language'], chat_types=["private"])
def pick_language(message, input_user=None):
    user = input_user or get_user(message)
    markup = InlineKeyboardMarkup()
    for chunk in chunks(list(texts.keys()), 2):
        markup.row(
            *[InlineKeyboardButton(
                text=texts[language_code].NAME,
                callback_data=f"pick_lang:{language_code}:{'1' if input_user else '0'}")
                for language_code in chunk])
    bot.send_message(message.chat.id, texts[user.lang].text.pick_language, reply_markup=markup)
    bot.delete_message(message.chat.id, message.message_id)


@bot.message_handler(commands=['menu'], chat_types=["private"])
def menu(message):
    bot.delete_message(chat_id=message.chat.id, message_id=message.message_id)
    show_last_menu(message)


@bot.callback_query_handler(func=lambda call: call.data == "my_trips_menu")
def my_trips_menu_handler(call):
    user = get_user(call)
    text = texts[user.language]
    bot.answer_callback_query(call.id)
    markup = InlineKeyboardMarkup()
    markup.row(
        InlineKeyboardButton(text=text.text.back, callback_data="show_last_menu"),
        InlineKeyboardButton(text=text.text.t_13, callback_data="my_trips:driver"),
        InlineKeyboardButton(text=text.text.t_14, callback_data="my_trips:passenger"))
    bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id,
                          text=text.text.pick_trip_type, reply_markup=markup)


def notify_all_if_trip_is_cancel(trip_id):
    for i in TakeASeat.select().where(TakeASeat.driver_trip_id == int(trip_id)):
        bot.send_message(i.passenger_trip.user.telegram_id,
                         text=texts[i.passenger_trip.user.language].text.cancel_trip_notification.format(
                             trip_date=f"{i.driver_trip.start_date} {i.driver_trip.start_time}"))
        i.delete_instance()


@bot.callback_query_handler(func=lambda call: call.data.startswith("trip_del:"))
def trip_del_handler(call):
    _, trip_id = call.data.split(":", 1)
    trip = Trips.get_by_id(trip_id)
    user = trip.user
    text = texts[user.language]
    notify_all_if_trip_is_cancel(trip_id)
    trip.status = -1
    trip.save()
    bot.answer_callback_query(call.id, text=text.text.success_delete, show_alert=True)
    my_trips_menu_handler(call)


@bot.callback_query_handler(func=lambda call: call.data.startswith("cancel_trip:"))
def cancel_trip_handler(call):
    _, trip_id = call.data.split(":", 1)
    trip = Trips.get_by_id(trip_id)
    user = trip.user
    text = texts[user.language]
    bot.answer_callback_query(call.id)
    markup = InlineKeyboardMarkup()
    markup.row(InlineKeyboardButton(text=text.text.no, callback_data=f'trip_dt:{trip.id}'),
               InlineKeyboardButton(text=text.text.yes, callback_data=f'trip_del:{trip.id}'))
    bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id,
                          text=text.text.delete_trip_question, reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data.startswith("change_st:"))
def change_start_time_handler(call):
    _, trip_id = call.data.split(":", 1)
    trip = Trips.get_by_id(trip_id)
    user = trip.user
    text = texts[user.language]
    bot.answer_callback_query(call.id)
    edit_timepicker.send(call, hour=trip.start_time.hour, minute=trip.start_time.minute, trip_id=trip_id, language=text)


@bot.callback_query_handler(func=lambda call: call.data.startswith("set_pname:"))
def save_trip_handler(call):
    _, trip_id, name = call.data.split(":", 2)
    trip = Trips.get_by_id(trip_id)
    user = trip.user
    text = texts[user.language]
    preset, _ = Presets.get_or_create(user=user, name=name)
    preset.trips = trip
    preset.save()
    bot.answer_callback_query(call.id, text=text.text.success_saved)
    trips_details_handler(call)


@bot.callback_query_handler(func=lambda call: call.data.startswith("save_trip:"))
def save_trip_handler(call):
    _, trip_id = call.data.split(":", 1)
    trip = Trips.get_by_id(trip_id)
    user = trip.user
    text = texts[user.language]
    bot.answer_callback_query(call.id)
    markup = InlineKeyboardMarkup()
    markup.row(*[InlineKeyboardButton(text=v, callback_data=f"set_pname:{trip.id}:{k}") for k, v in
                 text.preset_names.__dict__.items()])
    markup.row(InlineKeyboardButton(text=text.text.back, callback_data=f"trip_dt:{trip.id}"))
    bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text=text.text.t_44,
                          reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data.startswith("change_sd:"))
def change_start_date_handler(call):
    _, trip_id = call.data.split(":", 1)
    trip = Trips.get_by_id(trip_id)
    user = trip.user
    text = texts[user.language]
    bot.answer_callback_query(call.id)
    now = datetime.now()
    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=text.text.t_27,
        reply_markup=datepicker.create_calendar(
            name=change_calendar_callback.prefix,
            year=now.year,
            month=now.month,
            language=text,
            trip_id=trip.id,
            preset_id="0"
        ),
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith("take_a_seat:"))
def take_a_seat_details_handler(call):
    _, trip_id, from_trip_id = call.data.split(":", 2)
    trip = Trips.get_by_id(trip_id)
    user = get_user(call)
    text = texts[user.language]
    actual_trips = list(TakeASeat.select().where(TakeASeat.driver_trip == trip))
    if len(actual_trips) >= trip.place_count:
        bot.answer_callback_query(call.id, text.text.places_count_error, show_alert=True)
    else:
        TakeASeat.create(passenger_trip_id=from_trip_id, driver_trip=trip)
        bot.answer_callback_query(call.id, text.text.places_count_success)
    call.data = f"trip_dt:{from_trip_id}"
    return trips_details_handler(call)


@bot.callback_query_handler(func=lambda call: call.data.startswith("ras:"))
def remove_a_seat_details_handler(call):
    _, marker, from_trip_id = call.data.split(":", 2)
    user = get_user(call)
    text = texts[user.language]
    TakeASeat.delete().where(TakeASeat.id == marker).execute()
    bot.answer_callback_query(call.id, text=text.text.remove_a_seat_success)
    call.data = f"trip_dt:{marker}"
    call.data = f"trip_dt:{from_trip_id}"
    return trips_details_handler(call)


@bot.callback_query_handler(func=lambda call: call.data.startswith("pt:"))
def pick_trips_details_handler(call):
    _, trip_id, from_trip_id, marker = call.data.split(":", 3)
    trip = Trips.get_by_id(trip_id)
    user = get_user(call)
    text = texts[user.language]
    bot.answer_callback_query(call.id)
    markup = InlineKeyboardMarkup()
    if marker:
        second_btn = InlineKeyboardButton(text=text.text.remove_a_seat, callback_data=f"ras:{marker}:{from_trip_id}")
    else:
        second_btn = InlineKeyboardButton(text=text.text.take_a_seat,
                                          callback_data=f"take_a_seat:{trip_id}:{from_trip_id}")
    markup.row(InlineKeyboardButton(text=text.text.back, callback_data=f"trip_dt:{from_trip_id}"), second_btn)
    bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id,
                          text=f"{text.text.start_date}: {trip.start_date}\n"
                               f"{text.text.start_time}: {trip.start_time}\n"
                               f"{text.text.address_from}: {trip.from_text}\n"
                               f"{text.text.address_to}: {trip.to_text}", reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data.startswith("trip_dt:"))
def trips_details_handler(call):
    _, trip_id = call.data.split(":", 1)
    trip = Trips.get_by_id(trip_id)
    user = trip.user
    text = texts[user.language]
    bot.answer_callback_query(call.id)
    markup = InlineKeyboardMarkup()
    no_driver_text = ""
    if trip.role == "driver":
        no_driver_text = (f"{text.text.places_count}: {trip.place_count}\n"
                          f"{text.text.take_a_seat_count}: {TakeASeat.select().where(TakeASeat.driver_trip == trip).count()}\n")
        markup.row(InlineKeyboardButton(text=text.text.change_place_count, callback_data=f"edit_places:{trip.id}"))
    markup.row(InlineKeyboardButton(text=text.text.change_start_date, callback_data=f"change_sd:{trip.id}"))
    markup.row(InlineKeyboardButton(text=text.text.change_start_time, callback_data=f"change_st:{trip.id}"))
    if trip.role == "passenger":
        if pt := TakeASeat.get_or_none(passenger_trip=trip):
            markup.row(InlineKeyboardButton(text=text.text.my_seat,
                                            callback_data=f"pt:{pt.driver_trip_id}:{pt.passenger_trip_id}:{pt.id}"))
        else:
            markup.row(InlineKeyboardButton(text=text.text.search, callback_data=f"update:{trip.id}"))
    markup.row(InlineKeyboardButton(text=text.text.back, callback_data=f"my_trips:{trip.role}"),
               InlineKeyboardButton(text=text.text.save_trip, callback_data=f"save_trip:{trip.id}"),
               InlineKeyboardButton(text=text.text.cancel_trip, callback_data=f"cancel_trip:{trip.id}"))
    bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id,
                          text=f"{text.text.start_date}: {trip.start_date}\n"
                               f"{text.text.start_time}: {trip.start_time}\n"
                               f"{no_driver_text}"
                               f"{text.text.address_from}: {trip.from_text}\n"
                               f"{text.text.address_to}: {trip.to_text}", reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data.startswith("my_trips:"))
def my_trips_handler(call):
    _, role = call.data.split(":", 1)
    user = get_user(call)
    text = texts[user.language]
    bot.answer_callback_query(call.id)
    markup = InlineKeyboardMarkup()
    query = Trips.select().where(
        fn.TIMESTAMP(fn.CONCAT(Trips.start_date, ' ', Trips.start_time)) >= datetime.now(), Trips.status == 1,
        Trips.user == user, Trips.role == role)
    data = list(query)
    for trips in chunks(data, 4):
        markup.row(*[
            InlineKeyboardButton(text=f"{trip.start_date} {trip.start_time}", callback_data=f"trip_dt:{trip.id}")
            for trip in trips])
    markup.row(InlineKeyboardButton(text=text.text.back, callback_data="my_trips_menu"))
    bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id,
                          text=text.text.you_trips if data else text.text.trips_not_found, reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data.startswith("saved:"))
def load_saved_trip_handler(call):
    _, preset_id = call.data.split(":", 1)
    preset = Presets.get_by_id(preset_id)
    trip = preset.trips.duplicate()
    user = trip.user
    text = texts[user.language]
    bot.answer_callback_query(call.id)
    now = datetime.now()
    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=text.text.t_27,
        reply_markup=datepicker.create_calendar(
            name=calendar_callback.prefix,
            year=now.year,
            month=now.month,
            language=text,
            trip_id=trip.id,
            preset_id=preset_id
        ),
    )


@bot.callback_query_handler(func=lambda call: call.data == "load_from_preset")
def load_from_preset_handler(call):
    user = get_user(call)
    text = texts[user.language]
    markup = InlineKeyboardMarkup()
    if presets := Presets.select().where(Presets.user == user):
        markup.add(
            *[InlineKeyboardButton(text=getattr(text.preset_names, preset.name),
                                   callback_data=f'saved:{preset.id}') for preset in presets])
        markup.row(InlineKeyboardButton(text=text.text.back, callback_data=f'to_start:!'))
        msg_text = text.text.t_50
    else:
        markup.row(InlineKeyboardButton(text=text.text.back, callback_data=f'to_start:!'))
        msg_text = text.text.t_51
    bot.delete_message(call.message.chat.id, call.message.message_id)
    bot.send_message(call.message.chat.id, msg_text, reply_markup=markup)
    bot.answer_callback_query(call.id)


@bot.callback_query_handler(func=lambda call: bool(call.data) and call.data.startswith("pick_lang:"))
def pick_language_callback(call: CallbackQuery):
    _, language_code, from_start = call.data.split(":", 2)
    user = get_user(call)
    user.language = language_code
    if user.dirty_fields:
        user.save()
    bot.answer_callback_query(call.id,
                              texts[user.language].text.success_change_language.format(texts[user.language].NAME))
    bot.delete_message(call.message.chat.id, call.message.id)


@bot.callback_query_handler(func=lambda call: call.data.startswith("to_start:"))
def back_to_start(call):
    _, trip_id = call.data.split(":", 1)
    if trip_id != "!":
        Trips.delete().where(Trips.id == trip_id, Trips.status == 0).execute()
    start_function(call.message, user=get_user(call))
    bot.answer_callback_query(call.id)


@bot.callback_query_handler(func=lambda call: call.data.startswith('p_role:'))
def passenger_role_handler(call):
    _, role, trip_id = call.data.split(":", 2)
    trip = Trips.get_by_id(trip_id)
    user = trip.user
    text = texts[user.language]
    trip.passenger_role = role
    trip.save()
    markup = InlineKeyboardMarkup()
    markup.row(InlineKeyboardButton(text=text.text.back, callback_data=f'passenger:{trip.id}'))
    bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text=text.text.t_21,
                          reply_markup=markup)
    bot.clear_step_handler(call.message)
    bot.register_next_step_handler(call.message, handle_location, call=call, user=user, trip=trip)


@bot.callback_query_handler(func=lambda call: call.data == "new_drive")
def new_trip_handler(call):
    start_function(call.message, user=get_user(call))


@bot.callback_query_handler(
    func=lambda call: call.data.startswith("driver:") or call.data.startswith("passenger:") or call.data.startswith(
        "edit_places:"))
def start_function_handler(call):
    role, trip_id = call.data.split(":", 1)
    if trip_id:
        bot.clear_step_handler(call.message)
        trip = Trips.get_by_id(trip_id)
        user = trip.user
        trip.place_count = None
        trip.save()
    else:
        user = get_user(call)
        trip = Trips.create(user=user, role=role)
    text = texts[user.language]
    bot.answer_callback_query(call.id)
    markup = InlineKeyboardMarkup()
    match role:
        case "driver":
            markup.add(
                *[InlineKeyboardButton(text=str(i), callback_data=f'place:{i}:{trip.id}') for i in
                  PLACES])
            msg_text = text.text.t_24
        case "passenger":
            markup.add(*[InlineKeyboardButton(text=v, callback_data=f'p_role:{k}:{trip.id}') for k, v in
                         text.role_list.__dict__.items()])
            msg_text = text.text.t_59
        case "edit_places":
            markup.add(
                *[InlineKeyboardButton(text=str(i), callback_data=f'edit_place:{i}:{trip.id}') for i in
                  PLACES])
            msg_text = text.text.t_24
        case _:
            markup.add(InlineKeyboardButton(text=text.text.restart, callback_data='to_start:!'))
            msg_text = text.text.error
    if role == "edit_places":
        markup.row(InlineKeyboardButton(text=text.text.back, callback_data=f"trip_dt:{trip.id}"))
        bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text=msg_text,
                              reply_markup=markup)
    else:
        markup.row(InlineKeyboardButton(text=text.text.back, callback_data=f'to_start:{trip.id}'))
        bot.delete_message(call.message.chat.id, call.message.id)
        bot.send_message(call.message.chat.id, msg_text, reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data.startswith("place:") or call.data.startswith("edit_place:"))
def space_handler(call):
    command, places, trip_id = call.data.split(":", 2)
    trip = Trips.get_by_id(trip_id)
    user = trip.user
    text = texts[user.language]
    if places == "!":
        trip.from_location_latitude = None
        trip.from_location_longitude = None
        trip.save()
    else:
        take_count = TakeASeat.select().where(TakeASeat.passenger_trip == trip).count()
        if int(places) < take_count:
            bot.answer_callback_query(call.id, text=text.text.places_count_edit_error.format(
                new_count=places, take_count=take_count))
        else:
            trip.place_count = places
    trip.save()
    bot.answer_callback_query(call.id)
    match command:
        case "place":
            markup = InlineKeyboardMarkup()
            markup.row(InlineKeyboardButton(text=text.text.back, callback_data=f'driver:{trip.id}'))
            bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text=text.text.t_21,
                                  reply_markup=markup)
            bot.clear_step_handler(call.message)
            bot.register_next_step_handler(call.message, handle_location, call=call, user=user, trip=trip)
        case "edit_place":
            call.data = f"{command}:{trip_id}"
            trips_details_handler(call)


def handle_location(message, call, user, trip, to=False):
    text = texts[user.language]
    markup = InlineKeyboardMarkup()
    if message.location:
        if to:
            trip.to_location_latitude = message.location.latitude
            trip.to_location_longitude = message.location.longitude
            trip.to_text = get_address(message.location.latitude, message.location.longitude, language=user.lang)
            trip.save()
            now = datetime.now()
            bot.delete_message(message.chat.id, message.message_id)
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text=text.text.t_27,
                reply_markup=datepicker.create_calendar(
                    name=calendar_callback.prefix,
                    year=now.year,
                    month=now.month,
                    language=text,
                    trip_id=trip.id,
                    preset_id="0"
                ),
            )
        else:
            trip.from_location_latitude = message.location.latitude
            trip.from_location_longitude = message.location.longitude
            trip.from_text = get_address(message.location.latitude, message.location.longitude, language=user.lang)
            trip.save()
            markup.row(InlineKeyboardButton(text=text.text.back, callback_data=f'place:!:{trip.id}'))
            call.message = bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id,
                                                 text=text.text.t_31, reply_markup=markup)
            bot.delete_message(message.chat.id, message.message_id)
            bot.clear_step_handler(call.message)
            bot.register_next_step_handler(call.message, handle_location, call=call, user=user, trip=trip, to=True)
    else:
        markup.row(InlineKeyboardButton(text=text.text.back, callback_data=f'driver:{trip.id}'))
        if text.text.not_location_error not in call.message.text:
            call.message = bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id,
                                                 text=f"{text.text.not_location_error}{text.text.t_21}",
                                                 reply_markup=markup)
        bot.clear_step_handler(call.message)
        if message.text.lstrip("/") in [i.command for i in bot.get_my_commands()]:
            bot.delete_message(call.message.chat.id, call.message.message_id)
            trip.delete_instance()
            get_handler_for_command(bot, message.text.lstrip("/"))(message)
        else:
            bot.delete_message(message.chat.id, message.message_id)
            bot.register_next_step_handler(call.message, handle_location, call=call, user=user, trip=trip)


@bot.callback_query_handler(func=lambda call: call.data.startswith(change_calendar_callback.prefix))
def change_calendar_callback_handler(call: telebot.types.CallbackQuery):
    name, action, year, month, day, trip_id, preset_id = call.data.split(change_calendar_callback.sep)
    trip = Trips.get_by_id(trip_id)
    user = trip.user
    text = texts[user.language]
    bot.answer_callback_query(call.id)
    date = datepicker.calendar_query_handler(bot=bot, call=call, name=name, action=action, year=year, month=month,
                                             day=day, language=text, trip_id=trip_id, preset_id=preset_id)
    call.data = f"change_sd:{trip.id}"
    match action:
        case "DAY":
            trip.start_date = date.date()
            trip.save()
            trips_details_handler(call)
        case "CANCEL":
            trips_details_handler(call)


@bot.callback_query_handler(func=lambda call: call.data.startswith(calendar_callback.prefix))
def calendar_callback_handler(call: telebot.types.CallbackQuery):
    name, action, year, month, day, trip_id, preset_id = call.data.split(calendar_callback.sep)
    trip = Trips.get_by_id(trip_id)
    user = trip.user
    text = texts[user.language]
    bot.answer_callback_query(call.id)
    date = datepicker.calendar_query_handler(bot=bot, call=call, name=name, action=action, year=year, month=month,
                                             day=day, language=text, trip_id=trip_id, preset_id=preset_id)
    match action:
        case "DAY":
            trip.start_date = date.date()
            trip.save()
            timepicker.send(call, hour=12, minute=30, trip_id=trip_id, language=text, preset_id=preset_id)
        case "CANCEL":
            if preset_id:
                trip.delete_instance()
                load_from_preset_handler(call)
            else:
                trip.to_location_latitude = None
                trip.to_location_longitude = None
                trip.save()
                markup = InlineKeyboardMarkup()
                markup.row(InlineKeyboardButton(text=text.text.back, callback_data=f'place:!:{trip.id}'))
                call.message = bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id,
                                                     text=text.text.t_31, reply_markup=markup)
                bot.clear_step_handler(call.message)
                bot.register_next_step_handler(call.message, handle_location, call=call, user=user, trip=trip, to=True)


if __name__ == '__main__':
    bot.enable_save_next_step_handlers(delay=2)
    bot.load_next_step_handlers()
    bot.infinity_polling()
