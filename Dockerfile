FROM condaforge/mambaforge:latest

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install FreeCAD and dependencies using conda
RUN conda install -c conda-forge freecad python=3.10 -y \
    && conda install -c conda-forge wkhtmltopdf -y \
    && conda install -c conda-forge networkx -y \
    && conda clean -afy

# Install system dependencies (Redis only, MQTT is separate container)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    redis-server \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

COPY . /app

RUN mkdir -p /app/storage

# Copy and make entrypoint executable
COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

# Expose API port only (MQTT is separate container)
EXPOSE 8080

CMD ["/app/entrypoint.sh"]
