# 🤖 Real-time Job Alert Bot (Fastwork & Facebook Groups)

บอทแจ้งเตือนงานเขียนโปรแกรม ทำเว็บไซต์ พัฒนา AI / Machine Learning ซอฟต์แวร์ และสายไอทีแบบ Real-time แจ้งเตือนเข้า **LINE** โดยตรง พร้อมระบบจัดการคีย์เวิร์ดผ่าน LINE และบันทึก Log ลงฐานข้อมูล **PostgreSQL** บน **Railway**

---

## 🌟 ฟีเจอร์เด่น (Key Features)

1. **สแกนงานจาก 2 แหล่งหลัก**:
   - 🟣 **Fastwork Job Board**: ดึงงานใหม่ล่าสุดจากบอร์ดประกาศงาน Fastwork แบบ Real-time พร้อมงบประมาณและลิงก์ตรง
   - 🔵 **Facebook Groups**: ดึงโพสต์หางานจากกลุ่มเฟสบุ๊ค (รองรับทั้ง RSS Feed, Cookie session และ Webhook) พร้อมระบุชื่อกลุ่ม
2. **จัดการ Setting Keyword ผ่าน LINE ได้ทันที**:
   - พิมพ์ดูคีย์เวิร์ดทั้งหมดที่ตั้งไว้
   - พิมพ์เพิ่มคำค้นหาใหม่ได้ตลอดเวลา (เช่น `เพิ่ม react`, `เพิ่ม flutter`)
   - พิมพ์ลบคำค้นหาที่ไม่ต้องการออกได้
3. **แจ้งเตือนสวยงามผ่าน LINE Flex Message**:
   - ดีไซน์เป็นการ์ดทันสมัย แสดงหัวข้อ, แหล่งที่มา/กลุ่ม, งบประมาณ, สรุปเนื้อหา, คีย์เวิร์ดที่แมตช์
   - ปุ่มกด **"🔗 เปิดดูประกาศงาน"** ลิงก์ตรงไปยังโพสต์งานทันที
   - มีระบบ Text Message Fallback สำรองหากแสดงผล Flex Message ไม่ได้
4. **ป้องกันการแจ้งเตือนซ้ำ (Deduplication)**:
   - ตรวจสอบ `post_id` และบันทึก Log ลงในฐานข้อมูล **PostgreSQL บน Railway**
   - งานที่เคยแจ้งเตือนแล้วจะไม่ถูกส่งซ้ำ
5. **พร้อม Deploy ขึ้น GitHub และ Railway 100%**:
   - มี `Procfile`, `railway.json`, `Dockerfile` และ `requirements.txt` พร้อมรันทันที

---

## 📁 โครงสร้างโปรเจกต์ (Project Structure)

```text
LineBotFWFB/
├── scrapers/
│   ├── __init__.py
│   ├── fastwork_scraper.py   # ดึงข้อมูลจาก Fastwork Job Board API
│   └── facebook_scraper.py   # ดึงข้อมูลจาก Facebook Groups (RSS / Cookie / Demo)
├── notifier/
│   ├── __init__.py
│   ├── matcher.py            # ตัวกรองข้อความและจับคู่คีย์เวิร์ด (Regex / Substring)
│   └── line_notifier.py      # สร้างและส่ง LINE Flex Message & Text
├── config.py                 # จัดการการอ่านค่า Environment Variables
├── database.py               # SQLAlchemy ORM (รองรับ PostgreSQL บน Railway และ SQLite บน Local)
├── line_handler.py           # ตัวประมวลผลคำสั่งจากผู้ใช้ใน LINE
├── worker.py                 # Background thread รันสแกนงานตามรอบเวลา (ทุกๆ 3 นาที)
├── Main.py                   # Flask Web Server, Webhook `/callback` และ API Endpoints
├── requirements.txt          # รายการไลบรารีที่จำเป็น
├── Procfile                  # คำสั่ง Start Server สำหรับ Railway
├── railway.json              # ไฟล์ตั้งค่า Build & Deploy บน Railway
├── Dockerfile                # Docker container configuration
├── .env.example              # ตัวอย่างไฟล์ Environment Variables
├── .gitignore                # ป้องกันการเอาไฟล์ที่ไม่จำเป็นและ Secret ขึ้น Git
└── README.md                 # คู่มือการใช้งานฉบับสมบูรณ์
```

