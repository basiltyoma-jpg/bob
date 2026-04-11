from flask import Flask, request, Response

app = Flask(__name__)

# Строка подтверждения из настроек ВК
CONFIRMATION_TOKEN = "4a01fb80"

@app.route('/', methods=['POST'])
def callback():
    data = request.get_json(force=True, silent=True)

    # Проверка события подтверждения
    if data and data.get('type') == 'confirmation':
        # Возвращаем только строку с кодом 200
        return Response(CONFIRMATION_TOKEN, status=200, mimetype='text/plain')

    # Для всех остальных событий возвращаем "ok"
    return Response('ok', status=200, mimetype='text/plain')


if __name__ == '__main__':
    # Важно слушать все интерфейсы
    app.run(host='0.0.0.0', port=5000)