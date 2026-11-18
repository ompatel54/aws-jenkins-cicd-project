from flask import Flask, jsonify

app = Flask(__name__)

APP_VERSION = "v1"

@app.route("/")
def home():
    return jsonify({
        "message": "AWS CI/CD Pipeline Application",
        "version": APP_VERSION
    })

@app.route("/health")
def health():
    return jsonify({
        "status": "healthy",
        "version": APP_VERSION
    }), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
