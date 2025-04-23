FROM python:3.13-slim

WORKDIR /app

COPY rag-module/ingestion/requirements.txt ./requirements.txt
RUN pip install -r requirements.txt

COPY rag-module/ingestion/ingest_pubmed.py ./ingest_pubmed.py
COPY config.json ../../config.json

RUN echo '#!/bin/bash\n\
python ingest_pubmed.py "$@"\n\
' > /app/entrypoint.sh && chmod +x /app/entrypoint.sh

ENTRYPOINT ["/app/entrypoint.sh"]