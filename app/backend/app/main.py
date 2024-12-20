from fastapi import FastAPI, HTTPException, File, UploadFile, Form # type: ignore
from pydantic import BaseModel # type: ignore
from fastapi.middleware.cors import CORSMiddleware # type: ignore
from fastapi.responses import JSONResponse, StreamingResponse # type: ignore
import databases # type: ignore
import aiofiles # type: ignore
import urllib.parse
import os
import uuid
from typing import List
from minio import Minio # type: ignore

# Database configuration
DATABASE_URL = "postgresql://user:password@postgres-service:5432/corpmail"
database = databases.Database(DATABASE_URL)

# MinIO configuration
minio_client = Minio(
    "storage-service:9000",
    access_key="minioadmin",
    secret_key="minioadmin",
    secure=False,
)

app = FastAPI()

# Allow CORS for frontend and registration containers
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust this to specific origins in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Registration model
class RegistrationData(BaseModel):
    email: str
    password: str

class LoginData(BaseModel):
    email: str
    password: str

class EmailDeletionRequest(BaseModel):
    token:str

# Connect to the database on startup
@app.on_event("startup")
async def connect_to_db():
    await database.connect()

# Disconnect from the database on shutdown
@app.on_event("shutdown")
async def disconnect_from_db():
    await database.disconnect()

# Create tables on startup
@app.on_event("startup")
async def create_tables():
    user_table = """
    CREATE TABLE IF NOT EXISTS users (
        email VARCHAR(255) PRIMARY KEY,
        password VARCHAR(255) NOT NULL,
        token VARCHAR(255) UNIQUE NOT NULL
    );
    """
    email_table = """
    CREATE TABLE IF NOT EXISTS emails (
        id SERIAL PRIMARY KEY,
        sender VARCHAR(255) NOT NULL,
        receiver VARCHAR(255) NOT NULL,
        title TEXT NOT NULL,
        text TEXT NOT NULL,
        is_visible_to_sender BOOLEAN DEFAULT TRUE,
        is_visible_to_receiver BOOLEAN DEFAULT TRUE
    );
    """
    attachment_table = """
    CREATE TABLE IF NOT EXISTS attachments (
        id SERIAL PRIMARY KEY,
        email_id INTEGER REFERENCES emails(id) ON DELETE CASCADE,
        url TEXT NOT NULL
    );
    """
    await database.execute(user_table)
    await database.execute(email_table)
    await database.execute(attachment_table)

@app.on_event("startup")
async def create_minio_bucket():
    bucket_name = "emails"
    try:
        if not minio_client.bucket_exists(bucket_name):
            minio_client.make_bucket(bucket_name)
            print(f"Bucket '{bucket_name}' created.")
        else:
            print(f"Bucket '{bucket_name}' already exists.")
    except Exception as e:
        print(f"Error creating bucket: {e}")

# Registration endpoint
@app.post("/register")
async def register_user(data: RegistrationData):
    # Check if email already exists
    query = "SELECT email FROM users WHERE email = :email"
    existing_user = await database.fetch_one(query, {"email": data.email})
    if existing_user:
        raise HTTPException(status_code=400, detail="User already exists")
    
    # Generate a unique token
    token = str(uuid.uuid4())

    # Insert new user with token
    query = "INSERT INTO users (email, password, token) VALUES (:email, :password, :token)"
    await database.execute(query, {"email": data.email, "password": data.password, "token": token})

    return {"message": "Registration successful"}

# Login endpoints
@app.post("/login")
async def login_user(data: LoginData):
    # Check if the user exists
    query = "SELECT email, password, token FROM users WHERE email = :email"
    user = await database.fetch_one(query, {"email": data.email})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Verify password
    if user["password"] != data.password:
        raise HTTPException(status_code=403, detail="Invalid password")
    
    # Return the token
    return {"message": "Login successful", "token": user["token"]}

