FROM python:3.12-slim
WORKDIR /broker
COPY private_broker/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt && useradd --uid 10001 --create-home broker
COPY private_broker/__init__.py private_broker/runtime.py private_broker/store.py ./private_broker/
COPY scripts/dufynd_observer_credentials.py ./scripts/dufynd_observer_credentials.py
USER 10001
EXPOSE 8080
CMD ["uvicorn", "private_broker.runtime:production_app", "--factory", "--host", "0.0.0.0", "--port", "8080", "--no-access-log", "--log-level", "critical"]
