# Book API + Desktop Client

This project includes:
- A Flask REST API in `book.py`
- A Tkinter desktop client in `app.py`

## Prerequisites
- Python 3.11+
- VS Code Python extension (recommended)

## Setup
1. Create and activate a virtual environment.
2. Install dependencies:

```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## Run the API

```powershell
python book.py
```

The API runs on `http://127.0.0.1:5000`.

Useful endpoints:
- `GET /` : health check
- `GET /books` : list books
- `GET /books/<id>` : get one book
- `POST /books` : create book
- `PUT /books/<id>` : update book
- `DELETE /books/<id>` : delete book

## Run the Desktop App

Start the API first, then in another terminal run:

```powershell
python app.py
```

The desktop app reads from `http://127.0.0.1:5000/books`.

## Troubleshooting
- If `PIL` is unresolved in VS Code, select the project interpreter at `.venv\Scripts\python.exe`.
- If the desktop app cannot connect, verify `book.py` is running on port `5000`.
