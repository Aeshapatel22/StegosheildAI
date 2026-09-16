import streamlit as st
import numpy as np
from PIL import Image
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
import hashlib
import secrets
import struct
import io
import os
import cv2
import tempfile
import subprocess

# ============================================================
# STEGOSHIELD AI
# Multimedia Steganography Web Application
# ============================================================

st.set_page_config(
    page_title="StegoShield AI",
    page_icon="🛡️",
    layout="wide"
)

# ============================================================
# CUSTOM CSS
# ============================================================

st.markdown("""
<style>

.stApp {
    background:
        radial-gradient(circle at 10% 10%, #24105c 0%, transparent 30%),
        radial-gradient(circle at 90% 20%, #063c59 0%, transparent 30%),
        radial-gradient(circle at 50% 90%, #401047 0%, transparent 30%),
        #080b18;
    color: white;
}

.main-title {
    text-align: center;
    font-size: 55px;
    font-weight: 800;
    background: linear-gradient(
        90deg,
        #00eaff,
        #8a5cff,
        #ff4fd8
    );
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    margin-bottom: 10px;
}

.subtitle {
    text-align: center;
    color: #c8c9dc;
    font-size: 19px;
    margin-bottom: 40px;
}

.card {
    padding: 25px;
    border-radius: 20px;
    background: rgba(255,255,255,0.07);
    border: 1px solid rgba(255,255,255,0.12);
    backdrop-filter: blur(15px);
    margin-bottom: 20px;
}

.feature-card {
    text-align: center;
    padding: 25px;
    border-radius: 20px;
    background: linear-gradient(
        135deg,
        rgba(0,234,255,0.10),
        rgba(138,92,255,0.12),
        rgba(255,79,216,0.10)
    );
    border: 1px solid rgba(255,255,255,0.12);
}

h1, h2, h3 {
    color: white;
}

.stButton > button {
    width: 100%;
    border-radius: 12px;
    border: none;
    background: linear-gradient(
        90deg,
        #00bcd4,
        #7c4dff,
        #e040fb
    );
    color: white;
    font-weight: 700;
    padding: 12px;
}

.stButton > button:hover {
    transform: scale(1.02);
}

</style>
""", unsafe_allow_html=True)


# ============================================================
# CRYPTOGRAPHY
# ============================================================

MAGIC = b"STEGOSHIELD1"


def derive_key(password: str, salt: bytes) -> bytes:
    """
    Derive a 256-bit encryption key from password.
    """
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=300_000
    )

    return kdf.derive(password.encode("utf-8"))


def encrypt_message(message: str, password: str) -> bytes:
    """
    Encrypt secret message using AES-GCM.
    """

    salt = secrets.token_bytes(16)
    nonce = secrets.token_bytes(12)

    key = derive_key(password, salt)

    aes = AESGCM(key)

    encrypted = aes.encrypt(
        nonce,
        message.encode("utf-8"),
        None
    )

    # MAGIC + salt + nonce + encrypted data
    return MAGIC + salt + nonce + encrypted


def decrypt_message(data: bytes, password: str) -> str:

    if not data.startswith(MAGIC):
        raise ValueError("No valid StegoShield message found.")

    position = len(MAGIC)

    salt = data[position:position + 16]
    position += 16

    nonce = data[position:position + 12]
    position += 12

    encrypted = data[position:]

    key = derive_key(password, salt)

    aes = AESGCM(key)

    decrypted = aes.decrypt(
        nonce,
        encrypted,
        None
    )

    return decrypted.decode("utf-8")


# ============================================================
# BIT UTILITIES
# ============================================================

def bytes_to_bits(data: bytes):

    bits = []

    for byte in data:

        for i in range(7, -1, -1):
            bits.append((byte >> i) & 1)

    return bits


def bits_to_bytes(bits):

    output = bytearray()

    for i in range(0, len(bits), 8):

        byte = 0

        for bit in bits[i:i + 8]:

            byte = (byte << 1) | bit

        output.append(byte)

    return bytes(output)


