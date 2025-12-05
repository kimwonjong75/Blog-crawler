## 🚀 Supabase 통합 가이드

이 가이드는 여러 PC에서 블로그 데이터베이스에 액세스할 수 있도록 **Supabase**를 설정하는 방법을 설명합니다.

-----

## 1\. 프로젝트 설정 (Supabase)

1.  [Supabase](https://supabase.com/)로 이동하여 가입/로그인합니다.
2.  \*\*"New Project"\*\*를 클릭합니다.
3.  조직을 선택하고 다음 세부 정보를 입력합니다.
      * **이름(Name)**: Blog Crawler
      * **데이터베이스 비밀번호(Database Password)**: 강력한 비밀번호를 생성하고 저장합니다.
      * **지역(Region)**: 가까운 지역(예: Seoul, Tokyo)을 선택합니다.
4.  \*\*"Create new project"\*\*를 클릭합니다.
5.  데이터베이스가 프로비저닝될 때까지 기다립니다.

-----

## 2\. 데이터베이스 및 인증 구성

### 데이터베이스 스키마

1.  프로젝트 준비가 완료되면 **SQL 편집기** (왼쪽 아이콘)로 이동합니다.
2.  \*\*"New query"\*\*를 클릭합니다.
3.  이 저장소의 `supabase_setup.sql` 내용을 복사하여 쿼리 편집기에 붙여넣습니다.
4.  \*\*"Run"\*\*을 클릭하여 테이블과 보안 정책을 생성합니다.

### 인증 (Authentication)

1.  **Authentication** \> **Providers**로 이동합니다.
2.  **Email** 제공자가 활성화되어 있는지 확인합니다.
3.  (선택 사항) 이메일 인증 없이 빠르게 테스트하려면 **Authentication** \> **URL Configuration**에서 "Confirm email"을 비활성화하거나, 실제 이메일을 사용하여 인증합니다.

-----

## 3\. 클라이언트 설정

### 웹 클라이언트 (`supabase_client.html`)

블로그를 관리하고 게시물을 볼 수 있도록 간단한 웹 인터페이스인 `supabase_client.html`을 만들었습니다.

1.  브라우저에서 `supabase_client.html`을 엽니다.
2.  **Supabase URL**과 **Anon Key**를 요청합니다.
      * 이 값은 Supabase 대시보드 \> **Project Settings** \> **API**에서 찾을 수 있습니다.
3.  이를 입력하여 연결합니다.
4.  이메일/비밀번호로 가입합니다.
5.  로그인하면 블로그를 추가하고 게시물을 볼 수 있습니다.

### 환경 변수 (Python/Streamlit용)

Python 백엔드에 Supabase를 통합할 계획이라면:

1.  `.env` 파일에 다음을 추가합니다.
    ```
    SUPABASE_URL=your_supabase_url
    SUPABASE_KEY=your_supabase_anon_key
    ```
2.  Python 클라이언트를 설치해야 합니다.
    ```bash
    pip install supabase
    ```
3.  SQLite 대신 Supabase를 사용하도록 `app.py` 또는 `db_manager.py`를 업데이트합니다 (마이그레이션 필요).

-----

## 4\. 보안

  * **RLS (행 수준 보안, Row Level Security)**: `supabase_setup.sql`에서 RLS를 활성화했습니다.
      * Blogs: 공개적으로 읽을 수 있지만, 생성자만 편집/삭제할 수 있습니다.
      * Posts: 공개적으로 읽을 수 있으며, 인증된 사용자는 추가/편집할 수 있습니다.
  * **HTTPS**: Supabase API는 기본적으로 HTTPS입니다.
  * **환경 변수**: `.env` 파일을 커밋하거나 공개 파일에 키를 하드코딩하지 마십시오. `supabase_client.html`에서는 하드코딩을 방지하기 위해 키를 사용자가 입력합니다 (Local Storage에 저장됨).

-----

## 5\. 테스트 및 배포

  * **테스트**: 다른 브라우저나 장치에서 `supabase_client.html`을 엽니다 (배포된 경우 호스팅된 URL 사용).
  * **배포**: `supabase_client.html`을 Vercel, Netlify 또는 GitHub Pages에 호스팅할 수 있습니다.
  * **성능**: Supabase 대시보드를 사용하여 데이터베이스 사용량을 모니터링합니다.

## 다음 단계

  * Python 스크립트를 사용하여 기존 데이터를 SQLite에서 Supabase로 마이그레이션합니다.
  * Streamlit 앱을 클라우드에 연결하려면 로컬 SQLite 대신 Supabase에서 데이터를 가져오도록 `app.py`를 업데이트합니다.

-----

혹시 **SQLite에서 Supabase로 데이터를 마이그레이션하는 Python 스크립트** 예시를 만들어 드릴까요?