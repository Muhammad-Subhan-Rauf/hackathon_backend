from supabase import create_client

url = "https://uvvmrsbpgaoobnyhcuov.supabase.co"
key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InV2dm1yc2JwZ2Fvb2JueWhjdW92Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTExMTIxMjAsImV4cCI6MjA2NjY4ODEyMH0.9QurqCroiohnziqAxl357kV44waWcPUejBnoctB4Nc4"

supabase = create_client(url, key)

res = supabase.rpc("add_rider_rating_count").execute()
if res.error:
    print("❌ RPC error:", res.error.message)
else:
    print("✅ Column added or already existed.")
