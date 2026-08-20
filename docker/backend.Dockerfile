# Ritarinn backend.
#
# See docker-compose.yml for why containers are the optional path.

FROM python:3.11-slim

# Pinned dependencies are copied first so the layer caches independently of
# application code.
WORKDIR /app
COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r backend/requirements.txt

COPY backend/ backend/
RUN pip install --no-cache-dir --no-deps -e backend

# Load GreynirCorrect once at build time so the image fails fast if the
# language data is not usable, rather than at the user's first proofread.
RUN python -c "import reynir_correct; reynir_correct.GreynirCorrectAPI.from_options()"

# Run as an unprivileged user.
RUN useradd --create-home --uid 10001 ritarinn
USER ritarinn

EXPOSE 8756
CMD ["python", "-m", "ritarinn"]