@app.delete("/users/{token}")
async def delete_user(token: str):
    # Retrieve email associated with the token
    query = "SELECT email FROM users WHERE token = :token"
    user = await database.fetch_one(query, {"token": token})
    if not user:
        raise HTTPException(status_code=404, detail="Invalid token")

    email = user["email"]

    # Retrieve all emails where the user is sender or receiver
    query = "SELECT id FROM emails WHERE sender = :email OR receiver = :email"
    emails = await database.fetch_all(query, {"email": email})

    # Call the delete_email method for each email
    for email_entry in emails:
        email_id = email_entry["id"]
        # Call delete_email method
        try:
            request = EmailDeletionRequest(token=token)
            await delete_email(email_id=email_id, request=request)
        except HTTPException as e:
            # Log or handle errors if needed
            print(f"Error deleting email {email_id}: {e.detail}")

    # Delete the user
    query = "DELETE FROM users WHERE token = :token"
    await database.execute(query, {"token": token})

    return {"message": "User and associated emails processed successfully"}

# Email endpoints
@app.post("/emails")
async def send_email(
    sender: str = Form(...),
    receiver: str = Form(...),
    title: str = Form(...),
    text: str = Form(...),
    attachments: List[UploadFile] = File([])
):
    # Retrieve email of the sender
    query = "SELECT email FROM users WHERE token = :token"
    sender_data = await database.fetch_one(query, {"token": sender})
    if not sender_data:
        raise HTTPException(status_code=400, detail="Invalid sender token")
    sender_email = sender_data["email"]

    # Проверка: существует ли отправитель
    query = "SELECT email FROM users WHERE email = :email"
    sender_exists = await database.fetch_one(query, {"email": sender_email})
    if not sender_exists:
        raise HTTPException(status_code=400, detail="Sender email does not exist")

    # Проверка: существует ли получатель
    receiver_exists = await database.fetch_one(query, {"email": receiver})
    if not receiver_exists:
        raise HTTPException(status_code=400, detail="Receiver email does not exist")

    # Сохраняем текст письма в базу данных
    query = """
    INSERT INTO emails (sender, receiver, title, text) 
    VALUES (:sender, :receiver, :title, :text) RETURNING id
    """
    email_id = await database.execute(query, {"sender": sender_email, "receiver": receiver, "title":title, "text": text})

    # Получаем имя до "@" для отправителя и получателя
    sender_name = sender_email.split("@")[0]
    receiver_name = receiver.split("@")[0]

    # Создаём директорию для сохранения вложений, если её ещё нет
    email_folder = f"/data/emails/{sender_name}/{receiver_name}/{email_id}/"
    os.makedirs(email_folder, exist_ok=True)

    # Сохраняем вложения
    attachment_urls = []
    for attachment in attachments:
        file_path = f"{email_folder}{attachment.filename}"
        async with aiofiles.open(file_path, "wb") as out_file:
            content = await attachment.read()
            await out_file.write(content)

        # Загружаем файл в MinIO
        minio_path = f"{sender_name}/{receiver_name}/{email_id}/{attachment.filename}"
        minio_client.fput_object("emails", minio_path, file_path)

        attachment_urls.append(minio_path)

    # Сохраняем ссылки на вложения в базу данных
    for url in attachment_urls:
        query = "INSERT INTO attachments (email_id, url) VALUES (:email_id, :url)"
        await database.execute(query, {"email_id": email_id, "url": url})

    return {"message": "Email sent successfully"}

@app.get("/emails/sent/{token}")
async def get_sent_emails(token: str):
    # Получаем email, связанный с токеном
    query = "SELECT email FROM users WHERE token = :token"
    user_data = await database.fetch_one(query, {"token": token})
    if not user_data:
        raise HTTPException(status_code=400, detail="Invalid user token")
    sender_email = user_data["email"]

    # Получаем отправленные письма
    query = """
    SELECT id, sender, receiver, title, text 
    FROM emails 
    WHERE sender = :sender_email AND is_visible_to_sender = TRUE
    """
    emails = await database.fetch_all(query, {"sender_email": sender_email})

    # Формируем ответ с вложениями
    result = []
    for email in emails:
        query = "SELECT url FROM attachments WHERE email_id = :email_id"
        attachments = await database.fetch_all(query, {"email_id": email["id"]})
        result.append({
            "id": email["id"],
            "sender": email["sender"],
            "receiver": email["receiver"],
            "title": email["title"],
            "text": email["text"],
            "attachments": [attachment["url"] for attachment in attachments]
        })

    return JSONResponse(content=result)

