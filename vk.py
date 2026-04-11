import vk_api
from vk_api.longpoll import VkLongPoll, VkEventType
from vk_api.keyboard import VkKeyboard, VkKeyboardColor
import json
from datetime import datetime
import threading
import time

# AI поиск
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

TOKEN = "vk1.a.8lJ7EnqzklLXvnG3YXG79oBfmDjafZ4tfqtYx35ysbv9xtNCqyTgGWX6HPmrObkcs_x2jLuV9s-T2zjyVCjW1w26sP7YdGRshJK-V-_Ti8AW24WnDQ2CYkr_GSuujFgNINcvJiNJy3Q9S7gqMkf86vqvSPz3EG_9H2SLeOjq8QqWP9EMtHQkAM7UnMFSPZvScPIWEvxDiwqoO9srjdtl0Q"
DATA_FILE = "data.json"


# ================== ДАННЫЕ ==================

def load_data():
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}


def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)


# ================== КНОПКИ ==================

def main_keyboard():
    kb = VkKeyboard(one_time=False)

    kb.add_button("📅 Дедлайны", VkKeyboardColor.PRIMARY)
    kb.add_button("📝 Заметки", VkKeyboardColor.SECONDARY)
    kb.add_line()
    kb.add_button("➕ Дедлайн", VkKeyboardColor.POSITIVE)
    kb.add_button("➕ Заметка", VkKeyboardColor.POSITIVE)
    kb.add_line()
    kb.add_button("🔍 Найти", VkKeyboardColor.PRIMARY)

    return kb.get_keyboard()


def delete_keyboard(items, prefix):
    kb = VkKeyboard(one_time=True, inline=True)

    for i in range(len(items)):
        kb.add_button(
            f"Удалить {i+1}",
            color=VkKeyboardColor.NEGATIVE,
            payload={"cmd": f"del_{prefix}", "index": i}
        )
        kb.add_line()

    return kb.get_keyboard()


# ================== ОТПРАВКА ==================

def send(vk, user_id, text, keyboard=None, attachment=None):
    vk.messages.send(
        user_id=user_id,
        message=text,
        random_id=0,
        keyboard=keyboard,
        attachment=attachment
    )


# ================== AI ПОИСК ==================

def search_notes(notes, query):
    texts = [n["text"] for n in notes]

    if not texts:
        return []

    vectorizer = TfidfVectorizer()
    tfidf = vectorizer.fit_transform(texts + [query])

    similarities = cosine_similarity(tfidf[-1], tfidf[:-1])[0]

    results = []
    for i, score in enumerate(similarities):
        if score > 0.1:
            results.append((score, notes[i]))

    results.sort(reverse=True, key=lambda x: x[0])

    return [r[1] for r in results]


# ================== НАПОМИНАНИЯ ==================

def reminder_loop(vk, data):
    while True:
        now = datetime.now()

        for user_id, user_data in data.items():
            for d in user_data["deadlines"]:
                dt = datetime.strptime(d["datetime"], "%d.%m.%Y %H:%M")

                if abs((dt - now).total_seconds()) < 60 and not d.get("notified"):
                    send(vk, int(user_id),
                         f"⏰ Напоминание!\n{d['text']}\n{d['datetime']}")
                    d["notified"] = True
                    save_data(data)

        time.sleep(30)


# ================== MAIN ==================

