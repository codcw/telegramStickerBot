import logging, io, pickle, pathlib, requests, json, emoji
import os.path
import flask
import telegram.constants
import threading
from urllib.request import urlopen
from flask import Flask, request
from flask_cors import CORS
from telegram import    Update,\
                        InlineKeyboardButton,\
                        InlineKeyboardMarkup,\
                        ReplyKeyboardMarkup,\
                        ReplyKeyboardRemove,\
                        MessageEntity
from telegram.ext import    filters,\
                            MessageHandler,\
                            ApplicationBuilder,\
                            CommandHandler,\
                            ContextTypes,\
                            ConversationHandler,\
                            CallbackQueryHandler,\
                            TypeHandler
from telegram.ext.filters import MessageFilter
from PIL import Image
import sys

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

if pathlib.Path('stickerpacks').exists():
    with open('stickerpacks', 'rb') as packs:
        stickerpacks = pickle.load(packs)
else:
    with open('stickerpacks', 'wb') as packs:
        stickerpacks = dict()
        pickle.dump(stickerpacks, packs)

if pathlib.Path('IDs').exists():
    with open('IDs', 'rb') as file:
        IDs = pickle.load(file)
else:
    IDs = False

ACTIONS = {"thumbnail" : "Change thumbnail",
           "delete sticker" : "Delete sticker",
           "add sticker" : "Add sticker",
           "title" : "Change title",
           "emoji": "Change sticker emoji list"}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global IDs
    if IDs == False:
        with open('IDs', 'wb') as file:
            IDs = { "user_id": update.effective_user.id,
                    "chat_id": update.effective_chat.id}
            pickle.dump(IDs, file)
    if stickerpacks:
        keyboard = [    [InlineKeyboardButton(f"{packname}", callback_data = packname)]
                        for packname in stickerpacks.keys()]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("Please choose:", reply_markup = reply_markup)
        return 'get_pack'
    else:
        await update.message.reply_text("No stickerpacks have been created yet! Use /newpack instead")
        return ConversationHandler.END

def build_keyboard(actions, columns = 2, row_character_limit = 35):
    row_length = 0
    keyboard = [[]]
    for action in actions:
        keyboard[-1].append(action)
        row_length += 1
        if row_length >= columns:
            row_length = 0
            keyboard.append([])
    return keyboard

