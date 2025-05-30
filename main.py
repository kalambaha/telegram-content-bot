from telebot import TeleBot, types
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
from collections import defaultdict
import os, json 

# ⚙️ Настройки
API_TOKEN = '7903681133:AAHfN_MR7CH-C4Kq71ToI483_kxZFA2wARQ'
SPREADSHEET_ID = '1AiREZQQEM9W8l5NyzN4xJI9d1bWX2TiKfupFBJgLXKg'
CREDENTIALS_FILE = 'credentials.json'

bot = TeleBot(API_TOKEN)

models = {
    'Arina': {'name': '👠 Arina', 'chat_id': '453570257'},
    'Alexa': {'name': '🎮 Alexa', 'chat_id': '7190220327'},
    'Juliana': {'name': '💎 Юлия', 'chat_id': '1122334455'},
    'Miranda': {'name': '🌙 Miranda', 'chat_id': '598161936'},
    'Runa': {'name': '🍒 Runa', 'chat_id': '472901770'},
    'Polina': {'name': '🌟 Polina', 'chat_id': '1103002863'},
    'Milana': {'name': '👠 Milana', 'chat_id': '764988155'}
}

verified_users = {'1247157530', '368414650'}  # 👈 сюда добавляешь chat_id всех, кто имеет доступ

user_states = {}
request_links = {}
request_counter = 0
media_cache = defaultdict(list)

# Google Sheets
scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
creds_json = os.environ['GOOGLE_APPLICATION_CREDENTIALS_JSON']
creds_dict = json.loads(creds_json)
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)

client = gspread.authorize(creds)
sheet = client.open_by_key(SPREADSHEET_ID).worksheet('Log')

@bot.message_handler(commands=['start'])
def start(message):
    if str(message.chat.id) not in verified_users:
        bot.send_message(message.chat.id, "❌ У тебя нет доступа к боту. Свяжись с админом.")
        return
    keyboard = types.InlineKeyboardMarkup()
    for key, model in models.items():
        keyboard.add(types.InlineKeyboardButton(text=model['name'], callback_data=f'select_{key}'))
    bot.send_message(message.chat.id, "Выбери модель, для которой хочешь отправить запрос:", reply_markup=keyboard)

@bot.message_handler(commands=['help'])
def help_command(message):
    bot.send_message(message.chat.id, "📈 Для чатеров: /start — выбор модели\n💬 Для моделей: /done — когда завершили ответ")

@bot.message_handler(commands=['done'])
def model_done(message):
    uid = str(message.chat.id)
    if user_states.get(uid, {}).get('step') == 'model_reply':
        bot.send_message(message.chat.id, "✅ Ответ завершён.")
        user_states[uid] = {}
    else:
        bot.send_message(message.chat.id, "Нет активного ответа.")

@bot.callback_query_handler(func=lambda call: call.data.startswith('select_'))
def select_model(call):
    model_key = call.data.split('_')[1]
    user_states[str(call.from_user.id)] = {'step': 'waiting_text', 'model_key': model_key}
    bot.send_message(call.from_user.id, f"✍️ Напиши свой запрос для {models[model_key]['name']}: ")

# Обработка текстов и медиа
@bot.message_handler(content_types=['text', 'photo', 'video', 'document', 'voice', 'audio'], func=lambda m: user_states.get(str(m.from_user.id), {}).get('step') == 'waiting_text')
def handle_request(message):
    global request_counter
    uid = str(message.from_user.id)
    username = message.from_user.username or '—'
    state = user_states[uid]
    request_counter += 1
    request_id = f"req{request_counter}"
    model_key = state['model_key']
    model_chat_id = str(models[model_key]['chat_id'])
    request_links[request_id] = {'model_id': model_chat_id, 'chater_id': uid}

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("Ответить", callback_data=f"reply_{request_id}"))

    content_desc = []
    if message.text:
        bot.send_message(int(model_chat_id), f"📩 Запрос:\n\n{message.text}\n\n🏡 ID: {request_id}", reply_markup=markup)
        content_desc.append("Текст")
    if message.photo:
        bot.send_photo(int(model_chat_id), message.photo[-1].file_id, caption=message.caption or '', reply_markup=markup)
        content_desc.append("Фото x1")
    if message.video:
        bot.send_video(int(model_chat_id), message.video.file_id, caption=message.caption or '', reply_markup=markup)
        content_desc.append("Видео x1")
    if message.document:
        bot.send_document(int(model_chat_id), message.document.file_id, caption=message.caption or '', reply_markup=markup)
        content_desc.append("Документ")
    if message.voice:
        bot.send_voice(int(model_chat_id), message.voice.file_id, reply_markup=markup)
        content_desc.append("Голосовое")
    if message.audio:
        bot.send_audio(int(model_chat_id), message.audio.file_id, caption=message.caption or '', reply_markup=markup)
        content_desc.append("Аудио")

    sheet.append_row([str(datetime.now()), uid, username, model_chat_id, 'Запрос', ' + '.join(content_desc)])
    bot.send_message(int(uid), "✅ Запрос отправлен!")
    user_states[uid] = {}

@bot.callback_query_handler(func=lambda call: call.data.startswith('reply_'))
def reply_request(call):
    req_id = call.data.split('_')[1]
    model_id = str(call.from_user.id)
    req = request_links.get(req_id)
    if req and req['model_id'] == model_id:
        user_states[model_id] = {'step': 'model_reply', 'req_id': req_id}
        bot.send_message(call.from_user.id, "📲 Отправь свой ответ (медиа/текст), заверши командой /done")
    else:
        bot.send_message(call.from_user.id, "❌ Запрос не найден.")

@bot.message_handler(content_types=['text', 'photo', 'video', 'document', 'voice', 'audio'], func=lambda m: user_states.get(str(m.chat.id), {}).get('step') == 'model_reply')
def model_reply(message):
    uid = str(message.chat.id)
    username = message.from_user.username or '—'
    state = user_states.get(uid)
    req_id = state['req_id']
    chater_id = request_links.get(req_id, {}).get('chater_id')
    log_desc = []

    if message.text:
        bot.send_message(int(chater_id), f"📢 Ответ:\n\n{message.text}")
        log_desc.append("Текст")
    if message.photo:
        bot.send_photo(int(chater_id), message.photo[-1].file_id, caption=message.caption or '')
        log_desc.append("Фото x1")
    if message.video:
        bot.send_video(int(chater_id), message.video.file_id, caption=message.caption or '')
        log_desc.append("Видео x1")
    if message.document:
        bot.send_document(int(chater_id), message.document.file_id, caption=message.caption or '')
        log_desc.append("Документ")
    if message.voice:
        bot.send_voice(int(chater_id), message.voice.file_id)
        log_desc.append("Голосовое")
    if message.audio:
        bot.send_audio(int(chater_id), message.audio.file_id, caption=message.caption or '')
        log_desc.append("Аудио")

    sheet.append_row([str(datetime.now()), uid, username, chater_id, 'Ответ', ' + '.join(log_desc)])

bot.set_my_commands([
    types.BotCommand('start', 'Начать'),
    types.BotCommand('help', 'Помощь'),
    types.BotCommand('done', 'Завершить ответ')
])

bot.polling()
