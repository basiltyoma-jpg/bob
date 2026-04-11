from flask import Flask

app = Flask(__name__)

@app.route("/")
def home():
    return """
    <h1>Привет!</h1
    """

@app.route("/about")
def about():
    return """
    <h1>О сайте</h1>
    <p>Этот сайт сделан на Flask.</p>
    """

if __name__ == "__main__":
    app.run(debug=True)