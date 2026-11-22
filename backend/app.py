
# Import necessary libraries
import math
import numpy as np
import joblib  # For loading the serialized model
import pandas as pd  # For data manipulation
from flask import Flask, request, jsonify  # For creating the Flask API
from werkzeug.exceptions import HTTPException  # Base class of HTTP errors such as 404 or 413

# Initialize Flask app with a name
superkart_api = Flask("SuperKart")

# Reject oversize requests early: the limit is far above any realistic request (the sample batch file is under 1 KB)
superkart_api.config["MAX_CONTENT_LENGTH"] = 1024 * 1024  # 1 MB
MAX_BATCH_ROWS = 5000

# Load the trained model (preprocessing steps + regressor in one pipeline).
# The file is the artifact built in this notebook; never load a joblib/pickle file from an untrusted source.
model = joblib.load("superkart_model.joblib")

# Input features expected by the model, in training order
FEATURES = [
    "Product_Weight",
    "Product_Sugar_Content",
    "Product_Allocated_Area",
    "Product_MRP",
    "Store_Size",
    "Store_Location_City_Type",
    "Store_Type",
    "Product_Id_char",
    "Store_Age_Years",
    "Product_Type_Category",
]
NUMERIC_FEATURES = ["Product_Weight", "Product_Allocated_Area", "Product_MRP", "Store_Age_Years"]
CATEGORICAL_FEATURES = [f for f in FEATURES if f not in NUMERIC_FEATURES]


class InputError(ValueError):
    """A request with missing or invalid values (answered with HTTP 400)."""


def clean_record(record):
    """Validate one product-store record and return it with the features in model order."""
    if not isinstance(record, dict):
        raise InputError("Request body must be a JSON object.")
    missing = [f for f in FEATURES if f not in record]
    if missing:
        raise InputError(f"Missing required fields: {missing}")
    clean = {}
    for f in NUMERIC_FEATURES:
        value = record[f]
        # bool is a subclass of int in Python, so it is rejected explicitly
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
            raise InputError(f"{f} must be a finite, non-negative number.")
        clean[f] = float(value)
    for f in CATEGORICAL_FEATURES:
        value = record[f]
        if not isinstance(value, str) or not value.strip() or len(value) > 50:
            raise InputError(f"{f} must be non-empty text of at most 50 characters.")
        clean[f] = value.strip()
    return {f: clean[f] for f in FEATURES}


def clean_batch(batch):
    """Validate an uploaded batch and return the feature columns in model order."""
    missing = [f for f in FEATURES if f not in batch.columns]
    if missing:
        raise InputError(f"Missing required columns: {missing}")
    if batch.empty:
        raise InputError("The uploaded file contains no rows.")
    if len(batch) > MAX_BATCH_ROWS:
        raise InputError(f"Too many rows: the limit is {MAX_BATCH_ROWS} per request.")
    batch = batch[FEATURES].copy()
    for f in NUMERIC_FEATURES:
        batch[f] = pd.to_numeric(batch[f], errors="coerce")
    bad_numeric = ~np.isfinite(batch[NUMERIC_FEATURES]).all(axis=1) | (batch[NUMERIC_FEATURES] < 0).any(axis=1)
    bad_text = batch[CATEGORICAL_FEATURES].isna().any(axis=1)
    bad_rows = batch.index[(bad_numeric | bad_text).to_numpy()].tolist()
    if bad_rows:
        raise InputError(f"Missing or invalid values in rows (0-based): {bad_rows[:10]}")
    return batch


# Return HTTP errors (404, 405, 413 ...) as JSON, like every other response of this API
@superkart_api.errorhandler(HTTPException)
def handle_http_error(error):
    return jsonify({"error": error.description}), error.code


# Define a route for the home page
@superkart_api.get("/")
def home():
    return "Welcome to the SuperKart System"


# Define an endpoint to predict sales for a single product
@superkart_api.post("/v1/predict")
def predict_sales():
    try:
        # Get JSON data from the request
        data = request.get_json(silent=True)
        if data is None:
            raise InputError("Request body must be valid JSON.")

        # Validate the record and convert it into a one-row DataFrame (columns in training order)
        input_data = pd.DataFrame([clean_record(data)])

        # Make a prediction using the trained model
        prediction = round(float(model.predict(input_data)[0]), 2)

        # Return the prediction as a JSON response
        return jsonify({"Sales": prediction})
    except InputError as e:
        return jsonify({"error": str(e)}), 400
    except HTTPException:
        raise  # answered by the JSON handler above (for example 413 Request Entity Too Large)
    except Exception:
        # Full details go to the server log; the caller only gets a generic message
        superkart_api.logger.exception("Single prediction failed")
        return jsonify({"error": "Prediction failed. Please check the input values and try again."}), 500


# Define an endpoint to predict sales for a batch of products
@superkart_api.post("/v1/predictbatch")
def predict_sales_batch():
    try:
        # Get the uploaded CSV file from the request
        if "file" not in request.files:
            raise InputError("No file found. Upload a CSV file using the key 'file'.")
        try:
            batch = pd.read_csv(request.files["file"], nrows=MAX_BATCH_ROWS + 1)
        except (pd.errors.ParserError, pd.errors.EmptyDataError, UnicodeDecodeError):
            raise InputError("The uploaded file could not be read as a CSV.") from None

        # Make predictions for the validated batch data
        predictions = model.predict(clean_batch(batch)).tolist()

        # Create an output dictionary mapping row index to predicted sales
        output_dict = {str(i): round(pred, 2) for i, pred in enumerate(predictions)}
        return jsonify(output_dict)
    except InputError as e:
        return jsonify({"error": str(e)}), 400
    except HTTPException:
        raise
    except Exception:
        superkart_api.logger.exception("Batch prediction failed")
        return jsonify({"error": "Batch prediction failed. Please check the file and try again."}), 500


# Local development only: the container serves the app with Gunicorn. Debug mode stays off.
if __name__ == "__main__":
    superkart_api.run(host="127.0.0.1", port=7860, debug=False)
