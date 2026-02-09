import streamlit as st
import pandas as pd
import plotly.express as px
from database import (
    connect_to_gsheets,
    admin_update_user_password,
    admin_set_user_league,
    admin_delete_specific_record,
    reset_user_data,
    get_league_from_count
)

def show_admin_page(admin_user):
    st.success(f"{admin_user} 관리자님, 인증되었습니다.")

    sheet = connect_to_gsheets("records")
    sheet_users = connect_to_gsheets("users")
    if sheet:
        with st.spinner("전체 분석 데이터를 불러오는 중입니다..."):
            all_records = sheet.get_all_records()
        if all_records:
            df_all = pd.DataFrame(all_records)
            
            # 숫자형 계산을 위해 mean_pitch 컬럼을 숫자 타입으로 변환 (에러 데이터는 NaN 처리)
            df_all['mean_pitch'] = pd.to_numeric(df_all['mean_pitch'], errors='coerce')
            
            st.subheader("📊 전체 사용자 요약 대시보드")
            user_stats = df_all.groupby('name').agg({
                'mean_pitch': 'mean',
                'timestamp': 'count'
            }).reset_index().rename(columns={'timestamp': '측정 횟수', 'mean_pitch': '평균 피치 (Hz)'})
            
            fig_all = px.bar(user_stats, x="name", y="평균 피치 (Hz)", color="평균 피치 (Hz)", text_auto='.1f')
            st.plotly_chart(fig_all, use_container_width=True, config={'displayModeBar': False})
            
            st.markdown("---")
            st.subheader("📂 전체 데이터 관리")
            st.dataframe(df_all, width="stretch")
            
            st.markdown("---")
            st.subheader("👤 개별 사용자 관리")
            
            # records 시트와 users 시트의 사용자 목록 통합 및 정렬 데이터 준비
            users_from_records = df_all['name'].unique().tolist() if 'name' in df_all.columns else []
            users_from_auth = []
            df_users = pd.DataFrame()
            
            if sheet_users:
                users_data = sheet_users.get_all_records()
                if users_data:
                    df_users = pd.DataFrame(users_data)
                    if 'username' in df_users.columns:
                        users_from_auth = df_users['username'].unique().tolist()
            
            all_usernames = list(set(users_from_records + users_from_auth))
            
            user_sort_data = []
            for u in all_usernames:
                c_at = ""
                l_login = ""
                u_league = "미정"
                
                # 1. users 시트 정보
                if not df_users.empty and 'username' in df_users.columns:
                    u_row = df_users[df_users['username'] == u]
                    if not u_row.empty:
                        c_at = str(u_row.iloc[0].get('created_at', ''))
                        l_login = str(u_row.iloc[0].get('last_login', ''))
                        if 'league' in u_row.columns:
                            u_league = str(u_row.iloc[0].get('league', ''))
                
                # 2. 정보가 없으면 records 시트에서 추정 (구 계정 등)
                if not l_login and not df_all.empty and 'name' in df_all.columns and 'timestamp' in df_all.columns:
                    u_records = df_all[df_all['name'] == u]
                    if not u_records.empty:
                        timestamps = u_records['timestamp'].astype(str).tolist()
                        timestamps = [t for t in timestamps if t and t != 'nan']
                        if timestamps:
                            l_login = max(timestamps)
                            if not c_at:
                                c_at = min(timestamps)
                        # 등급 정보가 없으면 계산
                        if u_league == "미정" or not u_league:
                            u_league = get_league_from_count(len(u_records))
                
                user_sort_data.append({'name': u, 'created_at': c_at, 'last_login': l_login, 'league': u_league})

            # 정렬 옵션 UI
            st.write("▼ 사용자 목록 정렬 기준")
            sort_option = st.radio("정렬 기준", ["이름순", "가입일순 (최신순)", "최근 접속순"], horizontal=True, label_visibility="collapsed")
            
            if sort_option == "이름순":
                user_sort_data.sort(key=lambda x: x['name'])
            elif sort_option == "가입일순 (최신순)":
                user_sort_data.sort(key=lambda x: x['created_at'], reverse=True)
            elif sort_option == "최근 접속순":
                user_sort_data.sort(key=lambda x: x['last_login'], reverse=True)
            
            user_list = [u['name'] for u in user_sort_data]
            
            # 선택 박스에 등급 표시를 위한 포맷 함수
            def user_format(name):
                if name == "-- 선택하세요 --": return name
                info = next((item for item in user_sort_data if item["name"] == name), None)
                return f"{name} ({info['league']})" if info else name

            selected_user = st.selectbox("관리할 사용자 선택", ["-- 선택하세요 --"] + user_list, format_func=user_format)
            
            if selected_user != "-- 선택하세요 --":
                # 1. 사용자 가입/로그인 정보 표시
                if not df_users.empty and 'username' in df_users.columns:
                    u_info = df_users[df_users['username'] == selected_user]
                    if not u_info.empty:
                        uc1, uc2 = st.columns(2)
                        with uc1: 
                            st.info(f"📅 가입일: {u_info.iloc[0].get('created_at', '-')}")
                        with uc2: 
                            l_login = u_info.iloc[0].get('last_login', '-')
                            league_val = u_info.iloc[0].get('league', '-')
                            st.info(f"🕒 마지막 로그인: {l_login} | 🏆 {league_val}")
                    else:
                        st.caption("※ 회원가입 정보가 없는 사용자입니다 (게스트 또는 구 계정).")

                # 2. 관리 기능 및 기록 표시
                col_admin1, col_admin2 = st.columns(2)
                with col_admin1:
                    st.write(f"**{selected_user}**님 비밀번호 관리")
                    new_pwd = st.text_input("새 비밀번호 입력", type="password", key="admin_change_pwd")
                    if st.button("비밀번호 강제 변경"):
                        if new_pwd:
                            success, msg = admin_update_user_password(selected_user, new_pwd)
                            if success: st.success(msg)
                            else: st.error(msg)
                        else: st.warning("새 비밀번호를 입력해주세요.")
                    
                    st.write(f"**{selected_user}**님 등급 조정")
                    target_league = st.selectbox("목표 등급 선택", ["🥉 브론즈", "🥈 실버", "🥇 골드", "💎 다이아몬드"], key="admin_league_sel")
                    if st.button("등급 강제 조정 (분석 횟수 추가)"):
                        success, msg = admin_set_user_league(selected_user, target_league)
                        if success: st.success(msg); st.rerun()
                        else: st.error(msg)
                
                with col_admin2:
                    st.write(f"**{selected_user}**님 기록 관리")
                    user_specific_df = df_all[df_all['name'] == selected_user]
                    if not user_specific_df.empty:
                        record_to_del = st.selectbox("삭제할 기록 선택 (시간)", user_specific_df['timestamp'].tolist())
                        if st.button("선택한 기록 삭제"):
                            success, msg = admin_delete_specific_record(selected_user, record_to_del)
                            if success: st.success(msg); st.rerun()
                            else: st.error(msg)
                        
                        st.write("📋 저장된 분석 기록 목록")
                        st.dataframe(user_specific_df, width="stretch")
                    else:
                        st.warning("저장된 분석 기록이 없습니다.")
                
                if st.button(f"🔥 '{selected_user}' 데이터 전체 초기화", type="primary", use_container_width=True):
                    success, msg = reset_user_data(selected_user)
                    if success: st.success(msg); st.rerun()
                    else: st.error(msg)

            st.markdown("---")
            st.subheader("⚠️ 시스템 관리")
            if st.button("🔥 전체 데이터 초기화 (주의)", type="primary", use_container_width=True):
                # 헤더 제외 모든 행 삭제 (gspread 기능)
                sheet.resize(rows=1)
                st.success("모든 데이터가 삭제되었습니다.")
                st.rerun()
        else:
            st.info("데이터가 없습니다.")
    else:
        st.error("DB 연결에 실패했습니다.")
