

#Dockerfile always start from the version
FROM python:3.10

#Set up environment path
ENV PYTHONPATH=/app
#set default working directory of docker process as WORKDIR
WORKDIR /app

#COPY: a docker build language, copy the file from my original system to docker environment under the specified path
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/app/ /app/backend/app/
COPY backend/__init__.py /app/backend/__init__.py

#CMD: To run the docker file, the command is what we run on local computer
EXPOSE 8080
# Use Cloud Run's PORT when present, fallback to 8080 for local runs.
CMD ["sh", "-c", "uvicorn backend.app.main:app --host 0.0.0.0 --port ${PORT:-8080}"]
