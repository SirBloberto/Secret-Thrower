FROM python:3

WORKDIR /home/Secret-Thrower

COPY . .

RUN pip install -r requirements.txt
 
CMD [ "python", "bot.py" ]