def make_payload(message: str, password: str):

    encrypted = encrypt_message(
        message,
        password
    )

    # Store encrypted payload length
    header = struct.pack(
        ">I",
        len(encrypted)
    )

    return header + encrypted


def extract_payload(data: bytes, password: str):

    if len(data) < 4:
        raise ValueError("No hidden message found.")

    length = struct.unpack(
        ">I",
        data[:4]
    )[0]

    if length <= 0 or length > len(data) - 4:
        raise ValueError("Invalid hidden data.")

    encrypted = data[4:4 + length]

    return decrypt_message(
        encrypted,
        password
    )


# ============================================================
# IMAGE STEGANOGRAPHY
# ============================================================

def image_capacity(image):

    arr = np.array(image)

    return arr.size // 8


def image_encode(image, message, password):

    image = image.convert("RGB")

    arr = np.array(image).copy()

    payload = make_payload(
        message,
        password
    )

    bits = bytes_to_bits(payload)

    flat = arr.reshape(-1)

    if len(bits) > len(flat):

        raise ValueError(
            f"Message is too large. "
            f"Available capacity: {len(flat)//8} bytes."
        )

    for i, bit in enumerate(bits):

        flat[i] = (flat[i] & 254) | bit

    result = flat.reshape(arr.shape)

    return Image.fromarray(result)
def image_decode(image, password):

    image = image.convert("RGB")
    arr = np.array(image)
    flat = arr.reshape(-1)

    header_bits = [
        int(flat[i] & 1)
        for i in range(32)
    ]

    header = bits_to_bytes(header_bits)

    length = struct.unpack(
        ">I",
        header
    )[0]

    if length <= 0:
        raise ValueError(
            "No hidden message found."
        )

    total_bits = 32 + (length * 8)

    if total_bits > len(flat):
        raise ValueError(
            "Invalid hidden data or corrupted image."
        )

    payload_bits = [
        int(flat[i] & 1)
        for i in range(
            32,
            total_bits
        )
    ]

    encrypted_payload = bits_to_bytes(
        payload_bits
    )

    return decrypt_message(
        encrypted_payload,
        password
    )

# ============================================================
# AUDIO STEGANOGRAPHY
# WAV PCM LSB
# ============================================================

def audio_encode(input_file, output_file, message, password):

    import wave

    with wave.open(input_file, "rb") as wav:

        params = wav.getparams()
        frames = wav.readframes(
            wav.getnframes()
        )

    audio = bytearray(frames)

    payload = make_payload(
        message,
        password
    )

    bits = bytes_to_bits(payload)

    if len(bits) > len(audio):

        raise ValueError(
            "Secret message is too large "
            "for this WAV file."
        )

    for i, bit in enumerate(bits):

        audio[i] = (
            audio[i] & 254
        ) | bit

    with wave.open(
        output_file,
        "wb"
    ) as wav:

        wav.setparams(params)
        wav.writeframes(audio)

def audio_decode(input_file, password):

    import wave

    with wave.open(input_file, "rb") as wav:
        frames = wav.readframes(wav.getnframes())

    audio = bytearray(frames)

    # Read first 32 bits = encrypted payload length
    header_bits = [
        audio[i] & 1
        for i in range(32)
    ]

    header = bits_to_bytes(header_bits)

    length = struct.unpack(
        ">I",
        header
    )[0]

    if length <= 0:
        raise ValueError(
            "No hidden message found."
        )

    total_bits = 32 + (length * 8)

    if total_bits > len(audio):
        raise ValueError(
            "Invalid hidden data or corrupted audio."
        )

    # Read encrypted payload
    payload_bits = [
        audio[i] & 1
        for i in range(
            32,
            total_bits
        )
    ]

    encrypted_payload = bits_to_bytes(
        payload_bits
    )

    # Directly decrypt encrypted payload
    return decrypt_message(
        encrypted_payload,
        password
    )

# ============================================================
# VIDEO STEGANOGRAPHY
# ============================================================

