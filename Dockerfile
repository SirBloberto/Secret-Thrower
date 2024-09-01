FROM python:3.11

WORKDIR /home/Secret-Thrower

COPY . .

RUN pip install -r requirements.txt
 
CMD [ "python", "bot.py" ]
