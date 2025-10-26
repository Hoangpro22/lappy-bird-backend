from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from pathlib import Path
import threading, tempfile, json, os, logging, hashlib

logging.basicConfig(level=logging.INFO)
app = FastAPI()

# CORS (cho phép frontend truy cập)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = Path(__file__).resolve().parent
DB_FILE = BASE_DIR / "database.json"
USERS_FILE = BASE_DIR / "users.json"
_lock = threading.Lock()

# =====================================================
# 📁 TẠO FILE DATABASE
# =====================================================
def ensure_file(path):
    if not path.exists():
        path.write_text("[]", encoding="utf-8")
    else:
        try:
            json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            logging.warning(f"{path.name} hỏng, reset lại")
            path.write_text("[]", encoding="utf-8")

ensure_file(DB_FILE)
ensure_file(USERS_FILE)

# =====================================================
# 🧩 HÀM XỬ LÝ CƠ BẢN
# =====================================================
def read_json(path):
    with _lock:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception as e:
            logging.error("Lỗi đọc file %s: %s", path, e)
            path.write_text("[]", encoding="utf-8")
            return []

def write_json(path, data):
    with _lock:
        tmp = None
        try:
            tmp_fd, tmp_path = tempfile.mkstemp(dir=str(BASE_DIR), prefix="tmp_", suffix=".json")
            tmp = tmp_path
            with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
                f.flush(); os.fsync(f.fileno())
            os.replace(tmp_path, str(path))
        except Exception as e:
            logging.error("Lỗi ghi file %s: %s", path, e)
            if tmp and os.path.exists(tmp): os.remove(tmp)
            raise

# =====================================================
# 🧮 XỬ LÝ BẢNG ĐIỂM
# =====================================================
class ScoreSubmission(BaseModel):
    name: str = Field(..., min_length=1)
    score: int = Field(ge=0)

@app.get("/")
def home():
    return {"message": "✅ API Flappy Bird đang hoạt động"}

@app.get("/scores")
def get_scores():
    data = read_json(DB_FILE)
    sorted_data = sorted(data, key=lambda x: x.get("score", 0), reverse=True)[:10]
    return sorted_data

@app.post("/submit", status_code=status.HTTP_201_CREATED)
def submit_score(payload: ScoreSubmission):
    name, score = payload.name.strip(), int(payload.score)
    if not name:
        raise HTTPException(status_code=400, detail="Tên không được trống!")

    data = read_json(DB_FILE)
    updated = False

    for entry in data:
        if entry["name"].lower() == name.lower():
            if score > entry["score"]:
                entry["score"] = score
            updated = True
            break

    if not updated:
        data.append({"name": name, "score": score})

    write_json(DB_FILE, data)
    return {"message": "Lưu điểm thành công!"}

# =====================================================
# 👥 ĐĂNG KÝ / ĐĂNG NHẬP
# =====================================================
def hash_password(pw: str) -> str:
    return hashlib.sha256(pw.encode("utf-8")).hexdigest()

class UserCredentials(BaseModel):
    username: str = Field(..., min_length=3, max_length=20)
    password: str = Field(..., min_length=3)

@app.post("/register")
def register_user(creds: UserCredentials):
    users = read_json(USERS_FILE)
    if any(u["username"] == creds.username for u in users):
        raise HTTPException(status_code=400, detail="Tên người dùng đã tồn tại!")
    users.append({"username": creds.username, "password": hash_password(creds.password)})
    write_json(USERS_FILE, users)
    return {"message": "Đăng ký thành công!"}

@app.post("/login")
def login_user(creds: UserCredentials):
    users = read_json(USERS_FILE)
    hashed_pw = hash_password(creds.password)
    for u in users:
        if u["username"] == creds.username and u["password"] == hashed_pw:
            return {"message": "Đăng nhập thành công!"}
    raise HTTPException(status_code=401, detail="Sai tên hoặc mật khẩu!")

# =====================================================
# 🚀 CHẠY SERVER LOCAL
# =====================================================
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)
