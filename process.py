from flask import Flask, request, Response
import vk_api

app = Flask(__name__)

CONFIRMATION_TOKEN = "4e09fc4f"
GROUP_TOKEN = "vk1.a.8lJ7EnqzklLXvnG3YXG79oBfmDjafZ4tfqtYx35ysbv9xtNCqyTgGWX6HPmrObkcs_x2jLuV9s-T2zjyVCjW1w26sP7YdGRshJK-V-_Ti8AW24WnDQ2CYkr_GSuujFgNINcvJiNJy3Q9S7gqMkf86vqvSPz3EG_9H2SLeOjq8QqWP9EMtHQkAM7UnMFSPZvScPIWEvxDiwqoO9srjdtl0Q"

vk_session = vk_api.VkApi(token=GROUP_TOKEN)
vk = vk_session.get_api()


def send_message(user_id, text):
    vk.messages.send(
        user_id=user_id,
        message=text,
        random_id=0
    )


@app.route('/', methods=['POST'])
def callback():
    data = request.get_json()

    # подтверждение
    if data['type'] == 'confirmation':
        return Response(CONFIRMATION_TOKEN, status=200)

    # новое сообщение
    elif data['type'] == 'message_new':
        user_id = data['object']['message']['from_id']
        text = data['object']['message']['text']

        send_message(user_id, f"Ты написал: {text}")

        return Response("ok", status=200)

    return Response("ok", status=200)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)