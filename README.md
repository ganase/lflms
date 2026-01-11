# lflms
Management application of your little free library

## テスト手順
Mac

Open terminal

rm -rf lflms

git clone <このリポジトリのURL>

cd lflms

python3 -m venv .venv

source .venv/bin/activate

python -m pip install --upgrade pip

python -m pip install -r requirements.txt

export SECRET_KEY="0423"

export OPENAI_API_KEY=""

export OPENAI_MODEL="gpt-4o-mini"

export OPENAI_BASE_URL="https://api.openai.com/v1"

python app.py

http://127.0.0.1:5001
