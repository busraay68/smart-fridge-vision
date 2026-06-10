# deploy.py — Smart Fridge Unified Deployer & Git Pusher
import os
import sys
import zipfile
import time
import subprocess
import socket
import paramiko

PI_USER = "pi"
PI_PASS = "eren"
PI_IPS = ["192.168.1.107", "192.168.1.106"]

def check_ip_ssh(ip):
    """Checks if port 22 (SSH) is open on the target IP."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(1.0)
    try:
        s.connect((ip, 22))
        s.close()
        return True
    except:
        return False

def zip_source_files(zip_path):
    """Zips only the source code files and folders (excluding venv, models, uploads, etc.)."""
    source_dirs = ['templates', 'static/css', 'static/js']
    source_files = ['app.py', 'db.py', 'detection.py', 'gemini_service.py', 'theme.py', 'vision_sync.py', 'package-b-vision/vision_engine.py']
    
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        # Zip files
        for f in source_files:
            if os.path.exists(f):
                zipf.write(f)
                
        # Zip directories
        for d in source_dirs:
            if os.path.exists(d):
                for root, dirs, files in os.walk(d):
                    for file in files:
                        file_path = os.path.join(root, file)
                        zipf.write(file_path)

def main():
    start_time = time.time()
    print("[DEPLOY] Tek Tikla Dagitim ve Git Yedekleme Baslatiliyor...\n")
    
    # ─── ADIM 1: Aktif Pi IP Adresini Bul ───
    print("[1/5] Raspberry Pi bağlantısı sorgulanıyor...")
    active_ip = None
    for ip in PI_IPS:
        if check_ip_ssh(ip):
            active_ip = ip
            break
            
    if not active_ip:
        print("HATA: Pi bulunamadi! Lutfen ag baglantisini kontrol edin.")
        sys.exit(1)
    print(f"   -> Aktif Pi IP adresi: {active_ip}")
    
    # ─── ADIM 2: Git Commit & Push ───
    print("\n[2/5] Git'e yedekleniyor...")
    try:
        subprocess.run(["git", "add", "."], check=True)
        # Check if there are changes to commit
        status = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True)
        if status.stdout.strip():
            commit_msg = f"Auto deploy backup - {time.strftime('%Y-%m-%d %H:%M:%S')}"
            subprocess.run(["git", "commit", "-m", commit_msg], check=True)
            subprocess.run(["git", "push"], check=True)
            print("   -> Git yedeklemesi ve push işlemi tamamlandı.")
        else:
            print("   -> Değişiklik yok, git push atlandı.")
    except Exception as git_err:
        print(f"   [WARNING] Git adımı tamamlanamadı (Hata: {git_err}), yayına devam ediliyor...")

    # ─── ADIM 3: Kaynak Dosyaları Sıkıştır ───
    print("\n[3/5] Kaynak kodlar paketleniyor...")
    zip_filename = "project_temp.zip"
    if os.path.exists(zip_filename):
        os.remove(zip_filename)
        
    try:
        zip_source_files(zip_filename)
        size_kb = os.path.getsize(zip_filename) / 1024.0
        print(f"   -> Paket oluşturuldu: {zip_filename} ({size_kb:.1f} KB)")
    except Exception as e:
        print(f"Paketleme Hatasi: {e}")
        sys.exit(1)
        
    # ─── ADIM 4: Pi'ye Gönder ve Aç ───
    print("\n[4/5] Paket Pi'ye yükleniyor ve açılıyor...")
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    try:
        ssh.connect(active_ip, username=PI_USER, password=PI_PASS)
        
        # SFTP ile yükle
        sftp = ssh.open_sftp()
        sftp.put(zip_filename, f"/home/{PI_USER}/SmartFridge/{zip_filename}")
        sftp.close()
        print("   -> Zip dosyası başarıyla yüklendi.")
        
        # Zip'i aç ve temizle
        commands = [
            f"unzip -o /home/{PI_USER}/SmartFridge/{zip_filename} -d /home/{PI_USER}/SmartFridge/",
            f"rm /home/{PI_USER}/SmartFridge/{zip_filename}"
        ]
        
        for cmd in commands:
            stdin, stdout, stderr = ssh.exec_command(cmd)
            stdout.read() # Wait for execution
            
        print("   -> Paket Pi üzerinde açıldı ve temizlendi.")
        
    except Exception as e:
        print(f"SSH / Transfer Hatasi: {e}")
        if os.path.exists(zip_filename):
            os.remove(zip_filename)
        sys.exit(1)
    finally:
        if os.path.exists(zip_filename):
            os.remove(zip_filename)

    # ─── ADIM 5: Servisi Yeniden Başlat ───
    print("\n[5/5] Servis yeniden başlatılıyor...")
    try:
        cmd = f"echo {PI_PASS} | sudo -S systemctl restart smartfridge"
        stdin, stdout, stderr = ssh.exec_command(cmd)
        stdout.read() # Wait
        
        # Durumu kontrol et
        cmd_status = f"echo {PI_PASS} | sudo -S systemctl status smartfridge"
        stdin, stdout, stderr = ssh.exec_command(cmd_status)
        status_output = stdout.read().decode('utf-8', errors='ignore')
        
        if "active (running)" in status_output:
            print("   -> Servis basariyla yeniden baslatildi ve aktif durumda! [OK]")
        else:
            print("   [WARNING] Servis baslatilamamis olabilir! Lutfen Pi loglarini kontrol edin.")
            
    except Exception as e:
        print(f"Servis Yeniden Baslatma Hatasi: {e}")
    finally:
        ssh.close()
        
    duration = time.time() - start_time
    print(f"\n[BASARILI] Yayina alim {duration:.1f} saniyede tamamlandi!")

if __name__ == "__main__":
    main()
