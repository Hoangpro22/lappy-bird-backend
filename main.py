from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from pathlib import Path
import threading
import tempfile
import json
import os
import logging

logging.basicConfig(level=logging.INFO)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = Path(__file__).resolve().parent
DB_FILE = BASE_DIR / "database.json"
print("📁 Database path:", DB_FILE.resolve())
_lock = threading.Lock()

# Đảm bảo file DB tồn tại và hợp lệ
def ensure_db():
    if not DB_FILE.exists():
        DB_FILE.write_text("[]", encoding="utf-8")
    else:
        try:
            json.loads(DB_FILE.read_text(encoding="utf-8"))
        except Exception:
            logging.warning("database.json hỏng, ghi lại thành mảng rỗng")
            DB_FILE.write_text("[]", encoding="utf-8")

ensure_db()

def read_scores():
    with _lock:
        try:
            return json.loads(DB_FILE.read_text(encoding="utf-8"))
        except Exception as e:
            logging.error("Lỗi đọc DB: %s", e)
            DB_FILE.write_text("[]", encoding="utf-8")
            return []

def write_scores(data):
    # Ghi an toàn: ghi file tạm trong cùng thư mục rồi replace
    with _lock:
        tmp = None
        try:
            tmp_fd, tmp_path = tempfile.mkstemp(dir=str(BASE_DIR), prefix="db_", suffix=".tmp")
            tmp = tmp_path
            with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_path, str(DB_FILE))
        except Exception as e:
            logging.error("Lỗi ghi DB: %s", e)
            if tmp and os.path.exists(tmp):
                try:
                    os.remove(tmp)
                except:
                    pass
            raise

class ScoreSubmission(BaseModel):
    name: str = Field(..., min_length=1)
    score: int = Field(ge=0)

@app.get("/")
def home():
    return {"message": "✅ API Flappy Bird đang hoạt động"}

@app.get("/scores")
def get_scores():
    data = read_scores()
    try:
        sorted_data = sorted(data, key=lambda x: int(x.get("score", 0)), reverse=True)[:10]
    except Exception:
        sorted_data = data[:10]
    return sorted_data

@app.post("/submit", status_code=status.HTTP_201_CREATED)
def submit_score(payload: ScoreSubmission):
    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Tên không được trống!")
    score = int(payload.score)

    data = read_scores()
    updated = False

    # ✅ Kiểm tra nếu user đã có điểm -> chỉ cập nhật nếu điểm mới cao hơn
    for entry in data:
        if entry["name"].lower() == name.lower():
            if score > entry["score"]:
                entry["score"] = score
            updated = True
            break

    # ✅ Nếu chưa có thì thêm mới
    if not updated:
        data.append({"name": name, "score": score})

    # ✅ Ghi lại dữ liệu
    write_scores(data)

    return {"message": "Lưu điểm thành công!"}



# ================================================================
# 👇 THÊM PHẦN QUẢN LÝ NGƯỜI DÙNG (ĐĂNG KÝ / ĐĂNG NHẬP)
# ================================================================
import hashlib

USERS_FILE = BASE_DIR / "users.json"

def ensure_user_db():
    if not USERS_FILE.exists():
        USERS_FILE.write_text("[]", encoding="utf-8")
    else:
        try:
            json.loads(USERS_FILE.read_text(encoding="utf-8"))
        except Exception:
            logging.warning("users.json hỏng, ghi lại thành mảng rỗng")
            USERS_FILE.write_text("[]", encoding="utf-8")

ensure_user_db()

def read_users():
    with _lock:
        try:
            return json.loads(USERS_FILE.read_text(encoding="utf-8"))
        except Exception as e:
            logging.error("Lỗi đọc users.json: %s", e)
            USERS_FILE.write_text("[]", encoding="utf-8")
            return []

def write_users(data):
    with _lock:
        tmp = None
        try:
            tmp_fd, tmp_path = tempfile.mkstemp(dir=str(BASE_DIR), prefix="users_", suffix=".tmp")
            tmp = tmp_path
            with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_path, str(USERS_FILE))
        except Exception as e:
            logging.error("Lỗi ghi users.json: %s", e)
            if tmp and os.path.exists(tmp):
                os.remove(tmp)
            raise

def hash_password(pw: str) -> str:
    return hashlib.sha256(pw.encode("utf-8")).hexdigest()

class UserCredentials(BaseModel):
    username: str = Field(..., min_length=3, max_length=20)
    password: str = Field(..., min_length=3)

@app.post("/register")
def register_user(creds: UserCredentials):
    users = read_users()
    if any(u["username"] == creds.username for u in users):
        raise HTTPException(status_code=400, detail="Tên người dùng đã tồn tại!")

    hashed_pw = hash_password(creds.password)
    users.append({"username": creds.username, "password": hashed_pw})
    write_users(users)
    return {"message": "Đăng ký thành công!"}

@app.post("/login")
def login_user(creds: UserCredentials):
    users = read_users()
    hashed_pw = hash_password(creds.password)
    for u in users:
        if u["username"] == creds.username and u["password"] == hashed_pw:
            return {"message": "Đăng nhập thành công!"}
    raise HTTPException(status_code=401, detail="Sai tên người dùng hoặc mật khẩu!")


# ================================================================
# 👆 HẾT PHẦN THÊM MỚI
# ================================================================

if __name__ == "__main__":
    import uvicorn
    import os
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)