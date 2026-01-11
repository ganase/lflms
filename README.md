# lflms
Management application of your little free library

## テスト手順
Mac

1.Open terminal
rm -rf lflms

2.git clone <このリポジトリのURL>

3.cd lflms

4.python3 -m venv .venv

5.source .venv/bin/activate

6.python -m pip install --upgrade pip

7.python -m pip install -r requirements.txt

8.export SECRET_KEY="0423"

9.
export OPENAI_API_KEY=""
export OPENAI_MODEL="gpt-4o-mini"
export OPENAI_BASE_URL="https://api.openai.com/v1"

5.python app.py

6.http://127.0.0.1:5001
