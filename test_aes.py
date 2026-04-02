import sys
import base64
import hashlib
from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad

encrypted_pw = "SdF6Qm7PESath6bj8YNVWw==:fUMVLp737Y9b9faMA9A1ZGKM9yOtvvD9K5qVxbQUMns="
expected_plain = "aJrw8QaxbMQxZVodpsjq"
key_str = "awsaesproxykey"

iv_b64, cipher_b64 = encrypted_pw.split(':')
iv = base64.b64decode(iv_b64)
cipher = base64.b64decode(cipher_b64)

def try_decrypt(key):
    try:
        aes = AES.new(key, AES.MODE_CBC, iv)
        pt = unpad(aes.decrypt(cipher), AES.block_size).decode('utf-8')
        if pt == expected_plain:
            return True, pt
        return False, pt
    except Exception as e:
        return False, str(e)

# Attempt 1: SHA256
key_sha256 = hashlib.sha256(key_str.encode()).digest()
success, pt = try_decrypt(key_sha256)
print(f"SHA256: {success} -> {pt}")

# Attempt 2: MD5 (padded to 32? No, md5 is 16. AES-128)
key_md5 = hashlib.md5(key_str.encode()).digest()
success, pt = try_decrypt(key_md5)
print(f"MD5 (AES-128): {success} -> {pt}")

# Attempt 3: Key padded with zeros
key_padded = key_str.encode().ljust(32, b'\0')
success, pt = try_decrypt(key_padded)
print(f"Padded zeros: {success} -> {pt}")

# Attempt 4: Key padded with repeating
key_rep = (key_str * 3)[:32].encode()
success, pt = try_decrypt(key_rep)
print(f"Repeating: {success} -> {pt}")

# Attempt 5: Hashlib MD5 doubled?
key_md5_32 = key_md5 * 2
success, pt = try_decrypt(key_md5_32)
print(f"MD5 Doubled: {success} -> {pt}")
