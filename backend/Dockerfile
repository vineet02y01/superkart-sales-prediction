FROM python:3.13-slim

# Send logs straight to the container output and skip .pyc files
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1

# Set the working directory inside the container
WORKDIR /app

# libgomp1 (OpenMP runtime) is required by XGBoost on the slim base image
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 && rm -rf /var/lib/apt/lists/*

# Install the pinned dependencies first (cached layer), without the pip cache to keep the image small
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy only the app and the model, and run the API as a non-root user
RUN useradd --create-home --uid 10001 appuser
COPY --chown=appuser:appuser app.py superkart_model.joblib ./
USER appuser

# Port on which the API listens inside the container
EXPOSE 7860

# Health check: the home route must answer
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:7860/', timeout=3)"]

# Start the application with Gunicorn using 4 worker processes
# - `-w 4`: 4 worker processes handle requests
# - `-b 0.0.0.0:7860`: binds the server to port 7860 on all network interfaces
# - `app:superkart_api`: runs the Flask instance named `superkart_api` defined in app.py
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:7860", "app:superkart_api"]