def main():
    vk_session = vk_api.VkApi(token=TOKEN)
    vk = vk_session.get_api()
    longpoll = VkLongPoll(vk_session)

    data = load_data()
    states = {}

    # поток напоминаний
    threading.Thread(target=reminder_loop, args=(vk, data), daemon=True).start()

    print("Бот запущен")

    for event in longpoll.listen():

        # ===== INLINE КНОПКИ =====
        if event.type == VkEventType.MESSAGE_EVENT:
            payload = event.payload
            user_id = str(event.user_id)

            if payload["cmd"] == "del_note":
                idx = payload["index"]
                try:
                    del data[user_id]["notes"][idx]
                    save_data(data)
                    send(vk, user_id, "✅ Заметка удалена", main_keyboard())
                except:
                    send(vk, user_id, "❌ Ошибка удаления")

            elif payload["cmd"] == "del_deadline":
                idx = payload["index"]
                try:
                    del data[user_id]["deadlines"][idx]
                    save_data(data)
                    send(vk, user_id, "✅ Дедлайн удалён", main_keyboard())
                except:
                    send(vk, user_id, "❌ Ошибка удаления")

        # ===== СООБЩЕНИЯ =====
        if event.type == VkEventType.MESSAGE_NEW and event.to_me:

            user_id = str(event.user_id)
            msg = event.text.strip()

            if user_id not in data:
                data[user_id] = {"notes": [], "deadlines": []}

            # ===== СОСТОЯНИЯ =====

            if states.get(user_id) == "add_note":
                if event.attachments:
                    photo = event.attachments[0]['photo']['sizes'][-1]['url']

                    data[user_id]["notes"].append({
                        "photo": photo,
                        "text": msg
                    })

                    save_data(data)
                    states[user_id] = None
                    send(vk, user_id, "✅ Заметка сохранена!", main_keyboard())
                else:
                    send(vk, user_id, "❌ Пришли фото!")

                continue

            if states.get(user_id) == "add_deadline":
                try:
                    parts = msg.split(" ", 2)
                    dt = parts[0] + " " + parts[1]
                    text = parts[2]

                    datetime.strptime(dt, "%d.%m.%Y %H:%M")

                    data[user_id]["deadlines"].append({
                        "datetime": dt,
                        "text": text,
                        "notified": False
                    })

                    save_data(data)
                    states[user_id] = None
                    send(vk, user_id, "⏰ Дедлайн добавлен!", main_keyboard())

                except:
                    send(vk, user_id, "❌ Формат: ДД.ММ.ГГГГ ЧЧ:ММ текст")

                continue

            if states.get(user_id) == "search":
                results = search_notes(data[user_id]["notes"], msg)

                if results:
                    send(vk, user_id, f"🔎 Найдено: {len(results)}")

                    for n in results:
                        send(vk, user_id,
                             n["text"],
                             attachment=n["photo"])
                else:
                    send(vk, user_id, "❌ Ничего не найдено")

                states[user_id] = None
                continue

            # ===== КНОПКИ =====

            if msg.lower() in ["начать", "start"]:
                send(vk, user_id, "Привет 👋", main_keyboard())

            elif msg == "📝 Заметки":
                notes = data[user_id]["notes"]

                if notes:
                    for i, n in enumerate(notes):
                        send(vk, user_id,
                             f"{i+1}. {n['text']}",
                             attachment=n["photo"])

                    send(vk, user_id,
                         "Удалить заметку:",
                         delete_keyboard(notes, "note"))
                else:
                    send(vk, user_id, "❌ Нет заметок", main_keyboard())

            elif msg == "📅 Дедлайны":
                dls = data[user_id]["deadlines"]

                if dls:
                    text = ""
                    for i, d in enumerate(dls):
                        text += f"{i+1}. {d['datetime']} — {d['text']}\n"

                    send(vk, user_id,
                         text,
                         delete_keyboard(dls, "deadline"))
                else:
                    send(vk, user_id, "❌ Нет дедлайнов", main_keyboard())

            elif msg == "➕ Заметка":
                states[user_id] = "add_note"
                send(vk, user_id, "📸 Пришли фото + текст")

            elif msg == "➕ Дедлайн":
                states[user_id] = "add_deadline"
                send(vk, user_id,
                     "📅 Введи:\nДД.ММ.ГГГГ ЧЧ:ММ текст")

            elif msg == "🔍 Найти":
                states[user_id] = "search"
                send(vk, user_id, "🔍 Введи запрос")

            else:
                send(vk, user_id, "Выбери кнопку 👇", main_keyboard())


# ================== ЗАПУСК ==================

if __name__ == "__main__":
    main()