def video_encode(
    input_file,
    output_file,
    message,
    password
):

    cap = cv2.VideoCapture(
        input_file
    )

    if not cap.isOpened():

        raise ValueError(
            "Unable to open video."
        )

    width = int(
        cap.get(cv2.CAP_PROP_FRAME_WIDTH)
    )

    height = int(
        cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
    )

    fps = cap.get(
        cv2.CAP_PROP_FPS
    )

    frame_count = int(
        cap.get(cv2.CAP_PROP_FRAME_COUNT)
    )

    # Use AVI/MJPEG internally for more reliable frame processing.
    fourcc = cv2.VideoWriter_fourcc(
        *"MJPG"
    )

    writer = cv2.VideoWriter(
        output_file,
        fourcc,
        fps if fps > 0 else 25,
        (width, height)
    )

    payload = make_payload(
        message,
        password
    )

    bits = bytes_to_bits(payload)

    bit_index = 0

    # 32-bit length + encrypted payload
    total_bits = len(bits)

    frame_number = 0

    while True:

        ret, frame = cap.read()

        if not ret:
            break

        flat = frame.reshape(-1)

        if bit_index < total_bits:

            capacity = len(flat)

            count = min(
                capacity,
                total_bits - bit_index
            )

            for i in range(count):

                bit = bits[
                    bit_index + i
                ]

                flat[i] = (
                    flat[i] & 254
                ) | bit

            bit_index += count

        writer.write(
            frame
        )

        frame_number += 1

    cap.release()
    writer.release()

    if bit_index < total_bits:

        raise ValueError(
            "Secret message is too large "
            "for this video."
        )


def video_decode(
    input_file,
    password
):

    cap = cv2.VideoCapture(
        input_file
    )

    if not cap.isOpened():

        raise ValueError(
            "Unable to open video."
        )

    collected = []

    required_header = 32

    # Read enough bits for header first
    while len(collected) < required_header:

        ret, frame = cap.read()

        if not ret:
            break

        flat = frame.reshape(-1)

        collected.extend(
            [
                int(x & 1)
                for x in flat
            ]
        )

    if len(collected) < 32:

        cap.release()

        raise ValueError(
            "No hidden message found."
        )

    header = bits_to_bytes(
        collected[:32]
    )

    length = struct.unpack(
        ">I",
        header
    )[0]

    if length <= 0:

        cap.release()

        raise ValueError(
            "No hidden message found."
        )

    required_total = 32 + length * 8

    while len(collected) < required_total:

        ret, frame = cap.read()

        if not ret:
            break

        flat = frame.reshape(-1)

        collected.extend(
            [
                int(x & 1)
                for x in flat
            ]
        )

    cap.release()

    if len(collected) < required_total:

        raise ValueError(
            "Incomplete hidden data."
        )

    payload_bits = collected[
        32:required_total
    ]

    payload = bits_to_bytes(
        payload_bits
    )

    return extract_payload(
        payload,
        password
    )


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:

    st.markdown(
        "# 🛡️ StegoShield AI"
    )

    st.markdown(
        "### Multimedia Security"
    )

    st.divider()

    page = st.radio(
        "Navigation",
        [
            "🏠 Home",
            "🖼️ Image Steganography",
            "🎵 Audio Steganography",
            "🎬 Video Steganography",
            "📊 Dashboard",
            "ℹ️ About"
        ]
    )

    st.divider()

    st.info(
        "🔐 Your secret message is "
        "encrypted before embedding."
    )


# ============================================================
# HOME
# ============================================================

if page == "🏠 Home":

    st.markdown(
        '<div class="main-title">'
        'Secure Your Multimedia'
        '</div>',
        unsafe_allow_html=True
    )

    st.markdown(
        '<div class="subtitle">'
        'AI-inspired multimedia steganography '
        'with password-protected encryption.'
        '</div>',
        unsafe_allow_html=True
    )

    c1, c2, c3 = st.columns(3)

    with c1:

        st.markdown(
            """
            <div class="feature-card">

            ## 🖼️

            ### Image Steganography

            Hide encrypted messages inside
            PNG and JPG images.

            </div>
            """,
            unsafe_allow_html=True
        )

    with c2:

        st.markdown(
            """
            <div class="feature-card">

            ## 🎵

            ### Audio Steganography

            Hide encrypted messages inside
            WAV audio files.

            </div>
            """,
            unsafe_allow_html=True
        )

    with c3:

        st.markdown(
            """
            <div class="feature-card">

            ## 🎬

            ### Video Steganography

            Hide encrypted messages inside
            video frames.

            </div>
            """,
            unsafe_allow_html=True
        )

    st.markdown("---")

    st.markdown(
        """
        ## 🔐 How StegoShield AI Works

        1. Upload multimedia
        2. Enter your secret message
        3. Enter a password
        4. Encrypt the message
        5. Embed encrypted data
        6. Download the processed file
        7. Upload it again later to decrypt
        """
    )


