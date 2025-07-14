import sys
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from bs4 import BeautifulSoup
from selenium import webdriver
import time
import os
import csv
import re

sys.stdout.reconfigure(encoding='utf-8')

# --- 설정 ---
TARGET_URL = "https://place.map.kakao.com/26545925"
DESKTOP_PATH = os.path.join(os.path.expanduser("~"), "Desktop")
OUTPUT_CSV_NAME = "single_restaurant_test.csv"
OUTPUT_CSV_PATH = os.path.join(DESKTOP_PATH, OUTPUT_CSV_NAME)
# ------------

driver = None
try:
    driver = webdriver.Chrome()
    all_restaurants_data = []

    print(f"--- 단일 URL 상세 정보 크롤링 시작: {TARGET_URL} ---")
    driver.get(TARGET_URL)
    time.sleep(3)

    WebDriverWait(driver, 15).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, 'h3.tit_place'))
    )
    html_detail = driver.page_source
    soup_detail = BeautifulSoup(html_detail, 'html.parser')

    store_name = soup_detail.select_one('h3.tit_place').text.strip() if soup_detail.select_one('h3.tit_place') else "가게명 없음"
    store_image_element = soup_detail.select_one('div.board_photo img')
    store_image_url = store_image_element['src'] if store_image_element and 'src' in store_image_element.attrs else "이미지 없음"

    try:
        phone_element = driver.find_element(By.CSS_SELECTOR, "div.unit_default div.detail_info.info_suggest > div.row_detail > span.txt_detail")
        store_tel = phone_element.text.strip()
    except Exception:
        store_tel = "전화번호 없음"

    operating_hours = "영업시간 없음"
    try:
        expand_button = WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, 'span.ico_mapdesc.ico_arr16'))
        )
        driver.execute_script("arguments[0].click();", expand_button)
        time.sleep(2)
        html_after_expand = driver.page_source
        soup_detail = BeautifulSoup(html_after_expand, 'html.parser')
        time_elements = soup_detail.select('div.fold_detail div.line_fold')
        operating_hours_list = []
        for line_fold in time_elements:
            day_info = line_fold.select_one('span.tit_fold')
            time_details = line_fold.select('div.detail_fold span.txt_detail')
            if day_info and time_details:
                times = [t.text.strip() for t in time_details]
                operating_hours_list.append(f"{day_info.text.strip()} {' '.join(times)}")
        operating_hours = "\n".join(operating_hours_list) if operating_hours_list else "영업시간 없음"
    except:
        pass

    menu_list = []
    try:
        more_menu_button = WebDriverWait(driver, 3).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, 'div.section_product div.wrap_more a.link_more'))
        )
        driver.execute_script("arguments[0].click();", more_menu_button)
        time.sleep(1)
    except:
        pass
    html_menu = driver.page_source
    soup_menu = BeautifulSoup(html_menu, 'html.parser')
    menu_elements = soup_menu.select('ul.list_goods li')
    for menu in menu_elements:
        name = menu.select_one('strong.tit_item').text.strip() if menu.select_one('strong.tit_item') else ""
        price = menu.select_one('p.desc_item').text.strip() if menu.select_one('p.desc_item') else ""
        menu_list.append(f"{name} ({price})")
    full_menu = ', '.join(menu_list) if menu_list else '메뉴 없음'

    score_element = soup_detail.select_one('span.starred_grade span.num_star')
    score = score_element.text.strip() if score_element else "평점 없음"

    parking_info = "주차 정보 없음"
    parking_element = soup_detail.select_one("div.unit_default.unit_infoetc h5.tit_addinfo:-soup-contains('주차') + div.detail_info span.txt_detail")
    if parking_element:
        parking_info = parking_element.text.strip()

    address_element = soup_detail.select_one('div.unit_default h5.tit_info:-soup-contains("주소") + div.detail_info span.txt_detail')
    address = address_element.text.strip() if address_element else "주소 없음"

    latitude = ""
    longitude = ""
    og_image_meta = soup_detail.find('meta', property='og:image')
    if og_image_meta and 'content' in og_image_meta.attrs:
        content = og_image_meta['content']
        match = re.search(r'm=([0-9.]+)\%2C([0-9.]+)', content)
        if match:
            longitude = match.group(1)
            latitude = match.group(2)

    # --- 리뷰 추출 (긴 리뷰 더보기까지 모두 포함) ---
    review_list = []
    try:
        # 리뷰 탭 클릭
        review_tab = WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, 'ul.list_tab li a[href="#comment"]'))
        )
        driver.execute_script("arguments[0].click();", review_tab)
        time.sleep(2)

        # 더보기 반복 클릭
        while True:
            try:
                more_buttons = driver.find_elements(By.CSS_SELECTOR, 'a.link_more')
                clicked = False
                for btn in more_buttons:
                    if btn.is_displayed():
                        driver.execute_script("arguments[0].click();", btn)
                        time.sleep(0.3)
                        clicked = True
                if not clicked:
                    break
            except:
                break
            time.sleep(1)

        # 더보기 다 눌린 후 review text 추출 (Selenium 기반)
        review_elements = driver.find_elements(By.CSS_SELECTOR, 'ul.list_review > li .desc_review')
        for el in review_elements:
            full_comment = el.text.strip()
            full_comment = re.sub(r'(더보기|접기)', '', full_comment).strip()
            review_list.append(full_comment)

    except Exception as e:
        print(f"[리뷰 수집 실패] {e}")
        review_list = ['리뷰 없음']

    all_reviews = '\n'.join(review_list)

    data = {
        '구': "단일 테스트",
        '가게명': store_name,
        '전화번호': store_tel,
        '가게 이미지 URL': store_image_url,
        '영업시간': operating_hours,
        '전체 메뉴': full_menu,
        '평점': score,
        '주차 가능 여부': parking_info,
        '리뷰': all_reviews,
        '위도': latitude,
        '경도': longitude,
        '주소': address,
    }
    all_restaurants_data.append(data)

    # --- 저장 ---
    if all_restaurants_data:
        print("\n--- CSV 저장 중 ---")
        with open(OUTPUT_CSV_PATH, 'w', encoding='utf-8-sig', newline='') as f:
            fieldnames = all_restaurants_data[0].keys()
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(all_restaurants_data)
        print(f"저장 완료: 바탕화면 → {OUTPUT_CSV_NAME}")
    else:
        print("저장할 데이터가 없습니다.")

finally:
    if driver:
        driver.quit()
        print("브라우저 종료 완료.")
