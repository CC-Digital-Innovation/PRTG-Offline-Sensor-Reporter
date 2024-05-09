FROM python:3.12-slim
LABEL maintainer="Anthony Farina <anthony.farina@computacenter.com>"

WORKDIR /app

COPY requirements.txt requirements.txt
RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD [ "python", "src/PRTG_Offline_Sensor_Reporter.py" ]
