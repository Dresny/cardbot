FROM python:3.11-slim
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*
RUN useradd -m -u 1000 botuser
USER botuser
WORKDIR /app
COPY --chown=botuser:botuser re.txt .
RUN pip install --no-cache-dir --user -r re.txt
ENV PATH="/home/botuser/.local/bin:${PATH}"
COPY --chown=botuser:botuser . .
RUN mkdir -p /home/botuser/data
VOLUME /home/botuser/data
CMD ["python", "main.py"]