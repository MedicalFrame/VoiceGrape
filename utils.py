import streamlit as st
from PIL import Image, ImageDraw, ImageFont
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import plotly.io as pio
import textwrap
import io
import os
import json
import re
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
import numpy as np

def clean_text(text):
    if not text: return ""
    text = re.sub(r'[^\u0000-\uFFFF]', '', str(text))
    symbols = ['✨', '🎤', '👍', '🎙️', '🎂', '📉', '🌟', '😊', '🙂', '☁️', '🛌', '💡', '📋', '📊']
    for s in symbols: text = text.replace(s, '')
    return text.strip()

def send_email_report(to_email, subject, body, attachment_data, attachment_name):
    try:
        smtp_config = st.secrets.get("smtp", {})
        if not smtp_config: return False, "SMTP 설정이 secrets.toml에 없습니다."
        smtp_server = smtp_config.get("server", "smtp.gmail.com")
        smtp_port = smtp_config.get("port", 587)
        smtp_user = smtp_config.get("user")
        smtp_password = smtp_config.get("password")
        if not smtp_user or not smtp_password: return False, "SMTP 계정 정보가 설정되지 않았습니다."
        msg = MIMEMultipart()
        msg['From'] = smtp_user
        msg['To'] = to_email
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))
        if attachment_data:
            # PDF 확장자인 경우 MIME 타입을 명시적으로 지정
            if attachment_name.lower().endswith('.pdf'):
                part = MIMEBase('application', 'pdf')
            else:
                part = MIMEBase('application', 'octet-stream')
            part.set_payload(attachment_data)
            encoders.encode_base64(part)
            # 한글 파일명 깨짐(noname) 방지를 위해 파라미터 방식으로 설정 (RFC 2231 자동 대응)
            part.add_header('Content-Disposition', 'attachment', filename=attachment_name)
            msg.attach(part)
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(smtp_user, smtp_password)
        server.send_message(msg)
        server.quit()
        return True, "이메일이 성공적으로 전송되었습니다."
    except Exception as e: return False, f"이메일 전송 실패: {e}"

@st.cache_data
def load_passages(filename):
    base_path = os.path.dirname(__file__)
    file_path = os.path.join(base_path, filename)
    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            try: return json.load(f)
            except: pass
    return ["안녕하세요, 목소리 분석을 시작합니다.", "천천히 또박또박 읽어주세요."]