---

## 💬 คำสั่งใช้งานผ่าน LINE (LINE Commands Cheatsheet)

คุณสามารถพิมพ์คุยกับบอทใน LINE ได้ทั้งในแชทส่วนตัว หรือดึงบอทเข้ากลุ่ม:

### 🌟 สั่งงานด้วยภาษาธรรมชาติ (Prompt-based Job Search)
คนหางานสามารถพิมพ์บอกความต้องการเป็นประโยคได้เลย บอทจะวิเคราะห์ แยกแยะสกิล บันทึกคีย์เวิร์ด และค้นหางานสดมาแสดงทันที:
- `ช่วยหางานด้านซอฟต์แวร์ และการทำ AI`
- `หางานทำเว็บ React และ Node.js`
- `อยากได้งาน Mobile app Flutter ครับ`
- `มีงานเขียนโปรแกรม Python ไหม`

### 📌 คำสั่งระบบพื้นฐาน
| คำสั่ง | ตัวอย่างการพิมพ์ | รายละเอียด |
|---|---|---|
| **สั่งหางาน (Prompt)** | `ช่วยหางานด้านซอฟต์แวร์ และการทำ AI` | วิเคราะห์ความต้องการ บันทึกคำค้นหา และดึงงานสดมาแสดงทันที |
| **ดูวิธีใช้** | `วิธีใช้` หรือ `help` | แสดงคู่มือคำสั่งทั้งหมด |
| **ดูคีย์เวิร์ด** | `คีย์เวิร์ด` หรือ `keyword` | แสดงรายการคำค้นหาทั้งหมดที่กำลังเปิดใช้งานอยู่ |
| **เพิ่มคีย์เวิร์ด** | `เพิ่ม react` หรือ `add flutter` | เพิ่มคำค้นหาใหม่เข้าสู่ฐานข้อมูล |
| **ลบคีย์เวิร์ด** | `ลบ php` หรือ `del bot` | ลบคำค้นหาออกจากระบบ |
| **รีเซ็ตคีย์เวิร์ด** | `รีเซ็ต` หรือ `reset` | คืนค่าคีย์เวิร์ดกลับเป็นค่าเริ่มต้น (ด้าน Web, Programming, AI) |
| **ดูกลุ่ม Facebook** | `กลุ่ม` หรือ `groups` | ดูรายชื่อกลุ่ม Facebook สายโปรแกรมเมอร์ที่บอทคอยสแกน |
| **เปิดรับแจ้งเตือน** | `ติดตาม` หรือ `subscribe` | ลงทะเบียนแชทหรือกลุ่มนี้เพื่อรับแจ้งเตือนงานใหม่ |
| **หยุดรับแจ้งเตือน** | `ยกเลิก` หรือ `unsubscribe` | หยุดรับการแจ้งเตือนงานในแชทนี้ |
| **ดูสถานะระบบ** | `สถานะ` หรือ `status` | ดูสถานะเซิร์ฟเวอร์, ฐานข้อมูล, คำสั่งค้นหาล่าสุดของคุณ |
| **ทดสอบแจ้งเตือน** | `ทดสอบ` หรือ `test` | ให้บอทส่งตัวอย่างการแจ้งเตือนงานจำลองทันที |

---

## 🛠️ ขั้นตอนการเตรียม LINE Bot (LINE Developers)

