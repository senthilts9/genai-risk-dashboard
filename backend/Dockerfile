FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends g++ && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY cpp ./cpp
COPY kdb ./kdb
COPY setup.py .

# Build the C++ tick engine extension. If this fails for any reason (e.g. a
# platform quirk), the app still works -- cpp_tick_engine.py falls back to
# the pure-Python/numpy pipeline automatically, so this is best-effort, not
# a hard requirement of the image build.
RUN python setup.py build_ext --inplace || echo "C++ extension build failed -- will use Python fallback"

ENV RISK_DB_PATH=/app/data/risk.db
RUN mkdir -p /app/data

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
