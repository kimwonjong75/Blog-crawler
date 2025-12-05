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
    models = [
        (m.name, getattr(m, 'supported_generation_methods', []))
        for m in genai.list_models()
    ]
    for name, methods in models:
        print(f"{name} | methods: {','.join(methods)}")

if __name__ == '__main__':
    main()
