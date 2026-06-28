FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /home/Secret-Thrower

RUN groupadd -r botuser && useradd -r -g botuser botuser

COPY pyproject.toml uv.lock ./

# Install dependencies before copying source so this layer is cached
# UV_PYTHON_PREFERENCE=only-system tells uv to use the base image's Python
RUN UV_PYTHON_PREFERENCE=only-system uv sync --frozen --no-install-project --no-dev

COPY . .

RUN chown -R botuser:botuser /home/Secret-Thrower

USER botuser

ENV PATH="/home/Secret-Thrower/.venv/bin:$PATH"

# Run migrations before starting the bot so the schema is always up to date
CMD ["sh", "-c", "alembic upgrade head && python bot.py"]
