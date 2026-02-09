import streamlit as st
from streamlit_mic_recorder import mic_recorder
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import random
import datetime
import os
import io

from database import (
    verify_login, update_last_login, create_user, reset_user_data,
    update_user_password, load_history, load_favorites, delete_favorite,
    save_favorite, save_to_history, get_user_record_count, get_league_from_count,
)
from utils import load_passages, create_report_pdf, send_email_report
from analysis import analyze_voice
from admin import show_admin_page

st.set_page_config(page_title="VoiceGrape", layout="wide")

# --- URL Query Parameter Sync ---
if "page" in st.query_params:
    st.session_state.menu = st.query_params["page"]
elif "menu" not in st.session_state:
    st.session_state.menu = "음성 분석"

# --- 사이드바 구성 ---
with st.sidebar:
    # 사이드바 입력창 포커스 스타일 커스텀 (VoiceGrape 브랜드 컬러)
    st.markdown("""
        <style>
        div[data-testid="stSidebar"] div[data-baseweb="input"]:focus-within {
            border-color: #ab8eef !important;
            box-shadow: #ab8eef 0px 0px 0px 1px !important;
        }
        /* 사이드바 버튼 및 컨테이너 스타일 커스텀 */
        div[data-testid="stSidebar"] button {
            border: 1px solid #ab8eef !important;
            border-radius: 8px !important;
            transition: all 0.3s ease !important;
        }
        div[data-testid="stSidebar"] button:hover {
            transform: translateY(-2px) !important;
            box-shadow: 0 4px 8px rgba(171, 142, 239, 0.2) !important;
        }
        /* 활성화된 버튼 (Primary) */
        div[data-testid="stSidebar"] button[kind="primary"] {
            background-color: #ab8eef !important;
            color: white !important;
            font-weight: bold !important;
        }
        /* 비활성화된 버튼 (Secondary) */
        div[data-testid="stSidebar"] button[kind="secondary"] {
            color: #ab8eef !important;
            background-color: transparent !important;
        }
        /* 로그인 박스 강조 */
        .stExpander {
            border: 1px solid rgba(171, 142, 239, 0.3) !important;
            border-radius: 10px !important;
            background-color: rgba(171, 142, 239, 0.02) !important;
        }
        /* 메인 화면 카드 스타일 */
        .feature-card {
            background-color: var(--secondary-background-color);
            padding: 25px;
            border-radius: 15px;
            border: 1px solid var(--border-color);
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            height: 100%;
            transition: transform 0.3s ease;
        }
        .feature-card:hover {
            transform: translateY(-5px);
            border-color: #ab8eef;
        }
        /* 아이콘 선명도 및 렌더링 최적화 */
        div[data-testid="stSidebar"] img {
            image-rendering: auto;
            border-radius: 10px;
        }
        </style>
    """, unsafe_allow_html=True)

    icon_path = os.path.join(os.path.dirname(__file__), "App_icon.png")
    if os.path.exists(icon_path):
        st.image(icon_path, width=150) # width가 지정된 경우 파라미터 생략 가능
    st.title("VoiceGrape 음성 포도")
    st.markdown("---")
    
    if "recorder_id" not in st.session_state:
        st.session_state.recorder_id = 0

    if "close_sidebar" not in st.session_state:
        st.session_state.close_sidebar = False

    if "should_scroll" not in st.session_state:
        st.session_state.should_scroll = False

    if "logged_in" not in st.session_state:
        st.session_state.logged_in = False
    if "guest_mode" not in st.session_state:
        st.session_state.guest_mode = False
    if "user_name" not in st.session_state:
        st.session_state.user_name = ""
    if "user_password" not in st.session_state:
        st.session_state.user_password = ""
    if "last_login_time" not in st.session_state:
        st.session_state.last_login_time = ""
    if "auth_mode" not in st.session_state:
        st.session_state.auth_mode = "login" # login, signup

    if not st.session_state.logged_in and not st.session_state.guest_mode:
        if st.session_state.auth_mode == "login":
            st.subheader("로그인")
            input_name = st.text_input("이름", value="", placeholder="이름을 입력하세요", key="login_name")
            input_pw = st.text_input("비밀번호", type="password", key="login_pw")
            
            if st.button("🔓 로그인", use_container_width=True, type="primary"):
                if not input_name.strip():
                    st.error("이름을 입력해주세요.")
                else:
                    # 관리자 계정 체크
                    admin_info = st.secrets.get("admin", {})
                    admin_user = admin_info.get("user")
                    admin_pw = admin_info.get("password")

                    if admin_user and admin_pw and input_name.strip() == admin_user and input_pw == admin_pw:
                        st.session_state.logged_in = True
                        st.session_state.user_name = admin_user
                        st.session_state.user_password = admin_pw
                        st.session_state.menu = "관리자 메뉴"
                        st.success("관리자 계정으로 로그인되었습니다.")
                        st.rerun()
                    else:
                        with st.spinner("인증 중..."):
                            is_valid, last_login = verify_login(input_name, input_pw)
                            if is_valid:
                                st.session_state.logged_in = True
                                st.session_state.user_name = input_name.strip()
                                st.session_state.user_password = input_pw
                                st.session_state.last_login_time = last_login
                                update_last_login(input_name.strip())
                                st.session_state.menu = "음성 분석"
                                st.query_params["page"] = "음성 분석"
                                st.session_state.close_sidebar = True
                                st.success(f"{input_name}님, 환영합니다!")
                                st.rerun()
                            else:
                                st.error("아이디 또는 비밀번호가 일치하지 않습니다.")
            
            if st.button("회원가입", use_container_width=True):
                st.session_state.auth_mode = "signup"
                st.rerun()
            
            st.markdown("---")
            if st.button("👤 게스트로 참여", use_container_width=True):
                st.session_state.guest_mode = True
                st.session_state.user_name = "Guest"
                st.session_state.menu = "음성 분석"
                st.query_params["page"] = "음성 분석"
                st.session_state.close_sidebar = True
                st.rerun()

            # 비밀번호 분실 시 데이터 초기화 옵션
            with st.expander("비밀번호를 잊으셨나요?"):
                st.warning("데이터 초기화 시 기존의 모든 분석 기록과 즐겨찾기가 삭제되며 복구할 수 없습니다.")
                reset_name = st.text_input("초기화할 이름 입력", key="reset_name_input")
                if st.button("⚠️ 내 데이터 전체 초기화", use_container_width=True):
                    if not reset_name.strip():
                        st.error("이름을 입력해주세요.")
                    else:
                        success, msg = reset_user_data(reset_name)
                        if success: st.success(msg)
                        else: st.error(msg)

        elif st.session_state.auth_mode == "signup":
            st.subheader("회원가입")
            new_name = st.text_input("사용자 이름", placeholder="사용할 이름을 입력하세요", key="signup_name")
            new_pw = st.text_input("비밀번호", type="password", key="signup_pw")
            new_pw_confirm = st.text_input("비밀번호 재확인", type="password", key="signup_pw_confirm")
            
            if st.button("계정 생성", use_container_width=True, type="primary"):
                if not new_name.strip():
                    st.error("이름을 입력해주세요.")
                elif not new_pw:
                    st.error("비밀번호를 입력해주세요.")
                elif new_pw != new_pw_confirm:
                    st.error("비밀번호가 일치하지 않습니다.")
                else:
                    with st.spinner("계정 생성 중..."):
                        success, msg = create_user(new_name, new_pw)
                        if success:
                            st.success(msg)
                            st.session_state.auth_mode = "login"
                            st.rerun()
                        else:
                            st.error(msg)
            
            if st.button("로그인 화면으로 돌아가기", use_container_width=True):
                st.session_state.auth_mode = "login"
                st.rerun()

    else:
        if st.session_state.guest_mode:
            st.info("👤 게스트 모드 사용 중")
            if st.button("로그인 / 회원가입 하러가기", use_container_width=True):
                st.session_state.guest_mode = False
                st.session_state.user_name = ""
                if "analysis_results" in st.session_state:
                    del st.session_state.analysis_results
                st.rerun()
        else:
            st.write(f"✅ **{st.session_state.user_name}**님 로그인 중")
            if st.session_state.last_login_time and st.session_state.last_login_time != "nan":
                st.caption(f"🕒 마지막 로그인: {st.session_state.last_login_time}")
            
            record_count = get_user_record_count(st.session_state.user_name)
            
            # 등급 표시 및 다음 등급까지의 진행도 계산
            if record_count >= 100:
                league_icon = "💎 다이아몬드"
                progress_val = 1.0
                next_info = "최고 등급 달성! 🏆"
            elif record_count >= 50:
                league_icon = "🥇 골드"
                progress_val = (record_count - 50) / (100 - 50)
                next_info = f"다음 등급(💎)까지 {100 - record_count}회"
            elif record_count >= 20:
                league_icon = "🥈 실버"
                progress_val = (record_count - 20) / (50 - 20)
                next_info = f"다음 등급(🥇)까지 {50 - record_count}회"
            elif record_count >= 5:
                league_icon = "🥉 브론즈"
                progress_val = (record_count - 5) / (20 - 5)
                next_info = f"다음 등급(🥈)까지 {20 - record_count}회"
            else:
                league_icon = "🌱 새싹"
                progress_val = record_count / 5
                next_info = f"다음 등급(🥉)까지 {5 - record_count}회"

            st.caption(f"📊 총 분석 횟수: {record_count}회 ({league_icon})")
            st.progress(min(progress_val, 1.0))
            st.caption(f"📈 {next_info}")
            
            if st.button("🔒 로그아웃", use_container_width=True):
                st.session_state.logged_in = False
                st.session_state.user_name = ""
                st.session_state.user_password = ""
                if "analysis_results" in st.session_state:
                    del st.session_state.analysis_results
                st.session_state.close_sidebar = True
                st.rerun()

            # 비밀번호 변경 기능 추가
            with st.expander("🔑 비밀번호 변경"):
                curr_pw = st.text_input("현재 비밀번호", type="password", key="change_curr_pw")
                new_pw = st.text_input("새 비밀번호", type="password", key="change_new_pw")
                new_pw_conf = st.text_input("새 비밀번호 확인", type="password", key="change_new_pw_conf")
                
                if st.button("비밀번호 변경 실행", use_container_width=True):
                    if not curr_pw or not new_pw:
                        st.error("모든 필드를 입력해주세요.")
                    elif new_pw != new_pw_conf:
                        st.error("새 비밀번호가 일치하지 않습니다.")
                    else:
                        success, msg = update_user_password(st.session_state.user_name, curr_pw, new_pw)
                        if success:
                            st.success(msg)
                            st.session_state.user_password = new_pw # 세션 내 비밀번호 정보 갱신
                        else:
                            st.error(msg)

        st.markdown("---")
        # 메뉴 선택 (버튼 스타일) - 로그인 된 상태에서만 표시
        admin_user = st.secrets.get("admin", {}).get("user")
        if st.session_state.user_name == admin_user:
            # 관리자 전용 메뉴
            if st.button("⚙️ 관리자 메뉴", use_container_width=True, type="primary" if st.session_state.menu == "관리자 메뉴" else "secondary"):
                st.session_state.menu = "관리자 메뉴"
                st.query_params["page"] = "관리자 메뉴"
                st.session_state.close_sidebar = True
                st.rerun()
        else:
            # 일반 사용자 메뉴
            if st.button("🎙️ 음성 분석", use_container_width=True, type="primary" if st.session_state.menu == "음성 분석" else "secondary"):
                st.session_state.menu = "음성 분석"
                st.query_params["page"] = "음성 분석"
                st.session_state.close_sidebar = True
                st.rerun()
            # 게스트 모드에서는 과거 기록 접근 제한
            if not st.session_state.guest_mode:
                if st.button("📜 과거 기록", use_container_width=True, type="primary" if st.session_state.menu == "과거 기록" else "secondary"):
                    st.session_state.menu = "과거 기록"
                    st.query_params["page"] = "과거 기록"
                    st.session_state.close_sidebar = True
                    st.rerun()
            
            # FAQ 메뉴 추가 (로그인/게스트 모두 접근 가능)
            if st.button("❓ FAQ", use_container_width=True, type="primary" if st.session_state.menu == "FAQ" else "secondary"):
                if st.session_state.menu != "FAQ":
                    st.session_state.previous_menu = st.session_state.menu
                st.session_state.menu = "FAQ"
                st.query_params["page"] = "FAQ"
                st.session_state.close_sidebar = True
                st.rerun()

    # 전역 변수 설정 (기존 로직 호환용)
    user_name = st.session_state.user_name
    user_password = st.session_state.user_password
    
    # 엔터 키 내비게이션을 위한 자바스크립트 삽입
    st.components.v1.html(
        """
        <script>
        var doc = window.parent.document;
        var nameInput = doc.querySelector('input[aria-label="이름"]');
        var pwInput = doc.querySelector('input[aria-label="비밀번호"]');
        
        if (nameInput && pwInput) {
            nameInput.addEventListener('keydown', function(e) {
                if (e.key === 'Enter') { pwInput.focus(); }
            });
            pwInput.addEventListener('keydown', function(e) {
                if (e.key === 'Enter') { doc.querySelector('button[kind="primary"]').focus(); }
            });
        }
        </script>
        """, height=0
    )

    
    menu = st.session_state.menu

    st.caption("© 2026 Saerom")
    st.caption("[brunch.co.kr/@project-saerom](https://brunch.co.kr/@project-saerom)")