@st.cache_data(show_spinner=False)
def create_report_pdf(name, date, summary, gender_info, female_ratio, age, tone, clarity, karaoke, jitter, shimmer, jitter_score, shimmer_score, speech_rate, speed_label, condition_score, condition_label, pitch_xs=None, pitch_values=None, f1_list=None, f2_list=None, articulation_score=0, mean_f1=0, mean_f2=0):
    try:
        scale = 2
        width, height = 800 * scale, 1100 * scale
        # 2개의 페이지 이미지 생성
        image1 = Image.new('RGB', (width, height), color=(255, 255, 255))
        image2 = Image.new('RGB', (width, height), color=(255, 255, 255))
        draw1 = ImageDraw.Draw(image1)
        draw2 = ImageDraw.Draw(image2)

        base_path = os.path.dirname(__file__)
        font_path = os.path.join(base_path, "NanumGothic.ttf")
        if os.path.exists(font_path):
            font_title = ImageFont.truetype(font_path, 42 * scale)
            font_sub = ImageFont.truetype(font_path, 28 * scale)
            font_text = ImageFont.truetype(font_path, 20 * scale)
            font_small = ImageFont.truetype(font_path, 16 * scale)
        else: font_title = font_sub = font_text = font_small = ImageFont.load_default()

        # --- PAGE 1: Summary & Profile ---
        draw1.rectangle([0, 0, width, 180 * scale], fill=(60, 63, 65))
        icon_path = os.path.join(base_path, "App_icon.png")
        title_text = "VOICEGRAPE"
        if os.path.exists(icon_path):
            icon = Image.open(icon_path).convert("RGBA")
            icon_h = 80 * scale
            icon_w = int(icon.width * (icon_h / icon.height))
            icon = icon.resize((icon_w, icon_h), Image.LANCZOS)
            text_bbox = draw1.textbbox((0, 0), title_text, font=font_title)
            text_w = text_bbox[2] - text_bbox[0]
            total_w = icon_w + (20 * scale) + text_w
            start_x = (width - total_w) // 2
            image1.paste(icon, (start_x, (180 * scale - icon_h) // 2 - (10 * scale)), icon)
            draw1.text((start_x + icon_w + (20 * scale), 180 * scale // 2 - (10 * scale)), title_text, fill=(255, 255, 255), font=font_title, anchor="lm")
        else: draw1.text((width//2, 80 * scale), title_text, fill=(255, 255, 255), font=font_title, anchor="mm")
        
        draw1.text((width//2, 155 * scale), "Professional Voice Analysis Report - Page 1", fill=(200, 200, 200), font=font_small, anchor="mm")
        draw1.rectangle([0, 180 * scale, width, 240 * scale], fill=(240, 242, 246))
        draw1.text((50 * scale, 210 * scale), f"Name: {name}", fill=(80, 80, 80), font=font_text, anchor="lm")
        draw1.text((width - 50 * scale, 210 * scale), f"Date: {date}", fill=(80, 80, 80), font=font_text, anchor="rm")
        
        draw1.rounded_rectangle([40 * scale, 270 * scale, 760 * scale, 410 * scale], radius=15 * scale, fill=(220, 230, 245), outline=(170, 190, 230), width=2 * scale)
        draw1.text((60 * scale, 290 * scale), "Analysis Summary", fill=(25, 103, 210), font=font_sub)
        summary_clean = clean_text(summary)
        wrapped_summary = textwrap.fill(summary_clean, width=44)
        draw1.multiline_text((60 * scale, 330 * scale), wrapped_summary, fill=(50, 50, 50), font=font_text, spacing=8 * scale)
        
        score_color = (40, 167, 69) if condition_score >= 80 else (255, 193, 7) if condition_score >= 60 else (220, 53, 69)
        draw1.rounded_rectangle([520 * scale, 420 * scale, 760 * scale, 620 * scale], radius=20 * scale, fill=score_color)
        draw1.text((640 * scale, 460 * scale), "Condition Score", fill=(255, 255, 255), font=font_text, anchor="mm")
        draw1.text((640 * scale, 520 * scale), f"{condition_score:.1f}", fill=(255, 255, 255), font=font_title, anchor="mm")
        draw1.text((640 * scale, 580 * scale), clean_text(condition_label), fill=(255, 255, 255), font=font_sub, anchor="mm")
        
        y_pos = 440 * scale
        draw1.text((50 * scale, y_pos), "Voice Profile", fill=(60, 63, 65), font=font_sub)
        y_pos += 50 * scale
        profile_metrics = [
            ("Gender Category", gender_info), 
            ("Estimated Age", f"만 {age}세"), 
            ("Voice Tone", tone), 
            ("Clarity", clarity), 
            ("Articulation", f"{articulation_score:.1f} pts"),
            ("Speech Rate", f"{speed_label}"), 
            ("Karaoke Key", karaoke)
        ]
        for label, value in profile_metrics:
            draw1.text((60 * scale, y_pos), f"• {label}", fill=(120, 120, 120), font=font_text)
            draw1.text((260 * scale, y_pos), clean_text(value), fill=(30, 30, 30), font=font_text)
            y_pos += 45 * scale

        draw1.text((width//2, height - 40 * scale), "Page 1 / 2", fill=(180, 180, 180), font=font_small, anchor="mm")

        # --- PAGE 2: Detailed Metrics & Graphs ---
        draw2.rectangle([0, 0, width, 80 * scale], fill=(60, 63, 65))
        draw2.text((width//2, 40 * scale), "Detailed Analysis & Visuals", fill=(255, 255, 255), font=font_sub, anchor="mm")
        
        y_pos = 120 * scale
        draw2.text((50 * scale, y_pos), "Stability & Formant Metrics", fill=(60, 63, 65), font=font_sub)
        y_pos += 50 * scale
        detailed_metrics = [
            ("Jitter (Tremor)", f"{jitter:.3f}% ({jitter_score:.1f} pts)"), 
            ("Shimmer (Stability)", f"{shimmer:.3f}% ({shimmer_score:.1f} pts)"),
            ("Mean F1 (Openness)", f"{mean_f1:.1f} Hz"),
            ("Mean F2 (Frontness)", f"{mean_f2:.1f} Hz")
        ]
        for label, value in detailed_metrics:
            draw2.text((60 * scale, y_pos), f"• {label}", fill=(120, 120, 120), font=font_text)
            draw2.text((280 * scale, y_pos), clean_text(value), fill=(30, 30, 30), font=font_text)
            y_pos += 45 * scale

        y_pos += 20 * scale
        draw2.text((50 * scale, y_pos), "Visual Analysis", fill=(60, 63, 65), font=font_sub)
        y_pos += 40 * scale

        # Pitch Plot
        if pitch_xs is not None and pitch_values is not None:
            df_p = pd.DataFrame({'Time (s)': pitch_xs, 'Frequency (Hz)': pitch_values})
            fig_p = px.scatter(df_p, x='Time (s)', y='Frequency (Hz)', title="Pitch (F0) Contour")
            fig_p.update_traces(marker=dict(size=3, color='blue'))
            fig_p.add_hrect(y0=0, y1=130, fillcolor="#87CEEB", opacity=0.3, line_width=0, layer="below")
            fig_p.add_hrect(y0=130, y1=190, fillcolor="#D3D3D3", opacity=0.3, line_width=0, layer="below")
            fig_p.add_hrect(y0=190, y1=500, fillcolor="#FFC0CB", opacity=0.3, line_width=0, layer="below")
            fig_p.update_yaxes(range=[50, 500])
            
            voiced_mask = ~np.isnan(pitch_values)
            if voiced_mask.any():
                change_points = np.diff(voiced_mask.astype(int))
                starts = np.where(change_points == 1)[0] + 1
                ends = np.where(change_points == -1)[0]
                if voiced_mask[0]: starts = np.insert(starts, 0, 0)
                if voiced_mask[-1]: ends = np.append(ends, len(voiced_mask) - 1)
                for i, (s, e) in enumerate(zip(starts, ends)):
                    fig_p.add_vrect(x0=pitch_xs[s], x1=pitch_xs[e], fillcolor="rgba(0, 255, 0, 0.15)", line_width=0, layer="below", annotation_text="Voiced" if i == 0 else "")

            fig_p.update_layout(
                font=dict(family="NanumGothic, Malgun Gothic, AppleGothic, sans-serif", size=14),
                plot_bgcolor='white', paper_bgcolor='white', margin=dict(l=40, r=20, t=60, b=40)
            )
            img_bytes = pio.to_image(fig_p, format='png', width=1000, height=400, scale=2)
            graph_image = Image.open(io.BytesIO(img_bytes)).resize((700 * scale, 250 * scale))
            image2.paste(graph_image, (50 * scale, y_pos))
            y_pos += 280 * scale

        # Formant Plot
        if f1_list and f2_list:
            df_f = pd.DataFrame({'F1 (Hz)': f1_list, 'F2 (Hz)': f2_list})
            fig_f = px.scatter(df_f, x='F2 (Hz)', y='F1 (Hz)', title="Vowel Space (F1/F2 Scatter)")
            fig_f.update_xaxes(autorange="reversed")
            fig_f.update_yaxes(autorange="reversed")
            fig_f.update_traces(marker=dict(size=5, color='red', opacity=0.5))
            
            if female_ratio >= 50:
                std_vowels = [
                    {'v': '이', 'f1': 350, 'f2': 2300}, {'v': '에', 'f1': 550, 'f2': 2000},
                    {'v': '아', 'f1': 850, 'f2': 1400}, {'v': '오', 'f1': 500, 'f2': 900}, {'v': '우', 'f1': 400, 'f2': 800}
                ]
            else:
                std_vowels = [
                    {'v': '이', 'f1': 280, 'f2': 2100}, {'v': '에', 'f1': 450, 'f2': 1800},
                    {'v': '아', 'f1': 750, 'f2': 1200}, {'v': '오', 'f1': 400, 'f2': 700}, {'v': '우', 'f1': 300, 'f2': 600}
                ]
            
            for d in std_vowels:
                fig_f.add_shape(type="circle", xref="x", yref="y",
                    x0=d['f2']-100, y0=d['f1']-100, x1=d['f2']+100, y1=d['f1']+100,
                    line_color="rgba(150, 150, 150, 0.5)", fillcolor="rgba(200, 200, 200, 0.2)", layer="below")
                fig_f.add_trace(go.Scatter(x=[d['f2']], y=[d['f1']], mode='text', text=[d['v']],
                    textfont=dict(color='black', size=14), showlegend=False, hoverinfo='skip'))

            fig_f.update_layout(
                font=dict(family="NanumGothic, Malgun Gothic, AppleGothic, sans-serif", size=14),
                plot_bgcolor='white', paper_bgcolor='white', margin=dict(l=40, r=20, t=60, b=40)
            )
            img_bytes = pio.to_image(fig_f, format='png', width=1000, height=400, scale=2)
            graph_image = Image.open(io.BytesIO(img_bytes)).resize((700 * scale, 250 * scale))
            image2.paste(graph_image, (50 * scale, y_pos))

        draw2.text((width//2, height - 40 * scale), "© 2026 VoiceGrape. All rights reserved. | Page 2 / 2", fill=(180, 180, 180), font=font_small, anchor="mm")
        
        buf = io.BytesIO()
        # 2페이지 PDF로 저장
        image1.save(buf, format='PDF', save_all=True, append_images=[image2])
        return buf.getvalue()
    except Exception as e: return None
