import os

def load_env():
    try:
        from pathlib import Path
        env_path = Path('.env')
        if env_path.exists():
            for line in env_path.read_text(encoding='utf-8').splitlines():
                s = line.strip()
                if s and not s.startswith('#') and '=' in s:
                    k, v = s.split('=', 1)
                    k = k.strip(); v = v.strip()
                    os.environ.setdefault(k, v)
    except Exception:
        pass

def main():
    import google.generativeai as genai
    load_env()
    api = os.environ.get('GEMINI_API_KEY')
    if not api:
        raise SystemExit('No GEMINI_API_KEY in env')
    genai.configure(api_key=api)
    candidates = [
        'models/gemini-flash-latest',
        'models/gemini-2.5-flash',
        'models/gemini-pro-latest',
    ]
    last_err = None
    for name in candidates:
        try:
            m = genai.GenerativeModel(name)
            r = m.generate_content('테스트 메시지입니다')
            print('OK:', name)
            print(getattr(r, 'text', None) or str(r))
            return
        except Exception as e:
            last_err = e
    raise SystemExit(f'All candidates failed: {last_err}')

if __name__ == '__main__':
    main()