# ============================================================
# IMAGE PAGE
# ============================================================

elif page == "🖼️ Image Steganography":

    st.title(
        "🖼️ Image Steganography"
    )

    tab1, tab2 = st.tabs(
        [
            "🔐 Encrypt",
            "🔓 Decrypt"
        ]
    )

    # -------------------------
    # ENCRYPT
    # -------------------------

    with tab1:

        uploaded = st.file_uploader(
            "Upload PNG/JPG Image",
            type=[
                "png",
                "jpg",
                "jpeg"
            ],
            key="image_encrypt"
        )

        if uploaded:

            image = Image.open(
                uploaded
            )

            st.image(
                image,
                caption="Original Image",
                use_container_width=True
            )

            message = st.text_area(
                "Secret Message",
                key="image_message"
            )

            password = st.text_input(
                "Password",
                type="password",
                key="image_password"
            )

            if st.button(
                "🔐 Encrypt Image",
                key="encrypt_image"
            ):

                if not message:

                    st.error(
                        "Enter a secret message."
                    )

                elif not password:

                    st.error(
                        "Enter a password."
                    )

                else:

                    try:

                        with st.spinner(
                            "Encrypting image..."
                        ):

                            result = image_encode(
                                image,
                                message,
                                password
                            )

                        output = io.BytesIO()

                        # PNG is used to preserve LSB data.
                        result.save(
                            output,
                            format="PNG"
                        )

                        output.seek(0)

                        st.success(
                            "✅ Image encrypted successfully!"
                        )

                        st.image(
                            output,
                            caption="Encrypted Image",
                            use_container_width=True
                        )

                        st.download_button(
                            "⬇️ Download Encrypted Image",
                            output.getvalue(),
                            "stegoshield_encrypted.png",
                            "image/png"
                        )

                    except Exception as e:

                        st.error(
                            f"Encryption failed: {e}"
                        )

    # -------------------------
    # DECRYPT
    # -------------------------

    with tab2:

        uploaded = st.file_uploader(
            "Upload Encrypted PNG/JPG",
            type=[
                "png",
                "jpg",
                "jpeg"
            ],
            key="image_decrypt"
        )

        if uploaded:

            image = Image.open(
                uploaded
            )

            st.image(
                image,
                caption="Encrypted Image",
                use_container_width=True
            )

            password = st.text_input(
                "Password",
                type="password",
                key="image_decrypt_password"
            )

            if st.button(
                "🔓 Decrypt Image",
                key="decrypt_image"
            ):

                if not password:

                    st.error(
                        "Enter the password."
                    )

                else:

                    try:

                        with st.spinner(
                            "Decrypting image..."
                        ):

                            message = image_decode(
                                image,
                                password
                            )

                        st.success(
                            "✅ Message decrypted successfully!"
                        )

                        st.text_area(
                            "🔓 Hidden Message",
                            message,
                            height=150
                        )

                    except Exception as e:

                        st.error(
                            f"Decryption failed: {e}"
                        )


# ============================================================
# AUDIO PAGE
# ============================================================

