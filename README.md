# Shorts Archive

좋아요 누른 YouTube Shorts를 동기화해서 개인 아카이브로 보여주는 FastAPI 앱입니다.

## Project Structure

```text
app/
  api/          FastAPI route modules
  db/           Supabase access layer
  services/     YouTube and external service logic
  main.py       FastAPI app factory and middleware setup
public/         Static frontend files
database/       SQL schema and database assets
scripts/        Local utility scripts
main.py         Backward-compatible local entrypoint
```

## Run

```bash
pip install -r requirements.txt
python main.py
```

or:

```bash
uvicorn app.main:app --reload
```
