# Use a minimal base image with Python 3.9 installed
FROM python:3.9-slim

# Send logs straight to the container output and skip .pyc files
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1

# Set the working directory inside the container to /app
WORKDIR /app

# Install Python dependencies listed in requirements.txt (cached layer)
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

# Copy the app and run it as a non-root user
RUN useradd --create-home --uid 10001 appuser
COPY --chown=appuser:appuser app.py .
USER appuser

# Port on which the Streamlit app listens
EXPOSE 8501

# Health check: Streamlit's built-in health endpoint
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8501/_stcore/health', timeout=3)"]

# Run the Streamlit app on port 8501 and make it accessible externally.
# XSRF protection is switched off only because the Codespaces port proxy breaks Streamlit's file-upload check;
# the app has no login or stored state that a cross-site request could abuse.
CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0", "--server.enableXsrfProtection=false", "--browser.gatherUsageStats=false"]