1. เข้าไปที่ [LINE Developers Console](https://developers.line.biz/)
2. สร้าง **Provider** และสร้าง **Channel** ประเภท **Messaging API**
3. ไปที่แท็บ **Messaging API**:
   - เลื่อนลงมาด้านล่างสุด แล้วกด **Issue** ในส่วน **Channel access token (long-lived)** -> คัดลอกเก็บไว้ (`LINE_CHANNEL_ACCESS_TOKEN`)
4. ไปที่แท็บ **Basic settings**:
   - คัดลอก **Channel secret** -> เก็บไว้ (`LINE_CHANNEL_SECRET`)
5. ที่แท็บ **Messaging API** ในส่วน **LINE Official Account features**:
   - กดเข้าไปแก้ไขใน **LINE Official Account Manager**
   - ไปที่ **Settings (ตั้งค่า)** -> **Response settings (การตอบกลับ)**
   - ตั้งค่า **Response mode** เป็น **Bot**
   - ปิด **Auto-reply messages (ข้อความตอบกลับอัตโนมัติ)**
   - เปิด **Webhooks**

---

## 💻 วิธีการรันและทดสอบบนเครื่อง Local

1. เปิด Terminal ในโฟลเดอร์โปรเจกต์ `LineBotFWFB`
2. คัดลอกไฟล์ `.env.example` เป็น `.env`:
   ```bash
   cp .env.example .env
   ```
3. เปิดไฟล์ `.env` แล้วกรอกค่า `LINE_CHANNEL_ACCESS_TOKEN` และ `LINE_CHANNEL_SECRET`
4. ติดตั้ง Dependencies:
   ```bash
   pip install -r requirements.txt
   ```
5. รันโปรแกรม:
   ```bash
   python Main.py
   ```
6. เซิร์ฟเวอร์จะเริ่มทำงานที่พอร์ต `5000` โดยบนเครื่อง Local หากไม่ได้ใส่ `DATABASE_URL` ระบบจะสร้างไฟล์ฐานข้อมูล `jobs.db` (SQLite) ให้ใช้งานได้ทันทีโดยไม่ต้องลง Postgres ในเครื่อง

---

## 🚀 วิธีการนำโค้ดขึ้น GitHub

1. เปิด Terminal ที่โฟลเดอร์ `d:\PreTest\LineBotFWFB`
2. ตรวจสอบหรือกำหนด Git Repository:
   ```bash
   git init
   git add .
   git commit -m "feat: real-time job alert bot for Fastwork and Facebook"
   ```
3. สร้าง New Repository บน [GitHub](https://github.com/new) (เช่น ตั้งชื่อว่า `job-alert-linebot`)
4. เชื่อมต่อและ Push โค้ด:
   ```bash
   git branch -M main
   git remote add origin https://github.com/<YOUR_USERNAME>/job-alert-linebot.git
   git push -u origin main
   ```

---

## 🚂 วิธีการ Deploy บน Railway พร้อม PostgreSQL

1. สมัครหรือเข้าสู่ระบบที่ [Railway.app](https://railway.app/)
2. กดปุ่ม **+ New Project** -> เลือก **Deploy from GitHub repo**
3. เลือก Repository ที่เพิ่ง Push ขึ้นไป (`job-alert-linebot`)
4. **เพิ่มฐานข้อมูล PostgreSQL**:
   - ในหน้า Project บน Railway ให้กดปุ่ม **+ Create** หรือคลิกขวาในพื้นที่ว่าง -> เลือก **Database** -> เลือก **Add PostgreSQL**
   - Railway จะสร้างฐานข้อมูล Postgres ให้ในโปรเจกต์เดียวกัน
5. **ตั้งค่า Environment Variables**:
   - คลิกที่ Service ของตัวบอท (บ็อกซ์ที่เป็นโค้ด GitHub)
   - ไปที่แท็บ **Variables**
   - กด **Add Reference** หรือเพิ่มตัวแปรดังนี้:
     - `DATABASE_URL`: เลือก reference เป็น `${{Postgres.DATABASE_URL}}` (Railway จะเชื่อมต่อให้อัตโนมัติ)
     - `LINE_CHANNEL_ACCESS_TOKEN`: วาง Token จาก LINE Developers
     - `LINE_CHANNEL_SECRET`: วาง Secret จาก LINE Developers
     - `POLL_INTERVAL_SECONDS`: `180` (ความถี่ในการสแกนงาน ทุก 3 นาที)
     - `FASTWORK_ENABLED`: `true`
     - `FACEBOOK_ENABLED`: `true`
     - `FB_DEMO_FALLBACK`: `true`
6. **ตั้งค่า Domain & Webhook**:
   - ไปที่แท็บ **Settings** ของ Service ตัวบอท
   - ในส่วน **Networking** -> กด **Generate Domain** คุณจะได้ URL เช่น `https://job-alert-linebot-production.up.railway.app`
   - นำ URL นี้ไปกรอกใน **LINE Developers Console** ที่แท็บ **Messaging API** -> **Webhook URL**:
     ```text
     https://job-alert-linebot-production.up.railway.app/callback
     ```
   - กดปุ่ม **Verify** เพื่อทดสอบ (ต้องขึ้นคำว่า `Success`)
   - เปิดสวิตช์ **Use webhook** ให้เป็นสีเขียว
7. **เริ่มใช้งาน**:
   - แอดบอท LINE เข้าไปในเพื่อน หรือดึงเข้ากลุ่ม
   - พิมพ์คำว่า `ติดตาม` เพื่อเปิดรับการแจ้งเตือน
   - พิมพ์ `ทดสอบ` เพื่อเช็คความพร้อมการแจ้งเตือนทันที!

---

## 📘 ข้อมูลเพิ่มเติมสำหรับการมอนิเตอร์ Facebook Groups

เนื่องจาก Facebook มีระบบความเป็นส่วนตัวและ Anti-bot การติดตามกลุ่ม Facebook สามารถทำได้ 3 ทางเลือก:

1. **ผ่าน RSS Feed (แนะนำสำหรับ Public Groups)**:
   - ใช้บริการฟรีอย่าง RSS-Bridge หรือ FetchRSS แปลงกลุ่ม Facebook เป็น RSS URL
   - นำลิงก์ RSS มาใส่ในตัวแปร `FB_RSS_URLS` ใน `.env` หรือ Railway Variables (คั่นด้วย `,` หากมีหลายลิงก์)
2. **ผ่าน Session Cookie**:
   - นำ Cookie จากเบราว์เซอร์ (`c_user=...; xs=...`) มาใส่ในตัวแปร `FB_COOKIE`
   - ใส่รายชื่อ Group ID ใน `FB_GROUP_IDS` เช่น `FB_GROUP_IDS=123456789,987654321`
3. **ผ่าน Webhook Endpoint (`/api/webhook/facebook`)**:
   - หากคุณมี Extension บนเบราว์เซอร์ หรือสคริปต์ภายนอก (เช่น Apify หรือ Playwright) สามารถสั่ง POST ข้อมูลโพสต์เข้ามาที่ API ของบอทได้โดยตรงที่:
     ```http
     POST https://your-railway-domain.app/api/webhook/facebook
     Content-Type: application/json

     {
       "post_id": "998877",
       "group_name": "สมาคมโปรแกรมเมอร์ไทย",
       "title": "หาคนทำ Web Dashboard React",
       "content": "ต้องการฟรีแลนซ์ด่วน งบ 30,000 บาท...",
       "budget": "30,000 บาท",
       "url": "https://facebook.com/groups/..."
     }
     ```
   - ระบบจะทำการ Match คีย์เวิร์ด แจ้งเตือนเข้า LINE ทันที และบันทึก Log ลง Postgres โดยอัตโนมัติ

---

## 🛡️ License

MIT License - พัฒนาขึ้นสำหรับการศึกษาและนำไปใช้งานจริงได้อย่างอิสระ