async def get_pack(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    stickerpack_data = query.data
    if stickerpack_data:
        reply_keyboard = build_keyboard(ACTIONS.values())
        markup = ReplyKeyboardMarkup(keyboard = reply_keyboard,
                                     one_time_keyboard = True,
                                     input_field_placeholder = "I live in your walls",
                                     resize_keyboard = True)
        await context.bot.send_message( chat_id = update.effective_chat.id,
                                        text = f"You chose {stickerpack_data}, now pick an action",
                                        reply_markup = markup)
        context.user_data["current_pack_title"] = stickerpack_data
        context.user_data["current_pack_name"] = stickerpacks[stickerpack_data]
        return 'processing'
    else:
        await update.message.reply_text("No stickerpack data!")
        return ConversationHandler.END

async def newsticker(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Send new sticker as an attachment/7tv link/direct link",
                                    reply_markup = ReplyKeyboardRemove())
    return 'new_sticker_methods'

async def add_sticker(image: bytes, update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    #process the image and add to sticker set
    image = Image.open(image)
    image = image.crop(image.getbbox())  # trim transparent pixels
    width, height = image.size
    if width > height:
        ratio = height / width
        width = 512
        height = int(512 * ratio)
    elif width < height:
        ratio = width / height
        height = 512
        width = int(512 * ratio)
    else:
        width = height = 512
    image = image.resize((width, height))
    image_io = io.BytesIO()
    image.save(image_io, "PNG")
    input_sticker = telegram.InputSticker(sticker=image_io.getvalue(),
                                          emoji_list=["😢", "😥"])
    successful = True
    user_id = update.effective_user.id
    current_pack_name = context.user_data["current_pack_name"] #pack name
    insertion = await context.bot.add_sticker_to_set(user_id=user_id,
                                                     name=current_pack_name,
                                                     sticker=input_sticker)
    if insertion is successful:
        current_stickerset = await context.bot.get_sticker_set(current_pack_name)
        sticker_id = current_stickerset.stickers[-1].file_id
        # context.user_data['sticker_id'] = sticker_id
        await context.bot.send_sticker(chat_id=update.effective_chat.id,
                                       sticker=sticker_id)
        return True
    else:
        return False

async def new_sticker_from_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    link = update.message.text
    image = requests.get(link).content
    image = io.BytesIO(image)
    successful = await add_sticker(image = image, update = update, context = context)
    if successful:
        await update.message.reply_text("Added, send new emoji for sticker, 1-20")
    else:
        await update.message.reply_text("error")
    return 'change_emoji'

async def new_sticker_from_7tv(update: Update, context: ContextTypes.DEFAULT_TYPE):
    link = update.message.text
    source_id = link[link.rfind('/'):]  # get source id of emote from link
    response = requests.get(f"https://7tv.io/v3/emotes/{source_id}")  # get request from api
    emote_info = json.loads(response.content.decode('utf-8'))  # load json from request
    if emote_info["animated"]:
        await update.message.reply_text("image non-static")
        return ConversationHandler.END
    image_url = f"https://cdn.7tv.app/emote/{source_id}/4x.png"
    image = requests.get(image_url).content
    image = io.BytesIO(image)
    successful = await add_sticker(image = image, update = update, context = context)
    if successful:
        await update.message.reply_text("Added, send new emoji for sticker, 1-20")
    else:
        await update.message.reply_text("error")
    return 'change_emoji'

async def sticker_for_emoji(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Send a sticker that you wanna set associated emoji list for",
                                    reply_markup = ReplyKeyboardRemove())
    return 'emoji_for_sticker'

async def emoji_for_sticker(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['sticker_id'] = update.message.sticker.file_id
    await update.message.reply_text("Send new emoji for sticker, 1-20")
    return 'change_emoji'

async def change_emoji(update: Update, context: ContextTypes.DEFAULT_TYPE):
    emojis = emoji.distinct_emoji_list(update.message.text)
    await context.bot.set_sticker_emoji_list(sticker = context.user_data['sticker_id'],
                                       emoji_list = emojis)
    await update.message.reply_text("epic")
    return ConversationHandler.END

async def new_sticker_attachment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    photo_id = update.message.document.file_id
    image_data = await context.bot.get_file(photo_id)
    image = io.BytesIO()
    await image_data.download_to_memory(image)
    successful = await add_sticker(image = image, update = update, context = context)
    if successful:
        await update.message.reply_text("Added, send new emoji for sticker, 1-20")

    else:
        await update.message.reply_text("error")
    return 'change_emoji'

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("bye",
                                    reply_markup = ReplyKeyboardRemove())
    return ConversationHandler.END

async def unknown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message( chat_id=update.effective_chat.id,
                                    text="Sorry, I didn't understand that command.",
                                    reply_markup = ReplyKeyboardRemove())

async def newpack(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    bot_name = context.bot.username
    pack_title = context.args[0]
    pack_name = f'{pack_title}_by_{bot_name}'
    sticker_format = telegram.constants.StickerFormat.STATIC
    default_sticker = open("saj512.png", "rb")
    default_input_sticker = telegram.InputSticker(sticker = default_sticker,
                                                  emoji_list = ["😢", "😥"])
    successful = True
    creation = await context.bot.create_new_sticker_set(user_id = user_id,
                                                        name = pack_name,
                                                        title = pack_title,
                                                        stickers = [default_input_sticker],
                                                        sticker_format = sticker_format)
    if creation is successful:
        with open('stickerpacks', 'wb') as packs:
            stickerpacks[pack_title] = pack_name
            pickle.dump(stickerpacks, packs)
        await update.message.reply_text(f"Pack {pack_title} created")
    else:
        await update.message.reply_text("Error")

async def new_pack_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Send new sticker pack title",
                                    reply_markup = ReplyKeyboardRemove())
    return 'set_new_pack_title'

async def delete_sticker(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Send a sticker that you want to delete",
                                    reply_markup = ReplyKeyboardRemove())
    return 'pick_delete_sticker'

async def pick_delete_sticker(update: Update, context: ContextTypes.DEFAULT_TYPE):
    sticker_id = update.message.sticker.file_id
    deletion = await context.bot.delete_sticker_from_set(sticker_id)
    successful = True
    if deletion is successful:
        await update.message.reply_text("Deleted")
    else:
        await update.message.reply_text("Error")
    return ConversationHandler.END

async def set_new_pack_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    current_pack_name = context.user_data["current_pack_name"]
    new_title = update.message.text
    title_change = await context.bot.set_sticker_set_title( name = current_pack_name,
                                                            title = new_title)
    successful = True
    if title_change is successful:
        await update.message.reply_text("Sticker title changed")
        with open('stickerpacks', 'wb') as packs:
            old_title = context.user_data["current_pack_title"]
            del stickerpacks[old_title]
            stickerpacks[new_title] = current_pack_name
            pickle.dump(stickerpacks, packs)
    else:
        await update.message.reply_text("Error")
    return ConversationHandler.END

async def get_thumbnail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Send new thumbnail, make sure it has 1:1 aspect ratio",
                                    reply_markup = ReplyKeyboardRemove())
    return 'set_thumbnail'

async def set_thumbnail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    photo_id = update.message.document.file_id
    image_data = await context.bot.get_file(photo_id)
    image_ready = io.BytesIO()
    await image_data.download_to_memory(image_ready)
    image = Image.open(image_ready)
    width, height = image.size
    if width != height:
        await update.message.reply_text("Uneven ratio")
        return ConversationHandler.END
    else:
        width = height = 100
    image = image.resize((width, height))
    image_io = io.BytesIO()
    image.save(image_io, "PNG")
    successful = True
    user_id = update.effective_user.id
    current_pack_name = context.user_data["current_pack_name"]
    thumb_change = await context.bot.set_sticker_set_thumbnail( user_id = user_id,
                                                                name = current_pack_name,
                                                                thumbnail = image_io.getvalue())
    if thumb_change is successful:
        await update.message.reply_text("Thumbnail changed")
        print(image.size, image.info)
    else:
        await update.message.reply_text("Error")
    return ConversationHandler.END

# FLASK SECTION

app = Flask(__name__)
CORS(app)
app.secret_key = "supa secret"

class Chat:
    def __init__(self, chat_id):
        self.id = chat_id

class User:
    def __init__(self, user_id):
        self.id = user_id

class FlaskUpdate:
    def __init__(self, chat_id, user_id, packname, packtitle, pic):
        self.effective_chat = Chat(chat_id)
        self.effective_user = User(user_id)
        self.packname = packname
        self.packtitle = packtitle
        self.pic = pic

@app.route('/')
def index():
    defaultpage = "<p>Hello</p>"
    return defaultpage

@app.route('/getPacks', methods=["GET"])
def getPacks():
    return stickerpacks

@app.route('/updateFromExtension', methods=["POST"])
async def updateFromExtension():
    request_data = request.get_json()
    packtitle = request_data["packname"]
    packname = request_data["packtitle"] #fix title and name discrepancy
    pic = request_data["pic"]
    print(packname, packtitle, pic)
    ExtensionUpdate = FlaskUpdate(chat_id = IDs["chat_id"],
                                  user_id = IDs["user_id"],
                                  packtitle = packtitle,
                                  packname = packname,
                                  pic = pic)
    await application.update_queue.put(ExtensionUpdate)
    return "True"

async def addFromExtension(update, context: ContextTypes.DEFAULT_TYPE):
    print(context.bot)
    context.user_data["current_pack_title"] = update.packtitle
    context.user_data["current_pack_name"] = update.packname
    # with urlopen(data_uri) as response:
    #     data = response.read()
    pass

if __name__ == '__main__':

    with open("token.txt", "r") as file:
        mytoken = file.read()
    application = ApplicationBuilder().token(mytoken).build()
    # HANDLERS
        # /newpack
    newpack_handler = CommandHandler('newpack', newpack)

    # CONVERSATION HANDLERS
        # choosing pack
    start_handler = CommandHandler('start', start)
        # get_pack
    get_pack_handler = CallbackQueryHandler(get_pack)
        # new sticker
    sticker_attachment_handler = MessageHandler(filters.ATTACHMENT, new_sticker_attachment)
    newsticker_handler = MessageHandler(filters.Text([ACTIONS["add sticker"]]), newsticker)
    new_sticker_from_7tv_handler = MessageHandler(filters.Regex('7tv.app/emotes') &
                                                  filters.Entity(MessageEntity.URL),
                                                  new_sticker_from_7tv)
    new_sticker_from_link_handler = MessageHandler( filters.TEXT &
                                                    filters.Entity(MessageEntity.URL),
                                                    new_sticker_from_link)
        # cancel
    cancel_handler = CommandHandler('cancel', cancel)
        # thumbnail
    thumbnail_handler = MessageHandler(filters.Text([ACTIONS["thumbnail"]]), get_thumbnail)
    set_thumbnail_handler = MessageHandler(filters.ATTACHMENT, set_thumbnail)
        # new name
    new_pack_title_handler = MessageHandler(filters.Text([ACTIONS["title"]]), new_pack_title)
    set_new_pack_title_handler = MessageHandler(filters.TEXT & ~filters.COMMAND, set_new_pack_title)
        # delete sticker
    delete_sticker_handler = MessageHandler(filters.Text([ACTIONS["delete sticker"]]), delete_sticker)
    pick_delete_sticker_handler = MessageHandler(filters.Sticker.ALL, pick_delete_sticker)
        # emoji
    change_emoji_handler = MessageHandler(filters.TEXT, change_emoji)
    emoji_sticker_handler = MessageHandler(filters.Sticker.ALL, emoji_for_sticker)
    sticker_emoji_handler = MessageHandler(filters.Text([ACTIONS["emoji"]]), sticker_for_emoji)
    #  conversation
    conv_handler = ConversationHandler(
        entry_points=[start_handler],
        states={
            'get_pack': [get_pack_handler],
            'processing': [newsticker_handler, thumbnail_handler, new_pack_title_handler, delete_sticker_handler, sticker_emoji_handler],
            'new_sticker_methods': [sticker_attachment_handler, new_sticker_from_7tv_handler, new_sticker_from_link_handler],
            'set_thumbnail': [set_thumbnail_handler],
            'set_new_pack_title': [set_new_pack_title_handler],
            'pick_delete_sticker': [pick_delete_sticker_handler],
            'change_emoji': [change_emoji_handler],
            'emoji_for_sticker': [emoji_sticker_handler],
        },
        fallbacks=[cancel_handler],
        name="my_conversation"
    )
    application.add_handler(conv_handler)
    application.add_handler(newpack_handler)

    # extension
    def flaskthread():
        app.run()
    t = threading.Thread(target=flaskthread)
    t.start()
    extension_handler = TypeHandler(FlaskUpdate, addFromExtension)
    application.add_handler(extension_handler)

    # Other handlers
    unknown_handler = MessageHandler(filters.COMMAND, unknown)
    application.add_handler(unknown_handler)



    application.run_polling()