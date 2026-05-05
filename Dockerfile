FROM python:3.11

WORKDIR /home/Secret-Thrower

COPY . .

RUN pip install -r requirements.txt
 
#Needs a serious rework
CMD [ "python", "bot.py" ]
