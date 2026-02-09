import parselmouth
import numpy as np
import tempfile
import os
import random
import datetime

def analyze_voice(audio_bytes, active_passage, user_name):
    """Parselmouth를 사용하여 음성 데이터를 분석하고 결과를 딕셔너리로 반환"""
    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp_file:
        tmp_file.write(audio_bytes)
        tmp_file_path = tmp_file.name
    try:
        snd = parselmouth.Sound(tmp_file_path)
    finally:
        if os.path.exists(tmp_file_path):
            os.remove(tmp_file_path)

    # 1. 피치 분석
    pitch = snd.to_pitch()
    pitch_values = pitch.selected_array['frequency']
    pitch_values[pitch_values == 0] = np.nan
    mean_pitch = np.nanmean(pitch_values)

    if np.isnan(mean_pitch):
        return None

    # 2. 포먼트 분석
    formants = snd.to_formant_burg()
    f1_list, f2_list = [], []
    for t in pitch.xs():
        f1, f2 = formants.get_value_at_time(1, t), formants.get_value_at_time(2, t)
        if not np.isnan(f1) and not np.isnan(f2):
            f1_list.append(f1); f2_list.append(f2)
    mean_f1 = np.mean(f1_list) if f1_list else 0
    mean_f2 = np.mean(f2_list) if f2_list else 0

    # 3. 발음 명료도 계산
    f1_dist = np.percentile(f1_list, 95) - np.percentile(f1_list, 5) if f1_list else 0
    f2_dist = np.percentile(f2_list, 95) - np.percentile(f2_list, 5) if f2_list else 0
    articulation_score = np.clip((f1_dist / 400 + f2_dist / 1000) / 2 * 100, 0, 100)

    # 4. 성별 및 톤 분석
    p_score = np.clip((mean_pitch - 120) / (210 - 120), 0, 1)
    f1_score = np.clip((mean_f1 - 500) / (650 - 500), 0, 1) if mean_f1 else 0.5
    f2_score = np.clip((mean_f2 - 1350) / (1800 - 1350), 0, 1) if mean_f2 else 0.5
    female_ratio = ((p_score * 0.6) + (f1_score * 0.2) + (f2_score * 0.2)) * 100
    male_ratio = 100 - female_ratio

    if mean_pitch < 130: tone_eval, karaoke_rec = "저음", "🎤 남성 표준 키 (추천 최고음: 2옥타브 도~레)"
    elif mean_pitch < 190: tone_eval, karaoke_rec = "중음", "🎤 남성 높은 키 / 여성 낮은 키 (추천 최고음: 2옥타브 파~솔)"
    else: tone_eval, karaoke_rec = "고음", "🎤 여성 표준 키 (추천 최고음: 2옥타브 시 ~ 3옥타브 도)"

    # 5. 예상 나이 추정
    if mean_pitch > 250: estimated_age = random.randint(10, 15)
    else:
        if female_ratio > 50:
            age_p = np.interp(mean_pitch, [160, 240], [50, 19])
            f_idx = (mean_f1 / 650 + mean_f2 / 1800) / 2 if mean_f1 and mean_f2 else 1.0
            age_f = np.interp(f_idx, [0.85, 1.15], [50, 19])
        else:
            age_p = np.interp(mean_pitch, [90, 150], [50, 19])
            f_idx = (mean_f1 / 500 + mean_f2 / 1350) / 2 if mean_f1 and mean_f2 else 1.0
            age_f = np.interp(f_idx, [0.85, 1.15], [50, 19])
        calc_age = age_p * 0.7 + age_f * 0.3
        if np.isnan(calc_age): calc_age = 30
        estimated_age = int(calc_age) + random.randint(-3, 1)

    # 6. 선명도 및 안정성 분석
    harmonicity = snd.to_harmonicity_ac()
    valid_hnr = harmonicity.values[harmonicity.values > 0]
    mean_hnr = np.mean(valid_hnr) if len(valid_hnr) > 0 else 0
    clarity_score = np.clip((mean_hnr - 3) / 15 * 100, 0, 100)
    if mean_hnr > 17: clarity_label = "매우 맑음 ✨"
    elif mean_hnr > 11: clarity_label = "보통 (안정적) 👍"
    else: clarity_label = "허스키 (매력적) 🎙️"

    intensity = snd.to_intensity()
    avg_intensity = intensity.get_average()
    point_process = parselmouth.praat.call([snd, pitch], "To PointProcess (cc)")
    num_points = parselmouth.praat.call(point_process, "Get number of points")

    if avg_intensity > 45 and num_points > 5:
        jitter = parselmouth.praat.call(point_process, "Get jitter (local)", 0, 0, 0.0001, 0.02, 1.3) * 100
        shimmer = parselmouth.praat.call([snd, point_process], "Get shimmer (local)", 0, 0, 0.0001, 0.02, 1.3, 1.6) * 100
    else:
        jitter, shimmer = 0.0, 0.0
    
    jitter = 0.0 if np.isnan(jitter) else jitter
    shimmer = 0.0 if np.isnan(shimmer) else shimmer
    jitter_score = np.clip((6.0 - jitter) / 6.0 * 100, 0, 100)
    shimmer_score = np.clip((25.0 - shimmer) / 25.0 * 100, 0, 100)
    
    stability_desc = "매우 안정적이고" if jitter < 1.5 and shimmer < 5.0 else "개성 있는 떨림이 있는"

    # 7. 말하기 속도 및 컨디션
    syllable_count = len(active_passage.replace(" ", ""))
    speech_rate = syllable_count / snd.duration
    speed_label = "적당한 (보통)" if 3.5 <= speech_rate < 5.5 else "여유로운 (느린)" if speech_rate < 3.5 else "속도감 있는 (빠른)"

    condition_score = (jitter_score * 0.35) + (shimmer_score * 0.35) + (clarity_score * 0.3)
    condition_label = "최상 🌟" if condition_score >= 90 else "좋음 😊" if condition_score >= 80 else "보통 🙂" if condition_score >= 70 else "나쁨 ☁️" if condition_score >= 50 else "휴식 필요 🛌"

    gender_desc = "여성스러운" if female_ratio > 66 else ("남성스러운" if male_ratio > 66 else "중성적인")
    one_line_summary = f"✨ {user_name}님은 {gender_desc} 느낌의 {estimated_age}세 정도인, {stability_desc} {speed_label} {clarity_label} 목소리를 가지고 계시네요!"
    analysis_date = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).strftime("%Y-%m-%d %H:%M:%S")

    return {
        "mean_pitch": mean_pitch, "pitch_xs": pitch.xs(), "pitch_values": pitch_values,
        "mean_f1": mean_f1, "mean_f2": mean_f2, "f1_list": f1_list, "f2_list": f2_list,
        "female_ratio": female_ratio, "male_ratio": male_ratio, "tone_eval": tone_eval,
        "karaoke_rec": karaoke_rec, "estimated_age": estimated_age, "mean_hnr": mean_hnr,
        "articulation_score": articulation_score, "clarity_score": clarity_score, "clarity_label": clarity_label,
        "jitter": jitter, "shimmer": shimmer, "jitter_score": jitter_score, "shimmer_score": shimmer_score,
        "speech_rate": speech_rate, "speed_label": speed_label, "condition_score": condition_score, "condition_label": condition_label,
        "one_line_summary": one_line_summary, "timestamp": analysis_date, "audio_bytes": audio_bytes,
        "snd_duration": snd.duration, "snd_sampling": snd.sampling_frequency
    }