if (st.session_state.logged_in or st.session_state.guest_mode) and menu == "음성 분석":
    st.header("🎙️ 음성 분석")
    st.write("음성을 녹음하면 Parselmouth를 통해 실시간으로 피치와 포먼트를 분석합니다.")
    
    st.markdown("---")
    st.subheader("📖 읽기 문구 설정")
    
    passage_mode = st.radio("문구 선택 방식", ["짧은 문구", "긴 문구", "직접 입력"], horizontal=True)

    short_passages = load_passages("reading_passages.json")
    long_passages = load_passages("long_passages.json")

    if "current_short_passage" not in st.session_state:
        st.session_state.current_short_passage = random.choice(short_passages)
    if "current_long_passage" not in st.session_state:
        st.session_state.current_long_passage = random.choice(long_passages)

    if passage_mode == "짧은 문구":
        active_passage = st.session_state.current_short_passage
    elif passage_mode == "긴 문구":
        active_passage = st.session_state.current_long_passage

    if passage_mode in ["짧은 문구", "긴 문구"]:
        # 마침표 뒤에 줄바꿈을 추가하여 가독성 향상 (HTML <br> 사용)
        display_passage = active_passage.replace(". ", ".<br>")
        st.markdown(f"""
            <div style="background-color: #f0f2f6; padding: 20px; border-radius: 10px; border-left: 5px solid #ab8eef; margin-bottom: 10px; border-right: 1px solid var(--border-color); border-top: 1px solid var(--border-color); border-bottom: 1px solid var(--border-color);">
                <p style="margin: 0; font-size: 14px; color: var(--text-color); opacity: 0.7;">다음 문구를 읽으며 녹음해보세요:</p>
                <p style="margin: 10px 0 0 0; font-size: 18px; font-weight: bold; color: var(--text-color); line-height: 1.6;">{display_passage}</p>
            </div>
        """, unsafe_allow_html=True)

        if st.button("🔄 다른 문구 가져오기"):
            if passage_mode == "짧은 문구":
                st.session_state.current_short_passage = random.choice(short_passages)
            else:
                st.session_state.current_long_passage = random.choice(long_passages)
            st.rerun()
    else:
        if "custom_passage" not in st.session_state:
            st.session_state.custom_passage = "안녕하세요, 목소리 분석을 시작합니다."
        
        # 즐겨찾기 불러오기 UI
        if user_name:
            favs = load_favorites(user_name)
            if favs:
                col_fav1, col_fav2 = st.columns([3, 1])
                with col_fav1:
                    selected_fav = st.selectbox("⭐ 즐겨찾기에서 불러오기", ["-- 즐겨찾기 선택 --"] + favs)
                    if selected_fav != "-- 즐겨찾기 선택 --":
                        st.session_state.custom_passage = selected_fav
                with col_fav2:
                    st.write("") # 레이아웃 정렬용
                    st.write("")
                    if selected_fav != "-- 즐겨찾기 선택 --":
                        if st.button("❌ 삭제", use_container_width=True, help="선택한 즐겨찾기 문구를 삭제합니다."):
                            success, msg = delete_favorite(user_name, selected_fav)
                            if success:
                                st.success(msg)
                                st.rerun()
                            else:
                                st.error(msg)
        
        active_passage = st.text_area("분석할 문구를 직접 입력하세요", 
                                     key="custom_passage",
                                     help="입력한 문구의 길이를 바탕으로 말하기 속도를 측정합니다.")
        
        if st.button("⭐ 현재 문구를 즐겨찾기에 저장"):
            if not user_name:
                st.error("이름을 먼저 입력해주세요.")
            elif not active_passage:
                st.error("저장할 문구가 없습니다.")
            else:
                success, msg = save_favorite(user_name, active_passage)
                if success: st.success(msg); st.rerun()
                else: st.error(msg)

    st.subheader("1. 음성 녹음")
    if not st.session_state.logged_in and not st.session_state.guest_mode:
        st.warning("⚠️ 분석을 시작하려면 사이드바에서 로그인하거나 게스트로 참여해주세요.")
        st.button("🔴 녹음 시작", disabled=True, use_container_width=True, help="이름을 먼저 입력해야 합니다.")
        audio = None
    else:
        # 실시간 초시계 표시를 위한 HTML/JS
        st.markdown('<div id="voicegrape-timer" style="font-size: 1.5rem; font-weight: bold; color: #ab8eef; text-align: center; margin-bottom: 10px; height: 2rem;"></div>', unsafe_allow_html=True)
        st.components.v1.html(
            """
            <script>
            const doc = window.parent.document;
            let timerInterval = null;
            let seconds = 0;

            function findStopButton() {
                // 메인 문서에서 버튼 검색
                const mainButtons = Array.from(doc.querySelectorAll('button'));
                let btn = mainButtons.find(b => b.innerText.includes('⏹️ 녹음 중지'));
                if (btn) return btn;

                // iframe 내부 검색 (커스텀 컴포넌트인 mic_recorder 대응)
                const iframes = Array.from(doc.querySelectorAll('iframe'));
                for (const iframe of iframes) {
                    try {
                        const innerDoc = iframe.contentDocument || iframe.contentWindow.document;
                        const innerButtons = Array.from(innerDoc.querySelectorAll('button'));
                        btn = innerButtons.find(b => b.innerText.includes('⏹️ 녹음 중지'));
                        if (btn) return btn;
                    } catch (e) { /* CORS 등으로 접근 불가한 경우 무시 */ }
                }
                return null;
            }

            function updateTimer() {
                const stopButton = findStopButton();
                const timerDisplay = doc.getElementById('voicegrape-timer');
                if (!timerDisplay) return;

                if (stopButton) {
                    if (!timerInterval) {
                        seconds = 0;
                        timerDisplay.innerText = "⏱️ 녹음 중: 0초";
                        timerInterval = setInterval(() => {
                            seconds++;
                            timerDisplay.innerText = "⏱️ 녹음 중: " + seconds + "초";
                        }, 1000);
                    }
                } else {
                    if (timerInterval) {
                        clearInterval(timerInterval);
                        timerInterval = null;
                        timerDisplay.innerText = "";
                    }
                }
            }
            setInterval(updateTimer, 500);
            </script>
            """, height=0
        )

        audio = mic_recorder(
            start_prompt="🔴 녹음 시작",
            stop_prompt="⏹️ 녹음 중지",
            just_once=True,
            use_container_width=True,
            format="wav",
            key=f"mic_{st.session_state.recorder_id}"
        )

    if audio or "analysis_results" in st.session_state:
        # 새로운 녹음이 들어온 경우에만 분석 수행
        if audio:
            audio_id = hash(audio['bytes'])
            if st.session_state.get("last_audio_id") != audio_id:
                with st.spinner("목소리를 정밀 분석하고 결과를 저장 중입니다..."):
                    res = analyze_voice(audio['bytes'], active_passage, user_name)
                    if res is None:
                        st.error("목소리가 명확하게 감지되지 않았습니다. 마이크 설정을 확인하거나 조금 더 크게 말씀해주세요.")
                        st.stop()
                    st.session_state.analysis_results = res
                    st.session_state.last_audio_id = audio_id
                    st.session_state.should_scroll = True

                    # 게스트 모드가 아닐 때만 자동 저장
                    if not st.session_state.guest_mode:
                        # 저장 전 등급 확인 (축하 메시지용)
                        # get_user_record_count는 users 시트 값을 우선하므로,
                        # 저장 전 시점의 카운트를 가져옴.
                        current_count = get_user_record_count(user_name)
                        old_league = get_league_from_count(current_count)

                        save_to_history(user_name, {
                            "timestamp": res["timestamp"], "mean_pitch": res["mean_pitch"], "mean_f1": res["mean_f1"],
                            "mean_f2": res["mean_f2"], "female_ratio": res["female_ratio"], "male_ratio": res["male_ratio"],
                            "estimated_age": res["estimated_age"], "mean_hnr": res["mean_hnr"],
                            "jitter": res["jitter"], "shimmer": res["shimmer"], "speech_rate": res["speech_rate"],
                            "condition_score": res["condition_score"],
                            "articulation_score": res["articulation_score"]
                        }, active_passage)

                        # 저장 후 등급 확인
                        # save_to_history 내부에서 +1 업데이트를 수행했으므로
                        # 여기서는 단순히 +1 된 값으로 등급을 계산하여 비교
                        new_count = current_count + 1 
                        new_league = get_league_from_count(new_count)
                        if new_league != old_league:
                            st.balloons()
                            st.toast(f"🎉 축하합니다! {new_league} 등급으로 승급하셨습니다!", icon="🏆")

                # 분석 완료 후 다음 분석을 위해 문구 갱신
                st.session_state.current_short_passage = random.choice(short_passages)
                st.session_state.current_long_passage = random.choice(long_passages)

        res = st.session_state.analysis_results

        if st.button("🔄 새 분석 시작", use_container_width=True, type="secondary"):
            if "analysis_results" in st.session_state:
                del st.session_state.analysis_results
            if "last_audio_id" in st.session_state:
                del st.session_state.last_audio_id
            st.session_state.recorder_id += 1
            st.session_state.current_short_passage = random.choice(short_passages)
            st.session_state.current_long_passage = random.choice(long_passages)
            st.rerun()

        # 결과 화면으로 자동 스크롤 (앵커 설정 및 JS 실행)
        st.markdown('<div id="results-anchor"></div>', unsafe_allow_html=True)
        
        if st.session_state.get("should_scroll", False):
            st.components.v1.html(
                """
                <script>
                window.parent.document.getElementById('results-anchor').scrollIntoView({behavior: 'smooth'});
                </script>
                """, height=0
            )
            st.session_state.should_scroll = False

        st.audio(res["audio_bytes"])
        
        # 2. 종합평가
        st.markdown('<div id="anchor-summary"></div>', unsafe_allow_html=True)
        col_h2_1, col_h2_2 = st.columns([0.9, 0.1])
        col_h2_1.subheader("2. 종합평가")
        if col_h2_2.button("❓", key="faq_summary", help="지표 설명(FAQ) 보러가기"):
            st.session_state.previous_menu = "음성 분석"
            st.session_state.scroll_target = "anchor-summary"
            st.session_state.menu = "FAQ"
            st.query_params["page"] = "FAQ"
            st.rerun()
        
        # 컨디션 점수 (상단 이동)
        st.markdown(f"**오늘의 목소리 컨디션**")
        st.metric("컨디션 점수", f"{res['condition_score']:.1f}점", res['condition_label'], help="지터, 시머, HNR을 종합하여 계산한 목소리 건강 점수입니다.")
        st.progress(res['condition_score'] / 100)

        st.success(res["one_line_summary"])

        # 맞춤형 발성 팁 생성
        tips = []
        if res['condition_score'] < 70:
            tips.append("💤 컨디션이 다소 저조해요. 충분한 수분 섭취와 휴식이 필요합니다.")
        if res['clarity_score'] < 60:
            tips.append("💧 목소리에 거친 느낌이 있어요. 따뜻한 물을 마시고 성대를 촉촉하게 해주세요.")
        if res['jitter_score'] < 80 or res['shimmer_score'] < 80:
            tips.append("🌬️ 목소리의 떨림이 감지됩니다. 복식 호흡을 통해 호흡을 안정시켜 보세요.")
        if res['articulation_score'] < 60:
            tips.append("🗣️ 발음 명료도가 낮습니다. 입을 조금 더 크게 벌리고 또박또박 읽는 연습을 해보세요.")
        if res['speech_rate'] > 6.0:
            tips.append("🐇 말이 다소 빠릅니다. 문장 사이에서 충분히 숨을 쉬며 여유를 가져보세요.")
        elif res['speech_rate'] < 3.0:
            tips.append("🐢 말이 다소 느립니다. 리듬감을 살려 조금 더 경쾌하게 말해보는 건 어떨까요?")
        
        if not tips:
            tips.append("🌟 아주 훌륭한 목소리입니다! 지금의 좋은 습관을 유지하세요.")

        with st.expander("💡 나만을 위한 맞춤형 발성 팁", expanded=True):
            for tip in tips:
                st.write(f"- {tip}")

        st.markdown("---")

        # 3. 피치 & 포먼트 분석
        st.markdown('<div id="anchor-pitch"></div>', unsafe_allow_html=True)
        col_h3_1, col_h3_2 = st.columns([0.9, 0.1])
        col_h3_1.subheader("3. 피치 & 포먼트 분석")
        if col_h3_2.button("❓", key="faq_pitch", help="피치/포먼트 설명 보러가기"):
            st.session_state.previous_menu = "음성 분석"
            st.session_state.scroll_target = "anchor-pitch"
            st.session_state.menu = "FAQ"
            st.query_params["page"] = "FAQ"
            st.rerun()
        
        col_m1, col_m2 = st.columns(2)
        with col_m1:
            st.metric("평균 피치", f"{res['mean_pitch']:.2f} Hz", help="목소리의 높낮이(기본 주파수)입니다.")
        with col_m2:
            col_f1, col_f2 = st.columns(2)
            with col_f1: st.metric("평균 F1", f"{res['mean_f1']:.1f} Hz", help="입의 개방도와 관련된 공명 주파수입니다.")
            with col_f2: st.metric("평균 F2", f"{res['mean_f2']:.1f} Hz", help="혀의 전후 위치와 관련된 공명 주파수입니다.")

        # 그래프 시각화
        col_g1, col_g2 = st.columns(2)
        
        # 피치 그래프 생성 및 설정
        df_pitch = pd.DataFrame({'Time (s)': res['pitch_xs'], 'Frequency (Hz)': res['pitch_values']})
        fig_pitch = px.scatter(df_pitch, x='Time (s)', y='Frequency (Hz)', title="Pitch (F0) Contour", render_mode='webgl')
        fig_pitch.update_traces(marker=dict(size=3, color='blue'))
        fig_pitch.update_layout(height=450) # 높이 고정
        
        # 배경 색칠 (Plotly)
        fig_pitch.add_hrect(y0=0, y1=130, fillcolor="#87CEEB", opacity=0.3, line_width=0, layer="below")
        fig_pitch.add_hrect(y0=130, y1=190, fillcolor="#D3D3D3", opacity=0.3, line_width=0, layer="below")
        fig_pitch.add_hrect(y0=190, y1=500, fillcolor="#FFC0CB", opacity=0.3, line_width=0, layer="below")
        fig_pitch.update_yaxes(range=[50, 500]) # 500Hz 이상 표시 안 함
        
        voiced_mask = ~np.isnan(res['pitch_values'])
        if voiced_mask.any():
            change_points = np.diff(voiced_mask.astype(int))
            starts = np.where(change_points == 1)[0] + 1
            ends = np.where(change_points == -1)[0]
            if voiced_mask[0]: starts = np.insert(starts, 0, 0)
            if voiced_mask[-1]: ends = np.append(ends, len(voiced_mask) - 1)
            for i, (s, e) in enumerate(zip(starts, ends)):
                fig_pitch.add_vrect(x0=res['pitch_xs'][s], x1=res['pitch_xs'][e], fillcolor="rgba(0, 255, 0, 0.15)", line_width=0, layer="below", annotation_text="Voiced" if i == 0 else "")

        # 포먼트 그래프 생성 및 설정
        df_formant = pd.DataFrame({'F1 (Hz)': res['f1_list'], 'F2 (Hz)': res['f2_list']})
        fig_formant = px.scatter(df_formant, x='F2 (Hz)', y='F1 (Hz)', title="Formant Scatter Plot (Vowel Space)")
        fig_formant.update_xaxes(autorange="reversed")
        fig_formant.update_yaxes(autorange="reversed")
        fig_formant.update_traces(marker=dict(size=5, color='red', opacity=0.5))
        
        # 성별 비율에 따른 한국인 표준 모음 가이드라인 (아이우에오 + 원 표시)
        if res['female_ratio'] >= 50:
            std_vowels_data = [
                {'v': '이', 'f1': 350, 'f2': 2300}, {'v': '에', 'f1': 550, 'f2': 2000},
                {'v': '아', 'f1': 850, 'f2': 1400}, 
                {'v': '오', 'f1': 500, 'f2': 900}, {'v': '우', 'f1': 400, 'f2': 800}
            ]
        else:
            std_vowels_data = [
                {'v': '이', 'f1': 280, 'f2': 2100}, {'v': '에', 'f1': 450, 'f2': 1800},
                {'v': '아', 'f1': 750, 'f2': 1200}, 
                {'v': '오', 'f1': 400, 'f2': 700}, {'v': '우', 'f1': 300, 'f2': 600}
            ]
        
        for d in std_vowels_data:
            # 원 그리기
            fig_formant.add_shape(type="circle", xref="x", yref="y",
                x0=d['f2']-100, y0=d['f1']-100, x1=d['f2']+100, y1=d['f1']+100,
                line_color="rgba(150, 150, 150, 0.5)", fillcolor="rgba(200, 200, 200, 0.2)", layer="below")
            # 글자 진하게 표시
            fig_formant.add_trace(go.Scatter(x=[d['f2']], y=[d['f1']], mode='text', text=[d['v']],
                textfont=dict(color='black', size=14, weight='bold'), showlegend=False, hoverinfo='skip'))

        fig_formant.update_layout(height=450) # 높이 고정

        with col_g1:
            st.plotly_chart(fig_pitch, use_container_width=True, config={'displayModeBar': False})
        with col_g2:
            st.plotly_chart(fig_formant, use_container_width=True, config={'displayModeBar': False})

        st.markdown("---")
        
        # 4. 성별 범주 및 톤 분석
        st.markdown('<div id="anchor-gender"></div>', unsafe_allow_html=True)
        col_h4_1, col_h4_2 = st.columns([0.9, 0.1])
        col_h4_1.subheader("4. 성별 범주 및 톤 분석")
        if col_h4_2.button("❓", key="faq_gender", help="성별/톤 분석 설명 보러가기"):
            st.session_state.previous_menu = "음성 분석"
            st.session_state.scroll_target = "anchor-gender"
            st.session_state.menu = "FAQ"
            st.query_params["page"] = "FAQ"
            st.rerun()
        col_gender1, col_gender2 = st.columns(2)
        
        with col_gender1:
            if res["female_ratio"] > res["male_ratio"]:
                st.write(f"분석 결과, 목소리가 **여성 범주에 {res['female_ratio']:.1f}%**, **남성 범주에 {res['male_ratio']:.1f}%** 속합니다.")
            else:
                st.write(f"분석 결과, 목소리가 **남성 범주에 {res['male_ratio']:.1f}%**, **여성 범주에 {res['female_ratio']:.1f}%** 속합니다.")
            
            if res["female_ratio"] >= 50:
                left_label, right_label = "여성", "남성"
                left_color, right_color = "#FFC0CB", "#87CEEB"
                indicator_pos = 100 - res["female_ratio"]
            else:
                left_label, right_label = "남성", "여성"
                left_color, right_color = "#87CEEB", "#FFC0CB"
                indicator_pos = 100 - res["male_ratio"]
            indicator_pos = np.clip(indicator_pos, 2, 98)
            
            st.markdown(f"""
                <div style="width: 100%; padding-top: 45px; position: relative; margin-bottom: 20px;">
                    <div style="position: absolute; left: {indicator_pos}%; transform: translateX(-50%); top: 0px; text-align: center; width: 180px;">
                        <div style="font-size: 12px; font-weight: bold; color: #333;">{user_name} ({max(res['female_ratio'], res['male_ratio']):.1f}%)</div>
                        <div style="font-size: 14px; line-height: 10px;">▼</div>
                    </div>
                    <div style="background: linear-gradient(to right, {left_color} 0%, {left_color} 34%, #D3D3D3 34%, #D3D3D3 66%, {right_color} 66%, {right_color} 100%); border-radius: 10px; height: 15px; width: 100%;"></div>
                    <div style="display: flex; justify-content: space-between; margin-top: 5px;"><span style="font-size: 13px; color: #666;">{left_label}</span><span style="font-size: 13px; color: #666;">{right_label}</span></div>
                </div>
            """, unsafe_allow_html=True)
            
            st.write(f"사용자의 목소리 톤은 평균적으로 **'{res['tone_eval']}'**에 해당합니다.")
            st.info(f"**추천 노래방 키:** {res['karaoke_rec']}")

        with col_gender2:
            st.write("**평균 데이터와 내 데이터 비교**")
            order = ['여성 평균', '사용자', '남성 평균'] if res["female_ratio"] > res["male_ratio"] else ['남성 평균', '사용자', '여성 평균']
            freqs = [210, res["mean_pitch"], 120, 650, res["mean_f1"], 500, 1800, res["mean_f2"], 1350] if res["female_ratio"] > res["male_ratio"] else [120, res["mean_pitch"], 210, 500, res["mean_f1"], 650, 1350, res["mean_f2"], 1800]
            comp_df = pd.DataFrame({'지표': ['Pitch']*3 + ['F1']*3 + ['F2']*3, '구분': order * 3, '주파수 (Hz)': freqs})
            fig_comp = px.bar(comp_df, x='지표', y='주파수 (Hz)', color='구분', barmode='group', category_orders={"구분": order}, color_discrete_map={'남성 평균': 'skyblue', '사용자': 'green', '여성 평균': 'lightpink'}, text_auto='.1f')
            st.plotly_chart(fig_comp, use_container_width=True, config={'displayModeBar': False})

        st.markdown("---")

        # 5. 기타 목소리 지수
        st.markdown('<div id="anchor-etc"></div>', unsafe_allow_html=True)
        col_h5_1, col_h5_2 = st.columns([0.9, 0.1])
        col_h5_1.subheader("5. 상세 목소리 지수")
        if col_h5_2.button("❓", key="faq_etc", help="상세 지표 설명 보러가기"):
            st.session_state.previous_menu = "음성 분석"
            st.session_state.scroll_target = "anchor-etc"
            st.session_state.menu = "FAQ"
            st.query_params["page"] = "FAQ"
            st.rerun()
        col_etc1, col_etc2 = st.columns(2)
        
        with col_etc1:
            st.write(f"🎂 예상 목소리 나이: **만 {res['estimated_age']}세**")
            
            st.markdown(f"**목소리 선명도: {res['clarity_label']}**")
            st.progress(res["clarity_score"] / 100)
            st.caption(f"선명도 점수: {res['clarity_score']:.1f}% (HNR: {res['mean_hnr']:.2f} dB)")
            
            st.markdown(f"**발음 명료도 (Articulation)**")
            st.progress(res["articulation_score"] / 100)
            st.caption(f"발음 정확도 점수: {res['articulation_score']:.1f}% (포먼트 분산도 기반)")

        with col_etc2:
            st.markdown(f"**말하기 속도: {res['speed_label']}**")
            st.write(f"⏱️ 초당 음절 수: {res['speech_rate']:.2f} syll/sec")

            st.markdown(f"**목소리 안정성**")
            st.write(f"📉 지터 (Jitter) 점수: {res['jitter_score']:.1f}%")
            st.progress(res['jitter_score'] / 100)
            st.caption(f"수치: {res['jitter']:.3f}% (기준: 1.04% 이하)")
            
            st.write(f"📉 시머 (Shimmer) 점수: {res['shimmer_score']:.1f}%")
            st.progress(res['shimmer_score'] / 100)
            st.caption(f"수치: {res['shimmer']:.3f}% (기준: 3.81% 이하)")

        st.markdown("---")

        # 6. 분석 결과 저장
        st.subheader("6. 분석 결과 저장")
        # 파일명에 사용할 공통 일시 정보 생성 (특수문자 및 공백 제거)
        clean_date = res["timestamp"].replace("-", "").replace(":", "").replace(" ", "_")
        pdf_filename = f"{user_name}_{clean_date}.pdf"

        col_save1, col_save2 = st.columns(2)
        
        with col_save1:
            report_pdf = create_report_pdf(
                user_name, res["timestamp"], res["one_line_summary"], 
                f"여성 {res['female_ratio']:.1f}% / 남성 {res['male_ratio']:.1f}%", 
                res["female_ratio"],
                res["estimated_age"], res["tone_eval"], res["clarity_label"], 
                res["karaoke_rec"], res["jitter"], res["shimmer"],
                res["jitter_score"], res["shimmer_score"], res["speech_rate"], res["speed_label"],
                res["condition_score"], res["condition_label"],
                res["pitch_xs"], res["pitch_values"], res["f1_list"], res["f2_list"],
                res["articulation_score"], res["mean_f1"], res["mean_f2"]
            )
            
            if report_pdf is not None:
                st.download_button(
                    label="📸 분석 결과 PDF로 저장",
                    data=report_pdf,
                    file_name=pdf_filename,
                    mime="application/pdf",
                    use_container_width=True
                )
            
            with st.expander("📧 이메일로 리포트 전송"):
                email_receiver = st.text_input("받을 이메일 주소", placeholder="example@email.com")
                if st.button("전송하기", use_container_width=True):
                    if not email_receiver:
                        st.error("이메일 주소를 입력해주세요.")
                    else:
                        with st.spinner("이메일 전송 중..."):
                            subject = f"[VoiceGrape] {user_name}님의 목소리 분석 리포트"
                            body = f"""안녕하세요, {user_name}님.
VoiceGrape 분석 결과 리포트를 첨부해 드립니다.

분석 일시: {res['timestamp']}
한줄 평: {res['one_line_summary']}

VoiceGrape 드림."""
                            success, msg = send_email_report(email_receiver, subject, body, report_pdf, pdf_filename)
                            if success: st.success(msg)
                            else: st.error(msg)
        
        with col_save2:
            if "audio_bytes" in res:
                audio_filename = f"{user_name}_{clean_date}.mp3"
                st.download_button(
                    label="🎵 녹음된 음성(MP3) 다운로드",
                    data=res["audio_bytes"],
                    file_name=audio_filename,
                    mime="audio/mpeg",
                    use_container_width=True
                )

        with st.expander("상세 분석 데이터 보기"):
            st.write(f"샘플링 레이트: {res['snd_sampling']} Hz / 총 길이: {round(res['snd_duration'])} 초")
        
        # 게스트 모드일 경우 회원가입 유도
        if st.session_state.guest_mode:
            st.markdown("---")
            st.info("💡 현재 게스트 모드입니다. 분석 결과를 저장하려면 회원가입을 진행해주세요.")
            with st.form("guest_signup_form"):
                st.write("회원가입하고 결과 저장하기")
                g_name = st.text_input("사용자 이름")
                g_pw = st.text_input("비밀번호", type="password")
                g_pw_confirm = st.text_input("비밀번호 재확인", type="password")
                g_submit = st.form_submit_button("가입 및 저장")
                
                if g_submit:
                    if not g_name.strip() or not g_pw:
                        st.error("이름과 비밀번호를 입력해주세요.")
                    elif g_pw != g_pw_confirm:
                        st.error("비밀번호가 일치하지 않습니다.")
                    else:
                        with st.spinner("계정을 생성하고 데이터를 저장 중입니다..."):
                            success, msg = create_user(g_name, g_pw)
                            if success:
                                # 계정 생성 성공 시 현재 결과 저장
                                save_to_history(g_name, {
                                        "timestamp": res["timestamp"], "mean_pitch": res["mean_pitch"], "mean_f1": res["mean_f1"],
                                        "mean_f2": res["mean_f2"], "female_ratio": res["female_ratio"], "male_ratio": res["male_ratio"],
                                        "estimated_age": res["estimated_age"], "mean_hnr": res["mean_hnr"],
                                        "jitter": res["jitter"], "shimmer": res["shimmer"], "speech_rate": res["speech_rate"],
                                        "condition_score": res["condition_score"], "articulation_score": res["articulation_score"]
                                }, active_passage)
                                st.success("계정이 생성되고 결과가 저장되었습니다! 로그인 상태로 전환됩니다.")
                                st.session_state.guest_mode = False
                                st.session_state.logged_in = True
                                st.session_state.user_name = g_name
                                st.session_state.user_password = g_pw
                                st.session_state.last_login_time = "방금 가입"
                                update_last_login(g_name)
                                st.rerun()
                            else:
                                st.error(msg)
        
        # FAQ에서 돌아왔을 때 스크롤 위치 복구 로직
        if st.session_state.get("trigger_scroll", False) and st.session_state.get("scroll_target"):
            target_id = st.session_state.scroll_target
            st.components.v1.html(
                f"""
                <script>
                    setTimeout(function() {{
                        var element = window.parent.document.getElementById('{target_id}');
                        if (element) {{
                            element.scrollIntoView({{behavior: 'smooth', block: 'start'}});
                        }}
                    }}, 300);
                </script>
                """, height=0
            )
            st.session_state.trigger_scroll = False