elif page == "🎵 Audio Steganography":

    st.title(
        "🎵 Audio Steganography"
    )

    st.info(
        "WAV is recommended because it is "
        "lossless and suitable for LSB steganography."
    )

    tab1, tab2 = st.tabs(
        [
            "🔐 Encrypt",
            "🔓 Decrypt"
        ]
    )

    with tab1:

        uploaded = st.file_uploader(
            "Upload WAV Audio",
            type=["wav"],
            key="audio_encrypt"
        )

        if uploaded:

            st.audio(
                uploaded
            )

            message = st.text_area(
                "Secret Message",
                key="audio_message"
            )

            password = st.text_input(
                "Password",
                type="password",
                key="audio_password"
            )

            if st.button(
                "🔐 Encrypt Audio",
                key="encrypt_audio"
            ):

                if not message or not password:

                    st.error(
                        "Enter both message and password."
                    )

                else:

                    input_path = None
                    output_path = None

                    try:

                        with tempfile.NamedTemporaryFile(
                            delete=False,
                            suffix=".wav"
                        ) as f:

                            f.write(
                                uploaded.getbuffer()
                            )

                            input_path = f.name

                        output_path = tempfile.mktemp(
                            suffix=".wav"
                        )

                        with st.spinner(
                            "Encrypting audio..."
                        ):

                            audio_encode(
                                input_path,
                                output_path,
                                message,
                                password
                            )

                        st.success(
                            "✅ Audio encrypted successfully!"
                        )

                        with open(
                            output_path,
                            "rb"
                        ) as f:

                            data = f.read()

                        st.audio(
                            data
                        )

                        st.download_button(
                            "⬇️ Download Encrypted Audio",
                            data,
                            "stegoshield_encrypted.wav",
                            "audio/wav"
                        )

                    except Exception as e:

                        st.error(
                            f"Audio encryption failed: {e}"
                        )

                    finally:

                        for path in [
                            input_path,
                            output_path
                        ]:

                            if path and os.path.exists(path):

                                os.remove(path)

    with tab2:

        uploaded = st.file_uploader(
            "Upload Encrypted WAV",
            type=["wav"],
            key="audio_decrypt"
        )

        if uploaded:

            st.audio(
                uploaded
            )

            password = st.text_input(
                "Password",
                type="password",
                key="audio_decrypt_password"
            )

            if st.button(
                "🔓 Decrypt Audio",
                key="decrypt_audio"
            ):

                if not password:

                    st.error(
                        "Enter password."
                    )

                else:

                    input_path = None

                    try:

                        with tempfile.NamedTemporaryFile(
                            delete=False,
                            suffix=".wav"
                        ) as f:

                            f.write(
                                uploaded.getbuffer()
                            )

                            input_path = f.name

                        with st.spinner(
                            "Decrypting audio..."
                        ):

                            message = audio_decode(
                                input_path,
                                password
                            )

                        st.success(
                            "✅ Hidden message extracted!"
                        )

                        st.text_area(
                            "🔓 Hidden Message",
                            message,
                            height=150
                        )

                    except Exception as e:

                        st.error(
                            f"Audio decryption failed: {e}"
                        )

                    finally:

                        if input_path and os.path.exists(
                            input_path
                        ):

                            os.remove(
                                input_path
                            )


# ============================================================
# VIDEO PAGE
# ============================================================

