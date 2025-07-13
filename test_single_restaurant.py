import sys
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium import webdriver
import time
import os
import csv
import re
from bs4 import BeautifulSoup

sys.stdout.reconfigure(encoding='utf-8')

# --- 설정 ---
TARGET_URL = "https://place.map.kakao.com/12418029" # 강남구 을밀대 강남점
DESKTOP_PATH = os.path.join(os.path.expanduser("~"), "Desktop")
OUTPUT_CSV_NAME = "single_restaurant_test.csv"
OUTPUT_CSV_PATH = os.path.join(DESKTOP_PATH, OUTPUT_CSV_NAME)
# ------------

driver = None
try:
    driver = webdriver.Chrome()
    print(f"테스트 URL: {TARGET_URL}")
    driver.get(TARGET_URL)
    time.sleep(3) # 페이지 로딩 대기

    WebDriverWait(driver, 15).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, 'h3.tit_place'))
    )
    html_detail = driver.page_source
    soup_detail = BeautifulSoup(html_detail, 'html.parser')

    # --- 식당 정보 추출 시작 ---
    store_name = soup_detail.select_one('h3.tit_place').text.replace('장소명', '').strip() if soup_detail.select_one('h3.tit_place') else "가게명 없음"
    store_image_element = soup_detail.select_one('div.board_photo img')
    store_image_url = store_image_element['src'] if store_image_element and 'src' in store_image_element.attrs else "이미지 없음"
    operating_hours = "영업시간 없음"
    try:
        operation_info_section = soup_detail.select_one('div.default_info div.detail_info.info_operation')
        if operation_info_section:
            status_element = operation_info_section.select_one('span.tit_detail.emph_point2')
            time_element = operation_info_section.select_one('span.txt_detail.add_mdot')
            status = status_element.text.strip() if status_element else ""
            time_info = time_element.text.strip() if time_element else ""
            operating_hours = f"{status} {time_info}".strip()
    except Exception as e:
        print(f"    영업시간 추출 중 오류: {e}")

    menu_list = []
    try:
        more_menu_button = WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, 'div.section_product div.wrap_more a.link_more'))
        )
        driver.execute_script("arguments[0].click();", more_menu_button)
        time.sleep(1)
        html_after_click = driver.page_source
        soup_after_click = BeautifulSoup(html_after_click, 'html.parser')
        menu_elements = soup_after_click.select('ul.list_goods li')
        for menu in menu_elements:
            name = menu.select_one('strong.tit_item').text.strip() if menu.select_one('strong.tit_item') else ""
            price = menu.select_one('p.desc_item').text.strip() if menu.select_one('p.desc_item') else ""
            menu_list.append(f"{name} ({price})")
    except (NoSuchElementException, TimeoutException):
        menu_elements = soup_detail.select('ul.list_goods li')
        for menu in menu_elements:
            name = menu.select_one('strong.tit_item').text.strip() if menu.select_one('strong.tit_item') else ""
            price = menu.select_one('p.desc_item').text.strip() if menu.select_one('p.desc_item') else ""
            menu_list.append(f"{name} ({price})")
    full_menu = ', '.join(menu_list) if menu_list else '메뉴 없음'

    score_element = soup_detail.select_one('span.starred_grade span.num_star')
    score = score_element.text.strip() if score_element else "평점 없음"

    parking_info = "주차 정보 없음"
    parking_element = soup_detail.select_one('div.unit_default.unit_infoetc h5.tit_addinfo:-soup-contains("주차") + div.detail_info span.txt_detail')
    if parking_element:
        parking_info = parking_element.text.strip()

    latitude = ""
    longitude = ""
    og_image_meta = soup_detail.find('meta', property='og:image')
    if og_image_meta and 'content' in og_image_meta.attrs:
        content = og_image_meta['content']
        match = re.search(r'm=([0-9.]+)\%2C([0-9.]+)', content)
        if match:
            longitude = match.group(1)
            latitude = match.group(2)

    address_element = soup_detail.select_one('div.unit_default h5.tit_info:-soup-contains("주소") + div.detail_info span.txt_detail')
    address = address_element.text.strip() if address_element else "주소 없음"

    # --- 리뷰 크롤링 시작 (기존 test_crawler.py 로직) ---
    review_list = []
    try:
        # 1. 리뷰 탭 클릭
        review_tab = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, 'ul.list_tab li a[href="#comment"]'))
        )
        driver.execute_script("arguments[0].click();", review_tab)
        time.sleep(2) # 리뷰 탭 내용 로딩 대기

        # 2. '리뷰 목록 더보기' 버튼을 눌러 모든 리뷰 로드
        print("\n--- 전체 리뷰 로딩 시작 ---")
        while True:
            try:
                review_count_before_click = len(driver.find_elements(By.CSS_SELECTOR, 'ul.list_review > li'))

                load_more_button = WebDriverWait(driver, 2).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, 'span.btn_more'))
                )
                driver.execute_script("arguments[0].click();", load_more_button)

                WebDriverWait(driver, 5).until(
                    lambda d: len(d.find_elements(By.CSS_SELECTOR, 'ul.list_review > li')) > review_count_before_click
                )
                print(f"  - '리뷰 목록 더보기' 클릭 완료 (리뷰 {review_count_before_click}개 -> {len(driver.find_elements(By.CSS_SELECTOR, 'ul.list_review > li'))}개)")

            except (NoSuchElementException, TimeoutException):
                print("--- 모든 리뷰를 로드했습니다. 내용 수집을 시작합니다. ---")
                break

        # 3. 페이지에 로드된 모든 리뷰 엘리먼트를 가져와 개별 리뷰 내용 펼치기 및 수집
        review_elements = driver.find_elements(By.CSS_SELECTOR, 'ul.list_review > li')
        print(f"--- 총 {len(review_elements)}개의 리뷰를 찾았습니다. ---")
        
        for i, review_element in enumerate(review_elements):
            try:
                # 개별 리뷰의 '내용 더보기' 버튼을 찾아 클릭합니다.
                try:
                    expand_button = review_element.find_element(By.CSS_SELECTOR, '.desc_review > a.link_more')
                    driver.execute_script("arguments[0].click();", expand_button)
                    time.sleep(0.3) # 내용이 펼쳐질 때까지 잠시 대기
                except NoSuchElementException:
                    pass # '내용 더보기' 버튼이 없는 짧은 리뷰는 그냥 넘어갑니다.
                
                # 펼쳐진 전체 리뷰 텍스트를 가져옵니다.
                comment_element = review_element.find_element(By.CSS_SELECTOR, '.desc_review')
                full_comment = re.sub(r'\s+', ' ', comment_element.text).strip()
                review_list.append(full_comment)
                print(f"  - {i+1}번째 리뷰 수집 완료")

            except Exception as e:
                print(f"  - {i+1}번째 리뷰 처리 중 오류 발생: {e}")
                continue

    except (NoSuchElementException, TimeoutException) as e:
        print(f"리뷰 탭 또는 리뷰 로딩 중 오류 발생: {e}")
        pass
    all_reviews = '\n'.join(review_list) if review_list else '리뷰 없음'

    # --- 모든 정보 취합 및 CSV 저장 ---
    restaurant_data = {
        '구': "강남구", # 테스트용이므로 고정
        '가게명': store_name,
        '가게 이미지 URL': store_image_url,
        '영업시간': operating_hours,
        '전체 메뉴': full_menu,
        '평점': score,
        '주차 가능 여부': parking_info,
        '리뷰': all_reviews,
        '위도': latitude,
        '경도': longitude,
        '주소': address
    }

    all_restaurants_data = [restaurant_data] # 단일 식당 데이터 리스트

    if all_restaurants_data:
        print("\n--- CSV 파일 저장 시작 ---")
        try:
            with open(OUTPUT_CSV_PATH, 'w', encoding='utf-8-sig', newline='') as f:
                fieldnames = all_restaurants_data[0].keys()
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(all_restaurants_data)
            print(f"\n**테스트 크롤링 완료**\n결과가 바탕화면의 '{OUTPUT_CSV_NAME}' 파일에 저장되었습니다.")
        except IOError as e:
            print(f"CSV 파일 저장 중 오류가 발생했습니다: {e}")
    else:
        print("\n추출된 식당 정보가 없습니다.")

finally:
    if driver:
        driver.quit()
        print("\n브라우저를 종료했습니다.")
