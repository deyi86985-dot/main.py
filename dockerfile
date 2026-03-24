FROM python:3.10-slim

# প্রয়োজনীয় টুলস ইনস্টল
RUN apt-get update && apt-get install -y git && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# ফাইলগুলো কপি করা
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# আপনার বটের ফাইল রান করানো
CMD ["python", "Main.py"]