elif st.session_state.logged_in and menu == "과거 기록":
    if not st.session_state.logged_in:
        st.header("📜 과거 분석 기록")
        st.warning("⚠️ 과거 기록을 조회하려면 사이드바에서 로그인해주세요.")
    else:
        st.header(f"📜 {user_name}님의 과거 분석 기록")
        with st.spinner("과거 분석 기록을 불러오는 중입니다..."):
            user_history, is_authorized = load_history(user_name, user_password)

        if not is_authorized:
            st.warning("🔒 이 사용자의 기록은 비밀번호로 보호되어 있습니다. 올바른 비밀번호를 입력해주세요.")
        elif user_history:
            # 데이터프레임 생성 및 시간순 정렬
            df_history = pd.DataFrame(user_history)
            # 문자열로 읽어온 숫자 데이터들을 다시 숫자형으로 변환 (그래프 출력용)
            df_history = df_history.apply(pd.to_numeric, errors='ignore')
            df_history['timestamp_dt'] = pd.to_datetime(df_history['timestamp'])
            df_history = df_history.sort_values('timestamp_dt')

            # 기간 필터링 UI
            filter_col1, filter_col2 = st.columns([1, 2])
            with filter_col1:
                period = st.selectbox("📅 조회 기간 선택", ["전체", "최근 1주일", "최근 1개월"], index=0)

            # 필터링 로직
            now_dt = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).replace(tzinfo=None)
            if period == "최근 1주일":
                cutoff = now_dt - datetime.timedelta(days=7)
                df_history = df_history[df_history['timestamp_dt'] >= cutoff]
            elif period == "최근 1개월":
                cutoff = now_dt - datetime.timedelta(days=30)
                df_history = df_history[df_history['timestamp_dt'] >= cutoff]

            # --- 레이아웃 변경: 그래프를 상단으로 배치 ---
            if not df_history.empty:
                st.subheader("📊 지표별 변화 추이")
                st.info("기록이 하나만 있어도 그래프에 점으로 표시됩니다.")
                
                # 모든 지표를 포함하는 탭 생성
                tabs = st.tabs([
                    "목소리 컨디션", "피치 (Pitch)", "포먼트 (F1)", "포먼트 (F2)", 
                    "성별 비율 (여성)", "예상 나이", "선명도 (HNR)", 
                    "지터 (Jitter)", "시머 (Shimmer)", "말하기 속도"
                ])
                
                # 각 탭에 대응하는 컬럼명과 제목 매핑
                metrics_map = [
                    ('condition_score', '목소리 컨디션 변화 (점수)'),
                    ('mean_pitch', '평균 피치 변화 (Hz)'),
                    ('mean_f1', '제1포먼트(F1) 변화 (Hz)'),
                    ('mean_f2', '제2포먼트(F2) 변화 (Hz)'),
                    ('female_ratio', '여성성 비율 변화 (%)'),
                    ('estimated_age', '예상 나이 변화 (세)'),
                    ('mean_hnr', '목소리 선명도(HNR) 변화 (dB)'),
                    ('jitter', '목소리 떨림(Jitter) 변화 (%)'),
                    ('shimmer', '목소리 불안정성(Shimmer) 변화 (%)'),
                    ('speech_rate', '말하기 속도 변화 (음절/초)')
                ]

                # 반복문을 통해 각 탭에 그래프 렌더링
                for tab, (col, title) in zip(tabs, metrics_map):
                    with tab:
                        if col in df_history.columns:
                            fig = px.line(df_history, x='timestamp', y=col, markers=True, title=title)
                            # 가로축 간격을 일정하게 설정 (Categorical Axis)
                            fig.update_xaxes(type='category', categoryorder='trace')
                            st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

            st.markdown("---")
            st.subheader("📋 상세 데이터 기록")
            st.dataframe(df_history.drop(columns=['timestamp_dt']), width="stretch")
            
            # 엑셀 다운로드 기능 추가
            def convert_df_to_excel(df):
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    df.to_excel(writer, index=False, sheet_name='Voice_History')
                return output.getvalue()

            excel_data = convert_df_to_excel(df_history.drop(columns=['timestamp_dt']))
            st.download_button(
                label=f"📥 {period} 데이터 엑셀 다운로드",
                data=excel_data,
                file_name=f"voice_history_{user_name}_{datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).strftime('%Y%m%d')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )
        else:
            st.info("아직 저장된 과거 기록이 없습니다. 첫 분석을 시작해 보세요!")

elif menu == "FAQ":
    if st.button("⬅️ 뒤로 가기", use_container_width=True):
        st.session_state.menu = st.session_state.get("previous_menu", "음성 분석")
        st.query_params["page"] = st.session_state.menu
        st.session_state.trigger_scroll = True
        st.rerun()

    st.header("❓ FAQ: 음성 분석 지표 가이드")
    st.write("VoiceGrape에서 분석하는 각 지표가 무엇을 의미하는지 확인해보세요.")

    with st.expander("1. 피치 (Pitch / F0)", expanded=True):
        st.markdown("""
        **목소리의 높낮이**를 결정하는 기본 주파수입니다.
        - 성대가 초당 몇 번 진동하는지를 나타내며 단위는 Hz(헤르츠)를 사용합니다.
        - 일반적으로 성인 남성은 80에서 160Hz, 성인 여성은 150에서 250Hz 범위를 가집니다.
        """)

    with st.expander("2. 포먼트 (Formant F1, F2)"):
        st.markdown("""
        **목소리의 음색과 발음의 정확도**를 결정하는 공명 주파수입니다.
        - **F1 (제1포먼트):** 입을 얼마나 크게 벌리는가(개방도)와 관련이 있습니다. 입을 크게 벌릴수록 F1 수치가 높아집니다.
        - **F2 (제2포먼트):** 혀의 위치가 앞쪽인가 뒤쪽인가와 관련이 있습니다. 혀가 앞쪽으로 올수록 F2 수치가 높아집니다.
        - 이 두 수치의 조합을 통해 우리가 '아, 이, 우, 에, 오' 모음을 구분하여 인식하게 됩니다.
        """)

    with st.expander("3. 지터 (Jitter)"):
        st.markdown("""
        **목소리의 떨림(주파수 변동)**을 나타내는 지표입니다.
        - 성대 진동이 얼마나 규칙적인지를 측정합니다.
        - 수치가 낮을수록 목소리가 안정적이며, 1.04% 이하를 정상 범위로 봅니다.
        - 피로하거나 성대 질환이 있을 경우 수치가 높아질 수 있습니다.
        """)

    with st.expander("4. 시머 (Shimmer)"):
        st.markdown("""
        **목소리의 불안정성(진폭 변동)**을 나타내는 지표입니다.
        - 목소리 크기가 매 순간 얼마나 일정하게 유지되는지를 측정합니다.
        - 수치가 높으면 목소리가 거칠거나 쉰 소리(Breathiness)가 섞여 들릴 수 있으며, 3.81% 이하를 정상 범위로 봅니다.
        """)

    with st.expander("5. HNR (Harmonic-to-Noise Ratio) / 선명도"):
        st.markdown("""
        **목소리의 선명도**를 나타내는 지표입니다.
        - 목소리의 순수한 성분(배음)과 잡음의 비율을 측정합니다.
        - 수치가 높을수록 잡음이 적고 맑고 깨끗한 목소리를 의미합니다. 보통 12dB 이상이면 건강한 상태로 간주합니다.
        """)

    with st.expander("6. 발음 명료도 (Articulation Score)"):
        st.markdown("""
        **모음 발음이 얼마나 명확한지**를 나타내는 점수입니다.
        - 사용자가 발음한 모음들의 포먼트 분포 범위를 분석하여 계산합니다.
        - 입을 크게 벌리고 혀를 정확한 위치에 두어 발음할수록 점수가 높게 나타납니다.
        """)

elif st.session_state.logged_in and menu == "관리자 메뉴":
    st.header("⚙️ 데이터 관리자 메뉴")
    
    # secrets.toml에서 관리자 정보 로드
    admin_info = st.secrets.get("admin", {})
    admin_user = admin_info.get("user")
    admin_pw = admin_info.get("password")

    # 일반 사용자가 비정상적인 경로로 접근하는 것을 원천 차단
    if st.session_state.user_name != admin_user:
        st.error("관리자 권한이 없습니다. 접근이 거부되었습니다.")
        st.stop()

    # 계정명과 비밀번호가 모두 일치해야만 진입 허용
    if st.session_state.user_name == admin_user and st.session_state.user_password == admin_pw:
        show_admin_page(admin_user)
    else:
        st.error("관리자 계정명과 비밀번호가 일치하지 않습니다. 관리자 권한이 없습니다.")

else:
    # 로그인 전 메인 화면: 서비스 소개
    st.markdown(f"""
        <div style="background: linear-gradient(135deg, #ab8eef 0%, #8e74d1 100%); padding: 60px 40px; border-radius: 25px; color: white; text-align: center; margin-bottom: 40px;">
            <h1 style="color: white; font-size: 3.5rem; margin-bottom: 15px; font-weight: 800;">VOICEGRAPE</h1>
            <p style="font-size: 1.4rem; opacity: 0.95; font-weight: 300; max-width: 800px; margin: 0 auto;">
                당신의 목소리에 담긴 과학적 지표를 분석하고,<br>시간에 따른 변화를 체계적으로 관리하는 통합 음성 솔루션
            </p>
        </div>
    """, unsafe_allow_html=True)

    col_f1, col_f2, col_f3 = st.columns(3)
    
    with col_f1:
        st.markdown("""
            <div class="feature-card">
                <h3 style="color: #ab8eef;">🔬 정밀 분석</h3>
                <p style="color: var(--text-color); opacity: 0.8;">Praat 알고리즘을 통해 피치, 포먼트, 지터, 시머 등 전문가 수준의 음성 지표를 실시간으로 측정합니다.</p>
            </div>
        """, unsafe_allow_html=True)
        
    with col_f2:
        st.markdown("""
            <div class="feature-card">
                <h3 style="color: #ab8eef;">👤 목소리 프로필</h3>
                <p style="color: var(--text-color); opacity: 0.8;">당신의 목소리 톤, 예상 나이, 성별 범주를 분석하여 나만의 고유한 보이스 아이덴티티를 찾아드립니다.</p>
            </div>
        """, unsafe_allow_html=True)
        
    with col_f3:
        st.markdown("""
            <div class="feature-card">
                <h3 style="color: #ab8eef;">📈 히스토리 관리</h3>
                <p style="color: var(--text-color); opacity: 0.8;">Google Sheets로 모든 분석 결과가 안전하게 저장되며, 변화 추이를 그래프로 한눈에 확인합니다.</p>
            </div>
        """, unsafe_allow_html=True)

    st.markdown("<br><br>", unsafe_allow_html=True)
    st.info("💡 시작하시려면 왼쪽 사이드바에서 이름과 비밀번호를 입력하고 로그인해주세요.")

st.markdown("---")
st.caption("Powered by Parselmouth (Praat) & Streamlit")

# 모바일에서 메뉴 선택 후 사이드바를 자동으로 닫기 위한 스크립트 (파일 최하단 배치로 안정성 확보)
if st.session_state.get("close_sidebar", False):
    st.components.v1.html(
        """
        <script>
        setTimeout(function() {
            var doc = window.parent.document;
            var sidebar = doc.querySelector('section[data-testid="stSidebar"]');
            var isMobile = window.parent.innerWidth <= 768;
            
            // 사이드바가 열려있고(collapsed=false) 모바일 환경일 때만 닫기 버튼 클릭
            if (sidebar && sidebar.getAttribute('data-collapsed') === 'false' && isMobile) {
                var closeButton = doc.querySelector('button[data-testid="stSidebarCollapseButton"]');
                if (closeButton) { closeButton.click(); }
            }
        }, 300);
        </script>
        """, height=0
    )
    st.session_state.close_sidebar = False