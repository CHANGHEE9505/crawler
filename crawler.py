import sys
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, TimeoutException, StaleElementReferenceException
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.keys import Keys
import time
import os
import csv
import re

sys.stdout.reconfigure(encoding='utf-8')

# --- 설정 ---
SEOUL_DISTRICTS = [
    "강남구", "강동구", "강북구", "강서구", "관악구",
    "광진구", "구로구", "금천구", "노원구", "도봉구",
    "동대문구", "동작구", "마포구", "서대문구", "서초구",
    "성동구", "성북구", "송파구", "양천구", "영등포구",
    "용산구", "은평구", "종로구", "중구", "중랑구"
]
BASE_URL = "https://map.kakao.com/"
DESKTOP_PATH = os.path.join(os.path.expanduser("~"), "Desktop")
OUTPUT_CSV_NAME = "seoul_restaurants.csv"
OUTPUT_CSV_PATH = os.path.join(DESKTOP_PATH, OUTPUT_CSV_NAME)
# ------------

driver = None
try:
    driver = webdriver.Chrome()
    all_links_to_scrape = []

    print("--- 1단계: 서울 25개구 모든 식당 링크 수집 시작 ---")
    for district in SEOUL_DISTRICTS:
        SEARCH_KEYWORD = f"{district} 회식"
        print(f"\n'{SEARCH_KEYWORD}' 검색 중...")
        driver.get(BASE_URL)

        try:
            search_area = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.XPATH, '//*[@id="search.keyword.query"]'))
            )
            search_area.clear()
            search_area.send_keys(SEARCH_KEYWORD)
            driver.find_element(By.XPATH, '//*[@id="search.keyword.submit"]').send_keys(Keys.ENTER)
            time.sleep(2)

            place_tab = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, '//*[@id="info.main.options"]/li[2]/a'))
            )
            driver.execute_script("arguments[0].click();", place_tab)
            time.sleep(3)

            while True:
                page_index = 0
                while page_index < 5:
                    try:
                        page_buttons = WebDriverWait(driver, 10).until(
                            EC.presence_of_all_elements_located((By.CSS_SELECTOR, "div.pageWrap > a[id^='info.search.page.no']"))
                        )

                        if page_index >= len(page_buttons):
                            break

                        page_btn_to_click = page_buttons[page_index]
                        page_num_text = page_btn_to_click.text

                        if page_btn_to_click.get_attribute('class') != 'ACTIVE':
                            print(f"  - {district} {page_num_text} 페이지로 이동...")
                            driver.execute_script("arguments[0].click();", page_btn_to_click)
                            time.sleep(3)

                        print(f"  - {district} {page_num_text} 페이지 링크 수집...")
                        html = driver.page_source
                        soup = BeautifulSoup(html, 'html.parser')
                        list_items = soup.select('ul#info\\.search\\.place\\.list > li.PlaceItem')

                        for item in list_items:
                            link_element = item.select_one('div.contact > a.moreview')
                            if link_element and 'href' in link_element.attrs:
                                link = link_element['href']
                                if (link, district) not in all_links_to_scrape:
                                    all_links_to_scrape.append((link, district))

                        page_index += 1

                    except StaleElementReferenceException:
                        continue
                    except Exception as e:
                        print(f"    페이지 {page_index + 1} 처리 중 오류: {e}")
                        page_index += 1

                try:
                    next_block_button = WebDriverWait(driver, 3).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, 'button#info\\.search\\.page\\.next'))
                    )
                    if 'disabled' in next_block_button.get_attribute('class'):
                        print(f"    {district}의 마지막 페이지 블록입니다. 링크 수집을 마칩니다.")
                        break
                    else:
                        print("\n  다음 페이지 블록(>)으로 이동합니다.")
                        driver.execute_script("arguments[0].click();", next_block_button)
                        time.sleep(3)
                except (NoSuchElementException, TimeoutException):
                    print(f"    {district}의 마지막 페이지입니다. 링크 수집을 마칩니다.")
                    break

        except Exception as e:
            print(f"{district} 링크 수집 중 오류 발생: {e}")
            continue

    print(f"\n--- 1단계 완료: 총 {len(all_links_to_scrape)}개의 식당 링크 수집 ---")

    # --- 2단계: 상세 정보 크롤링 (이 부분은 변경 없음) ---
    print("\n--- 2단계: 상세 정보 크롤링 시작 ---")
    all_restaurants_data = []

    for i, (link, district) in enumerate(all_links_to_scrape):
        try:
            print(f"  ({i+1}/{len(all_links_to_scrape)}) {district} - {link}")
            driver.get(link)
            time.sleep(3)

            WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'h3.tit_place'))
            )
            html_detail = driver.page_source
            soup_detail = BeautifulSoup(html_detail, 'html.parser')

            store_name = soup_detail.select_one('h3.tit_place').text.replace('장소명', '').strip() if soup_detail.select_one('h3.tit_place') else "가게명 없음"
            store_image_element = soup_detail.select_one('div.board_photo img')
            store_image_url = store_image_element['src'] if store_image_element and 'src' in store_image_element.attrs else "이미지 없음"

            # --- 전화번호 딱 보이는 한 개만 가져오기 (셀레니움 사용) ---
            try:
                phone_element = driver.find_element(By.CSS_SELECTOR, "div.unit_default div.detail_info.info_suggest > div.row_detail > span.txt_detail")
                store_tel = phone_element.text.strip()
            except Exception:
                store_tel = "전화번호 없음"

            operating_hours = "영업시간 없음"
            try:
                expanded = False
                # '펼치기' 버튼 클릭 시도
                try:
                    expand_button = WebDriverWait(driver, 5).until( # Increased wait time
                        EC.element_to_be_clickable((By.CSS_SELECTOR, 'span.ico_mapdesc.ico_arr16'))
                    )
                    driver.execute_script("arguments[0].click();", expand_button)
                    time.sleep(2) # Increased sleep time
                    html_after_expand = driver.page_source
                    soup_detail = BeautifulSoup(html_after_expand, 'html.parser') # 업데이트된 HTML로 soup 객체 다시 생성
                    expanded = True
                except (NoSuchElementException, TimeoutException):
                    pass # '펼치기' 버튼이 없으면 무시

                operation_info_section = soup_detail.select_one('div.default_info div.detail_info.info_operation')
                if operation_info_section:
                    if expanded: # If the expand button was clicked, try to get the full list
                        # Updated selectors for the expanded operating hours structure
                        time_elements = operation_info_section.select('div.fold_detail div.line_fold')
                        if time_elements:
                            operating_hours_list = []
                            for line_fold in time_elements:
                                day_info = line_fold.select_one('span.tit_fold')
                                time_details = line_fold.select('div.detail_fold span.txt_detail')
                                if day_info and time_details:
                                    times = [t.text.strip() for t in time_details]
                                    operating_hours_list.append(f"{day_info.text.strip()} {' '.join(times)}")
                            operating_hours = "\n".join(operating_hours_list)
                        # If expanded is True but time_elements is empty, operating_hours remains "영업시간 없음"
                        # or whatever its initial value was, which is correct.
                    else: # If the expand button was not clicked, get the single line
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
            review_list = []
            try:
                review_tab = WebDriverWait(driver, 5).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, 'ul.list_tab li a[href="#comment"]'))
                )
                driver.execute_script("arguments[0].click();", review_tab)
                time.sleep(2)

                # --- 전체 리뷰 로딩 시작 ---
                while True:
                    try:
                        # 현재 로드된 리뷰의 개수를 확인합니다.
                        review_count_before_click = len(driver.find_elements(By.CSS_SELECTOR, 'ul.list_review > li'))

                        # '리뷰 목록 더보기' 버튼을 찾아 클릭합니다.
                        load_more_button = WebDriverWait(driver, 2).until(
                            EC.element_to_be_clickable((By.CSS_SELECTOR, 'span.btn_more'))
                        )
                        driver.execute_script("arguments[0].click();", load_more_button)

                        # 새 리뷰가 로드되어 리뷰 개수가 늘어날 때까지 최대 5초간 기다립니다.
                        WebDriverWait(driver, 5).until(
                            lambda d: len(d.find_elements(By.CSS_SELECTOR, 'ul.list_review > li')) > review_count_before_click
                        )
                        # print(f"  - '리뷰 목록 더보기' 클릭 완료 (리뷰 {review_count_before_click}개 -> {len(driver.find_elements(By.CSS_SELECTOR, 'ul.list_review > li'))}개)")

                    except (NoSuchElementException, TimeoutException):
                        # 더 이상 '더보기' 버튼이 없거나, 클릭해도 리뷰가 늘어나지 않으면 로딩을 종료합니다.
                        # print("--- 모든 리뷰를 로드했습니다. 내용 수집을 시작합니다. ---")
                        break

                # 페이지에 로드된 모든 리뷰 엘리먼트를 가져옵니다.
                review_elements = driver.find_elements(By.CSS_SELECTOR, 'ul.list_review > li')
                # print(f"--- 총 {len(review_elements)}개의 리뷰를 찾았습니다. ---")
                
                for review_element in review_elements:
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

                    except Exception as e:
                        # print(f"  - 개별 리뷰 처리 중 오류 발생: {e}")
                        continue

            except (NoSuchElementException, TimeoutException):
                pass
            all_reviews = '\n'.join(review_list) if review_list else '리뷰 없음'
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

            data = {
                '구': district,
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
                '주소': address
            }
            all_restaurants_data.append(data)

        except Exception as e:
            print(f"    상세 정보 추출 중 오류 발생: {link}, 오류: {e}")
            continue

    # --- 3단계: CSV 파일로 저장 ---
    if all_restaurants_data:
        print("\n--- 3단계: CSV 파일 저장 시작 ---")
        try:
            with open(OUTPUT_CSV_PATH, 'w', encoding='utf-8-sig', newline='') as f:
                fieldnames = all_restaurants_data[0].keys()
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(all_restaurants_data)
            print(f"\n**크롤링 완료**\n결과가 바탕화면의 '{OUTPUT_CSV_NAME}' 파일에 저장되었습니다.")
        except IOError as e:
            print(f"CSV 파일 저장 중 오류가 발생했습니다: {e}")
    else:
        print("\n추출된 식당 정보가 없습니다.")

finally:
    if driver:
        driver.quit()
        print("\n브라우저를 종료했습니다.")