"""Comprehensive integration test suite for Antigravity Network Share & Vault."""
import os
import sys
import time
import requests
import io

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def run_tests():
    from core.storage import StorageManager
    from core.server import ServerController

    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    test_storage_dir = os.path.join(base_dir, "test_storage_env")
    os.makedirs(test_storage_dir, exist_ok=True)

    storage_mgr = StorageManager(test_storage_dir)
    server_ctrl = ServerController(storage_mgr)

    test_port = 5599
    success, msg = server_ctrl.start(port=test_port)
    assert success, f"Failed to start test server: {msg}"
    time.sleep(1)

    base_url = f"http://127.0.0.1:{test_port}"
    print(f"[TEST] Server started on {base_url}")

    try:
        # 1. Test /api/status
        r = requests.get(f"{base_url}/api/status")
        assert r.status_code == 200, f"Status failed: {r.status_code}"
        status_data = r.json()
        assert status_data["status"] == "online"
        assert "qr_code" in status_data
        print("[PASS] 1. /api/status returned online and QR code.")

        # 2. Test /api/drives
        r = requests.get(f"{base_url}/api/drives")
        assert r.status_code == 200
        drives_data = r.json()
        root_ids = [d["id"] for d in drives_data["roots"]]
        assert "public" in root_ids and "vault" in root_ids
        print("[PASS] 2. /api/drives returned public and vault roots.")

        # 3. Test /api/files on Public
        r = requests.get(f"{base_url}/api/files?root=public")
        assert r.status_code == 200
        print("[PASS] 3. /api/files?root=public accessible without auth.")

        # 4. Test upload to Public
        dummy_content = b"Hello, this is a test file for local network file transfer."
        files = {'files': ('test_doc.txt', io.BytesIO(dummy_content), 'text/plain')}
        r = requests.post(f"{base_url}/api/upload", data={'root': 'public', 'path': ''}, files=files)
        assert r.status_code == 200, f"Upload failed: {r.text}"
        print("[PASS] 4. /api/upload successfully saved test_doc.txt.")

        # 5. Verify file listed in Public
        r = requests.get(f"{base_url}/api/files?root=public")
        items = r.json()["items"]
        file_names = [i["name"] for i in items]
        assert "test_doc.txt" in file_names
        print("[PASS] 5. Uploaded file appears in file listing.")

        # 6. Test /api/preview for text file
        r = requests.get(f"{base_url}/api/preview?root=public&path=test_doc.txt")
        assert r.status_code == 200
        assert r.content == dummy_content
        print("[PASS] 6. /api/preview streams file correctly.")

        # 7. Test /api/download for file
        r = requests.get(f"{base_url}/api/download?root=public&path=test_doc.txt")
        assert r.status_code == 200
        assert r.content == dummy_content
        print("[PASS] 7. /api/download returns file attachment.")

        # 8. Test Private Vault unauthorized access (must be 401)
        r = requests.get(f"{base_url}/api/files?root=vault")
        assert r.status_code == 401
        print("[PASS] 8. Vault unauthorized access correctly blocked (401).")

        # 9. Test Vault wrong password
        r = requests.post(f"{base_url}/api/auth/vault", json={"password": "wrong_password"})
        assert r.status_code == 403
        print("[PASS] 9. Vault rejected incorrect password (403).")

        # 10. Test Vault correct password
        r = requests.post(f"{base_url}/api/auth/vault", json={"password": "admin123"})
        assert r.status_code == 200
        token = r.json()["token"]
        assert token
        print("[PASS] 10. Vault accepted correct password and issued session token.")

        # 11. Test Vault access with token
        headers = {"X-Vault-Token": token}
        r = requests.get(f"{base_url}/api/files?root=vault", headers=headers)
        assert r.status_code == 200
        print("[PASS] 11. Vault accessible with session token.")

        # 12. Test upload to Vault with token
        v_content = b"Top secret admin data inside secure vault."
        files = {'files': ('secret.txt', io.BytesIO(v_content), 'text/plain')}
        r = requests.post(f"{base_url}/api/upload", data={'root': 'vault', 'path': ''}, files=files, headers=headers)
        assert r.status_code == 200
        print("[PASS] 12. Authenticated upload to Vault succeeded.")

        # 13. Test ZIP archive download of folder
        r = requests.get(f"{base_url}/api/download?root=public&path=&zip=true")
        assert r.status_code == 200
        assert r.headers.get("content-type") == "application/zip"
        assert len(r.content) > 0
        print("[PASS] 13. Folder zipped and downloaded successfully.")

        # 14. Test clean up / delete
        r = requests.post(f"{base_url}/api/delete", json={"root": "public", "path": "test_doc.txt"})
        assert r.status_code == 200
        print("[PASS] 14. File deletion endpoint verified.")

        # 15. Test Sharing to USB / External Drives
        simulated_usb_dir = os.path.join(test_storage_dir, "Simulated_USB_Drive")
        os.makedirs(simulated_usb_dir, exist_ok=True)
        storage_mgr.set_usb_share(simulated_usb_dir, "FlashDrive_E", enabled=True, read_only=False)
        
        # Verify drive is listed as writable
        r = requests.get(f"{base_url}/api/drives")
        assert r.status_code == 200
        drive_roots = [d for d in r.json()["roots"] if d["type"] == "usb"]
        assert len(drive_roots) > 0
        usb_root_id = drive_roots[0]["id"]
        assert drive_roots[0]["read_only"] is False
        print(f"[PASS] 15. Simulated drive '{usb_root_id}' mounted with writable/upload permissions.")

        # Upload file directly to Drive
        usb_file_content = b"Data transferred directly into USB drive."
        files = {'files': ('direct_drive_file.txt', io.BytesIO(usb_file_content), 'text/plain')}
        r = requests.post(f"{base_url}/api/upload", data={'root': usb_root_id, 'path': ''}, files=files)
        assert r.status_code == 200
        print("[PASS] 16. Upload directly to external Drive succeeded.")

        # 17. Test /api/copy: Share a file from Vault to the Drive
        r = requests.post(
            f"{base_url}/api/copy",
            json={"src_root": "vault", "src_path": "secret.txt", "dest_root": usb_root_id, "dest_path": ""},
            headers=headers
        )
        assert r.status_code == 200
        print("[PASS] 17. /api/copy successfully copied file from Vault to Drive.")

        # Verify both files exist on the Drive
        r = requests.get(f"{base_url}/api/files?root={usb_root_id}")
        assert r.status_code == 200
        item_names = [i["name"] for i in r.json()["items"]]
        assert "direct_drive_file.txt" in item_names and "secret.txt" in item_names
        # 19. Test /api/thumbnail for Public file
        r = requests.get(f"{base_url}/api/thumbnail?root={usb_root_id}&path=direct_drive_file.txt")
        assert r.status_code == 200
        assert r.headers.get("content-type") == "image/jpeg"
        assert len(r.content) > 0
        print("[PASS] 19. /api/thumbnail generated visual preview thumbnail for file.")

        # 20. Test /api/thumbnail for Vault file (must be 401 without auth, 200 with auth)
        r = requests.get(f"{base_url}/api/thumbnail?root=vault&path=secret.txt")
        assert r.status_code == 401
        r = requests.get(f"{base_url}/api/thumbnail?root=vault&path=secret.txt", headers=headers)
        assert r.status_code == 200
        print("[PASS] 20. Vault thumbnail endpoint security verified (401 without auth, 200 with auth).")

        print("\n===========================================================")
        print(" ALL 20 AUTOMATED API, THUMBNAIL & SECURITY TESTS PASSED!  ")
        print("===========================================================\n")

    finally:
        server_ctrl.stop()
        # Clean up test dir
        import shutil
        shutil.rmtree(test_storage_dir, ignore_errors=True)

if __name__ == "__main__":
    run_tests()
