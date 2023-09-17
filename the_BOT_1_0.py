#(c) Ivan Babariko, Minsk 2023

import enum
import telebot
from telebot import types
import sqlite3 as sq

old_costament_books = ["Быт", "Исх", "Лев", "Чис", "Втор", "Нав", "Суд", "Руфь",\
               "1Цар", "2Цар", "3Цар", "4Цар", "1Пар", "2Пар", "Ездр", "Неем", "Есф", "Иов",\
              "Пс", "Прит", "Еккл", "Песн", "Ис", "Иер", "Плач", "Иез", "Дан", "Ос", "Иоил",\
             "Ам", "Авд", "Ион", "Мих", "Наум", "Авв", "Соф", "Агг", "Зах", "Мал"]

new_costament_books = ["Мат", "Мар", "Лук", "Ин", "Деян", "Иак", "1Пет", "2Пет",\
               "1Ин", "2Ин", "3Ин", "Иуд", "Рим", "1Кор", "2Кор", "Гал", "Еф", "Флп", "Кол",\
              "1Фес", "2Фес", "1Тим", "2Тим", "Тит", "Флм", "Евр", "Откр",]

class DialogStatus(enum.IntEnum):
    begin = 0
    costament = 1
    book = 2
    chapter = 3
    verse = 4
    completed = 5

class Comand(enum.IntEnum):
    ask_costament = 0
    ask_book_old = 1
    ask_book_new = 2
    ask_chapter = 3
    reask_chapter = 4
    ask_verse = 5
    reask_verse = 6
    give_answer = 7
    so_bad = 8

class TGDispatcher:
    def __init__(self, bot_, db):
        self.bot = bot_
        self.dbm = db
        self.chats = []
        self.cur_id = 0
        self.cur_dialog = 0

    def find_cur_dialog(self, id_):
        for dialog in self.chats:
            if dialog.id_ == id_:
                return dialog
        return None

    def handle_message(self, id_, data):
        self.cur_dialog = self.find_cur_dialog(id_)
        self.cur_id = id_
        #если не нашли такого диалога, создаём новый
        if self.cur_dialog is None:
            self.chats.append(Dialog(id_))
            self.cur_dialog = self.chats[-1]
        #обработка сообщения происходит следующим образом
        #1. Устанавливаем, нужно ли начинать заново сеанс
        if data == "/restart":
            self.chats.remove(self.cur_dialog)
            self.bot.send_message(self.cur_id, "диалог очищен")
            return
        #2 Объект cur_dialog общается через нас с пользователем
        to_do = self.cur_dialog.handle_and_answer(data)
        if to_do == Comand.ask_costament:
            keyboard = types.InlineKeyboardMarkup()
            key_old = types.InlineKeyboardButton("ветхий", callback_data = "old")
            key_new = types.InlineKeyboardButton("новый", callback_data = "new")
            keyboard.add(key_old, key_new)
            self.bot.send_message(self.cur_id, "это место из...", reply_markup = keyboard)
        elif to_do == Comand.ask_book_old:
            super_list = [[],]
            book_num = 1
            for book in old_costament_books:
                if book_num % 6 == 0:
                    super_list.append([])
                (super_list[-1]).append(types.InlineKeyboardButton(book, callback_data=book_num))
                book_num += 1
            keyboard2 = types.InlineKeyboardMarkup(super_list)
            self.bot.send_message(self.cur_id, "выберите книгу", reply_markup = keyboard2)
        elif to_do == Comand.ask_book_new:
            super_list = [[],]
            book_num = 40
            for book in new_costament_books:
                if (book_num - 4) % 6 == 0:
                    super_list.append([])
                (super_list[-1]).append(types.InlineKeyboardButton(book, callback_data=book_num))
                book_num += 1
            keyboard2 = types.InlineKeyboardMarkup(super_list)
            self.bot.send_message(self.cur_id, "выберите книгу", reply_markup = keyboard2)
        elif to_do == Comand.ask_chapter:
            self.bot.send_message(self.cur_id, "номер главы>")
        elif to_do == Comand.reask_chapter:
            self.bot.send_message(self.cur_id, "Это дожно быть просто число. Ещё раз: номер главы>")
        elif to_do == Comand.ask_verse:
            self.bot.send_message(self.cur_id, "номер стиха или *  - поиск по всей главе>")
        elif to_do == Comand.reask_verse:
            self.bot.send_message(self.cur_id, "Так. Ещё раз: номер стиха или *  - поиск по всей главе>")
        elif to_do == Comand.give_answer:
            req = self.cur_dialog.give_bible_link()
            #здесь должен быть запрос к базе данных
            #пока заглушка
            rez = ["URL1", "URL2"]
            if len(rez) == 0:
                self.bot.send_message(self.cur_id, "По Вашему запросу " + self.cur_dialog.give_link_string() + " ничего не найдено")
            else:
                self.bot.send_message(self.cur_id, "По Вашему запросу " + self.cur_dialog.give_link_string() + " найдено: ")
                n = 0
                for link in rez:
                    self.bot.send_message(self.cur_id, link)
                    n += 1
                    # я не знаю, может ли бот слать слишком много сообщений, плюс защита от дурака
                    if n > 10:
                        break
                self.chats.remove(self.cur_dialog)
        elif to_do == Comand.so_bad:
            self.bot.send_message(self.cur_id, "Что-то пошло не так. Начнём сначала")
            self.chats.remove(self.cur_dialog)

