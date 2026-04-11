from flask import Flask, request, Response
import vk_api

app = Flask(__name__)

CONFIRMATION_TOKEN = "4a01fb80"
GROUP_TOKEN = "vk1.a.8lJ7EnqzklLXvnG3YXG79oBfmDjafZ4tfqtYx35ysbv9xtNCqyTgGWX6HPmrObkcs_x2jLuV9s-T2zjyVCjW1w26sP7YdGRshJK-V-_Ti8AW24WnDQ2CYkr_GSuujFgNINcvJiNJy3Q9S7gqMkf86vqvSPz3EG_9H2SLeOjq8QqWP9EMtHQkAM7UnMFSPZvScPIWEvxDiwqoO9srjdtl0Q"

vk_session = vk_api.VkApi(token=GROUP_TOKEN)
vk = vk_session.get_api()


@app.route('/', methods=['POST'])
def callback():
    data = request.get_json()

    print("DEBUG:", data)  # смотри в консоль

    if data['type'] == 'confirmation':
        return CONFIRMATION_TOKEN

    elif data['type'] == 'message_new':
        message = data['object']['message']

        user_id = message['from_id']
        text = message['text']

        try:
            vk.messages.send(
                user_id=user_id,
                message=f"Ответ: {text}",
                random_id=0
            )
            print("Сообщение отправлено")

        except Exception as e:
            print("ОШИБКА:", e)

        return "ok"

    return "ok"


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)