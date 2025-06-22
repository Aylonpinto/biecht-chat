FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    alsa-utils \
    libsdl2-mixer-2.0-0 \
    libportaudio2 \
    portaudio19-dev \
    linux-headers-generic \
    build-essential \
    libudev-dev \
    libevdev-dev \
    udev \
    && rm -rf /var/lib/apt/lists/*

# No special group setup needed for X11 forwarding

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install -r requirements.txt

# Copy application
COPY src/ ./src/
COPY elevator.mp3 .
COPY .env .

CMD ["python", "src/voice_gpt.py"]