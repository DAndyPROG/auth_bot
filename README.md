# Telegram Bot with Auth0 Authentication

This project is a Telegram bot that authenticates users through Auth0 using the Device Authorization Flow.

## Bot Functionality

1. User starts a chat with the bot
2. Bot requests authorization through Auth0
3. On unsuccessful authorization, the bot displays an appropriate message and suggests trying again
4. On successful authorization, the bot sends a JSON with user data received from Auth0
5. After authorization, the bot repeats all messages from the user
6. If the user is inactive for more than 1 minute, the session closes and the authorization is revoked

## Technologies

- Python 3.11
- aiogram 3.x (asynchronous Telegram client)
- SQLAlchemy with asyncpg for database operations
- PostgreSQL 13
- Docker and Docker Compose for containerization

## Setup

1. Create an `.env` file based on the example:

```bash
cp .env.example .env
```

2. Fill in all the necessary environment variables in the `.env` file:
   - `BOT_TOKEN`: Your Telegram bot token (get it from [@BotFather](https://t.me/BotFather))
   - `AUTH0_DOMAIN`: Your Auth0 application domain
   - `AUTH0_CLIENT_ID`: Auth0 client ID
   - `AUTH0_CLIENT_SECRET`: Auth0 client secret key
   - `AUTH0_AUDIENCE`: Auth0 audience URI (if needed)
   - `AUTH0_SCOPE`: Access scopes (default is "openid profile email")
   - `DATABASE_URL`: Database connection string (default is "postgresql+asyncpg://postgres:postgress@db:5432/tgbot" for Docker)
   - `SESSION_TIMEOUT`: Inactivity time for session closure (in seconds, default is 3600)

## Auth0 Configuration

1. Create a new application in your Auth0 account
2. Application type: "Native" or "Regular Web Applications"
3. Enable "Device Authorization Flow" in the application settings
4. Add the necessary scopes

## Running the Application

### Using Docker Compose

The easiest way to run the bot is using Docker Compose:

```bash
# Build and start the containers
docker-compose build
docker-compose up -d

# View bot logs
docker-compose logs -f bot

# Stop the containers
docker-compose down
```

### Local Development

1. Install dependencies:

```bash
pip install -r requirements.txt
```

2. Start the bot:

```bash
python bot.py
```

## Testing

To run the tests:

```bash
pytest
```

To check test coverage:

```bash
pytest --cov=. --cov-report=term-missing
```

The project has extensive test coverage (87-94%) for key components.

## Project Structure

- `bot.py` - Main bot file
- `handlers/` - Message handlers
- `utils/` - Utilities for database, Auth0, and sessions
- `keyboards/` - Telegram keyboards
- `tests/` - Unit tests
- `Dockerfile` - Container configuration for the bot
- `docker-compose.yml` - Multi-container setup for the bot and database

## Troubleshooting Docker Deployment

If you encounter issues with the Docker deployment:

1. Check if Docker service is running:
   ```bash
   docker ps
   ```

2. Verify environment variables in the `.env` file, especially the database URL

3. Common issues:
   - Database connection errors: Ensure the database URL uses `db` as hostname, not `localhost`
   - Missing asyncpg: The bot requires both psycopg2-binary and asyncpg libraries
   - Container restarts: Check the logs with `docker-compose logs -f bot`

## License

MIT 