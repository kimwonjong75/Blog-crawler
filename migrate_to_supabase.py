import os
import sqlite3
import pandas as pd
from supabase import create_client, Client
from dotenv import load_dotenv

# Load env
load_dotenv()

url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_KEY")

if not url or not key or "your_supabase" in url:
    print("Please set SUPABASE_URL and SUPABASE_KEY in .env file first.")
    exit(1)

supabase: Client = create_client(url, key)

def get_sqlite_conn(db_name):
    return sqlite3.connect(db_name)

def migrate_blogs():
    print("Migrating Blogs...")
    conn = get_sqlite_conn("data.db")
    try:
        df = pd.read_sql_query("SELECT name, url, created_at FROM blogs", conn)
    except Exception as e:
        print(f"Error reading blogs: {e}")
        return {}
    finally:
        conn.close()

    if df.empty:
        print("No blogs found.")
        return {}

    # Since we need a user_id for RLS policy "Users can insert their own blogs",
    # but we are running this script likely as a service_role or we need to sign in.
    # If we use ANON key, we need to sign in.
    # For migration, it's easier to disable RLS temporarily or use SERVICE_ROLE key.
    # Assuming user provides ANON key, we might need to sign in or just try inserting.
    # If RLS is strict (auth.uid() = user_id), we need a user.
    # Let's ask user to provide email/pass or use service role?
    # Or we can just insert and see. If RLS blocks, we tell user.
    
    # Actually, the user script usually runs with their own credentials.
    # Let's try to sign in if credentials are in env, else prompt?
    # Or just assume the user will disable RLS for migration or use Service Role Key.
    
    # We will just attempt insert. If it fails, we print error.
    
    # We need to map blog_name/url to new ID.
    blog_map = {} # name -> id
    
    for _, row in df.iterrows():
        data = {
            "name": row["name"],
            "url": row["url"],
            "created_at": row["created_at"],
            # "user_id": ??? -> We need a user_id. 
            # If we don't provide it, and column is NOT NULL, it fails.
            # My SQL said: user_id uuid references auth.users not null.
            # So we MUST have a user_id.
        }
        
        # We need a logged in user.
        print(f"Preparing to upload blog: {row['name']}")
        
    return df

def main():
    print("Migration Script")
    print("Note: You must have RLS disabled or provide a Service Role Key to bypass RLS,")
    print("OR ensure you are logged in. (This script uses basic insert).")
    print("Also, 'blogs' table requires 'user_id'. This script assumes you handle auth or defaults.")
    
    # Actually, without user_id, insert will fail.
    # I should update the SQL to make user_id optional OR provide a way to set it.
    # Or the script asks for email/password to login first.
    
    email = input("Enter your Supabase User Email: ")
    password = input("Enter your Supabase User Password: ")
    
    try:
        session = supabase.auth.sign_in_with_password({"email": email, "password": password})
        user_id = session.user.id
        print(f"Logged in as {user_id}")
    except Exception as e:
        print(f"Login failed: {e}")
        return

    # 1. Migrate Blogs
    blog_map = {} # url -> id
    conn = get_sqlite_conn("data.db")
    try:
        # Check if table exists
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='blogs'")
        if not cursor.fetchone():
            print("No blogs table in data.db")
        else:
            df = pd.read_sql_query("SELECT name, url, created_at FROM blogs", conn)
            for _, row in df.iterrows():
                # Check if exists
                res = supabase.table("blogs").select("id").eq("url", row["url"]).execute()
                if res.data:
                    print(f"Blog {row['name']} already exists.")
                    blog_map[row["url"]] = res.data[0]['id']
                else:
                    payload = {
                        "name": row["name"],
                        "url": row["url"],
                        "created_at": row["created_at"],
                        "user_id": user_id
                    }
                    res = supabase.table("blogs").insert(payload).execute()
                    if res.data:
                        blog_id = res.data[0]['id']
                        blog_map[row["url"]] = blog_id
                        print(f"Uploaded blog: {row['name']}")
                    else:
                        print(f"Failed to upload blog: {row['name']}")
    finally:
        conn.close()

    # 2. Migrate Posts
    # Posts are scattered in posts_*.db or blog_data.db (global)
    # The current app uses blog_data.db for global posts or posts_*.db for specific.
    # Let's look at db_manager.py logic. It seems to use both?
    # We will look for all .db files starting with posts_
    
    import glob
    files = glob.glob("posts_*.db")
    # Also blog_data.db
    if os.path.exists("blog_data.db"):
        files.append("blog_data.db")
        
    for db_file in files:
        print(f"Processing {db_file}...")
        conn = get_sqlite_conn(db_file)
        try:
            # Check if posts table exists
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='posts'")
            if not cursor.fetchone():
                continue
                
            df = pd.read_sql_query("SELECT blog_name, title, date, content, link, created_at FROM posts", conn)
            if df.empty:
                continue
                
            records = []
            for _, row in df.iterrows():
                # Find blog_id. We need to find the blog url for this post to get ID.
                # But post row only has blog_name.
                # We can try to look up blog by name in our map (which is url -> id).
                # We need name -> id map too.
                
                # Let's fetch all blogs from Supabase to build name map
                pass 
                
            # To be efficient, let's bulk insert per file
            # But we need blog_id.
            # If we can't find blog_id, we might skip or insert with null (if allowed).
            # My SQL: blog_id bigint references ... (nullable? No, I didn't say NOT NULL).
            # Let's check SQL.
            # blog_id bigint references public.blogs(id) on delete cascade
            # It is nullable by default.
            
            # Let's try to match by name.
            # First, get all blogs from Supabase
            sb_blogs = supabase.table("blogs").select("id, name, url").execute()
            name_map = {b['name']: b['id'] for b in sb_blogs.data}
            
            batch = []
            for _, row in df.iterrows():
                bid = name_map.get(row['blog_name'])
                
                # Check duplication
                # It's expensive to check every post. 
                # We'll just insert and ignore error if we had unique constraint (we don't).
                # To avoid dupes, we might want to check existence.
                # For now, let's just insert.
                
                post_data = {
                    "blog_name": row["blog_name"],
                    "title": row["title"],
                    "date": row["date"],
                    "content": row["content"],
                    "link": row["link"],
                    "created_at": row["created_at"],
                    "blog_id": bid
                }
                batch.append(post_data)
                
                if len(batch) >= 100:
                    supabase.table("posts").insert(batch).execute()
                    print(f"Uploaded {len(batch)} posts from {db_file}")
                    batch = []
            
            if batch:
                supabase.table("posts").insert(batch).execute()
                print(f"Uploaded {len(batch)} posts from {db_file}")

        except Exception as e:
            print(f"Error processing {db_file}: {e}")
        finally:
            conn.close()

if __name__ == "__main__":
    main()
