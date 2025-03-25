FROM python:3.11-slim

WORKDIR /app

# Install system dependencies and Rust
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    pkg-config \
    libssl-dev \
    && curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y \
    && . $HOME/.cargo/env \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Add Cargo to PATH
ENV PATH="/root/.cargo/bin:${PATH}"

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the project files
COPY . .

# Run the bot
CMD ["python", "bot.py"] 