elif page == "🎬 Video Steganography":

    st.title(
        "🎬 Video Steganography"
    )

    st.warning(
        "Video processing is frame-based. "
        "Large videos may require more processing time."
    )

    tab1, tab2 = st.tabs(
        [
            "🔐 Encrypt",
            "🔓 Decrypt"
        ]
    )

    with tab1:

        uploaded = st.file_uploader(
            "Upload Video",
            type=["mp4", "avi", "mov"],
            key="video_encrypt"
        )

        if uploaded:

            st.video(
                uploaded
            )

            message = st.text_area(
                "Secret Message",
                key="video_message"
            )

            password = st.text_input(
                "Password",
                type="password",
                key="video_password"
            )

            if st.button(
                "🔐 Encrypt Video",
                key="encrypt_video"
            ):

                if not message or not password:

                    st.error(
                        "Enter both message and password."
                    )

                else:

                    input_path = None
                    output_path = None

                    try:

                        with tempfile.NamedTemporaryFile(
                            delete=False,
                            suffix=".mp4"
                        ) as f:

                            f.write(
                                uploaded.getbuffer()
                            )

                            input_path = f.name

                        # Internally write AVI because
                        # MJPEG frame writing is reliable.
                        output_path = tempfile.mktemp(
                            suffix=".avi"
                        )

                        with st.spinner(
                            "Processing video frames..."
                        ):

                            video_encode(
                                input_path,
                                output_path,
                                message,
                                password
                            )

                        st.success(
                            "✅ Video encrypted successfully!"
                        )

                        with open(
                            output_path,
                            "rb"
                        ) as f:

                            data = f.read()

                        st.video(
                            data
                        )

                        st.download_button(
                            "⬇️ Download Encrypted Video",
                            data,
                            "stegoshield_encrypted.avi",
                            "video/x-msvideo"
                        )

                    except Exception as e:

                        st.error(
                            f"Video encryption failed: {e}"
                        )

                    finally:

                        for path in [
                            input_path,
                            output_path
                        ]:

                            if path and os.path.exists(
                                path
                            ):

                                os.remove(
                                    path
                                )

    with tab2:

        uploaded = st.file_uploader(
            "Upload Encrypted Video",
            type=[
                "avi",
                "mp4",
                "mov"
            ],
            key="video_decrypt"
        )

        if uploaded:

            st.video(
                uploaded
            )

            password = st.text_input(
                "Password",
                type="password",
                key="video_decrypt_password"
            )

            if st.button(
                "🔓 Decrypt Video",
                key="decrypt_video"
            ):

                if not password:

                    st.error(
                        "Enter password."
                    )

                else:

                    input_path = None

                    try:

                        with tempfile.NamedTemporaryFile(
                            delete=False,
                            suffix=".avi"
                        ) as f:

                            f.write(
                                uploaded.getbuffer()
                            )

                            input_path = f.name

                        with st.spinner(
                            "Extracting hidden message..."
                        ):

                            message = video_decode(
                                input_path,
                                password
                            )

                        st.success(
                            "✅ Hidden message extracted!"
                        )

                        st.text_area(
                            "🔓 Hidden Message",
                            message,
                            height=150
                        )

                    except Exception as e:

                        st.error(
                            f"Video decryption failed: {e}"
                        )

                    finally:

                        if input_path and os.path.exists(
                            input_path
                        ):

                            os.remove(
                                input_path
                            )


# ============================================================
# DASHBOARD
# ============================================================

elif page == "📊 Dashboard":

    st.title(
        "📊 StegoShield Dashboard"
    )

    c1, c2, c3, c4 = st.columns(4)

    c1.metric(
        "🖼️ Images",
        "0"
    )

    c2.metric(
        "🎵 Audio",
        "0"
    )

    c3.metric(
        "🎬 Video",
        "0"
    )

    c4.metric(
        "🔐 Encryption",
        "0"
    )

    st.markdown(
        """
        <div class="card">

        ### 📈 Processing Overview

        This dashboard can be connected to
        SQLite, Firebase, or Supabase to store
        real processing statistics.

        </div>
        """,
        unsafe_allow_html=True
    )


# ============================================================
# ABOUT
# ============================================================

elif page == "ℹ️ About":

    st.title(
        "ℹ️ About StegoShield AI"
    )

    st.markdown(
        """
        ## 🛡️ What is Steganography?

        Steganography is the technique of hiding
        information inside another digital medium.

        StegoShield AI combines steganography with
        password-based encryption.

        ### Supported Multimedia

        🖼️ Images

        🎵 Audio

        🎬 Video

        ### Security Flow

        Secret Message

        ↓

        AES-GCM Encryption

        ↓

        Password Protection

        ↓

        Steganographic Embedding

        ↓

        Multimedia File

        ### Important

        Keep your password safe. Without the
        correct password, the encrypted message
        cannot be recovered.
        """
    )


# ============================================================
# FOOTER
# ============================================================

st.markdown("---")

st.markdown(
    """
    <div style="text-align:center; color:#9fa4bd;">

    🛡️ <b>StegoShield AI</b>

    <br>

    Secure Data • Hidden Intelligence • Protected Multimedia

    <br><br>

    © 2026 StegoShield AI

    </div>
    """,
    unsafe_allow_html=True
)
#streamlit run app.py