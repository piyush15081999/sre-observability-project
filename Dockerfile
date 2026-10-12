# Small Python runtime; an image download happens only when you build it.
FROM python:3.12-slim

# Keep logs visible immediately and avoid writing Python bytecode in the image.
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /app

# Copy dependencies first so Docker can reuse this layer when only code changes.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Run the API as an unprivileged user.
RUN useradd --create-home appuser
COPY --chown=appuser:appuser app ./app
COPY --chown=appuser:appuser wsgi.py .
USER appuser

EXPOSE 8000
# One worker keeps in-memory metrics consistent without multiprocess configuration.
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "1", "--threads", "4", "--access-logfile", "-", "--error-logfile", "-", "wsgi:app"]
