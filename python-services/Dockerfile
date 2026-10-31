FROM python:3.11-slim

WORKDIR /workspace/python-services

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN pip install --no-cache-dir -i https://pypi.tuna.tsinghua.edu.cn/simple playwright==1.63.0
RUN playwright install --with-deps chromium
COPY requirements.txt .
RUN pip install --no-cache-dir -i https://pypi.tuna.tsinghua.edu.cn/simple -r requirements.txt

COPY . .

CMD ["sleep", "infinity"]   