import sys
import os

# Add the ai_mock_interview directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import and run the app
from ai_mock_interview.app import app

if __name__ == "__main__":
    port = int(os.getenv("PORT", "5001"))
    app.run(debug=False, host="0.0.0.0", port=port)