@app.get("/emails/received/{token}")
async def get_received_emails(token: str):
    # Получаем email, связанный с токеном
    query = "SELECT email FROM users WHERE token = :token"
    user_data = await database.fetch_one(query, {"token": token})
    if not user_data:
        raise HTTPException(status_code=400, detail="Invalid user token")
    receiver_email = user_data["email"]

    # Получаем полученные письма
    query = """
    SELECT id, sender, receiver, title, text 
    FROM emails 
    WHERE receiver = :receiver_email AND is_visible_to_receiver = TRUE
    """
    emails = await database.fetch_all(query, {"receiver_email": receiver_email})

    # Формируем ответ с вложениями
    result = []
    for email in emails:
        query = "SELECT url FROM attachments WHERE email_id = :email_id"
        attachments = await database.fetch_all(query, {"email_id": email["id"]})
        result.append({
            "id": email["id"],
            "sender": email["sender"],
            "receiver": email["receiver"],
            "title": email["title"],
            "text": email["text"],
            "attachments": [attachment["url"] for attachment in attachments]
        })

    return JSONResponse(content=result)

@app.get("/download/{sender}/{receiver}/{email_id}/{filename}")
async def download_file(sender: str, receiver: str, email_id: int, filename: str):
    bucket_name = "emails"
    object_name = f"{sender}/{receiver}/{email_id}/{filename}"

    try:
        # Получаем объект из MinIO
        data = minio_client.get_object(bucket_name, object_name)

        # Возвращаем файл в виде потока
        return StreamingResponse(
            data,
            media_type="application/octet-stream",
            headers={"Content-Disposition": f"attachment; filename*=UTF-8''{urllib.parse.quote(filename)}"}
        )
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"File not found: {e}")

@app.delete("/emails/{email_id}")
async def delete_email(email_id: int, request: EmailDeletionRequest):
    # Retrieve email of the user
    query = "SELECT email FROM users WHERE token = :token"
    user_data = await database.fetch_one(query, {"token": request.token})
    if not user_data:
        raise HTTPException(status_code=400, detail="Invalid user token")
    user_email = user_data["email"]

    # Проверяем, существует ли письмо
    query = "SELECT sender, receiver, is_visible_to_sender, is_visible_to_receiver FROM emails WHERE id = :email_id"
    email = await database.fetch_one(query, {"email_id": email_id})
    if not email:
        raise HTTPException(status_code=404, detail="Email not found")
    
    ownLetter = False
    is_visible_to_sender = email["is_visible_to_sender"]
    is_visible_to_receiver = email["is_visible_to_receiver"]
    # Проверяем, принадлежит ли запрос отправителю или получателю
    if user_email == email["sender"]:
        is_visible_to_sender = False
        ownLetter = True
        # Отключаем отображение для отправителя
        query = "UPDATE emails SET is_visible_to_sender = FALSE WHERE id = :email_id"
        await database.execute(query, {"email_id": email_id})
    if user_email == email["receiver"]:
        is_visible_to_receiver = False
        ownLetter = True
        # Отключаем отображение для получателя
        query = "UPDATE emails SET is_visible_to_receiver = FALSE WHERE id = :email_id"
        await database.execute(query, {"email_id": email_id})
    if not ownLetter:
        raise HTTPException(status_code=403, detail="You are not authorized to delete this email")
    
    # Проверяем, нужно ли удалять письмо полностью
    if not is_visible_to_sender and not is_visible_to_receiver:
        # Удаляем письмо и вложения
        query = "SELECT url FROM attachments WHERE email_id = :email_id"
        attachments = await database.fetch_all(query, {"email_id": email_id})
        
        # Удаляем запись письма
        query = "DELETE FROM emails WHERE id = :email_id"
        await database.execute(query, {"email_id": email_id})

        if attachments:
            sender_name = email["sender"].split("@")[0]
            receiver_name = email["receiver"].split("@")[0]
            folder_path = f"{sender_name}/{receiver_name}/{email_id}/"

            try:
                # Удаляем вложения
                objects = minio_client.list_objects("emails", prefix=folder_path, recursive=True)
                for obj in objects:
                    minio_client.remove_object("emails", obj.object_name)
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Failed to delete attachments: {e}")

    return {"message": "Email visibility updated or email deleted"}