class DBMenager:
    def __init__(self, filname):
        self.conn = sq.connect(filname)
        self.cursor = self.conn.cursor()

    def __del__(self):
        self.conn.close()

    def execute_promt(self, link):
        promt = r"SELECT archive_links.URL FROM archive_links JOIN Bible_links ON\
       archive_links.sermon_id = Bible_links.sermon_id WHERE Bible_links.book_id ="
        #Если кортеж promt содержит 2 элемента, то мы интерпретируем их как книга + глава
        #если 3, то как книга + глава + стих
        try:
            promt += (str(promt[0]) + "AND Bible_links.chapter = " + str(promt[1]))
            if 3 == len(link):
                my_verse = str(promt[2])
                promt += ("AND Bible_links.verse_from <= " + my_verse + "AND Bible_links.verse_to >= " + my_verse)
            self.cursor.execute(promt)
            return self.cursor.fetchall()
        except:
            return []
            
class Dialog:
    def __init__(self, id_):
        self.id_ = id_
        self.status = DialogStatus(DialogStatus.begin)
        self.costament = ""
        self.book_num = 0
        self.chapter_num = 0
        self.verse_num = 0
        self.is_all_chapter = False

        #мы знаем, что делать с прилетевшей строкой
    def handle_and_answer(self, s):
        if self.status == DialogStatus.costament:
            if s == "old":
                result = Comand.ask_book_old
            else:
                result =  Comand.ask_book_new
            self.status = DialogStatus.book
            return result
        elif self.status == DialogStatus.begin:
            self.status = DialogStatus.costament
            return Comand.ask_costament
        elif self.status == DialogStatus.book:
            self.book_num = int(s)
            self.status = DialogStatus.chapter
            return Comand.ask_chapter
        elif self.status == DialogStatus.chapter:
            if s.isnumeric():
                self.chapter_num = int(s)
                self.status = DialogStatus.verse
                return Comand.ask_verse
            else:
                return Comand.reask_chapter
        elif self.status == DialogStatus.verse:
            if "*" in s:
                self.is_all_chapter = True
                self.status = DialogStatus.completed
                return Comand.give_answer
            elif s.isnumeric():
                self.verse_num = int(s)
                self.status = DialogStatus.completed
                return Comand.give_answer
            else:
                return Comand.reask_verse
        else:
            return Comand.so_bad

    def give_bible_link(self):
        if not self.status == DialogStatus.completed:
            return None
        else:
            if self.is_all_chapter:
                return (self.book_num, self.chapter_num)
            else:
                return (self.book_num, self.chapter_num, self.verse_num)

    def give_link_string(self):
        if not self.status == DialogStatus.completed:
            return None
        result = ""
        if self.book_num < 40:
            result += old_costament_books[self.book_num - 1]
        else:
            result += new_costament_books[self.book_num - 40]
        result += (" " + str(self.chapter_num))
        if self.is_all_chapter:
            return result
        else:
            result += (":" + str(self.verse_num))
            return result
        
print("Здарова!")
bot = telebot.TeleBot("5020970091:AAHWA11yynQC4wfP8c6447q4JMgnU2ZfnkQ")
db = 1 #DBMenager(r"E:\всё для проекта Фарисей\sermons_data.db")
dispatcher = TGDispatcher(bot, db)

@bot.message_handler(content_types=['text'])
def m(message):
    global dispatcher, bot
    id_ = message.from_user.id
    mes_id = message.id
    data = message.text
    bot.delete_message(id_, mes_id)
    dispatcher.handle_message(id_, data)

@bot.callback_query_handler(func=lambda call: True)
def t(call):
    id_ = call.message.chat.id
    inf = call.data
    m_id = call.message.id
    bot.delete_message(id_, m_id)
    dispatcher.handle_message(id_, inf)
    
bot.polling(none_stop = True, interval = 1)




