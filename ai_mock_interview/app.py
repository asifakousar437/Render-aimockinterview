from flask import Flask, render_template  # pyright: ignore[reportMissingImports]

# Use absolute imports for consistency
from routes.interview_routes import interview_bp

app = Flask(__name__)
app.register_blueprint(interview_bp)

@app.route("/")
def home():
    return render_template("interview.html")

@app.route("/result")
def result():
    return render_template("result.html")

if __name__ == "__main__":
    # Port 5000 may be occupied by macOS services (e.g., AirTunes).
    # Use PORT env var to override when needed.
    import os

    port = int(os.getenv("PORT", "5001"))
    app.run(debug=True, host="0.0.0.0", port=port)