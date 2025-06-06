#!/usr/bin/env python3
"""Simple Flask application for testing requirements-based project."""

from flask import Flask, jsonify
import pandas as pd
import numpy as np
import requests

app = Flask(__name__)


@app.route("/")
def hello():
    return jsonify(
        {
            "message": "Hello from requirements-based project!",
            "pandas_version": pd.__version__,
            "numpy_version": np.__version__,
        }
    )


@app.route("/fetch")
def fetch_data():
    """Fetch sample data from a public API."""
    response = requests.get("https://api.github.com")
    return jsonify({"status": response.status_code, "headers": dict(response.headers)})


if __name__ == "__main__":
    app.run(debug=True)
