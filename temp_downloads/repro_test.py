import os, sys, io, time, requests, shutil

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.storage import StorageManager
from core.server import ServerController

base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
test_storage_dir = os.path.join(base_dir, "test_storage_env")
shutil.rmtree(test_storage_dir, ignore_errors=True)
os.makedirs(test_storage_dir, exist_ok=True)

storage_mgr = StorageManager(test_storage_dir)
server_ctrl = ServerController(storage_mgr)
success, msg = server_ctrl.start(port=5601)
assert success, msg
time.sleep(1)
base_url = "http://127.0.0.1:5601"

# Build a folder with subfolders and unicode names
pub = os.path.join(test_storage_dir, "Shared_Storage", "Public", "photos")
os.makedirs(pub, exist_ok=True)
with open(os.path.join(pub, "a.txt"), "w") as f:
    f.write("hello " * 1000)
sub = os.path.join(pub, "sub dir")
os.makedirs(sub)
with open(os.path.join(sub, "b.bin"), "wb") as f:
    f.write(os.urandom(500000))

uni = os.path.join(pub, "\u0928\u0947\u092a\u093e\u0932\u0940 \u092b\u093e\u0907\u0932.txt")
with open(uni, "w") as f:
    f.write("unicode test")

print("== Test 1: download subfolder as zip ==")
r = requests.get(f"{base_url}/api/download?root=public&path=photos&zip=true")
print("status:", r.status_code, "content-type:", r.headers.get("content-type"), "bytes:", len(r.content))

print("== Test 2: whole-root zip (empty path) ==")
try:
    r = requests.get(f"{base_url}/api/download?root=public&path=&zip=true", timeout=5)
    print("status:", r.status_code, "bytes:", len(r.content))
except Exception as e:
    print("EXC:", repr(e))

server_ctrl.stop()
shutil.rmtree(test_storage_dir, ignore_errors=True)
print("DONE")